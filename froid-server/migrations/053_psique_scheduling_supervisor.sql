BEGIN;

-- 053: a agenda no painel (decisoes do dono, 18/10/2026).
--
-- 1. O supervisor clinico (CLINICAL_SUPERVISOR) ve a agenda inteira e marca,
--    reagenda e cancela atendimentos dos profissionais, como secretaria e
--    administrador. As cinco funcoes abaixo sao copias BYTE A BYTE das
--    definicoes correntes (create/change da 045; cancel/history/list da 044)
--    com UMA troca: o supervisor entra nas duas listas de papeis. Teste de
--    espelho em tests/test_psique_scheduling_supervisor.py.
-- 2. A listagem devolve o nome do paciente para secretaria, administrador e
--    o clinico do atendimento; o supervisor recebe a agenda sem nome.
-- 3. Duas listagens novas para o painel montar a agenda: os clinicos (com a
--    disponibilidade semanal) e os pacientes (nome ou identificador curto,
--    pela mesma regra do item 2).

CREATE OR REPLACE FUNCTION psique_v2_appointment_create(org uuid, member uuid, actor uuid, args jsonb)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=public,pg_temp AS $$
DECLARE clinician uuid:=(args->>'clinician_membership_id')::uuid;
    appointment psique_appointments%ROWTYPE; idem text:=trim(args->>'idempotency_key');
BEGIN
    PERFORM psique_v2_scheduling_member(org,member,actor,
        ARRAY['SECRETARY','ORG_ADMIN','CLINICAL_SUPERVISOR','CLINICIAN']);
    IF NOT psique_v2_role_check(ARRAY['SECRETARY','ORG_ADMIN','CLINICAL_SUPERVISOR']) AND clinician IS DISTINCT FROM member THEN
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
        ARRAY['SECRETARY','ORG_ADMIN','CLINICAL_SUPERVISOR','CLINICIAN']);
    SELECT * INTO appointment FROM psique_appointments
        WHERE organization_id=org AND id=(args->>'appointment_id')::uuid FOR UPDATE;
    IF NOT FOUND THEN RAISE EXCEPTION 'APPOINTMENT_ACCESS_DENIED' USING ERRCODE='42501'; END IF;
    IF NOT psique_v2_role_check(ARRAY['SECRETARY','ORG_ADMIN','CLINICAL_SUPERVISOR'])
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

CREATE OR REPLACE FUNCTION psique_v2_appointment_cancel(org uuid, member uuid, actor uuid,
    appointment_ref uuid, expected bigint, reason text)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=public,pg_temp AS $$
DECLARE appointment psique_appointments%ROWTYPE; before jsonb;
BEGIN
    PERFORM psique_v2_scheduling_member(org,member,actor,
        ARRAY['SECRETARY','ORG_ADMIN','CLINICAL_SUPERVISOR','CLINICIAN']);
    SELECT * INTO appointment FROM psique_appointments
        WHERE organization_id=org AND id=appointment_ref FOR UPDATE;
    IF NOT FOUND THEN RAISE EXCEPTION 'APPOINTMENT_ACCESS_DENIED' USING ERRCODE='42501'; END IF;
    IF NOT psique_v2_role_check(ARRAY['SECRETARY','ORG_ADMIN','CLINICAL_SUPERVISOR'])
        AND appointment.clinician_membership_id IS DISTINCT FROM member THEN
        RAISE EXCEPTION 'OWN_AGENDA_ONLY' USING ERRCODE='42501';
    END IF;
    IF expected IS DISTINCT FROM appointment.version THEN
        RETURN jsonb_build_object('applied',false,'code','APPOINTMENT_VERSION_CONFLICT',
            'version',appointment.version);
    END IF;
    IF appointment.appointment_status='CANCELLED' THEN
        RETURN jsonb_build_object('applied',false,'code','APPOINTMENT_ALREADY_CANCELLED');
    END IF;
    IF appointment.appointment_status IN ('COMPLETED','NO_SHOW') THEN
        RETURN jsonb_build_object('applied',false,'code','APPOINTMENT_TERMINAL');
    END IF;
    before:=psique_v2_appointment_snapshot(appointment);
    UPDATE psique_appointments SET appointment_status='CANCELLED',updated_by=actor,
        updated_at=clock_timestamp(),version=version+1
        WHERE id=appointment.id RETURNING * INTO appointment;
    INSERT INTO psique_appointment_events(organization_id,appointment_id,event_kind,
        previous_state,current_state,actor_user_id)
    VALUES(org,appointment.id,'CANCELLED',
        before||jsonb_build_object('reason',coalesce(nullif(trim(reason),''),'NOT_STATED')),
        psique_v2_appointment_snapshot(appointment),actor);
    INSERT INTO psique_calendar_outbox(organization_id,appointment_id,operation,payload)
    VALUES(org,appointment.id,'CANCEL',psique_v2_appointment_snapshot(appointment));
    RETURN jsonb_build_object('applied',true,'version',appointment.version,
        'appointment_status','CANCELLED');
