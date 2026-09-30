BEGIN;

-- Phase 4: organizational scheduling for Psique V2. The internal Appointment
-- is the authority; Google is a mirror fed by an outbox AFTER commit, so a
-- mirror failure can never lose or block a booking, and no external token is
-- ever stored here. Scheduling requires RBAC V2 (SECRETARY books without any
-- clinical content; CLINICIAN sees their own agenda); V1 organizations keep
-- their current calendar behavior untouched.

CREATE EXTENSION IF NOT EXISTS btree_gist;

CREATE TABLE psique_organization_units (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT,
    unit_name text NOT NULL CHECK (length(trim(unit_name)) > 0),
    active boolean NOT NULL DEFAULT true,
    created_by uuid NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE (organization_id, unit_name),
    UNIQUE (organization_id, id)
);

CREATE TABLE psique_clinician_availability (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id uuid NOT NULL,
    clinician_membership_id uuid NOT NULL,
    weekday smallint NOT NULL CHECK (weekday BETWEEN 0 AND 6),
    start_minute smallint NOT NULL CHECK (start_minute BETWEEN 0 AND 1439),
    end_minute smallint NOT NULL CHECK (end_minute BETWEEN 1 AND 1440),
    availability_timezone text NOT NULL CHECK (length(trim(availability_timezone)) > 0),
    active boolean NOT NULL DEFAULT true,
    created_by uuid NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    CHECK (end_minute > start_minute),
    FOREIGN KEY (organization_id, clinician_membership_id)
        REFERENCES organization_memberships(organization_id, id) ON DELETE RESTRICT,
    UNIQUE (clinician_membership_id, weekday, start_minute)
);

CREATE TABLE psique_appointments (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id uuid NOT NULL,
    patient_id uuid NOT NULL,
    clinician_membership_id uuid NOT NULL,
    unit_id uuid,
    start_at timestamptz NOT NULL,
    end_at timestamptz NOT NULL,
    appointment_timezone text NOT NULL CHECK (length(trim(appointment_timezone)) > 0),
    appointment_status text NOT NULL DEFAULT 'SCHEDULED' CHECK (appointment_status IN
        ('SCHEDULED','CONFIRMED','IN_PROGRESS','COMPLETED','CANCELLED','NO_SHOW')),
    created_by uuid NOT NULL,
    updated_by uuid NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    version bigint NOT NULL DEFAULT 1 CHECK (version >= 1),
    idempotency_key text NOT NULL CHECK (length(trim(idempotency_key)) > 0),
    CHECK (end_at > start_at),
    FOREIGN KEY (organization_id, patient_id)
        REFERENCES patients(organization_id, id) ON DELETE RESTRICT,
    FOREIGN KEY (organization_id, clinician_membership_id)
        REFERENCES organization_memberships(organization_id, id) ON DELETE RESTRICT,
    FOREIGN KEY (organization_id, unit_id)
        REFERENCES psique_organization_units(organization_id, id) ON DELETE RESTRICT,
    UNIQUE (organization_id, idempotency_key),
    UNIQUE (organization_id, id),
    -- The database itself forbids a clinician being double-booked while the
    -- appointment still occupies the slot.
    EXCLUDE USING gist (
        clinician_membership_id WITH =,
        tstzrange(start_at, end_at) WITH &&
    ) WHERE (appointment_status IN ('SCHEDULED','CONFIRMED','IN_PROGRESS'))
);
CREATE INDEX psique_appointments_by_clinician
    ON psique_appointments(clinician_membership_id, start_at);
CREATE INDEX psique_appointments_by_org_window
    ON psique_appointments(organization_id, start_at);

CREATE TABLE psique_appointment_events (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id uuid NOT NULL,
    appointment_id uuid NOT NULL,
    event_kind text NOT NULL CHECK (event_kind IN
        ('CREATED','RESCHEDULED','STATUS_CHANGED','CANCELLED','SESSION_LINKED')),
    -- Administrative snapshot only (times/status/clinician/unit); clinical
    -- content never enters the trail.
    previous_state jsonb,
    current_state jsonb NOT NULL,
    actor_user_id uuid NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    FOREIGN KEY (organization_id, appointment_id)
        REFERENCES psique_appointments(organization_id, id) ON DELETE RESTRICT
);
CREATE INDEX psique_appointment_events_by_appointment
    ON psique_appointment_events(appointment_id, created_at);

