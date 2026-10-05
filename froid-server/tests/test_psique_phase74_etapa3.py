"""Fase 7.4, etapa 3: conta nova nasce no V2 e portao V2 de inicio de sessao.

Duas partes:
- regras puras de main (quando a conta pode nascer no V2, que identidade vale
  como prova, e o portao que nunca bloqueia por falha de leitura);
- a cadeia real contra PostgreSQL descartavel: carteira no formato que o espelho
  cria para conta nova (v1, saldo 0, migration_opening de 0) -> backfill(net=0)
  -> GRANT_TRIAL -> 10 creditos; e o sinal "ja comprou" do portao.
"""

import base64
import os
import secrets
import sys
import uuid
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import main  # noqa: E402
from psique_credits import PsiqueCredits  # noqa: E402
from psique_identity import TrialIdentity, TrialKeyring  # noqa: E402
from tenant_access import AccessContext  # noqa: E402
from tenant_store import TenantStore  # noqa: E402
from tools.migrate_schema import apply  # noqa: E402


# -- Regras puras ---------------------------------------------------------------

class _Store:
    enabled = True

    def __init__(self, ja_comprou=lambda _org: False):
        self.psique_v2_ever_purchased = ja_comprou


def _ligar(monkeypatch, *, chave=True):
    monkeypatch.setattr(main, "FROID_PSIQUE_V2_NEW_ACCOUNTS", True)
    monkeypatch.setattr(main, "FROID_PSIQUE_V2_BILLING_ENABLED", True)
    monkeypatch.setattr(main, "TENANT_STORE", _Store())
    monkeypatch.setenv("FROID_RUNTIME_DATABASE_URL", "host=127.0.0.1 dbname=x")
    if chave:
        monkeypatch.setenv("FROID_PSIQUE_TRIAL_HMAC_KEYS",
                           '{"v1": "%s"}' % base64.b64encode(b"k" * 32).decode())
        monkeypatch.setenv("FROID_PSIQUE_TRIAL_HMAC_ACTIVE_VERSION", "v1")
    else:
        monkeypatch.delenv("FROID_PSIQUE_TRIAL_HMAC_KEYS", raising=False)
        monkeypatch.delenv("FROID_PSIQUE_TRIAL_HMAC_ACTIVE_VERSION", raising=False)


def test_identidade_google_vale_e_senha_so_verificada(monkeypatch):
    monkeypatch.setattr(main, "PROFESSIONAL_CREDENTIALS", {
        "ok@x.test": {"email_verified": True, "verified_via": "clinic_invitation"},
        "nao@x.test": {"email_verified": False},
    })
    google = main._psique_v2_identidade_para_trial({"provider": "google"}, "g@x.test")
    assert google.verification_ref == "google-login" and google.legacy_history_checked
    senha = main._psique_v2_identidade_para_trial({"provider": "password"}, "ok@x.test")
    assert senha.verification_ref == "password-clinic_invitation"
    assert main._psique_v2_identidade_para_trial({"provider": "password"}, "nao@x.test") is None
    assert main._psique_v2_identidade_para_trial({"provider": "local"}, "l@x.test") is None


def test_conta_nova_so_nasce_v2_com_tudo_pronto(monkeypatch):
    monkeypatch.setattr(main, "PROFESSIONAL_PROFILES", {})
    google = {"provider": "google"}
    _ligar(monkeypatch)
    assert main._psique_v2_conta_nova_pode_nascer(google, "novo@x.test", "individual", None)
    monkeypatch.setattr(main, "FROID_PSIQUE_V2_NEW_ACCOUNTS", False)
    assert not main._psique_v2_conta_nova_pode_nascer(google, "novo@x.test", "individual", None)
    _ligar(monkeypatch, chave=False)
    assert not main._psique_v2_conta_nova_pode_nascer(google, "novo@x.test", "individual", None)


def test_clinica_que_ja_existe_pelo_cnpj_fica_no_v1(monkeypatch):
    _ligar(monkeypatch)
    cnpj = "12345678000190"
    monkeypatch.setattr(main, "PROFESSIONAL_PROFILES", {
        "colega@clinica.test": {"account_type": "organization", "organization_document": cnpj},
    })
    google = {"provider": "google"}
    assert not main._psique_v2_conta_nova_pode_nascer(google, "nova@clinica.test", "organization", cnpj)
    assert main._psique_v2_conta_nova_pode_nascer(google, "nova@outra.test", "organization", "99999999000199")


def _contexto():
    return AccessContext.create(organization_id=str(uuid.uuid4()), membership_id=str(uuid.uuid4()),
                                user_id=str(uuid.uuid4()), roles=["professional"])


def test_portao_v2_libera_quem_tem_saldo_ou_ja_comprou_e_bloqueia_o_resto(monkeypatch):
    monkeypatch.setattr(main, "FROID_PSIQUE_V2_BILLING_ENABLED", True)
    monkeypatch.setattr(main, "_organization_uses_psique_v2", lambda _org: True)

    class Saldo:
        def __init__(self, disponivel):
            self.disponivel = disponivel

        def balance(self, _ctx):
            return {"available_balance": self.disponivel}

    comprou = {"v": False}
    monkeypatch.setattr(main, "TENANT_STORE", _Store(lambda _org: comprou["v"]))
    monkeypatch.setattr(main, "_psique_session_charger", lambda: Saldo(3), raising=False)
    assert main._psique_v2_start_block_detail(_contexto()) == ""
    monkeypatch.setattr(main, "_psique_session_charger", lambda: Saldo(0), raising=False)
    assert main._psique_v2_start_block_detail(_contexto()) == main.PSIQUE_V2_TRIAL_BLOCK_DETAIL
    comprou["v"] = True
    assert main._psique_v2_start_block_detail(_contexto()) == ""


