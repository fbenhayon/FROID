# -*- coding: utf-8 -*-
"""O harness compartilhado das provas do Psique V2 contra PostgreSQL real.

Revisao de 20/10/2026, item 24: o mesmo banco descartavel, o mesmo contexto
de runtime e os mesmos fabricantes de organizacao, membro e paciente estavam
copiados em tres modulos (fase 4, supervisor, cota). Tres copias divergem em
silencio; aqui ha uma. Cada modulo estende `HarnessBase` com o que so ele
precisa.

Sem FROID_PSIQUE_TEST_DATABASE_URL os testes sao pulados — e isso aparece
como "s", nunca como verde. O banco de cada modulo e criado do zero ate a
migration pedida e destruido no fim.
"""

from __future__ import annotations

import os
import re
import secrets
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

ROOT = Path(__file__).resolve().parents[1]
MIGRACOES = ROOT / "migrations"

SP = ZoneInfo("America/Sao_Paulo")
BASE_START = datetime(2027, 3, 10, 14, 0, tzinfo=SP)  # quarta-feira, 14h em SP
BASE_DOW = (BASE_START.weekday() + 1) % 7  # DOW do PostgreSQL: domingo=0


def dsn() -> str:
    """O DSN administrativo do banco de prova, ou skip."""
    valor = os.environ.get("FROID_PSIQUE_TEST_DATABASE_URL", "")
    if not valor:
        pytest.skip("explicit disposable Psique database required")
    from psycopg.conninfo import conninfo_to_dict

    params = conninfo_to_dict(valor)
    assert params.get("host") in {"127.0.0.1", "localhost"}
    assert params.get("dbname", "").startswith("psique_v2_test_")
    return valor


def banco_descartavel(dsn_admin: str, through: str):
    """Gerador: cria um banco novo, aplica as migrations ate `through`,
    entrega (dsn_isolado, nome) e destroi o banco ao fim."""
    import psycopg
    from psycopg.conninfo import make_conninfo

    from tools.migrate_schema import apply

    name = "psique_v2_test_" + uuid.uuid4().hex
    with psycopg.connect(dsn_admin, autocommit=True) as admin:
        assert admin.execute("SELECT 1 FROM pg_roles WHERE rolname='froid_runtime'").fetchone()
        admin.execute(psycopg.sql.SQL("CREATE DATABASE {}").format(psycopg.sql.Identifier(name)))
        try:
            isolated = make_conninfo(dsn_admin, dbname=name)
            with psycopg.connect(isolated, autocommit=True) as conn:
                apply(conn, MIGRACOES, through, name)
            yield isolated, name
        finally:
            admin.execute(psycopg.sql.SQL("DROP DATABASE {} WITH (FORCE)").format(psycopg.sql.Identifier(name)))


def fixture_de_banco(through: str):
    """`database = fixture_de_banco("054_...")` no modulo: um banco por modulo."""

    @pytest.fixture(scope="module")
    def database():
        yield from banco_descartavel(dsn(), through)

    return database


def aplica_incremental_e_reaplicar_e_no_op(anterior: str, migracao: str) -> None:
    """A prova comum de toda migration: sobre um banco em `anterior`, aplicar
    ate `migracao` registra exatamente ela, e aplicar de novo nao faz nada."""
    import psycopg

    from tools.migrate_schema import apply

    gerador = banco_descartavel(dsn(), anterior)
    isolated, name = next(gerador)
    try:
        with psycopg.connect(isolated, autocommit=True) as conn:
            assert apply(conn, MIGRACOES, migracao, name) == [migracao]
            assert apply(conn, MIGRACOES, migracao, name) == []
            assert conn.execute(
                "SELECT count(*) FROM schema_migrations WHERE version=%s", (migracao,)
            ).fetchone()[0] == 1
    finally:
        try:
            next(gerador)
        except StopIteration:
            pass


# -- Espelho de funcoes entre migrations ----------------------------------------

def funcao_sql(texto: str, nome: str) -> str:
    """O CREATE [OR REPLACE] FUNCTION `nome` ... END $$; de um arquivo, com o
    prefixo normalizado para comparacao."""
    texto = texto.replace("\r\n", "\n")
    inicio = texto.index(f"FUNCTION {nome}(")
    inicio = texto.rindex("CREATE", 0, inicio)
    fim = texto.index("END $$;", inicio) + len("END $$;")
    return texto[inicio:fim].replace("CREATE FUNCTION", "CREATE OR REPLACE FUNCTION", 1)


