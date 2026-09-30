BEGIN;

-- Review before Phase 3 (30/09/2026): the financial lookups of the credit
-- command query the ledger by source/consumption WITHOUT the ledger_version
-- predicate, so the partial UNIQUE indexes of migration 037 (which include
-- ledger_version=2 in their predicate) cannot serve them and every CONSUME,
-- BEGIN and RESTORE scanned the whole ledger. These plain partial indexes
-- match the queries as written. No semantics change; additive only.

CREATE INDEX psique_ledger_source_lookup
    ON credit_ledger(analysis_source_id, event_type)
    WHERE analysis_source_id IS NOT NULL;

CREATE INDEX psique_ledger_restore_lookup
    ON credit_ledger(original_consumption_id)
    WHERE original_consumption_id IS NOT NULL;

-- Seat counting and preview supersession are per-organization scans on
-- tables whose only key was the row identity.
CREATE INDEX psique_clinical_active_by_org
    ON psique_clinical_memberships(organization_id)
    WHERE clinical_status='ACTIVE';

CREATE INDEX psique_seat_changes_previewed
    ON psique_seat_changes(organization_id)
    WHERE change_status='PREVIEWED';

INSERT INTO schema_migrations(version) VALUES('041_psique_financial_lookup_indexes');
COMMIT;