CREATE TABLE psique_appointment_session_links (
    appointment_id uuid PRIMARY KEY,
    organization_id uuid NOT NULL,
    analysis_source_id uuid NOT NULL,
    linked_by uuid NOT NULL,
    linked_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    FOREIGN KEY (organization_id, appointment_id)
        REFERENCES psique_appointments(organization_id, id) ON DELETE RESTRICT,
    FOREIGN KEY (organization_id, analysis_source_id)
        REFERENCES psique_analysis_sources(organization_id, id) ON DELETE RESTRICT
);

CREATE TABLE psique_calendar_outbox (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id uuid NOT NULL,
    appointment_id uuid NOT NULL,
    operation text NOT NULL CHECK (operation IN ('UPSERT','CANCEL')),
    -- Administrative payload for the mirror: times/status only. No patient
    -- name, no clinical content, and never any credential/token.
    payload jsonb NOT NULL,
    outbox_status text NOT NULL DEFAULT 'PENDING'
        CHECK (outbox_status IN ('PENDING','DELIVERED','FAILED')),
    attempts integer NOT NULL DEFAULT 0 CHECK (attempts >= 0),
    external_event_id text,
    last_error_sanitized text,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    delivered_at timestamptz,
    FOREIGN KEY (organization_id, appointment_id)
        REFERENCES psique_appointments(organization_id, id) ON DELETE RESTRICT
);
CREATE INDEX psique_calendar_outbox_pending
    ON psique_calendar_outbox(created_at) WHERE outbox_status='PENDING';

CREATE FUNCTION psique_scheduling_history_guard() RETURNS trigger
LANGUAGE plpgsql SET search_path=public,pg_temp AS $$
BEGIN
    RAISE EXCEPTION 'PSIQUE_SCHEDULING_HISTORY_IMMUTABLE';
END $$;
CREATE TRIGGER psique_appointment_no_delete BEFORE DELETE ON psique_appointments
    FOR EACH ROW EXECUTE FUNCTION psique_scheduling_history_guard();
CREATE TRIGGER psique_appointment_events_immutable BEFORE UPDATE OR DELETE ON psique_appointment_events
    FOR EACH ROW EXECUTE FUNCTION psique_scheduling_history_guard();
CREATE TRIGGER psique_session_links_immutable BEFORE UPDATE OR DELETE ON psique_appointment_session_links
    FOR EACH ROW EXECUTE FUNCTION psique_scheduling_history_guard();

ALTER TABLE psique_organization_units ENABLE ROW LEVEL SECURITY;
ALTER TABLE psique_clinician_availability ENABLE ROW LEVEL SECURITY;
ALTER TABLE psique_appointments ENABLE ROW LEVEL SECURITY;
ALTER TABLE psique_appointment_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE psique_appointment_session_links ENABLE ROW LEVEL SECURITY;
ALTER TABLE psique_calendar_outbox ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON psique_organization_units,psique_clinician_availability,psique_appointments,
    psique_appointment_events,psique_appointment_session_links,psique_calendar_outbox FROM PUBLIC;

-- ---------------------------------------------------------------------------
-- Command boundary. Scheduling requires RBAC V2; V1 organizations are refused
-- with a named reason and keep their existing calendar behavior.
-- ---------------------------------------------------------------------------

CREATE FUNCTION psique_v2_scheduling_member(org uuid, member uuid, actor uuid, needed text[])
RETURNS void LANGUAGE plpgsql SET search_path=public,pg_temp AS $$
BEGIN
    PERFORM psique_v2_rbac_require_member(org,member,actor);
    IF NOT psique_rbac_v2_active(org) THEN
        RAISE EXCEPTION 'RBAC_V2_NOT_ENABLED';
    END IF;
    IF NOT psique_v2_role_check(needed) THEN
        RAISE EXCEPTION 'PSIQUE_SCHEDULING_ROLE_DENIED' USING ERRCODE='42501';
    END IF;
