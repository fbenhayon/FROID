BEGIN;

-- 049: a retirada da fila de espelho da agenda passa a RESERVAR o item.
--
-- Defeito apurado em 05/10/2026 por test_outbox_take_is_concurrent_safe: a
-- 044 travava os itens so durante a transacao do take (FOR UPDATE SKIP LOCKED)
-- e nao os tirava de PENDING. Assim que o primeiro take terminava, um segundo
-- pegava os MESMOS itens -- o mesmo evento podia ir duas vezes ao Google. Em
-- producao nao havia consumidor da fila ainda, entao o defeito estava latente.
--
-- Agora o take marca leased_until (5 min) e so retira PENDING sem reserva
-- vigente. Item reservado que nao for liquidado volta sozinho quando a reserva
-- vence (worker caido no meio da entrega). O settle limpa a reserva.

ALTER TABLE psique_calendar_outbox ADD COLUMN leased_until timestamptz;

CREATE OR REPLACE FUNCTION psique_v2_outbox_take(org uuid, member uuid, actor uuid, how_many integer)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=public,pg_temp AS $$
DECLARE result jsonb;
BEGIN
    PERFORM psique_v2_scheduling_member(org,member,actor,ARRAY['ORG_ADMIN']);
    WITH taken AS (
        SELECT id FROM psique_calendar_outbox
        WHERE organization_id=org AND outbox_status='PENDING'
          AND (leased_until IS NULL OR leased_until < clock_timestamp())
        ORDER BY created_at
        LIMIT greatest(1,least(how_many,50))
        FOR UPDATE SKIP LOCKED
    ), bumped AS (
        UPDATE psique_calendar_outbox o SET attempts=attempts+1,
            leased_until=clock_timestamp()+interval '5 minutes'
        FROM taken WHERE o.id=taken.id
        RETURNING o.id,o.appointment_id,o.operation,o.payload,o.attempts
    )
    SELECT coalesce(jsonb_agg(jsonb_build_object('outbox_id',id,
        'appointment_id',appointment_id,'operation',operation,
        'payload',payload,'attempts',attempts)),'[]'::jsonb)
    INTO result FROM bumped;
    RETURN jsonb_build_object('items',result);
END $$;

CREATE OR REPLACE FUNCTION psique_v2_outbox_settle(org uuid, member uuid, actor uuid,
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
    -- 049: quem demorou mais que a reserva nao entrega mais; o item ja pode ter
    -- sido retirado por outro worker (evento duplicado no Google).
    IF row_out.outbox_status='PENDING' AND row_out.leased_until IS NOT NULL
       AND row_out.leased_until < clock_timestamp() THEN
        RAISE EXCEPTION 'OUTBOX_LEASE_EXPIRED';
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

CREATE OR REPLACE FUNCTION psique_calendar_outbox_clear_lease() RETURNS trigger
LANGUAGE plpgsql SET search_path=public,pg_temp AS $$
BEGIN
    IF NEW.outbox_status <> 'PENDING' THEN NEW.leased_until := NULL; END IF;
    RETURN NEW;
END $$;

CREATE TRIGGER psique_calendar_outbox_clear_lease
    BEFORE UPDATE OF outbox_status ON psique_calendar_outbox
    FOR EACH ROW EXECUTE FUNCTION psique_calendar_outbox_clear_lease();

INSERT INTO schema_migrations(version) VALUES('049_psique_outbox_lease');
COMMIT;
