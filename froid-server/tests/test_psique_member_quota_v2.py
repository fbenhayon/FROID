# -*- coding: utf-8 -*-
"""Cota por membro na cobranca V2 (migrations 052 e 054).

Regra do dono (18/10/2026): a sessao de um profissional so e recusada por
dois motivos — o limite que o responsavel lhe atribuiu, ou o esgotamento dos
creditos da clinica. Sem limite, consome do pool. Decisoes: sessao pendente
por falta de saldo CONTA na cota (aconteceu); pool esgotado segue pendente.

Decisao do dono (20/10/2026, revisao pre-fase 5, item 1): a cobranca NUNCA
recusa. A 052 levantava PSIQUE_MEMBER_QUOTA_EXHAUSTED ao arquivar, e a
politica A deixava o relatorio com credit_charge="falhou" para sempre — nem
debitava, nem contava, nem virava pendencia. Quem barra e o portao de inicio
(main._member_quota_block_detail); a sessao que aconteceu conta e debita
mesmo acima da cota. Os testes que afirmavam o RAISE foram reescritos para
a decisao nova.

Prova contra PostgreSQL real e descartavel (FROID_PSIQUE_TEST_DATABASE_URL),
como as fases do Psique. Sem o banco, os testes sao pulados — e isso aparece
como "s", nunca como verde.
"""

from __future__ import annotations

import re
import secrets
import sys
import uuid
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from psique_credits import PsiqueCredits  # noqa: E402
from psique_identity import TrialKeyring  # noqa: E402
from tenant_access import AccessContext  # noqa: E402
from tools.migrate_schema import apply  # noqa: E402

MIGRACAO = "054_cota_conta_e_paciente_do_clinico"
ANTERIOR = "053_psique_scheduling_supervisor"
COM_RAISE = "052_psique_member_quota_v2"


def _dsn():
    import os

    dsn = os.environ.get("FROID_PSIQUE_TEST_DATABASE_URL", "")
    if not dsn:
        pytest.skip("explicit disposable Psique database required")
    import psycopg
    from psycopg.conninfo import conninfo_to_dict

    params = conninfo_to_dict(dsn)
    assert params.get("host") in {"127.0.0.1", "localhost"}
    assert params.get("dbname", "").startswith("psique_v2_test_")
    return dsn


def _banco_descartavel(dsn, through):
    import psycopg
    from psycopg.conninfo import make_conninfo

    name = "psique_v2_test_" + uuid.uuid4().hex
    with psycopg.connect(dsn, autocommit=True) as admin:
        assert admin.execute("SELECT 1 FROM pg_roles WHERE rolname='froid_runtime'").fetchone()
        admin.execute(psycopg.sql.SQL("CREATE DATABASE {}").format(psycopg.sql.Identifier(name)))
        try:
            isolated = make_conninfo(dsn, dbname=name)
            with psycopg.connect(isolated, autocommit=True) as conn:
                apply(conn, ROOT / "migrations", through, name)
            yield isolated, name
        finally:
            admin.execute(psycopg.sql.SQL("DROP DATABASE {} WITH (FORCE)").format(psycopg.sql.Identifier(name)))


@pytest.fixture(scope="module")
def database():
    yield from _banco_descartavel(_dsn(), MIGRACAO)


class Harness:
    def __init__(self, dsn):
        import psycopg

        self.pg = psycopg
        self.dsn = dsn
        factory = lambda: psycopg.connect(dsn, autocommit=True, options="-c role=froid_runtime")
        self.credits = PsiqueCredits(
            factory, identity_loader=lambda user: None, material_loader=lambda user, ref: None,
            keyring=TrialKeyring({"test": secrets.token_bytes(32)}, "test"))

    def sql(self, query, params=()):
        with self.pg.connect(self.dsn, autocommit=True) as conn:
            cursor = conn.execute(query, params)
            return cursor.fetchall() if cursor.description else []

    def clinica(self, credits):
        org, user, member = str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4())
        self.sql("INSERT INTO organizations(id,organization_type,legal_name,display_name) "
                 "VALUES(%s,'clinic','SYNTHETIC test','SYNTHETIC test')", (org,))
        self.sql("INSERT INTO users(id,email) VALUES(%s,%s)", (user, user + "@example.invalid"))
        self.sql("INSERT INTO organization_memberships(id,organization_id,user_id) VALUES(%s,%s,%s)",
                 (member, org, user))
        self.sql("INSERT INTO membership_roles(membership_id,role) VALUES(%s,'owner')", (member,))
        dono = AccessContext.create(organization_id=org, membership_id=member, user_id=user,
                                    roles=["owner"], organization_type="clinic")
        self.credits.enroll_empty_wallet(dono)
        if credits:
            self.credits.manual_adjustment(dono, credits, reason="seed cortesia",
                                           idempotency_key="seed:" + uuid.uuid4().hex)
        return dono

    def profissional(self, dono):
        user, member = str(uuid.uuid4()), str(uuid.uuid4())
        self.sql("INSERT INTO users(id,email) VALUES(%s,%s)", (user, user + "@example.invalid"))
        self.sql("INSERT INTO organization_memberships(id,organization_id,user_id) VALUES(%s,%s,%s)",
                 (member, dono.organization_id, user))
        self.sql("INSERT INTO membership_roles(membership_id,role) VALUES(%s,'professional')", (member,))
        return AccessContext.create(organization_id=dono.organization_id, membership_id=member,
                                    user_id=user, roles=["professional"], organization_type="clinic")

    def cota(self, ctx, quota):
        self.sql("INSERT INTO organization_member_quotas(organization_id,membership_id,quota_sessions) "
                 "VALUES(%s,%s,%s)", (ctx.organization_id, ctx.membership_id, quota))

    def consumido(self, ctx):
        linhas = self.sql("SELECT consumed_sessions FROM organization_member_quotas "
                          "WHERE organization_id=%s AND membership_id=%s",
                          (ctx.organization_id, ctx.membership_id))
        return linhas[0][0] if linhas else None

    def saldo(self, dono):
        return self.sql("SELECT balance FROM organization_wallets WHERE organization_id=%s",
                        (dono.organization_id,))[0][0]

    def cobrar(self, ctx, sid):
        return self.credits.charge_session(ctx, sid)


