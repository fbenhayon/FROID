"""Real, disposable PostgreSQL acceptance tests for Psique Phase 1 only.

Opt in with FROID_PSIQUE_TEST_DATABASE_URL pointing at a local database named
psique_v2_test_*. Each class creates and drops its OWN random child database.
Never uses the runtime, production or generic integration-test credentials.
Stripe objects below are synthetic fixtures, not evidence of a Stripe API call.
"""

import copy
import os
import unittest
import uuid
from pathlib import Path
from tempfile import TemporaryDirectory

from froid_schema import SchemaNotReady, migration_paths
from psique_catalog_store import install_draft, read_catalog, register_test_mapping
from psique_pricing import PricingError, load_config, pricing_hash
from tenant_store import TenantStore
from tools.migrate_schema import apply, plan

DSN = os.environ.get("FROID_PSIQUE_TEST_DATABASE_URL", "")
ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ROOT / "migrations"
LEGACY = "034_anonimato_apos_o_fechamento"
FINAL = "036_psique_v2_purchases"


@unittest.skipUnless(DSN, "requires an explicit disposable Psique database")
class MigrationPostgresTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import psycopg
        from psycopg.conninfo import conninfo_to_dict, make_conninfo

        params = conninfo_to_dict(DSN)
        if (params.get("host") not in {"127.0.0.1", "localhost"}
            or not params.get("dbname", "").startswith("psique_v2_test_")
            or params.get("service") or params.get("hostaddr")):
            raise RuntimeError("only an explicit local psique_v2_test_* database is allowed")
        cls.pg = psycopg
        cls.admin = psycopg.connect(DSN, autocommit=True)
        cls.database = "psique_v2_test_" + uuid.uuid4().hex
        cls.admin.execute(psycopg.sql.SQL("CREATE DATABASE {}").format(
            psycopg.sql.Identifier(cls.database)))
        cls.addClassCleanup(cls.drop_own_database)
        cls.dsn = make_conninfo(DSN, dbname=cls.database)
        cls.conn = psycopg.connect(cls.dsn, autocommit=True)
        cls.addClassCleanup(cls.conn.close)

    @classmethod
    def drop_own_database(cls):
        try:
            cls.admin.execute(cls.pg.sql.SQL("DROP DATABASE {} WITH (FORCE)").format(
                cls.pg.sql.Identifier(cls.database)))
        finally:
            cls.admin.close()

    def test_explicit_migrations_preserve_legacy_and_reads_never_apply(self):
        conn = self.conn
        with self.pg.connect(self.dsn, autocommit=True,
                             options="-c default_transaction_read_only=on") as readonly:
            store = TenantStore("dual", self.dsn, MIGRATIONS / "001_multitenant_foundation.sql")
            with self.assertRaises(SchemaNotReady):
                store.ensure_schema(readonly)
            self.assertTrue(all(not item["applied"] for item in plan(readonly, MIGRATIONS, FINAL)))
        self.assertIsNone(conn.execute("SELECT to_regclass('schema_migrations')").fetchone()[0])
        with self.assertRaisesRegex(ValueError, "database_confirmation_mismatch"):
            apply(conn, MIGRATIONS, FINAL, "wrong_database")
        self.assertIsNone(conn.execute(
            "SELECT to_regclass('schema_migration_execution_log')").fetchone()[0])
        applied = apply(conn, MIGRATIONS, LEGACY, self.database)
        self.assertEqual(applied, [p.stem for p in migration_paths(MIGRATIONS) if p.stem <= LEGACY])

        # Synthetic legacy money/history witnesses, never clinical information.
        org = uuid.uuid4()
        conn.execute("INSERT INTO organizations(id,organization_type,legal_name,display_name) "
                     "VALUES(%s,'solo','TEST legacy','TEST legacy')", (org,))
        conn.execute("INSERT INTO organization_wallets(organization_id,balance) VALUES(%s,7)", (org,))
        conn.execute("INSERT INTO credit_ledger(id,organization_id,delta,balance_after,event_type,"
                     "idempotency_key) VALUES(%s,%s,7,7,'migration_opening','TEST witness')",
                     (uuid.uuid4(), org))
        before = self.legacy_snapshot(conn)
        with self.pg.connect(self.dsn, autocommit=True,
                             options="-c default_transaction_read_only=on") as readonly:
            for _ in range(2):
                TenantStore("dual", self.dsn, MIGRATIONS / "001_multitenant_foundation.sql").ensure_schema(readonly)
            pending = [x["version"] for x in plan(readonly, MIGRATIONS, FINAL) if not x["applied"]]
            self.assertEqual(pending, ["035_psique_v2_pricing", FINAL])
            with self.assertRaises(SchemaNotReady):
                read_catalog(readonly, version="2.1")
        self.assertIsNone(conn.execute("SELECT to_regclass('psique_pricing_tables')").fetchone()[0])
        self.assertEqual(apply(conn, MIGRATIONS, FINAL, self.database), pending)
        self.assertEqual(before, self.legacy_snapshot(conn))
        purchase_org_fk = conn.execute(
            "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
            "WHERE conrelid='psique_purchases'::regclass AND confrelid='organizations'::regclass"
        ).fetchall()
        self.assertEqual(purchase_org_fk, [(
            "FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE RESTRICT",)])
        self.assertEqual(apply(conn, MIGRATIONS, FINAL, self.database), [])
        logs = conn.execute("SELECT version,sha256,status,actor,finished_at "
                            "FROM schema_migration_execution_log ORDER BY version").fetchall()
        self.assertEqual(len(logs), len([p for p in migration_paths(MIGRATIONS) if p.stem <= FINAL]))
        self.assertTrue(all(len(r[1]) == 64 and r[2] == 'applied' and r[3] and r[4] for r in logs))
        self.assertEqual(conn.execute("SELECT count(*) FROM psique_pricing_tables").fetchone()[0], 0)
        with TemporaryDirectory() as directory:
            migrations = Path(directory)
            # Same applied version, different file: evidence must not be overwritten.
            source = MIGRATIONS / "035_psique_v2_pricing.sql"
            (migrations / source.name).write_bytes(source.read_bytes() + b"\n-- changed\n")
            with self.assertRaisesRegex(RuntimeError, "checksum_mismatch"):
                apply(conn, migrations, source.stem, self.database)
        with TemporaryDirectory() as directory:
            migrations = Path(directory)
            (migrations / "999_test_failure.sql").write_text(
                "BEGIN; CREATE TABLE test_failed_migration(id int); SELECT 1/0; COMMIT;",
                encoding="utf-8")
            with self.assertRaises(self.pg.errors.DivisionByZero):
                apply(conn, migrations, "999_test_failure", self.database)
            self.assertIsNone(conn.execute("SELECT to_regclass('test_failed_migration')").fetchone()[0])
            self.assertEqual(conn.execute(
                "SELECT status,error_class FROM schema_migration_execution_log "
                "WHERE version='999_test_failure'").fetchone(), ("failed", "DivisionByZero"))

    @staticmethod
    def legacy_snapshot(conn):
        # Compare all legacy table definitions, privileges, RLS, policies,
        # constraints, triggers and function definitions, not just row counts.
        queries = [
            ("SELECT c.oid,c.relname,c.relrowsecurity,c.relforcerowsecurity,c.relacl "
            "FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
            "WHERE n.nspname='public' AND c.relkind IN ('r','p') "
            "AND c.relname NOT LIKE 'psique_%' ORDER BY c.oid"),
            ("SELECT a.attrelid,a.attnum,a.attname,a.atttypid,a.attnotnull,pg_get_expr(d.adbin,d.adrelid) "
            "FROM pg_attribute a JOIN pg_class c ON c.oid=a.attrelid "
            "LEFT JOIN pg_attrdef d ON d.adrelid=a.attrelid AND d.adnum=a.attnum "
            "WHERE c.relnamespace='public'::regnamespace AND c.relname NOT LIKE 'psique_%' "
            "AND a.attnum>0 AND NOT a.attisdropped ORDER BY a.attrelid,a.attnum"),
            ("SELECT con.oid,pg_get_constraintdef(con.oid) FROM pg_constraint con "
            "JOIN pg_class c ON c.oid=con.conrelid WHERE c.relnamespace='public'::regnamespace "
            "AND c.relname NOT LIKE 'psique_%' ORDER BY con.oid"),
            ("SELECT * FROM pg_policies WHERE schemaname='public' AND tablename NOT LIKE 'psique_%' "
            "ORDER BY tablename,policyname"),
            ("SELECT p.oid,pg_get_functiondef(p.oid),p.proacl FROM pg_proc p "
            "WHERE p.pronamespace='public'::regnamespace AND p.proname NOT LIKE 'psique_%' ORDER BY p.oid"),
            ("SELECT t.oid,pg_get_triggerdef(t.oid) FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid "
            "LEFT JOIN pg_constraint fk ON fk.oid=t.tgconstraint "
            "LEFT JOIN pg_class child ON child.oid=fk.conrelid "
            "WHERE c.relnamespace='public'::regnamespace AND c.relname NOT LIKE 'psique_%' "
            # Adding the Purchase FK creates internal RI triggers on organizations.
            # Exclude precisely that new child's FK; verify it separately above.
            "AND (child.relname IS NULL OR child.relname <> 'psique_purchases') ORDER BY t.oid"),
            "SELECT * FROM organization_wallets ORDER BY organization_id",
            "SELECT * FROM credit_ledger ORDER BY id",
        ]
        return [conn.execute(query).fetchall() for query in queries]