END $$;

CREATE FUNCTION psique_v2_appointment_snapshot(a psique_appointments)
RETURNS jsonb LANGUAGE sql IMMUTABLE SET search_path=public,pg_temp AS $$
    SELECT jsonb_build_object(
        'start_at',a.start_at,'end_at',a.end_at,'timezone',a.appointment_timezone,
        'appointment_status',a.appointment_status,
        'clinician_membership_id',a.clinician_membership_id,'unit_id',a.unit_id,
        'version',a.version);
$$;

CREATE FUNCTION psique_v2_unit_upsert(org uuid, member uuid, actor uuid, name text)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=public,pg_temp AS $$
DECLARE unit psique_organization_units%ROWTYPE;
BEGIN
    PERFORM psique_v2_scheduling_member(org,member,actor,ARRAY['ORG_ADMIN']);
    IF coalesce(trim(name),'')='' THEN RAISE EXCEPTION 'UNIT_NAME_REQUIRED'; END IF;
    INSERT INTO psique_organization_units(organization_id,unit_name,created_by)
        VALUES(org,trim(name),actor)
        ON CONFLICT (organization_id,unit_name) DO NOTHING;
    SELECT * INTO unit FROM psique_organization_units
        WHERE organization_id=org AND unit_name=trim(name);
    RETURN jsonb_build_object('unit_id',unit.id,'unit_name',unit.unit_name,'active',unit.active);
END $$;

CREATE FUNCTION psique_v2_availability_set(org uuid, member uuid, actor uuid, args jsonb)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=public,pg_temp AS $$
DECLARE clinician uuid:=(args->>'clinician_membership_id')::uuid; slot psique_clinician_availability%ROWTYPE;
BEGIN
    PERFORM psique_v2_scheduling_member(org,member,actor,
        ARRAY['ORG_ADMIN','SECRETARY','CLINICIAN']);
    -- A clinician manages only their own availability; staff manage anyone's.
    IF NOT psique_v2_role_check(ARRAY['ORG_ADMIN','SECRETARY']) AND clinician IS DISTINCT FROM member THEN
        RAISE EXCEPTION 'OWN_AVAILABILITY_ONLY' USING ERRCODE='42501';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM psique_membership_role_grants g
        JOIN organization_memberships m ON m.id=g.membership_id AND m.status='active'
        WHERE g.membership_id=clinician AND g.organization_id=org
          AND g.v2_role='CLINICIAN' AND g.revoked_at IS NULL) THEN
        RAISE EXCEPTION 'AVAILABILITY_CLINICIAN_REQUIRED';
    END IF;
    IF (args->>'active')::boolean IS FALSE THEN
        UPDATE psique_clinician_availability SET active=false
            WHERE clinician_membership_id=clinician AND organization_id=org
              AND weekday=(args->>'weekday')::smallint
              AND start_minute=(args->>'start_minute')::smallint
            RETURNING * INTO slot;
        RETURN jsonb_build_object('changed',FOUND,'availability_id',slot.id,'active',false);
    END IF;
    INSERT INTO psique_clinician_availability(organization_id,clinician_membership_id,weekday,
        start_minute,end_minute,availability_timezone,created_by)
    VALUES(org,clinician,(args->>'weekday')::smallint,(args->>'start_minute')::smallint,
        (args->>'end_minute')::smallint,args->>'timezone',actor)
    ON CONFLICT (clinician_membership_id,weekday,start_minute) DO UPDATE
        SET end_minute=EXCLUDED.end_minute,availability_timezone=EXCLUDED.availability_timezone,
            active=true
    RETURNING * INTO slot;
    RETURN jsonb_build_object('changed',true,'availability_id',slot.id,'active',true);
END $$;

CREATE FUNCTION psique_v2_within_availability(org uuid, clinician uuid,
    from_at timestamptz, to_at timestamptz)