def definicao_corrente(nome: str, antes_de: str) -> tuple[str, str]:
    """A ultima definicao de `nome` numa migration ANTERIOR a `antes_de`.

    Revisao de 20/10/2026, item 25: o espelho apontava fontes fixas (044 e
    045), e uma migration intermediaria que regravasse a funcao passaria
    despercebida. Devolve (stem da migration, texto da funcao)."""
    candidatas = sorted(p for p in MIGRACOES.glob("[0-9][0-9][0-9]_*.sql") if p.stem < antes_de)
    for caminho in reversed(candidatas):
        texto = caminho.read_text(encoding="utf-8")
        if re.search(rf"FUNCTION {re.escape(nome)}\(", texto):
            return caminho.stem, funcao_sql(texto, nome)
    raise LookupError(f"nenhuma migration antes de {antes_de} define {nome}")


# -- O harness -----------------------------------------------------------------

class HarnessBase:
    """Conexao de runtime (papel froid_runtime), os servicos do Psique e os
    fabricantes de organizacao, membro e paciente."""

    def __init__(self, dsn_isolado: str):
        import psycopg

        from psique_credits import PsiqueCredits
        from psique_identity import TrialKeyring
        from psique_rbac import PsiqueRbac
        from psique_scheduling import PsiqueScheduling

        self.pg = psycopg
        self.dsn = dsn_isolado
        self.materials: dict = {}
        self.factory = lambda: psycopg.connect(dsn_isolado, autocommit=True, options="-c role=froid_runtime")
        self.rbac = PsiqueRbac(self.factory)
        self.scheduling = PsiqueScheduling(self.factory)
        self.credits = PsiqueCredits(
            self.factory, identity_loader=lambda u: None,
            material_loader=lambda user, ref: self.materials[ref],
            keyring=TrialKeyring({"t": secrets.token_bytes(32)}, "t"))

    def sql(self, query, params=()):
        with self.pg.connect(self.dsn, autocommit=True) as conn:
            cursor = conn.execute(query, params)
            return cursor.fetchall() if cursor.description else []

    def organizacao(self, tipo: str = "clinic", nome: str = "SYNTHETIC org") -> str:
        org = str(uuid.uuid4())
        self.sql("INSERT INTO organizations(id,organization_type,legal_name,display_name) "
                 "VALUES(%s,%s,%s,%s)", (org, tipo, nome, nome))
        return org

    def member(self, org: str, *, v1_role: str = "professional"):
        from tenant_access import AccessContext

        user, membership = str(uuid.uuid4()), str(uuid.uuid4())
        self.sql("INSERT INTO users(id,email) VALUES(%s,%s)", (user, user + "@example.invalid"))
        self.sql("INSERT INTO organization_memberships(id,organization_id,user_id) VALUES(%s,%s,%s)",
                 (membership, org, user))
        self.sql("INSERT INTO membership_roles(membership_id,role) VALUES(%s,%s)", (membership, v1_role))
        return AccessContext.create(organization_id=org, membership_id=membership, user_id=user,
                                    roles=[v1_role], organization_type="clinic")

    def patient(self, org: str, nome: str = "SYNTHETIC PACIENTE") -> str:
        patient = str(uuid.uuid4())
        self.sql("INSERT INTO patients(id,organization_id,full_name,legacy_payload) "
                 "VALUES(%s,%s,%s,'{\"clinico\":\"SYNTHETIC\"}')", (patient, org, nome))
        return patient

    def clinico_disponivel(self, owner):
        """Um CLINICIAN com disponibilidade na quarta-feira de BASE_START."""
        clinician = self.member(owner.organization_id)
        self.rbac.grant_role(owner, clinician.membership_id, "CLINICIAN")
        self.scheduling.set_availability(
            owner, clinician_membership_id=clinician.membership_id, weekday=BASE_DOW,
            start_minute=8 * 60, end_minute=18 * 60, timezone_name="America/Sao_Paulo")
        return clinician

    def marcar(self, actor, clinician, patient, *, offset_minutes=0, minutes=50, idem=None):
        start = BASE_START + timedelta(minutes=offset_minutes)
        return self.scheduling.create_appointment(
            actor, patient_id=patient, clinician_membership_id=clinician.membership_id,
            start_at=start, end_at=start + timedelta(minutes=minutes),
            timezone_name="America/Sao_Paulo", idempotency_key=idem or uuid.uuid4().hex)
