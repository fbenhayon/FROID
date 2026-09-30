BEGIN;

-- Revisao da prova da Fase 5 (30/09/2026): sob corrida real, o perdedor do
-- mesmo horario recebia as vezes 40P01 (deadlock na checagem da exclusion
-- constraint GiST) em vez de APPOINTMENT_CONFLICT. As duas funcoes abaixo
-- sao as da migration 044, textualmente identicas, com UMA adicao cada: o
-- advisory lock transacional por clinico antes da checagem/insercao.

CREATE OR REPLACE FUNCTION psique_v2_appointment_create(org uuid, member uuid, actor uuid, args jsonb)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=public,pg_temp AS $$
DECLARE clinician uuid:=(args->>'clinician_membership_id')::uuid;
    appointment psique_appointments%ROWTYPE; idem text:=trim(args->>'idempotency_key');
BEGIN
    PERFORM psique_v2_scheduling_member(org,member,actor,
        ARRAY['SECRETARY','ORG_ADMIN','CLINICIAN']);
    IF NOT psique_v2_role_check(ARRAY['SECRETARY','ORG_ADMIN']) AND clinician IS DISTINCT FROM member THEN
        RAISE EXCEPTION 'OWN_AGENDA_ONLY' USING ERRCODE='42501';
    END IF;
    IF coalesce(idem,'')='' THEN RAISE EXCEPTION 'IDEMPOTENCY_KEY_REQUIRED'; END IF;
    SELECT * INTO appointment FROM psique_appointments
        WHERE organization_id=org AND idempotency_key=idem;
    IF FOUND THEN
        RETURN jsonb_build_object('appointment_id',appointment.id,'created',false,
            'version',appointment.version,'appointment_status',appointment.appointment_status);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM psique_membership_role_grants g
        JOIN organization_memberships m ON m.id=g.membership_id AND m.status='active'
        WHERE g.membership_id=clinician AND g.organization_id=org
          AND g.v2_role='CLINICIAN' AND g.revoked_at IS NULL) THEN
        RAISE EXCEPTION 'APPOINTMENT_CLINICIAN_REQUIRED';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM patients p WHERE p.organization_id=org
        AND p.id=(args->>'patient_id')::uuid AND p.status='active') THEN
        RAISE EXCEPTION 'APPOINTMENT_PATIENT_REQUIRED';
    END IF;
    -- Serializa a agenda DO CLINICO: duas insercoes simultaneas no indice
    -- de exclusao podem terminar em deadlock (40P01) em vez do conflito
    -- limpo; com o lock, o perdedor sempre recebe APPOINTMENT_CONFLICT.
    -- Clinicos diferentes continuam paralelos; a exclusion constraint
    -- permanece como garantia final no proprio banco.
    PERFORM pg_advisory_xact_lock(hashtextextended('psique_agenda:'||clinician::text, 0));
    IF NOT psique_v2_within_availability(org,clinician,
        (args->>'start_at')::timestamptz,(args->>'end_at')::timestamptz) THEN
        RAISE EXCEPTION 'OUTSIDE_AVAILABILITY';
    END IF;
    BEGIN
        INSERT INTO psique_appointments(organization_id,patient_id,clinician_membership_id,
            unit_id,start_at,end_at,appointment_timezone,created_by,updated_by,idempotency_key)
        VALUES(org,(args->>'patient_id')::uuid,clinician,nullif(args->>'unit_id','')::uuid,
            (args->>'start_at')::timestamptz,(args->>'end_at')::timestamptz,
            args->>'timezone',actor,actor,idem)
        RETURNING * INTO appointment;
    EXCEPTION WHEN exclusion_violation THEN
        RAISE EXCEPTION 'APPOINTMENT_CONFLICT';
    END;
    INSERT INTO psique_appointment_events(organization_id,appointment_id,event_kind,
        current_state,actor_user_id)
    VALUES(org,appointment.id,'CREATED',psique_v2_appointment_snapshot(appointment),actor);
    INSERT INTO psique_calendar_outbox(organization_id,appointment_id,operation,payload)
    VALUES(org,appointment.id,'UPSERT',psique_v2_appointment_snapshot(appointment));
    INSERT INTO audit_events(id,organization_id,actor_user_id,action,resource_type,resource_id)
    VALUES(gen_random_uuid(),org,actor,'psique.appointment.create','psique_appointment',
        appointment.id::text);
    RETURN jsonb_build_object('appointment_id',appointment.id,'created',true,
        'version',appointment.version,'appointment_status',appointment.appointment_status);