RETURNS boolean LANGUAGE sql STABLE SET search_path=public,pg_temp AS $$
    SELECT EXISTS (
        SELECT 1 FROM psique_clinician_availability s
        WHERE s.organization_id=org AND s.clinician_membership_id=clinician AND s.active
          AND (from_at AT TIME ZONE s.availability_timezone)::date
              = (to_at AT TIME ZONE s.availability_timezone)::date
          AND s.weekday = EXTRACT(DOW FROM from_at AT TIME ZONE s.availability_timezone)::smallint
          AND s.start_minute <= (EXTRACT(HOUR FROM from_at AT TIME ZONE s.availability_timezone)*60
              + EXTRACT(MINUTE FROM from_at AT TIME ZONE s.availability_timezone))
          AND s.end_minute >= (EXTRACT(HOUR FROM to_at AT TIME ZONE s.availability_timezone)*60
              + EXTRACT(MINUTE FROM to_at AT TIME ZONE s.availability_timezone))
    );
$$;

CREATE FUNCTION psique_v2_appointment_create(org uuid, member uuid, actor uuid, args jsonb)
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

CREATE FUNCTION psique_v2_appointment_change(org uuid, member uuid, actor uuid, args jsonb)
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

CREATE FUNCTION psique_v2_appointment_cancel(org uuid, member uuid, actor uuid,
    appointment_ref uuid, expected bigint, reason text)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=public,pg_temp AS $$
DECLARE appointment psique_appointments%ROWTYPE; before jsonb;
BEGIN
    PERFORM psique_v2_scheduling_member(org,member,actor,
        ARRAY['SECRETARY','ORG_ADMIN','CLINICIAN']);
    SELECT * INTO appointment FROM psique_appointments
        WHERE organization_id=org AND id=appointment_ref FOR UPDATE;
    IF NOT FOUND THEN RAISE EXCEPTION 'APPOINTMENT_ACCESS_DENIED' USING ERRCODE='42501'; END IF;
    IF NOT psique_v2_role_check(ARRAY['SECRETARY','ORG_ADMIN'])
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

CREATE FUNCTION psique_v2_appointments_list(org uuid, member uuid, actor uuid,
    from_at timestamptz, to_at timestamptz)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=public,pg_temp AS $$
DECLARE result jsonb;
BEGIN
    PERFORM psique_v2_scheduling_member(org,member,actor,
        ARRAY['SECRETARY','ORG_ADMIN','CLINICIAN']);
    SELECT coalesce(jsonb_agg(psique_v2_appointment_snapshot(a)
        ||jsonb_build_object('appointment_id',a.id,'patient_id',a.patient_id)
        ORDER BY a.start_at),'[]'::jsonb)
    INTO result
    FROM psique_appointments a
    WHERE a.organization_id=org AND a.start_at < to_at AND a.end_at > from_at
      AND (psique_v2_role_check(ARRAY['SECRETARY','ORG_ADMIN'])
           OR a.clinician_membership_id=member);
    RETURN jsonb_build_object('appointments',result);
END $$;

CREATE FUNCTION psique_v2_appointment_history(org uuid, member uuid, actor uuid,
    appointment_ref uuid)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=public,pg_temp AS $$
DECLARE appointment psique_appointments%ROWTYPE; result jsonb;
BEGIN
    PERFORM psique_v2_scheduling_member(org,member,actor,
        ARRAY['SECRETARY','ORG_ADMIN','CLINICIAN']);
    SELECT * INTO appointment FROM psique_appointments
        WHERE organization_id=org AND id=appointment_ref;
    IF NOT FOUND THEN RAISE EXCEPTION 'APPOINTMENT_ACCESS_DENIED' USING ERRCODE='42501'; END IF;
    IF NOT psique_v2_role_check(ARRAY['SECRETARY','ORG_ADMIN'])
        AND appointment.clinician_membership_id IS DISTINCT FROM member THEN
        RAISE EXCEPTION 'OWN_AGENDA_ONLY' USING ERRCODE='42501';
    END IF;
    SELECT coalesce(jsonb_agg(jsonb_build_object('event_kind',e.event_kind,
        'previous_state',e.previous_state,'current_state',e.current_state,
        'created_at',e.created_at) ORDER BY e.created_at),'[]'::jsonb)
    INTO result FROM psique_appointment_events e WHERE e.appointment_id=appointment_ref;
    RETURN jsonb_build_object('events',result);
END $$;

