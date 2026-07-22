#!/bin/sh
set -eu

if [ "$#" -ne 1 ]; then
  printf '%s\n' "Usage: $0 /root/froid-backups/.../froid-*.dump" >&2
  exit 2
fi

postgres_container=${FROID_POSTGRES_CONTAINER:-froid-postgres-1}
project_root=${FROID_PROJECT_ROOT:-/root/froid-project}
docker inspect "$postgres_container" >/dev/null

backup_path=$(readlink -f "$1")
case "$backup_path" in
  "$project_root"/backups/postgres/*|/root/froid-backups/*) ;;
  *) printf '%s\n' "FROID backup is outside an allowed root" >&2; exit 2 ;;
esac
backup_name=$(basename "$backup_path")
case "$backup_name" in
  froid-[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]T[0-9][0-9][0-9][0-9][0-9][0-9]Z.dump|froid-homologacao.dump) ;;
  *) printf '%s\n' "Invalid FROID backup filename" >&2; exit 2 ;;
esac

test -s "$backup_path"
test -s "${backup_path}.sha256"
expected_sha256=$(awk 'NR==1 {print $1}' "${backup_path}.sha256")
actual_sha256=$(sha256sum "$backup_path" | awk '{print $1}')
test -n "$expected_sha256"
test "$actual_sha256" = "$expected_sha256"

restore_db="froid_restore_verify_$(date -u +%Y%m%d%H%M%S)_$$"
case "$restore_db" in
  froid_restore_verify_*) ;;
  *) printf '%s\n' "Invalid temporary database name" >&2; exit 2 ;;
esac

cleanup() {
  docker exec -e RESTORE_DB="$restore_db" "$postgres_container" sh -ceu \
    'dropdb -U "$POSTGRES_USER" --if-exists "$RESTORE_DB"' \
    >/dev/null 2>&1 || true
}
trap cleanup EXIT INT TERM

docker exec -e RESTORE_DB="$restore_db" "$postgres_container" sh -ceu \
  'createdb -U "$POSTGRES_USER" "$RESTORE_DB"'
docker exec -i -e RESTORE_DB="$restore_db" "$postgres_container" sh -ceu \
  'pg_restore -U "$POSTGRES_USER" -d "$RESTORE_DB" --no-owner --no-acl --exit-on-error' \
  < "$backup_path"

docker exec -i -e RESTORE_DB="$restore_db" "$postgres_container" sh -ceu \
  'psql -U "$POSTGRES_USER" -d "$RESTORE_DB" -v ON_ERROR_STOP=1' <<'SQL'
DO $$
DECLARE migration_count integer; rls_count integer;
BEGIN
  SELECT count(*) INTO migration_count FROM schema_migrations
  WHERE version IN (
    '001_multitenant_foundation', '002_access_control',
    '003_runtime_role_grants', '004_shared_credit_wallet',
    '005_wallet_activation_safety', '006_subscription_entitlements',
    '007_multitenant_security_hardening', '008_data_subject_rights',
    '009_legal_acceptance_ledger'
  );
  IF migration_count <> 9 THEN
    RAISE EXCEPTION 'restore missing required migrations: %', migration_count;
  END IF;
  SELECT count(*) INTO rls_count FROM pg_class
  WHERE relnamespace='public'::regnamespace AND relname IN (
    'organization_memberships', 'patients', 'patient_assignments',
    'session_reports', 'consents', 'organization_wallets',
    'credit_ledger', 'audit_events', 'organization_subscriptions',
    'data_subject_requests', 'data_subject_request_events',
    'legal_acceptance_events'
  ) AND relrowsecurity;
  IF rls_count <> 12 THEN
    RAISE EXCEPTION 'restore RLS check failed: %', rls_count;
  END IF;
END $$;
SQL

printf '%s\n' "Temporary restore verified: $restore_db"