def test_portao_v2_nunca_bloqueia_por_falha_nem_org_v1(monkeypatch):
    monkeypatch.setattr(main, "FROID_PSIQUE_V2_BILLING_ENABLED", True)

    def quebra(_org):
        raise RuntimeError("banco fora")

    monkeypatch.setattr(main, "_organization_uses_psique_v2", lambda _org: True)
    monkeypatch.setattr(main, "TENANT_STORE", _Store(quebra))
    assert main._psique_v2_start_block_detail(_contexto()) == ""
    monkeypatch.setattr(main, "_organization_uses_psique_v2", lambda _org: False)
    assert main._psique_v2_start_block_detail(_contexto()) == ""
    assert main._psique_v2_start_block_detail(None) == ""


# -- Cadeia real contra PostgreSQL ------------------------------------------------

@pytest.fixture(scope="module")
def database():
    dsn = os.environ.get("FROID_PSIQUE_TEST_DATABASE_URL", "")
    if not dsn:
        pytest.skip("explicit disposable Psique database required")
    import psycopg
    from psycopg.conninfo import conninfo_to_dict, make_conninfo

    params = conninfo_to_dict(dsn)
    assert params.get("host") in {"127.0.0.1", "localhost"}
    assert params.get("dbname", "").startswith("psique_v2_test_")
    name = "psique_v2_test_" + uuid.uuid4().hex
    with psycopg.connect(dsn, autocommit=True) as admin:
        admin.execute(psycopg.sql.SQL("CREATE DATABASE {}").format(psycopg.sql.Identifier(name)))
        try:
            isolated = make_conninfo(dsn, dbname=name)
            with psycopg.connect(isolated, autocommit=True) as conn:
                apply(conn, ROOT / "migrations", "048_psique_v2_backfill", name)
            yield isolated
        finally:
            admin.execute(psycopg.sql.SQL("DROP DATABASE {} WITH (FORCE)").format(psycopg.sql.Identifier(name)))


def _sql(dsn, query, params=()):
    import psycopg

    with psycopg.connect(dsn, autocommit=True) as conn:
        cur = conn.execute(query, params)
        return cur.fetchall() if cur.description else []


def _conta_nova_como_o_espelho_cria(dsn):
    org, user, member = str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4())
    email = f"novo-{user[:8]}@x.test"
    _sql(dsn, "INSERT INTO organizations(id,organization_type,legal_name,display_name) "
              "VALUES(%s,'solo','SYNTHETIC','SYNTHETIC')", (org,))
    _sql(dsn, "INSERT INTO users(id,email) VALUES(%s,%s)", (user, email))
    _sql(dsn, "INSERT INTO organization_memberships(id,organization_id,user_id) VALUES(%s,%s,%s)",
         (member, org, user))
    _sql(dsn, "INSERT INTO membership_roles(membership_id,role) VALUES(%s,'owner')", (member,))
    _sql(dsn, "INSERT INTO organization_wallets(organization_id,balance) VALUES(%s,0)", (org,))
    _sql(dsn, "INSERT INTO credit_ledger(id,organization_id,delta,balance_after,event_type,"
              "idempotency_key,actor_user_id) VALUES(gen_random_uuid(),%s,0,0,'migration_opening',%s,%s)",
         (org, "legacy-opening-v1:" + user, user))
    ctx = AccessContext.create(organization_id=org, membership_id=member, user_id=user,
                               roles=["owner"], organization_type="solo")
    return ctx, email


def _servico(dsn, email):
    import psycopg
    from datetime import datetime, timezone

    identidade = TrialIdentity(email=email, verified_at=datetime.now(timezone.utc),
                               verification_ref="google-login", legacy_history_checked=True)
    return PsiqueCredits(lambda: psycopg.connect(dsn, autocommit=True, options="-c role=froid_runtime"),
                         identity_loader=lambda _u: identidade, material_loader=lambda *_a: None,
                         keyring=TrialKeyring({"v1": secrets.token_bytes(32)}, "v1"))


def test_conta_nova_vira_v2_com_10_creditos_de_teste(database):
    ctx, email = _conta_nova_como_o_espelho_cria(database)
    servico = _servico(database, email)
    conversao = servico.backfill_from_v1(ctx, 0, ever_purchased=False, note="conta nova")
    assert conversao["converted"] is True
    trial = servico.grant_trial(ctx)
    assert trial["granted"] is True
    saldo = servico.balance(ctx)
    assert saldo["available_balance"] == 10 and saldo["trial_status"] == "ACTIVE"
    modelo = _sql(database, "SELECT credit_model FROM organization_wallets WHERE organization_id=%s",
                  (ctx.organization_id,))[0][0]
    assert modelo == "psique_v2"
    # Trilha do espelho preservada.
    assert _sql(database, "SELECT count(*) FROM credit_ledger WHERE organization_id=%s "
                          "AND event_type='migration_opening'", (ctx.organization_id,))[0][0] == 1


def test_sinal_ja_comprou_do_portao(database):
    store = TenantStore(mode="dual", database_url=database,
                        migration_path=ROOT / "migrations" / "001_multitenant_foundation.sql",
                        runtime_database_url=database)
    nunca, email = _conta_nova_como_o_espelho_cria(database)
    _servico(database, email).backfill_from_v1(nunca, 0, ever_purchased=False)
    assert store.psique_v2_ever_purchased(nunca.organization_id) is False
    comprou, email2 = _conta_nova_como_o_espelho_cria(database)
    _servico(database, email2).backfill_from_v1(comprou, 3, ever_purchased=True)
    assert store.psique_v2_ever_purchased(comprou.organization_id) is True