@unittest.skipUnless(DSN, "requires an explicit disposable Psique database")
class CatalogPostgresTests(MigrationPostgresTests):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        apply(cls.conn, MIGRATIONS, FINAL, cls.database)

    # The migration scenario belongs only to the fresh-database class.
    test_explicit_migrations_preserve_legacy_and_reads_never_apply = None

    def setUp(self):
        self.transaction = self.conn.transaction(force_rollback=True)
        self.transaction.__enter__()
        self.addCleanup(self.transaction.__exit__, None, None, None)
        self.config = load_config()
        self.table_id = install_draft(self.conn, self.config, actor="TEST operator")

    def assert_sql_rejected(self, sql, params=(), error=None):
        with self.assertRaises(error or self.pg.Error), self.conn.transaction():
            self.conn.execute(sql, params)

    def mapping(self):
        metadata = {"froid_product": "psique", "family": "psique_credits",
                    "product_code": "FROID_PRO_25", "credits": "25", "pricing_version": "2.1",
                    "pricing_hash": pricing_hash(self.config)}
        product = {"id": "prod_SYNTHETIC", "livemode": False, "active": True, "metadata": metadata}
        price = {"id": "price_SYNTHETIC", "product": product["id"], "livemode": False,
                 "active": True, "currency": "brl", "unit_amount": 46900,
                 "type": "one_time", "billing_scheme": "per_unit", "recurring": None,
                 "metadata": metadata}
        return {"version": "2.1", "product_code": "FROID_PRO_25", "account_id": "acct_SYNTHETIC",
                    "product": product, "price": price, "actor": "TEST operator"}

    def create_purchase(self, org_type="solo", **overrides):
        mapping_id = register_test_mapping(self.conn, **self.mapping())
        org = uuid.uuid4()
        self.conn.execute("INSERT INTO organizations(id,organization_type,legal_name,display_name) "
                          "VALUES(%s,%s,'TEST only','TEST only')", (org, org_type))
        offer_id = self.conn.execute("SELECT id FROM psique_pricing_offers WHERE pricing_table_id=%s "
                                     "AND product_code='FROID_PRO_25'", (self.table_id,)).fetchone()[0]
        values = {"organization_id": org, "offer_id": offer_id, "pricing_table_id": self.table_id,
                      "mapping_id": mapping_id, "product_code": "FROID_PRO_25", "pricing_version": "2.1",
                      "pricing_hash": pricing_hash(self.config), "currency": "brl", "credits": 25,
                      "total_cents": 46900, "stripe_account_id": "acct_SYNTHETIC", "livemode": False,
                      "idempotency_key": uuid.uuid4().hex, "created_by": "TEST operator"}
        values.update(overrides)
        query = self.pg.sql.SQL("INSERT INTO psique_purchases ({}) VALUES ({}) RETURNING id").format(
            self.pg.sql.SQL(",").join(map(self.pg.sql.Identifier, values)),
            self.pg.sql.SQL(",").join(self.pg.sql.Placeholder() for _ in values))
        return self.conn.execute(query, list(values.values())).fetchone()[0]

    def test_catalog_install_is_idempotent_and_draft_is_not_effective(self):
        self.assertEqual(install_draft(self.conn, self.config, actor="TEST retry"), self.table_id)
        self.assertEqual(self.conn.execute("SELECT count(*) FROM psique_pricing_tables").fetchone()[0], 1)
        self.assertEqual(self.conn.execute("SELECT count(*) FROM psique_pricing_offers").fetchone()[0], 8)
        self.assertEqual(read_catalog(self.conn, version="2.1", include_draft=True)["code"], "FROID_PSIQUE_V2")
        with self.assertRaisesRegex(PricingError, "pricing_not_effective"):
            read_catalog(self.conn, version="2.1")
        with self.assertRaisesRegex(PricingError, "pricing_version_not_found"):
            read_catalog(self.conn, version="absent", include_draft=True)

    def test_existing_version_cannot_change_prices(self):
        changed = copy.deepcopy(self.config)
        changed["offers"][0]["total_cents"] += 1
        with self.assertRaisesRegex(PricingError, "different_content"):
            install_draft(self.conn, changed, actor="TEST")
        self.assert_sql_rejected("UPDATE psique_pricing_offers SET total_cents=1")
        self.assert_sql_rejected("UPDATE psique_pricing_tables SET config_hash=repeat('a',64)")
        self.assert_sql_rejected("DELETE FROM psique_pricing_tables")

    def test_database_rejects_wrong_hash_and_unmatched_offer(self):
        self.assert_sql_rejected(
            "INSERT INTO psique_pricing_tables(code,version,currency,canonical_json,config_hash,created_by) "
            "SELECT code,'bad','brl',canonical_json,repeat('a',64),'TEST' FROM psique_pricing_tables",
            error=self.pg.errors.CheckViolation)
        self.assert_sql_rejected(
            "INSERT INTO psique_pricing_offers(pricing_table_id,product_code,name,credits,total_cents,"
            "billing_type,active,public) VALUES(%s,'FROID_FAKE','FAKE',1000,1,'one_time',true,false)",
            (self.table_id,))

    def test_published_validity_cannot_be_rewritten_by_returning_to_draft(self):
        self.conn.execute("UPDATE psique_pricing_tables SET status='active',valid_from=now()")
        self.assert_sql_rejected("UPDATE psique_pricing_tables SET status='draft'")
        self.assert_sql_rejected("UPDATE psique_pricing_tables SET valid_from=now()+interval '1 day'")
        self.conn.execute("UPDATE psique_pricing_tables SET status='inactive'")
        with self.assertRaisesRegex(PricingError, "pricing_not_effective"):
            read_catalog(self.conn, version="2.1", include_draft=True)

    def test_mapping_is_idempotent_and_live_price_or_wrong_metadata_is_refused(self):
        kwargs = self.mapping()
        mapping_id = register_test_mapping(self.conn, **kwargs)
        self.assertEqual(register_test_mapping(self.conn, **kwargs), mapping_id)
        for obj, key, value in (("price", "livemode", True), ("product", "livemode", True),
                                ("price", "unit_amount", 1), ("price", "currency", "usd"),
                                ("price", "active", False), ("price", "metadata", {})):
            changed = copy.deepcopy(kwargs)
            changed[obj][key] = value
            with self.subTest(obj=obj, key=key), self.assertRaises(PricingError):
                register_test_mapping(self.conn, **changed)
        self.assert_sql_rejected("UPDATE psique_stripe_price_mappings SET stripe_price_id='price_OTHER'")
        self.assert_sql_rejected(
            "INSERT INTO psique_stripe_price_mappings(pricing_table_id,offer_id,stripe_account_id,livemode,"
            "stripe_product_id,stripe_price_id,verified_at,verified_by) SELECT pricing_table_id,offer_id,"
            "'acct_OTHER',true,stripe_product_id,'price_OTHER',now(),'TEST' FROM psique_stripe_price_mappings",
            error=self.pg.errors.CheckViolation)

    def test_purchase_snapshot_cannot_diverge_and_nr1_is_rejected(self):
        for overrides in ({"credits": 26}, {"total_cents": 1}, {"currency": "usd"},
                          {"pricing_hash": "a" * 64}, {"livemode": True},
                          {"stripe_checkout_session_id": "cs_live_SYNTHETIC"},
                          {"status": "paid"}, {"org_type": "enterprise"}, {"org_type": "legacy"}):
            with self.subTest(overrides=overrides), self.assertRaises(self.pg.Error), self.conn.transaction():
                self.create_purchase(**overrides)
        purchase = self.create_purchase()
        self.assert_sql_rejected("UPDATE psique_purchases SET credits=26 WHERE id=%s", (purchase,))
        self.assert_sql_rejected("DELETE FROM psique_purchases WHERE id=%s", (purchase,))
        self.assertEqual(self.conn.execute("SELECT count(*) FROM credit_ledger").fetchone()[0], 0)
        self.assertEqual(self.conn.execute("SELECT count(*) FROM organization_wallets").fetchone()[0], 0)

    def test_duplicate_checkout_and_idempotency_keys_are_blocked(self):
        purchase = self.create_purchase(stripe_checkout_session_id="cs_test_SYNTHETIC")
        org, key = self.conn.execute("SELECT organization_id,idempotency_key FROM psique_purchases "
                                     "WHERE id=%s", (purchase,)).fetchone()
        for overrides in ({"stripe_checkout_session_id": "cs_test_SYNTHETIC"},
                          {"organization_id": org, "idempotency_key": key}):
            with self.assertRaises(self.pg.errors.UniqueViolation), self.conn.transaction():
                self.create_purchase(**overrides)
        self.assert_sql_rejected("UPDATE psique_purchases SET stripe_checkout_session_id='cs_test_OTHER'")
        self.conn.execute("UPDATE psique_purchases SET status='canceled'")
        self.assert_sql_rejected("UPDATE psique_purchases SET status='prepared'")

    def test_runtime_cannot_read_or_mutate_phase1_tables_even_with_accidental_grant(self):
        self.create_purchase()
        tables = ("psique_pricing_tables", "psique_pricing_offers",
                  "psique_stripe_price_mappings", "psique_purchases")
        for table in tables:
            for privilege in ("SELECT", "INSERT", "UPDATE", "DELETE"):
                self.assertFalse(self.conn.execute("SELECT has_table_privilege('froid_runtime',%s,%s)",
                                                    (table, privilege)).fetchone()[0])
            with self.assertRaises(self.pg.errors.InsufficientPrivilege), self.conn.transaction():
                self.conn.execute("SET LOCAL ROLE froid_runtime")
                self.conn.execute(self.pg.sql.SQL("SELECT * FROM {}").format(self.pg.sql.Identifier(table)))
            # RLS denies rows even if someone later grants SELECT accidentally.
            with self.conn.transaction(force_rollback=True):
                self.conn.execute(self.pg.sql.SQL("GRANT SELECT ON {} TO froid_runtime").format(
                    self.pg.sql.Identifier(table)))
                self.conn.execute("SET LOCAL ROLE froid_runtime")
                self.assertEqual(self.conn.execute(self.pg.sql.SQL("SELECT * FROM {}").format(
                    self.pg.sql.Identifier(table))).fetchall(), [])


if __name__ == "__main__":
    unittest.main()