CREATE FUNCTION psique_v2_appointment_link_source(org uuid, member uuid, actor uuid,
    appointment_ref uuid, source_ref uuid)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=public,pg_temp AS $$
DECLARE appointment psique_appointments%ROWTYPE;
BEGIN
    PERFORM psique_v2_scheduling_member(org,member,actor,ARRAY['CLINICIAN']);
    SELECT * INTO appointment FROM psique_appointments
        WHERE organization_id=org AND id=appointment_ref FOR UPDATE;
    IF NOT FOUND OR appointment.clinician_membership_id IS DISTINCT FROM member THEN
        -- Só o clínico do atendimento liga a sessão; secretaria nunca toca
        -- em vínculo clínico.
        RAISE EXCEPTION 'APPOINTMENT_ACCESS_DENIED' USING ERRCODE='42501';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM psique_analysis_sources s
        WHERE s.organization_id=org AND s.id=source_ref AND s.owner_membership_id=member) THEN
        RAISE EXCEPTION 'SOURCE_ACCESS_DENIED' USING ERRCODE='42501';
    END IF;
    INSERT INTO psique_appointment_session_links(appointment_id,organization_id,
        analysis_source_id,linked_by)
    VALUES(appointment_ref,org,source_ref,actor)
    ON CONFLICT (appointment_id) DO NOTHING;
    IF NOT FOUND THEN RETURN jsonb_build_object('linked',false,'code','APPOINTMENT_ALREADY_LINKED'); END IF;
    INSERT INTO psique_appointment_events(organization_id,appointment_id,event_kind,
        current_state,actor_user_id)
    VALUES(org,appointment_ref,'SESSION_LINKED',
        jsonb_build_object('analysis_source_id',source_ref),actor);
    RETURN jsonb_build_object('linked',true);
END $$;

-- Mirror worker boundary: take with SKIP LOCKED, then settle. A failure is
-- visible state on the outbox row; the appointment itself is never touched.
CREATE FUNCTION psique_v2_outbox_take(org uuid, member uuid, actor uuid, how_many integer)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=public,pg_temp AS $$
DECLARE result jsonb;
BEGIN
    PERFORM psique_v2_scheduling_member(org,member,actor,ARRAY['ORG_ADMIN']);
    WITH taken AS (
        SELECT id FROM psique_calendar_outbox
        WHERE organization_id=org AND outbox_status='PENDING'
        ORDER BY created_at
        LIMIT greatest(1,least(how_many,50))
        FOR UPDATE SKIP LOCKED
    ), bumped AS (
        UPDATE psique_calendar_outbox o SET attempts=attempts+1
        FROM taken WHERE o.id=taken.id
        RETURNING o.id,o.appointment_id,o.operation,o.payload,o.attempts
    )
    SELECT coalesce(jsonb_agg(jsonb_build_object('outbox_id',id,
        'appointment_id',appointment_id,'operation',operation,
        'payload',payload,'attempts',attempts)),'[]'::jsonb)
    INTO result FROM bumped;
    RETURN jsonb_build_object('items',result);
END $$;

CREATE FUNCTION psique_v2_outbox_settle(org uuid, member uuid, actor uuid,
    outbox_ref uuid, delivered boolean, external_ref text, error_note text)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=public,pg_temp AS $$
DECLARE row_out psique_calendar_outbox%ROWTYPE;
BEGIN
    PERFORM psique_v2_scheduling_member(org,member,actor,ARRAY['ORG_ADMIN']);
    SELECT * INTO row_out FROM psique_calendar_outbox
        WHERE organization_id=org AND id=outbox_ref FOR UPDATE;
    IF NOT FOUND THEN RAISE EXCEPTION 'OUTBOX_ITEM_NOT_FOUND'; END IF;
    IF row_out.outbox_status='DELIVERED' THEN
        RETURN jsonb_build_object('settled',false,'outbox_status','DELIVERED');
    END IF;
    IF delivered THEN
        UPDATE psique_calendar_outbox SET outbox_status='DELIVERED',
            external_event_id=nullif(trim(external_ref),''),
            delivered_at=clock_timestamp(),last_error_sanitized=NULL
            WHERE id=outbox_ref RETURNING * INTO row_out;
    ELSE
        -- Falha do espelho e estado visivel, nunca degradacao silenciosa; o
        -- agendamento interno permanece a autoridade e nao e tocado.
        UPDATE psique_calendar_outbox SET outbox_status='FAILED',
            last_error_sanitized=left(coalesce(nullif(trim(error_note),''),'MIRROR_FAILURE'),200)
            WHERE id=outbox_ref RETURNING * INTO row_out;
    END IF;
    RETURN jsonb_build_object('settled',true,'outbox_status',row_out.outbox_status,
        'attempts',row_out.attempts);