END $$;

CREATE OR REPLACE FUNCTION psique_v2_appointment_change(org uuid, member uuid, actor uuid, args jsonb)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=public,pg_temp AS $$
DECLARE appointment psique_appointments%ROWTYPE; before jsonb; new_status text;
    new_start timestamptz; new_end timestamptz; kind text;
BEGIN
    PERFORM psique_v2_scheduling_member(org,member,actor,
        ARRAY['SECRETARY','ORG_ADMIN','CLINICIAN']);
    SELECT * INTO appointment FROM psique_appointments
        WHERE organization_id=org AND id=(args->>'appointment_id')::uuid FOR UPDATE;
    IF NOT FOUND THEN RAISE EXCEPTION 'APPOINTMENT_ACCESS_DENIED' USING ERRCODE='42501'; END IF;
    IF NOT psique_v2_role_check(ARRAY['SECRETARY','ORG_ADMIN'])
        AND appointment.clinician_membership_id IS DISTINCT FROM member THEN
        RAISE EXCEPTION 'OWN_AGENDA_ONLY' USING ERRCODE='42501';
    END IF;
    IF (args->>'expected_version')::bigint IS DISTINCT FROM appointment.version THEN
        RETURN jsonb_build_object('applied',false,'code','APPOINTMENT_VERSION_CONFLICT',
            'version',appointment.version);
    END IF;
    IF appointment.appointment_status IN ('COMPLETED','CANCELLED','NO_SHOW') THEN
        RETURN jsonb_build_object('applied',false,'code','APPOINTMENT_TERMINAL',
            'appointment_status',appointment.appointment_status);
    END IF;
    before:=psique_v2_appointment_snapshot(appointment);
    new_status:=coalesce(args->>'appointment_status',appointment.appointment_status);
    IF new_status NOT IN ('SCHEDULED','CONFIRMED','IN_PROGRESS','COMPLETED','NO_SHOW') THEN
        RAISE EXCEPTION 'APPOINTMENT_STATUS_INVALID';  -- cancelamento tem comando proprio
    END IF;
    new_start:=coalesce((args->>'start_at')::timestamptz,appointment.start_at);
    new_end:=coalesce((args->>'end_at')::timestamptz,appointment.end_at);
    kind:=CASE WHEN new_start IS DISTINCT FROM appointment.start_at
               OR new_end IS DISTINCT FROM appointment.end_at THEN 'RESCHEDULED'
          ELSE 'STATUS_CHANGED' END;
    -- Serializa a agenda DO CLINICO: duas insercoes simultaneas no indice
    -- de exclusao podem terminar em deadlock (40P01) em vez do conflito
    -- limpo; com o lock, o perdedor sempre recebe APPOINTMENT_CONFLICT.
    -- Clinicos diferentes continuam paralelos; a exclusion constraint
    -- permanece como garantia final no proprio banco.
    PERFORM pg_advisory_xact_lock(hashtextextended('psique_agenda:'||appointment.clinician_membership_id::text, 0));
    IF kind='RESCHEDULED' AND NOT psique_v2_within_availability(
        org,appointment.clinician_membership_id,new_start,new_end) THEN
        RAISE EXCEPTION 'OUTSIDE_AVAILABILITY';
    END IF;
    BEGIN
        UPDATE psique_appointments SET start_at=new_start,end_at=new_end,
            appointment_status=new_status,updated_by=actor,
            updated_at=clock_timestamp(),version=version+1
            WHERE id=appointment.id RETURNING * INTO appointment;
    EXCEPTION WHEN exclusion_violation THEN
        RAISE EXCEPTION 'APPOINTMENT_CONFLICT';
    END;
    INSERT INTO psique_appointment_events(organization_id,appointment_id,event_kind,
        previous_state,current_state,actor_user_id)
    VALUES(org,appointment.id,kind,before,psique_v2_appointment_snapshot(appointment),actor);
    INSERT INTO psique_calendar_outbox(organization_id,appointment_id,operation,payload)
    VALUES(org,appointment.id,'UPSERT',psique_v2_appointment_snapshot(appointment));
    RETURN jsonb_build_object('applied',true,'appointment_id',appointment.id,
        'version',appointment.version,'appointment_status',appointment.appointment_status);
END $$;

INSERT INTO schema_migrations(version) VALUES('045_psique_scheduling_serialization');
COMMIT;