END $$;

CREATE OR REPLACE FUNCTION psique_v2_appointment_history(org uuid, member uuid, actor uuid,
    appointment_ref uuid)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=public,pg_temp AS $$
DECLARE appointment psique_appointments%ROWTYPE; result jsonb;
BEGIN
    PERFORM psique_v2_scheduling_member(org,member,actor,
        ARRAY['SECRETARY','ORG_ADMIN','CLINICAL_SUPERVISOR','CLINICIAN']);
    SELECT * INTO appointment FROM psique_appointments
        WHERE organization_id=org AND id=appointment_ref;
    IF NOT FOUND THEN RAISE EXCEPTION 'APPOINTMENT_ACCESS_DENIED' USING ERRCODE='42501'; END IF;
    IF NOT psique_v2_role_check(ARRAY['SECRETARY','ORG_ADMIN','CLINICAL_SUPERVISOR'])
        AND appointment.clinician_membership_id IS DISTINCT FROM member THEN
        RAISE EXCEPTION 'OWN_AGENDA_ONLY' USING ERRCODE='42501';
    END IF;
    SELECT coalesce(jsonb_agg(jsonb_build_object('event_kind',e.event_kind,
        'previous_state',e.previous_state,'current_state',e.current_state,
        'created_at',e.created_at) ORDER BY e.created_at),'[]'::jsonb)
    INTO result FROM psique_appointment_events e WHERE e.appointment_id=appointment_ref;
    RETURN jsonb_build_object('events',result);
END $$;

CREATE OR REPLACE FUNCTION psique_v2_appointments_list(org uuid, member uuid, actor uuid,
    from_at timestamptz, to_at timestamptz)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=public,pg_temp AS $$
DECLARE result jsonb;
BEGIN
    PERFORM psique_v2_scheduling_member(org,member,actor,
        ARRAY['SECRETARY','ORG_ADMIN','CLINICAL_SUPERVISOR','CLINICIAN']);
    SELECT coalesce(jsonb_agg(psique_v2_appointment_snapshot(a)
        ||jsonb_build_object('appointment_id',a.id,'patient_id',a.patient_id,
            'patient_name',CASE WHEN psique_v2_role_check(ARRAY['SECRETARY','ORG_ADMIN'])
                OR a.clinician_membership_id=member THEN p.full_name ELSE NULL END)
        ORDER BY a.start_at),'[]'::jsonb)
    INTO result
    FROM psique_appointments a
    LEFT JOIN patients p ON p.organization_id=a.organization_id AND p.id=a.patient_id
    WHERE a.organization_id=org AND a.start_at < to_at AND a.end_at > from_at
      AND (psique_v2_role_check(ARRAY['SECRETARY','ORG_ADMIN','CLINICAL_SUPERVISOR'])
           OR a.clinician_membership_id=member);
    RETURN jsonb_build_object('appointments',result);
END $$;

