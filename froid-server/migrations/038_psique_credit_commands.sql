BEGIN;

-- Internal primitives have no runtime EXECUTE grant. The command boundary
-- validates membership/actor/organization and locks the existing wallet first.
CREATE FUNCTION psique_v2_append(
    org uuid, actor uuid, kind text, amount integer, held integer, idem text,
    source_id uuid DEFAULT NULL, reservation uuid DEFAULT NULL,
    origin uuid DEFAULT NULL, fund text DEFAULT NULL, explanation text DEFAULT NULL
) RETURNS uuid LANGUAGE plpgsql SET search_path=public,pg_temp AS $$
DECLARE result uuid:=gen_random_uuid(); wallet organization_wallets%ROWTYPE;
BEGIN
    UPDATE organization_wallets SET balance=balance+amount,reserved_balance=reserved_balance+held,
        version=version+1,updated_at=clock_timestamp()
        WHERE organization_id=org AND credit_model='psique_v2' RETURNING * INTO wallet;
    IF NOT FOUND THEN RAISE EXCEPTION 'PSIQUE_WALLET_REQUIRED'; END IF;
    INSERT INTO credit_ledger(id,organization_id,delta,balance_after,event_type,idempotency_key,
        actor_user_id,ledger_version,reserved_delta,reserved_after,analysis_source_id,
        reservation_id,original_consumption_id,funding,reason)
    VALUES(result,org,amount,wallet.balance,kind,idem,actor,2,held,wallet.reserved_balance,
        source_id,reservation,origin,fund,explanation);
    INSERT INTO audit_events(id,organization_id,actor_user_id,action,resource_type,resource_id,metadata)
    VALUES(gen_random_uuid(),org,actor,'psique.'||kind,'credit_ledger',result::text,
        jsonb_build_object('reason',explanation,'source_id',source_id,'original_consumption_id',origin));
    RETURN result;
END $$;

CREATE FUNCTION psique_v2_expire(org uuid, actor uuid, instant timestamptz)
RETURNS void LANGUAGE plpgsql SET search_path=public,pg_temp AS $$
DECLARE trial psique_trials%ROWTYPE; free integer;
BEGIN
    SELECT * INTO trial FROM psique_trials WHERE organization_id=org;
    IF NOT FOUND OR trial.status='INELIGIBLE' THEN RETURN; END IF;
    free:=trial.credits_granted-trial.credits_used-trial.credits_reserved-trial.credits_expired;
    IF instant>=trial.expires_at THEN
        IF free>0 THEN
            PERFORM psique_v2_append(org,actor,'TRIAL_EXPIRATION',-free,0,
                'trial-expiration:'||trial.beneficiary_id||':'||(trial.credits_expired+free),
                fund=>'TRIAL',explanation=>'TRIAL_DEADLINE');
            UPDATE psique_trials SET credits_expired=credits_expired+free WHERE organization_id=org;
        END IF;
        UPDATE psique_trials SET status='EXPIRED' WHERE organization_id=org;
    ELSE
        UPDATE psique_trials SET status=CASE WHEN free=0 THEN 'EXHAUSTED' ELSE 'ACTIVE' END
            WHERE organization_id=org;
    END IF;
END $$;

CREATE FUNCTION psique_v2_credit_command(org uuid, member uuid, actor uuid, command text, args jsonb)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=public,pg_temp AS $$
DECLARE
    wallet organization_wallets%ROWTYPE; trial psique_trials%ROWTYPE;
    source psique_analysis_sources%ROWTYPE; attempt psique_analysis_attempts%ROWTYPE;
    reservation psique_credit_reservations%ROWTYPE; entry credit_ledger%ROWTYPE;
    previous credit_ledger%ROWTYPE; saved_report session_reports%ROWTYPE;
    instant timestamptz; free integer; paid_free integer; amount integer;
    event_id uuid; source_id uuid; attempt_id uuid; beneficiary uuid; report_key text;
    explanation text; idem text; funding_source text; token jsonb; evidence text;
    verified timestamptz; origin text; payload jsonb; digest_value text; actor_email text;