END $$;

CREATE FUNCTION psique_v2_calendar_sync_status(org uuid, member uuid, actor uuid)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=public,pg_temp AS $$
DECLARE result jsonb;
BEGIN
    PERFORM psique_v2_scheduling_member(org,member,actor,ARRAY['ORG_ADMIN','SECRETARY']);
    SELECT jsonb_build_object(
        'pending',count(*) FILTER (WHERE outbox_status='PENDING'),
        'delivered',count(*) FILTER (WHERE outbox_status='DELIVERED'),
        'failed',count(*) FILTER (WHERE outbox_status='FAILED'),
        'failures',coalesce(jsonb_agg(jsonb_build_object('outbox_id',id,
            'appointment_id',appointment_id,'operation',operation,
            'attempts',attempts,'last_error_sanitized',last_error_sanitized))
            FILTER (WHERE outbox_status='FAILED'),'[]'::jsonb))
    INTO result FROM psique_calendar_outbox WHERE organization_id=org;
    RETURN result;
END $$;

REVOKE ALL ON FUNCTION
    psique_scheduling_history_guard(),
    psique_v2_scheduling_member(uuid,uuid,uuid,text[]),
    psique_v2_appointment_snapshot(psique_appointments),
    psique_v2_within_availability(uuid,uuid,timestamptz,timestamptz),
    psique_v2_unit_upsert(uuid,uuid,uuid,text),
    psique_v2_availability_set(uuid,uuid,uuid,jsonb),
    psique_v2_appointment_create(uuid,uuid,uuid,jsonb),
    psique_v2_appointment_change(uuid,uuid,uuid,jsonb),
    psique_v2_appointment_cancel(uuid,uuid,uuid,uuid,bigint,text),
    psique_v2_appointments_list(uuid,uuid,uuid,timestamptz,timestamptz),
    psique_v2_appointment_history(uuid,uuid,uuid,uuid),
    psique_v2_appointment_link_source(uuid,uuid,uuid,uuid,uuid),
    psique_v2_outbox_take(uuid,uuid,uuid,integer),
    psique_v2_outbox_settle(uuid,uuid,uuid,uuid,boolean,text,text),
    psique_v2_calendar_sync_status(uuid,uuid,uuid)
    FROM PUBLIC;
DO $$ BEGIN IF EXISTS(SELECT 1 FROM pg_roles WHERE rolname='froid_runtime') THEN
    GRANT EXECUTE ON FUNCTION
        psique_v2_unit_upsert(uuid,uuid,uuid,text),
        psique_v2_availability_set(uuid,uuid,uuid,jsonb),
        psique_v2_appointment_create(uuid,uuid,uuid,jsonb),
        psique_v2_appointment_change(uuid,uuid,uuid,jsonb),
        psique_v2_appointment_cancel(uuid,uuid,uuid,uuid,bigint,text),
        psique_v2_appointments_list(uuid,uuid,uuid,timestamptz,timestamptz),
        psique_v2_appointment_history(uuid,uuid,uuid,uuid),
        psique_v2_appointment_link_source(uuid,uuid,uuid,uuid,uuid),
        psique_v2_outbox_take(uuid,uuid,uuid,integer),
        psique_v2_outbox_settle(uuid,uuid,uuid,uuid,boolean,text,text),
        psique_v2_calendar_sync_status(uuid,uuid,uuid)
    TO froid_runtime;
END IF; END $$;

INSERT INTO schema_migrations(version) VALUES('044_psique_org_scheduling');
COMMIT;