CREATE OR REPLACE FUNCTION psique_v2_scheduling_clinicians(org uuid, member uuid, actor uuid)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=public,pg_temp AS $$
DECLARE result jsonb;
BEGIN
    PERFORM psique_v2_scheduling_member(org,member,actor,
        ARRAY['SECRETARY','ORG_ADMIN','CLINICAL_SUPERVISOR','CLINICIAN']);
    SELECT coalesce(jsonb_agg(jsonb_build_object(
        'membership_id',g.membership_id,'email',u.email,
        'availability',(SELECT coalesce(jsonb_agg(jsonb_build_object(
            'weekday',av.weekday,'start_minute',av.start_minute,'end_minute',av.end_minute,
            'timezone',av.availability_timezone,'active',av.active) ORDER BY av.weekday,av.start_minute),'[]'::jsonb)
            FROM psique_clinician_availability av
            WHERE av.organization_id=org AND av.clinician_membership_id=g.membership_id))
        ORDER BY u.email),'[]'::jsonb)
    INTO result
    FROM psique_membership_role_grants g
    JOIN organization_memberships m ON m.id=g.membership_id AND m.status='active'
    JOIN users u ON u.id=m.user_id
    WHERE g.organization_id=org AND g.v2_role='CLINICIAN' AND g.revoked_at IS NULL;
    RETURN jsonb_build_object('clinicians',result);
END $$;

CREATE OR REPLACE FUNCTION psique_v2_scheduling_patients(org uuid, member uuid, actor uuid)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=public,pg_temp AS $$
DECLARE result jsonb; com_nome boolean;
BEGIN
    PERFORM psique_v2_scheduling_member(org,member,actor,
        ARRAY['SECRETARY','ORG_ADMIN','CLINICAL_SUPERVISOR','CLINICIAN']);
    -- Nome para secretaria, administrador e clinico; o supervisor recebe so
    -- o identificador curto (decisao do dono, 18/10/2026).
    com_nome:=psique_v2_role_check(ARRAY['SECRETARY','ORG_ADMIN','CLINICIAN']);
    SELECT coalesce(jsonb_agg(jsonb_build_object(
        'patient_id',p.id,
        'label',CASE WHEN com_nome THEN p.full_name ELSE 'Paciente '||right(p.id::text,4) END)
        ORDER BY CASE WHEN com_nome THEN p.full_name ELSE p.id::text END),'[]'::jsonb)
    INTO result
    FROM patients p WHERE p.organization_id=org AND p.status='active';
    RETURN jsonb_build_object('patients',result,'with_names',com_nome);
END $$;

CREATE OR REPLACE FUNCTION psique_v2_role_grants_list(org uuid, member uuid, actor uuid)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=public,pg_temp AS $$
DECLARE result jsonb;
BEGIN
    -- Quem gere os papeis ve quem tem qual papel. Antes disto o painel so
    -- conhecia os papeis de quem perguntava (capabilities).
    PERFORM psique_v2_scheduling_member(org,member,actor,ARRAY['ORG_ADMIN']);
    SELECT coalesce(jsonb_agg(jsonb_build_object('membership_id',m.id,'email',u.email,
        'v2_roles',(SELECT coalesce(jsonb_agg(g.v2_role ORDER BY g.v2_role),'[]'::jsonb)
            FROM psique_membership_role_grants g
            WHERE g.organization_id=org AND g.membership_id=m.id AND g.revoked_at IS NULL))
        ORDER BY u.email),'[]'::jsonb)
    INTO result
    FROM organization_memberships m JOIN users u ON u.id=m.user_id
    WHERE m.organization_id=org AND m.status='active';
    RETURN jsonb_build_object('members',result);
END $$;

DO $$ BEGIN IF EXISTS(SELECT 1 FROM pg_roles WHERE rolname='froid_runtime') THEN
  GRANT EXECUTE ON FUNCTION psique_v2_scheduling_clinicians(uuid,uuid,uuid) TO froid_runtime;
  GRANT EXECUTE ON FUNCTION psique_v2_scheduling_patients(uuid,uuid,uuid) TO froid_runtime;
  GRANT EXECUTE ON FUNCTION psique_v2_role_grants_list(uuid,uuid,uuid) TO froid_runtime;
END IF; END $$;

INSERT INTO schema_migrations(version) VALUES('053_psique_scheduling_supervisor');
COMMIT;