BEGIN
    IF froid_current_organization_id() IS DISTINCT FROM org OR
        froid_current_membership_id() IS DISTINCT FROM member THEN
        RAISE EXCEPTION 'PSIQUE_CONTEXT_MISMATCH' USING ERRCODE='42501';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM organization_memberships m JOIN organizations o ON o.id=m.organization_id
        JOIN users u ON u.id=m.user_id WHERE m.id=member AND m.organization_id=org AND m.user_id=actor
        AND m.status='active' AND u.status='active' AND o.status='active'
        AND o.organization_type IN ('solo','clinic')) THEN
        RAISE EXCEPTION 'PSIQUE_ACTIVE_MEMBERSHIP_REQUIRED' USING ERRCODE='42501';
    END IF;
    IF NOT froid_has_role(ARRAY['owner','administrator','professional']) THEN
        RAISE EXCEPTION 'PSIQUE_ROLE_DENIED' USING ERRCODE='42501';
    END IF;
    IF command IN ('ENROLL','GRANT_TRIAL') AND NOT froid_has_role(ARRAY['owner']) THEN
        RAISE EXCEPTION 'TRIAL_OWNER_REQUIRED' USING ERRCODE='42501';
    END IF;
    IF command IN ('RESTORE','ADJUST') AND NOT froid_has_role(ARRAY['owner','administrator']) THEN
        RAISE EXCEPTION 'PSIQUE_CREDIT_ADMIN_REQUIRED' USING ERRCODE='42501';
    END IF;
    IF command='ENROLL' THEN
        INSERT INTO organization_wallets(organization_id,balance) VALUES(org,0)
            ON CONFLICT(organization_id) DO NOTHING;
    END IF;
    SELECT * INTO wallet FROM organization_wallets WHERE organization_id=org FOR UPDATE;
    IF NOT FOUND THEN RAISE EXCEPTION 'PSIQUE_WALLET_REQUIRED'; END IF;
    instant:=clock_timestamp(); -- after the lock, so wait time never extends Trial eligibility
    IF command='ENROLL' THEN
        IF wallet.credit_model='psique_v2' THEN RETURN jsonb_build_object('enrolled',false); END IF;
        IF wallet.balance<>0 OR EXISTS(SELECT 1 FROM credit_ledger WHERE organization_id=org) THEN
            RAISE EXCEPTION 'V1_WALLET_CONVERSION_NOT_AUTHORIZED';
        END IF;
        UPDATE organization_wallets SET credit_model='psique_v2',authority='shared',version=version+1
            WHERE organization_id=org;
        INSERT INTO audit_events(id,organization_id,actor_user_id,action,resource_type,resource_id)
            VALUES(gen_random_uuid(),org,actor,'psique.wallet.enroll','organization_wallet',org::text);
        RETURN jsonb_build_object('enrolled',true);
    END IF;
    IF wallet.credit_model<>'psique_v2' THEN RAISE EXCEPTION 'PSIQUE_WALLET_REQUIRED'; END IF;

    IF command='KEY_VERSIONS' THEN
        RETURN jsonb_build_object('versions',coalesce((SELECT jsonb_agg(key_version) FROM
            (SELECT DISTINCT key_version FROM psique_trial_eligibility) keys),'[]'::jsonb));
    END IF;
    IF command='PENDING_ATTEMPTS' THEN
        RETURN jsonb_build_object('attempt_ids',coalesce((SELECT jsonb_agg(a.id)
            FROM psique_analysis_attempts a JOIN psique_analysis_sources s ON s.id=a.analysis_source_id
            WHERE a.organization_id=org AND s.owner_membership_id=member AND
                ((a.status='PROCESSING' AND a.lease_until<=instant) OR
                 (a.status='DELIVERED' AND EXISTS(SELECT 1 FROM psique_credit_reservations r
                    WHERE r.analysis_attempt_id=a.id AND r.status='RESERVED')))), '[]'::jsonb));
    END IF;
    IF command='GRANT_TRIAL' THEN
        verified:=(args->>'verified_at')::timestamptz;
        evidence:=trim(args->>'evidence_ref');
        IF verified IS NULL OR verified>instant OR coalesce(evidence,'')='' OR
            jsonb_typeof(args->'tokens') IS DISTINCT FROM 'array' OR jsonb_array_length(args->'tokens')=0 THEN
            RAISE EXCEPTION 'VERIFIED_IDENTITY_REQUIRED';
        END IF;
        IF EXISTS(SELECT key_version FROM psique_trial_eligibility
            EXCEPT SELECT item->>'version' FROM jsonb_array_elements(args->'tokens') item) THEN
            RAISE EXCEPTION 'TRIAL_HISTORICAL_KEY_REQUIRED';
        END IF;
        SELECT * INTO trial FROM psique_trials WHERE organization_id=org;
        IF FOUND THEN RETURN jsonb_build_object('granted',false,'status',trial.status); END IF;
        FOR token IN SELECT value FROM jsonb_array_elements(args->'tokens') ORDER BY value->>'version' LOOP
            IF coalesce(token->>'version','')='' OR coalesce(token->>'hmac','') !~ '^[0-9a-f]{64}$' THEN
                RAISE EXCEPTION 'INVALID_ELIGIBILITY_TOKEN';
            END IF;
            PERFORM pg_advisory_xact_lock(hashtextextended((token->>'version')||':'||(token->>'hmac'),0));
        END LOOP;
        SELECT e.beneficiary_id INTO beneficiary FROM psique_trial_eligibility e
            JOIN jsonb_array_elements(args->'tokens') item
            ON e.key_version=item->>'version' AND e.email_hmac=item->>'hmac' LIMIT 1;
        origin:=CASE WHEN beneficiary IS NOT NULL OR args->>'legacy_benefit'='true' THEN 'V1' ELSE 'V2' END;
        -- Prior V2 eligibility also blocks a new benefit; preserve its original provenance.
        IF beneficiary IS NOT NULL THEN
            SELECT eligibility_origin INTO origin FROM psique_trial_eligibility
                WHERE beneficiary_id=beneficiary LIMIT 1;
            INSERT INTO psique_trials(organization_id,beneficiary_id,status,credits_granted)
                VALUES(org,beneficiary,'INELIGIBLE',0);
        ELSE
            beneficiary:=gen_random_uuid();
            IF origin='V1' THEN
                INSERT INTO psique_trials(organization_id,beneficiary_id,status,credits_granted)
                    VALUES(org,beneficiary,'INELIGIBLE',0);
            ELSE
                INSERT INTO psique_trials(organization_id,beneficiary_id,status,started_at,expires_at,credits_granted)
                    VALUES(org,beneficiary,'ACTIVE',instant,instant+interval '336 hours',10);
                PERFORM psique_v2_append(org,actor,'TRIAL_GRANT',10,0,'trial-grant:'||beneficiary,fund=>'TRIAL');
            END IF;
        END IF;
        FOR token IN SELECT value FROM jsonb_array_elements(args->'tokens') LOOP
            INSERT INTO psique_trial_eligibility(key_version,email_hmac,beneficiary_id,organization_id,
                eligibility_origin,evidence_ref,verified_at)
                VALUES(token->>'version',token->>'hmac',beneficiary,org,origin,evidence,verified)
                ON CONFLICT(key_version,email_hmac) DO NOTHING;
        END LOOP;
        SELECT * INTO trial FROM psique_trials WHERE organization_id=org;
        INSERT INTO audit_events(id,organization_id,actor_user_id,action,resource_type,resource_id,metadata)
            VALUES(gen_random_uuid(),org,actor,'psique.trial.eligibility','psique_trial',beneficiary::text,
                jsonb_build_object('status',trial.status,'evidence_ref',evidence));
        RETURN jsonb_build_object('granted',trial.credits_granted=10,'status',trial.status);
    END IF;

    PERFORM psique_v2_expire(org,actor,instant);
    SELECT * INTO wallet FROM organization_wallets WHERE organization_id=org;
    SELECT * INTO trial FROM psique_trials WHERE organization_id=org;
    free:=CASE WHEN trial.status IN ('ACTIVE','EXHAUSTED') THEN
        trial.credits_granted-trial.credits_used-trial.credits_reserved-trial.credits_expired ELSE 0 END;

    IF command IN ('BALANCE','EXPIRE') THEN
        RETURN jsonb_build_object('balance',wallet.balance,'reserved_balance',wallet.reserved_balance,
            'available_balance',wallet.balance-wallet.reserved_balance,'trial_status',trial.status,
            'trial_free_remaining',free,'trial_expires_at',trial.expires_at);
    ELSIF command='IDENTITY' THEN
        SELECT email INTO actor_email FROM users WHERE id=actor;
        RETURN jsonb_build_object('email',actor_email);
    ELSIF command='REGISTER_SOURCE' THEN
        INSERT INTO psique_analysis_sources(organization_id,owner_membership_id,material_key,
            legacy_session_id,source_kind,source_sha256)
        VALUES(org,member,(args->>'material_key')::uuid,args->>'session_id',args->>'source_kind',args->>'source_sha256')
        ON CONFLICT(organization_id,material_key) DO NOTHING;
        SELECT * INTO source FROM psique_analysis_sources
            WHERE organization_id=org AND material_key=(args->>'material_key')::uuid;
        IF source.owner_membership_id<>member OR source.legacy_session_id IS DISTINCT FROM args->>'session_id'
            OR source.source_kind IS DISTINCT FROM args->>'source_kind'
            OR source.source_sha256 IS DISTINCT FROM args->>'source_sha256' THEN
            RAISE EXCEPTION 'SOURCE_IDENTITY_MISMATCH' USING ERRCODE='42501';
        END IF;
        RETURN jsonb_build_object('analysis_source_id',source.id,'source_sha256',source.source_sha256);
    ELSIF command='ADJUST' THEN
        amount:=(args->>'delta')::integer; explanation:=trim(args->>'reason'); idem:=trim(args->>'idempotency_key');
        IF amount IS NULL OR amount=0 OR coalesce(explanation,'')='' OR coalesce(idem,'')='' THEN
            RAISE EXCEPTION 'ADJUSTMENT_REASON_AND_AMOUNT_REQUIRED';
        END IF;
        SELECT * INTO previous FROM credit_ledger WHERE organization_id=org AND idempotency_key='adjust:'||idem;
        IF FOUND THEN
            IF previous.delta<>amount OR previous.reason<>explanation THEN RAISE EXCEPTION 'IDEMPOTENCY_MISMATCH'; END IF;
            RETURN jsonb_build_object('ledger_id',previous.id,'applied',false);
        END IF;
        paid_free:=wallet.balance-wallet.reserved_balance-free;
        IF amount<0 AND paid_free+amount<0 THEN RAISE EXCEPTION 'INSUFFICIENT_PAID_CREDITS'; END IF;
        event_id:=psique_v2_append(org,actor,'MANUAL_ADJUSTMENT',amount,0,'adjust:'||idem,
            fund=>'PAID',explanation=>explanation);
        RETURN jsonb_build_object('ledger_id',event_id,'applied',true);
    ELSIF command='RESTORE' THEN
        explanation:=trim(args->>'reason'); evidence:=trim(args->>'evidence_ref');
        IF coalesce(explanation,'')='' OR coalesce(evidence,'')='' THEN RAISE EXCEPTION 'RESTORE_EVIDENCE_REQUIRED'; END IF;
        SELECT * INTO entry FROM credit_ledger WHERE id=(args->>'consumption_id')::uuid
            AND organization_id=org AND event_type='CREDIT_CONSUMPTION' AND ledger_version=2;
        IF NOT FOUND THEN RAISE EXCEPTION 'ORIGINAL_CONSUMPTION_REQUIRED' USING ERRCODE='42501'; END IF;
        SELECT * INTO previous FROM credit_ledger WHERE original_consumption_id=entry.id AND event_type='CREDIT_RESTORE';
        IF FOUND THEN RETURN jsonb_build_object('ledger_id',previous.id,'applied',false); END IF;
        IF entry.funding='TRIAL' THEN
            UPDATE psique_trials SET credits_used=credits_used-1 WHERE organization_id=org;
        END IF;
        event_id:=psique_v2_append(org,actor,'CREDIT_RESTORE',1,0,'restore:'||entry.id,
            entry.analysis_source_id,entry.reservation_id,entry.id,entry.funding,explanation||' ['||evidence||']');
        PERFORM psique_v2_expire(org,actor,instant);
        RETURN jsonb_build_object('ledger_id',event_id,'applied',true);
    END IF;

    IF command='BEGIN' THEN
        SELECT * INTO source FROM psique_analysis_sources
            WHERE organization_id=org AND id=(args->>'source_id')::uuid AND owner_membership_id=member;
        IF NOT FOUND THEN RAISE EXCEPTION 'SOURCE_ACCESS_DENIED' USING ERRCODE='42501'; END IF;
        SELECT * INTO attempt FROM psique_analysis_attempts WHERE organization_id=org
            AND analysis_source_id=source.id AND execution_key=args->>'execution_key';
        IF FOUND THEN RETURN jsonb_build_object('attempt_id',attempt.id,'status',attempt.status,'started',false); END IF;
        IF EXISTS(SELECT 1 FROM psique_analysis_attempts WHERE analysis_source_id=source.id AND status='PROCESSING')
            OR EXISTS(SELECT 1 FROM psique_credit_reservations WHERE analysis_source_id=source.id AND status='RESERVED') THEN
            RETURN jsonb_build_object('started',false,'reason','SOURCE_IN_PROGRESS');
        END IF;
        SELECT * INTO entry FROM credit_ledger WHERE analysis_source_id=source.id AND event_type='CREDIT_CONSUMPTION';
        IF NOT FOUND AND wallet.balance-wallet.reserved_balance<1 THEN
            RETURN jsonb_build_object('started',false,'reason','INSUFFICIENT_CREDITS');
        END IF;
        INSERT INTO psique_analysis_attempts(organization_id,analysis_source_id,execution_key,started_at,lease_until)
            VALUES(org,source.id,args->>'execution_key',instant,(args->>'lease_until')::timestamptz)
            RETURNING * INTO attempt;
        IF entry.id IS NULL THEN
            funding_source:=CASE WHEN free>0 THEN 'TRIAL' ELSE 'PAID' END;
            INSERT INTO psique_credit_reservations(organization_id,analysis_source_id,analysis_attempt_id,funding)
                VALUES(org,source.id,attempt.id,funding_source) RETURNING * INTO reservation;
            IF funding_source='TRIAL' THEN
                UPDATE psique_trials SET credits_reserved=credits_reserved+1 WHERE organization_id=org;
            END IF;
            PERFORM psique_v2_append(org,actor,'CREDIT_RESERVATION',0,1,'reserve:'||attempt.id,
                source.id,reservation.id,fund=>funding_source);
            PERFORM psique_v2_expire(org,actor,instant);
        END IF;
        RETURN jsonb_build_object('attempt_id',attempt.id,'status',attempt.status,'started',true,'chargeable',entry.id IS NULL);
    END IF;

    SELECT * INTO attempt FROM psique_analysis_attempts WHERE organization_id=org AND id=(args->>'attempt_id')::uuid;
    SELECT * INTO source FROM psique_analysis_sources WHERE organization_id=org AND id=attempt.analysis_source_id
        AND owner_membership_id=member;
    IF attempt.id IS NULL OR source.id IS NULL THEN RAISE EXCEPTION 'ATTEMPT_ACCESS_DENIED' USING ERRCODE='42501'; END IF;
    SELECT * INTO reservation FROM psique_credit_reservations WHERE analysis_attempt_id=attempt.id;
    IF command='RECONCILE' THEN
        IF attempt.status='DELIVERED' THEN command:='CONSUME';
        ELSIF attempt.status='PROCESSING' AND attempt.lease_until<=instant THEN
            command:='RELEASE'; args:=args||jsonb_build_object('reason','WORKER_LEASE_EXPIRED');
        ELSE RETURN jsonb_build_object('status',attempt.status,'applied',false); END IF;
    END IF;
    IF command='HEARTBEAT' THEN
        IF attempt.status<>'PROCESSING' OR attempt.lease_until<=instant THEN RAISE EXCEPTION 'ATTEMPT_NOT_RUNNING'; END IF;
        IF (args->>'lease_until')::timestamptz<=attempt.lease_until THEN RAISE EXCEPTION 'LEASE_MUST_ADVANCE'; END IF;
        UPDATE psique_analysis_attempts SET lease_until=(args->>'lease_until')::timestamptz WHERE id=attempt.id;
        RETURN jsonb_build_object('status','PROCESSING');
    ELSIF command='DELIVER' THEN
        IF attempt.status='DELIVERED' THEN RETURN jsonb_build_object('report_id',attempt.report_id,'applied',false); END IF;
        IF attempt.status<>'PROCESSING' OR attempt.lease_until<=instant THEN RAISE EXCEPTION 'ATTEMPT_NOT_RUNNING'; END IF;
        payload:=args->'protected_report';
        IF args->>'technical_complete' IS DISTINCT FROM 'true' OR args->>'minimum_result_verified' IS DISTINCT FROM 'true'
            OR jsonb_typeof(payload) IS DISTINCT FROM 'object' OR payload='{}'::jsonb THEN
            RAISE EXCEPTION 'DELIVERY_CONTRACT_NOT_MET';
        END IF;
        IF coalesce(payload->>'transcript','')<>'' THEN RAISE EXCEPTION 'PROTECTED_REPORT_REQUIRED'; END IF;
        SELECT email INTO actor_email FROM users WHERE id=actor;
        report_key:='psique-v2:'||source.id;
        payload:=payload||jsonb_build_object('sessionId',report_key,'organizationId',org,
            'professionalEmail',actor_email,'analysisSourceId',source.id,'analysisAttemptId',attempt.id);
        INSERT INTO session_reports(id,organization_id,legacy_session_id,professional_membership_id,report_payload)
            VALUES(gen_random_uuid(),org,report_key,member,payload)
            ON CONFLICT(organization_id,legacy_session_id) DO UPDATE SET
                report_payload=EXCLUDED.report_payload,updated_at=clock_timestamp(),deleted_at=NULL
            WHERE session_reports.professional_membership_id=member
            RETURNING * INTO saved_report;
        IF NOT FOUND THEN RAISE EXCEPTION 'DELIVERY_OWNER_MISMATCH' USING ERRCODE='42501'; END IF;
        digest_value:=encode(digest(saved_report.report_payload::text,'sha256'),'hex');
        UPDATE psique_analysis_attempts SET status='DELIVERED',technical_completed_at=instant,
            delivered_at=instant,report_id=saved_report.id,delivery_sha256=digest_value WHERE id=attempt.id;
        RETURN jsonb_build_object('report_id',saved_report.id,'applied',true);
    ELSIF command='READ_DELIVERY' THEN
        SELECT * INTO saved_report FROM session_reports WHERE id=attempt.report_id AND organization_id=org
            AND professional_membership_id=member AND deleted_at IS NULL;
        IF attempt.status<>'DELIVERED' OR saved_report.id IS NULL THEN RAISE EXCEPTION 'DELIVERY_UNAVAILABLE'; END IF;
        RETURN jsonb_build_object('report_id',saved_report.id,'report',saved_report.report_payload);
    ELSIF command='CONSUME' THEN
        SELECT * INTO entry FROM credit_ledger WHERE analysis_source_id=source.id AND event_type='CREDIT_CONSUMPTION';
        IF entry.id IS NOT NULL THEN RETURN jsonb_build_object('ledger_id',entry.id,'applied',false); END IF;
        IF attempt.status<>'DELIVERED' OR reservation.id IS NULL OR reservation.status<>'RESERVED' THEN
            RAISE EXCEPTION 'DURABLE_DELIVERY_REQUIRED';
        END IF;
        SELECT * INTO saved_report FROM session_reports WHERE id=attempt.report_id AND organization_id=org
            AND professional_membership_id=member AND deleted_at IS NULL FOR SHARE;
        IF saved_report.id IS NULL OR encode(digest(saved_report.report_payload::text,'sha256'),'hex')<>attempt.delivery_sha256 THEN
            RAISE EXCEPTION 'DELIVERY_UNAVAILABLE';
        END IF;
        UPDATE psique_credit_reservations SET status='CONSUMED',resolved_at=instant WHERE id=reservation.id;
        IF reservation.funding='TRIAL' THEN
            UPDATE psique_trials SET credits_reserved=credits_reserved-1,credits_used=credits_used+1 WHERE organization_id=org;
        END IF;
        event_id:=psique_v2_append(org,actor,'CREDIT_CONSUMPTION',-1,-1,'consume:'||source.id,
            source.id,reservation.id,fund=>reservation.funding);
        PERFORM psique_v2_expire(org,actor,instant);
        RETURN jsonb_build_object('ledger_id',event_id,'applied',true);
    ELSIF command='RELEASE' THEN
        explanation:=trim(args->>'reason');
        IF coalesce(explanation,'')='' THEN RAISE EXCEPTION 'RELEASE_REASON_REQUIRED'; END IF;
        IF attempt.status='DELIVERED' THEN
            SELECT * INTO saved_report FROM session_reports WHERE id=attempt.report_id AND organization_id=org
                AND professional_membership_id=member AND deleted_at IS NULL FOR SHARE;
            IF saved_report.id IS NOT NULL AND
                encode(digest(saved_report.report_payload::text,'sha256'),'hex')=attempt.delivery_sha256 THEN
                RAISE EXCEPTION 'DELIVERED_REQUIRES_SETTLEMENT';
            END IF;
            IF reservation.status='CONSUMED' OR EXISTS(SELECT 1 FROM credit_ledger
                WHERE analysis_source_id=source.id AND event_type='CREDIT_CONSUMPTION') THEN
                RAISE EXCEPTION 'CONSUMED_REQUIRES_RESTORE';
            END IF;
            -- Failed availability before settlement: release without deleting
            -- the report or the historical delivery receipt.
        END IF;
        IF attempt.status='FAILED' THEN RETURN jsonb_build_object('applied',false,'status','FAILED'); END IF;
        UPDATE psique_analysis_attempts SET status='FAILED',failure_reason=explanation WHERE id=attempt.id;
        IF reservation.status='RESERVED' THEN
            UPDATE psique_credit_reservations SET status='RELEASED',resolved_at=instant WHERE id=reservation.id;
            IF reservation.funding='TRIAL' THEN
                UPDATE psique_trials SET credits_reserved=credits_reserved-1 WHERE organization_id=org;
            END IF;
            PERFORM psique_v2_append(org,actor,'CREDIT_RELEASE',0,-1,'release:'||attempt.id,
                source.id,reservation.id,fund=>reservation.funding,explanation=>explanation);
            PERFORM psique_v2_expire(org,actor,instant);
        END IF;
        RETURN jsonb_build_object('applied',true,'status','FAILED');
    END IF;
    RAISE EXCEPTION 'UNKNOWN_PSIQUE_COMMAND';
END $$;

REVOKE ALL ON FUNCTION psique_v2_append(uuid,uuid,text,integer,integer,text,uuid,uuid,uuid,text,text),
    psique_v2_expire(uuid,uuid,timestamptz),psique_v2_credit_command(uuid,uuid,uuid,text,jsonb) FROM PUBLIC;
DO $$ BEGIN IF EXISTS(SELECT 1 FROM pg_roles WHERE rolname='froid_runtime') THEN
    GRANT SELECT ON schema_migrations TO froid_runtime;
    GRANT EXECUTE ON FUNCTION psique_v2_credit_command(uuid,uuid,uuid,text,jsonb) TO froid_runtime;
END IF; END $$;

INSERT INTO schema_migrations(version) VALUES('038_psique_credit_commands');
COMMIT;