@pytest.fixture
def harness(database):
    return Harness(database[0])


def _sid():
    return "s-" + uuid.uuid4().hex[:12]


# -- A regra ------------------------------------------------------------------

def test_a_sessao_acima_do_limite_conta_e_debita_sem_recusar(harness):
    """Decisao do dono (20/10/2026): a cobranca nunca recusa. Duas sessoes
    iniciadas com 1 restante (corrida), ou cota reduzida depois: a sessao
    aconteceu, entao conta na cota E debita o credito da clinica. Quem barra
    a proxima e o portao de inicio, que le consumed > quota."""
    dono = harness.clinica(10)
    prof = harness.profissional(dono)
    harness.cota(prof, 2)
    assert harness.cobrar(prof, _sid())["charged"] is True
    assert harness.cobrar(prof, _sid())["charged"] is True
    terceira = harness.cobrar(prof, _sid())
    assert terceira["charged"] is True and terceira["applied"] is True
    assert harness.consumido(prof) == 3
    assert harness.saldo(dono) == 7


def test_sem_limite_o_profissional_consome_do_pool(harness):
    dono = harness.clinica(3)
    prof = harness.profissional(dono)
    for _ in range(3):
        assert harness.cobrar(prof, _sid())["charged"] is True
    assert harness.consumido(prof) is None


def test_pool_esgotado_segue_pendente_e_a_pendencia_conta_na_cota(harness):
    dono = harness.clinica(0)
    prof = harness.profissional(dono)
    harness.cota(prof, 1)
    primeira = _sid()
    resultado = harness.cobrar(prof, primeira)
    assert resultado["charged"] is False and resultado["pending"] is True
    assert harness.consumido(prof) == 1
    # A segunda sessao, acima da cota e sem saldo: pendente e contada, nunca recusada.
    segunda = harness.cobrar(prof, _sid())
    assert segunda["charged"] is False and segunda["pending"] is True
    assert harness.consumido(prof) == 2
    # Credito chega: a FIFO da 050 liquida primeiro a OUTRA pendencia e so
    # depois a sessao atual; com dois creditos as duas liquidam, e nenhuma
    # conta de novo na cota.
    harness.credits.manual_adjustment(dono, 2, reason="seed", idempotency_key="seed:" + uuid.uuid4().hex)
    liquidada = harness.cobrar(prof, primeira)
    assert liquidada["charged"] is True and liquidada["settled_pending"] == 1
    assert harness.consumido(prof) == 2
    assert harness.saldo(dono) == 0


def test_a_mesma_sessao_conta_uma_vez(harness):
    dono = harness.clinica(5)
    prof = harness.profissional(dono)
    harness.cota(prof, 1)
    sid = _sid()
    assert harness.cobrar(prof, sid)["charged"] is True
    de_novo = harness.cobrar(prof, sid)
    assert de_novo["charged"] is True and de_novo["applied"] is False
    assert harness.consumido(prof) == 1


def test_a_cota_e_do_membro_nao_da_clinica(harness):
    dono = harness.clinica(10)
    limitado = harness.profissional(dono)
    livre = harness.profissional(dono)
    harness.cota(limitado, 1)
    assert harness.cobrar(limitado, _sid())["charged"] is True
    assert harness.cobrar(limitado, _sid())["charged"] is True
    assert harness.consumido(limitado) == 2
    assert harness.cobrar(livre, _sid())["charged"] is True
    assert harness.cobrar(livre, _sid())["charged"] is True
    assert harness.consumido(livre) is None


