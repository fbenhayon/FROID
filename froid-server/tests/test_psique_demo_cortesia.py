"""Ferramenta de cortesia de demonstracao: ensaio não escreve, aplicar concede
uma única vez pelo comando auditado, e nunca se passa por quem não é dono.

Fixtures 100% sintéticas; mesmo PostgreSQL descartável da Fase 2A.
"""

import json
import sys
import uuid
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from test_psique_phase2a import database  # noqa: F401 (fixture reutilizada)

from tools import psique_demo_cortesia


@pytest.fixture
def cenario(database, monkeypatch):  # noqa: F811
    import psycopg
    from psycopg.conninfo import conninfo_to_dict

    monkeypatch.setenv(psique_demo_cortesia.ENV_DSN, database)
    dbname = conninfo_to_dict(database)["dbname"]

    org, user, member = str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4())
    email = f"dono-{user[:8]}@example.invalid"
    with psycopg.connect(database, autocommit=True) as conn:
        conn.execute("INSERT INTO organizations(id,organization_type,legal_name,display_name) "
                     "VALUES(%s,'clinic','SYNTHETIC demo','SYNTHETIC demo')", (org,))
        conn.execute("INSERT INTO users(id,email) VALUES(%s,%s)", (user, email))
        conn.execute("INSERT INTO organization_memberships(id,organization_id,user_id) "
                     "VALUES(%s,%s,%s)", (member, org, user))
        conn.execute("INSERT INTO membership_roles(membership_id,role) VALUES(%s,'owner')",
                     (member,))
    return {"org": org, "email": email, "dbname": dbname, "dsn": database}


def saldo(cenario):
    import psycopg

    with psycopg.connect(cenario["dsn"], autocommit=True) as conn:
        row = conn.execute("SELECT credit_model, balance FROM organization_wallets "
                           "WHERE organization_id=%s", (cenario["org"],)).fetchone()
    return row


def resultado(texto):
    marca = texto.index('"enroll"')
    return json.loads(texto[texto.rindex("{", 0, marca):])


def rodar(cenario, *extras):
    return psique_demo_cortesia.main([
        "--organizacao", cenario["org"], "--owner-email", cenario["email"],
        "--creditos", "500", "--motivo", "SYNTHETIC cortesia de demonstracao",
        "--confirm-database", cenario["dbname"], *extras])


def test_ensaio_nao_escreve_e_aplicar_concede_uma_unica_vez(cenario, capsys):
    assert rodar(cenario) == 0
    assert "ENSAIO" in capsys.readouterr().out
    assert saldo(cenario) is None  # ensaio: nem a carteira nasce

    assert rodar(cenario, "--aplicar") == 0
    primeira = resultado(capsys.readouterr().out)
    assert saldo(cenario) == ("psique_v2", 500)
    assert primeira["ajuste"]["applied"] is True

    # Reexecucao integral: idempotente pela chave derivada, saldo inalterado.
    assert rodar(cenario, "--aplicar") == 0
    segunda = resultado(capsys.readouterr().out)
    assert segunda["ajuste"]["applied"] is False
    assert saldo(cenario) == ("psique_v2", 500)


def test_dono_errado_banco_errado_e_debito_sao_recusados(cenario, capsys):
    with pytest.raises(SystemExit, match="DONO_ATIVO_NAO_ENCONTRADO"):
        psique_demo_cortesia.main([
            "--organizacao", cenario["org"], "--owner-email", "intruso@example.invalid",
            "--creditos", "500", "--motivo", "SYNTHETIC",
            "--confirm-database", cenario["dbname"], "--aplicar"])
    with pytest.raises(SystemExit, match="CONFIRMACAO_DIVERGE"):
        rodar(cenario, "--aplicar", "--confirm-database", "outro_banco")
    with pytest.raises(SystemExit, match="CREDITOS_POSITIVOS"):
        psique_demo_cortesia.main([
            "--organizacao", cenario["org"], "--owner-email", cenario["email"],
            "--creditos", "-5", "--motivo", "SYNTHETIC",
            "--confirm-database", cenario["dbname"], "--aplicar"])
    assert saldo(cenario) is None


def test_dsn_ausente_falha_fechado(cenario, monkeypatch):
    monkeypatch.delenv(psique_demo_cortesia.ENV_DSN)
    with pytest.raises(SystemExit, match=psique_demo_cortesia.ENV_DSN):
        rodar(cenario, "--aplicar")
