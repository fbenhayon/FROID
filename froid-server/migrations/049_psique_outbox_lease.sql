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
