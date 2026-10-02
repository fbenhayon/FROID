"""Leitura do convite de equipe para a tela de aceite (GET publico).

Exercita tenant_store.member_invitation_details contra PostgreSQL real
descartavel: a tela de aceite usa isto para mostrar a clinica e o e-mail
convidado ANTES do login, sem resgatar nada. O aceite em si (com a trava de
e-mail) tem o seu proprio caminho e nao e tocado aqui.
"""

import hashlib
import json
import secrets
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tenant_store import TenantStore
from tools.migrate_schema import apply


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
            yield isolated
        finally:
            admin.execute(psycopg.sql.SQL("DROP DATABASE {} WITH (FORCE)").format(psycopg.sql.Identifier(name)))


def _store(dsn):
    return TenantStore(mode="dual", database_url=dsn,
                       migration_path=ROOT / "migrations" / "001_multitenant_foundation.sql",
                       runtime_database_url=dsn)


def _sql(dsn, query, params=()):
    import psycopg

    with psycopg.connect(dsn, autocommit=True) as conn:
        cursor = conn.execute(query, params)
        return cursor.fetchall() if cursor.description else []


def _seed_invitation(dsn, *, invited_email, roles, status="pending",
                     expires_delta_hours=72, clinic="Clinica Teste"):
    org = str(uuid.uuid4())
    user = str(uuid.uuid4())
    member = str(uuid.uuid4())
    token = secrets.token_urlsafe(16)
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    _sql(dsn, "INSERT INTO organizations(id,organization_type,legal_name,display_name) "
              "VALUES(%s,'clinic',%s,%s)", (org, clinic, clinic))
    _sql(dsn, "INSERT INTO users(id,email) VALUES(%s,%s)", (user, "owner-" + user + "@x.invalid"))
    _sql(dsn, "INSERT INTO organization_memberships(id,organization_id,user_id) VALUES(%s,%s,%s)",
         (member, org, user))
    expires = datetime.now(timezone.utc) + timedelta(hours=expires_delta_hours)
    _sql(dsn, "INSERT INTO membership_invitations(id,organization_id,invited_email,"
              "invited_by_membership_id,token_hash,requested_roles,status,expires_at) "
              "VALUES(%s,%s,%s,%s,%s,%s::jsonb,%s,%s)",
         (str(uuid.uuid4()), org, invited_email, member, token_hash,
          json.dumps(sorted(roles)), status, expires))
    return token_hash


def test_details_returns_clinic_and_invited_email(database):
    token_hash = _seed_invitation(database, invited_email="joao@x.com",
                                  roles=["professional"], clinic="Clinica Alfa")
    details = _store(database).member_invitation_details(token_hash=token_hash)
    assert details == {
        "invited_email": "joao@x.com",
        "roles": ["professional"],
        "status": "pending",
        "expired": False,
        "clinic_name": "Clinica Alfa",
    }


def test_details_marks_expired(database):
    token_hash = _seed_invitation(database, invited_email="ana@x.com",
                                  roles=["professional"], expires_delta_hours=-1)
    details = _store(database).member_invitation_details(token_hash=token_hash)
    assert details is not None
    assert details["expired"] is True and details["status"] == "pending"


def test_details_unknown_token_is_none(database):
    assert _store(database).member_invitation_details(token_hash="de" * 32) is None
