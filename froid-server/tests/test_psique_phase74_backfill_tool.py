"""Fase 7.4, etapa 1: ferramenta de conversao em massa V1 -> V2.

O agrupamento por organizacao e testado puro (sem banco). A conversao roda o
main() da ferramenta contra PostgreSQL real descartavel, com organizacoes cujo
id vem da MESMA regra do espelho dual (organization_id_for_profile), para provar
que o JSON e o banco se encontram na mesma organizacao.
"""

import json
import sys
import uuid
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tenant_store import organization_id_for_profile
from tools import psique_v2_backfill as ferramenta
from tools.migrate_schema import apply

CNPJ = "12.345.678/0001-90"


def _estado():
    return {"professional_profiles": {
        "ana@clinica.test": {"account_type": "organization", "organization_document": CNPJ,
                             "remaining_sessions": 4, "session_credit_purchases": [],
                             "pending_settlement_session_ids": ["s-1"]},
        "bia@clinica.test": {"account_type": "organization", "organization_document": CNPJ,
                             "remaining_sessions": 6, "session_credit_purchases": [{"id": "p"}],
                             "pending_settlement_session_ids": ["s-1", "s-2"]},
        "solo@autonomo.test": {"account_type": "individual", "remaining_sessions": -3},
    }}


def _org(email, account_type="individual", doc=None):
    return str(organization_id_for_profile(email, account_type, doc))


def test_planejar_agrupa_clinica_por_cnpj_e_soma():
    planos = ferramenta.planejar(_estado())
    clinica = planos[_org("ana@clinica.test", "organization", CNPJ)]
    assert clinica["net"] == 10
    assert clinica["ever_purchased"] is True
    assert clinica["pendencias"] == ["s-1", "s-2"]
    assert sorted(clinica["profissionais"]) == ["ana@clinica.test", "bia@clinica.test"]
    solo = planos[_org("solo@autonomo.test")]
    assert solo["net"] == 0 and solo["ever_purchased"] is False


def test_aplicar_sem_alvo_e_recusado(monkeypatch, tmp_path):
    caminho = tmp_path / "estado.json"
    caminho.write_text(json.dumps(_estado()), encoding="utf-8")
    monkeypatch.setenv(ferramenta.ENV_DSN, "dbname=x host=127.0.0.1")
    with pytest.raises(SystemExit, match="ALVO_OBRIGATORIO"):
        ferramenta.main(["--estado", str(caminho), "--confirm-database", "x", "--aplicar"])


@pytest.fixture(scope="module")
def database():
    import os

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
            yield isolated, name
        finally:
            admin.execute(psycopg.sql.SQL("DROP DATABASE {} WITH (FORCE)").format(psycopg.sql.Identifier(name)))


def _sql(dsn, query, params=()):
    import psycopg

    with psycopg.connect(dsn, autocommit=True) as conn:
        cur = conn.execute(query, params)
        return cur.fetchall() if cur.description else []


def _semear_org(dsn, org_id, owner_email, *, carteira=None, pool=0):
    user = str(uuid.uuid4())
    member = str(uuid.uuid4())
    _sql(dsn, "INSERT INTO organizations(id,organization_type,legal_name,display_name) "
              "VALUES(%s,'clinic','SYNTHETIC','SYNTHETIC')", (org_id,))
    _sql(dsn, "INSERT INTO users(id,email) VALUES(%s,%s)", (user, owner_email))
    _sql(dsn, "INSERT INTO organization_memberships(id,organization_id,user_id) VALUES(%s,%s,%s)",
         (member, org_id, user))
    _sql(dsn, "INSERT INTO membership_roles(membership_id,role) VALUES(%s,'owner')", (member,))
    if carteira == "v1":
        _sql(dsn, "INSERT INTO organization_wallets(organization_id,balance,credit_model) "
                  "VALUES(%s,%s,'v1')", (org_id, pool))
        _sql(dsn, "INSERT INTO credit_ledger(id,organization_id,delta,balance_after,event_type,"
                  "idempotency_key,actor_user_id) VALUES(gen_random_uuid(),%s,%s,%s,"
                  "'migration_opening',%s,%s)",
             (org_id, pool, pool, "legacy-opening-v1:" + user, user))


def _carteira(dsn, org_id):
    return _sql(dsn, "SELECT balance,credit_model,ever_purchased FROM organization_wallets "
                     "WHERE organization_id=%s", (org_id,))[0]


def test_converte_frota_pelo_json_e_e_idempotente(database, monkeypatch, tmp_path, capsys):
    dsn, name = database
    sufixo = uuid.uuid4().hex[:8]
    doc = str(uuid.uuid4().int)[:14]
    estado = {"professional_profiles": {
        f"ana-{sufixo}@c.test": {"account_type": "organization", "organization_document": doc,
                                 "remaining_sessions": 4, "session_credit_purchases": [],
                                 "pending_settlement_session_ids": [f"s1-{sufixo}"]},
        f"bia-{sufixo}@c.test": {"account_type": "organization", "organization_document": doc,
                                 "remaining_sessions": 6,
                                 "session_credit_purchases": [{"id": "p"}]},
        f"semcarteira-{sufixo}@c.test": {"account_type": "individual", "remaining_sessions": 2},
    }}
    clinica = _org(f"ana-{sufixo}@c.test", "organization", doc)
    sem_carteira = _org(f"semcarteira-{sufixo}@c.test")
    # Pool velho (3) diverge do JSON (10): a verdade e o JSON.
    _semear_org(dsn, clinica, f"dono-{sufixo}@c.test", carteira="v1", pool=3)
    _semear_org(dsn, sem_carteira, f"semcarteira-{sufixo}@c.test")

    caminho = tmp_path / "estado.json"
    caminho.write_text(json.dumps(estado), encoding="utf-8")
    monkeypatch.setenv(ferramenta.ENV_DSN, dsn)
    base = ["--estado", str(caminho), "--confirm-database", name]

    assert ferramenta.main(base) == 0
    ensaio = capsys.readouterr().out
    assert "ENSAIO" in ensaio and _carteira(dsn, clinica)[1] == "v1"

    assert ferramenta.main(base + ["--todas", "--aplicar"]) == 0
    saida = capsys.readouterr().out
    assert '"PULAR_SEM_CARTEIRA": 1' in saida
    assert _carteira(dsn, clinica) == (10, "psique_v2", True)
    pendente = _sql(dsn, "SELECT count(*) FROM credit_ledger WHERE organization_id=%s "
                         "AND event_type='SESSION_PENDING'", (clinica,))[0][0]
    assert pendente == 1

    # Reexecutar: a clinica aparece como JA_V2 e o saldo nao dobra.
    assert ferramenta.main(base + ["--todas", "--aplicar"]) == 0
    assert '"JA_V2": 1' in capsys.readouterr().out
    assert _carteira(dsn, clinica)[0] == 10