def test_o_portao_le_a_cota_do_membro_pelo_papel_de_runtime(harness):
    from froid_schema import PSIQUE_V2_VERSIONS
    from tenant_store import TenantStore

    assert MIGRACAO in PSIQUE_V2_VERSIONS  # o arranque nao aplica V2 sozinho
    store = TenantStore(mode="dual", database_url=harness.dsn,
                        migration_path=ROOT / "migrations" / "001_multitenant_foundation.sql",
                        runtime_database_url=harness.dsn)
    dono = harness.clinica(5)
    prof = harness.profissional(dono)
    assert store.member_quota(organization_id=prof.organization_id,
                              membership_id=prof.membership_id) is None
    harness.cota(prof, 2)
    harness.cobrar(prof, _sid())
    cota = store.member_quota(organization_id=prof.organization_id, membership_id=prof.membership_id)
    assert cota == {"quota_sessions": 2, "consumed_sessions": 1, "remaining": 1}
    # Acima da cota (a cobranca contou): o portao ve remaining 0, nunca negativo.
    harness.cobrar(prof, _sid())
    harness.cobrar(prof, _sid())
    cota = store.member_quota(organization_id=prof.organization_id, membership_id=prof.membership_id)
    assert cota == {"quota_sessions": 2, "consumed_sessions": 3, "remaining": 0}
    # Outro membro nao enxerga a cota alheia pela RLS do proprio contexto.
    outro = harness.profissional(dono)
    assert store.member_quota(organization_id=outro.organization_id,
                              membership_id=outro.membership_id) is None


def test_sem_dsn_de_runtime_a_leitura_levanta_em_vez_de_fingir_sem_cota(harness):
    """Padrao 2.11: None e "sem limite atribuido", so isso. Nao conseguir ler
    e outra causa, e levanta — o portao registra e decide."""
    from tenant_store import TenantStore

    store = TenantStore(mode="dual", database_url=harness.dsn,
                        migration_path=ROOT / "migrations" / "001_multitenant_foundation.sql",
                        runtime_database_url="")
    with pytest.raises(RuntimeError, match="member_quota_sem_dsn_de_runtime"):
        store.member_quota(organization_id=str(uuid.uuid4()), membership_id=str(uuid.uuid4()))


# -- A migration ----------------------------------------------------------------

def _funcao(texto, nome="psique_v2_session_charge"):
    inicio = texto.index(f"CREATE OR REPLACE FUNCTION {nome}(")
    return texto[inicio: texto.index("END $$;", inicio) + len("END $$;")].replace("\r\n", "\n")


def _sql(nome):
    return (ROOT / "migrations" / f"{nome}.sql").read_text(encoding="utf-8").replace("\r\n", "\n")


def test_a_052_e_a_050_byte_a_byte_mais_o_bloco_marcado():
    antiga = _funcao(_sql("050_psique_session_charge_fix"))
    nova = _funcao(_sql(COM_RAISE))
    sem_bloco = re.sub(r"    -- 052: cota por membro.*?    END IF;\n\n", "", nova, flags=re.DOTALL)
    sem_bloco = sem_bloco.replace("\n    quota_row organization_member_quotas%ROWTYPE; -- 052", "")
    assert sem_bloco == antiga


def test_a_054_e_a_052_byte_a_byte_sem_o_raise():
    """A unica diferenca entre a cobranca da 054 e a da 052 e o IF/RAISE
    trocado por comentario. Qualquer outra mudanca na funcao aparece aqui."""
    com_raise = _funcao(_sql(COM_RAISE))
    nova = _funcao(_sql(MIGRACAO))
    assert "PSIQUE_MEMBER_QUOTA_EXHAUSTED" not in nova
    assert "RAISE" not in nova.split("-- 052: cota por membro")[1].split("UPDATE organization_member_quotas")[0]
    esperado = com_raise.replace(
        "        IF quota_row.consumed_sessions + 1 > quota_row.quota_sessions THEN\n"
        "            RAISE EXCEPTION 'PSIQUE_MEMBER_QUOTA_EXHAUSTED' USING ERRCODE='P0001';\n"
        "        END IF;\n",
        "        -- 054: nao recusa. A sessao aconteceu: conta e debita mesmo acima da\n"
        "        -- cota (decisao do dono, 20/10/2026); quem barra e o portao de inicio.\n",
    )
    assert nova == esperado
    assert nova != com_raise  # o replace casou: o teste pode falhar


def test_aplica_incremental_sobre_a_053_e_reaplicar_e_no_op():
    import psycopg

    dsn = _dsn()
    gerador = _banco_descartavel(dsn, ANTERIOR)
    isolated, name = next(gerador)
    try:
        with psycopg.connect(isolated, autocommit=True) as conn:
            assert apply(conn, ROOT / "migrations", MIGRACAO, name) == [MIGRACAO]
            assert apply(conn, ROOT / "migrations", MIGRACAO, name) == []
            assert conn.execute(
                "SELECT count(*) FROM schema_migrations WHERE version=%s", (MIGRACAO,)
            ).fetchone()[0] == 1
    finally:
        try:
            next(gerador)
        except StopIteration:
            pass
