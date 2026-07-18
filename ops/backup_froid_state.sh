#!/bin/sh
set -eu

project_root=${FROID_PROJECT_ROOT:-/root/froid-project}
destination=${FROID_BACKUP_DIR:-/root/froid-backups/automatic}
postgres_container=${FROID_POSTGRES_CONTAINER:-froid-postgres-1}
tenant_database=${FROID_BACKUP_POSTGRES_DATABASE:-froid_homologacao}
retention_days=${FROID_BACKUP_RETENTION_DAYS:-30}

case "$destination" in
  /*) ;;
  *) printf '%s\n' "FROID_BACKUP_DIR must be absolute" >&2; exit 2 ;;
esac
if [ "$destination" = "/" ] || [ ${#destination} -lt 12 ]; then
  printf '%s\n' "FROID_BACKUP_DIR is unsafe" >&2
  exit 2
fi
case "$retention_days" in
  ''|*[!0-9]*) printf '%s\n' "Invalid retention days" >&2; exit 2 ;;
esac

: "${FROID_BACKUP_ENCRYPTION_PASSPHRASE:?backup encryption passphrase is required}"
: "${FROID_BACKUP_INTEGRITY_KEY:?backup integrity key is required}"

test -d "$project_root/data"
test -f "$project_root/.env"
docker inspect "$postgres_container" >/dev/null

umask 077
mkdir -p "$destination"
lock_dir="$destination/.backup.lock"
if ! mkdir "$lock_dir" 2>/dev/null; then
  printf '%s\n' "Another FROID backup is already running" >&2
  exit 1
fi

stamp=$(date -u +%Y%m%dT%H%M%SZ)
name="froid-state-$stamp"
work="$destination/.partial-$name-$$"
raw="$work/raw"
encrypted_partial="$work/$name.tar.gz.enc"
encrypted_final="$destination/$name.tar.gz.enc"

cleanup() {
  rm -rf "$work"
  rmdir "$lock_dir" 2>/dev/null || true
}
trap cleanup EXIT INT TERM
mkdir -p "$raw"

legacy_database=$(docker exec "$postgres_container" printenv POSTGRES_DB)
test -n "$legacy_database"

docker exec -e BACKUP_DATABASE="$legacy_database" "$postgres_container" sh -ceu \
  'pg_dump -U "$POSTGRES_USER" -d "$BACKUP_DATABASE" --format=custom --no-owner --no-acl' \
  > "$raw/postgres-legacy.dump"
test -s "$raw/postgres-legacy.dump"
docker exec -i "$postgres_container" pg_restore --list \
  < "$raw/postgres-legacy.dump" >/dev/null

docker exec -e BACKUP_DATABASE="$tenant_database" "$postgres_container" sh -ceu \
  'pg_dump -U "$POSTGRES_USER" -d "$BACKUP_DATABASE" --format=custom --no-owner --no-acl' \
  > "$raw/postgres-tenant.dump"
test -s "$raw/postgres-tenant.dump"
docker exec -i "$postgres_container" pg_restore --list \
  < "$raw/postgres-tenant.dump" >/dev/null

tar -C "$project_root" -czf "$raw/application-data.tar.gz" data
test -s "$raw/application-data.tar.gz"
cp -p "$project_root/.env" "$raw/deployment.env"
chmod 600 "$raw/deployment.env"

{
  printf '%s\n' "created_at_utc=$stamp"
  printf '%s\n' "hostname=$(hostname)"
  printf '%s\n' "git_commit=$(git -C "$project_root" rev-parse HEAD 2>/dev/null || printf unknown)"
  printf '%s\n' "postgres_container=$postgres_container"
  printf '%s\n' "legacy_database=$legacy_database"
  printf '%s\n' "tenant_database=$tenant_database"
} > "$raw/manifest.txt"

tar -C "$raw" -czf "$work/$name.tar.gz" .
openssl enc -aes-256-cbc -pbkdf2 -iter 250000 -salt \
  -in "$work/$name.tar.gz" -out "$encrypted_partial" \
  -pass env:FROID_BACKUP_ENCRYPTION_PASSPHRASE
test -s "$encrypted_partial"
sha256sum "$encrypted_partial" | awk '{print $1}' > "$encrypted_partial.sha256"
openssl dgst -sha256 -hmac "$FROID_BACKUP_INTEGRITY_KEY" "$encrypted_partial" \
  | awk '{print $NF}' > "$encrypted_partial.hmac"
test -s "$encrypted_partial.sha256"
test -s "$encrypted_partial.hmac"

sh "$project_root/ops/verify_froid_state_backup.sh" "$encrypted_partial"

# Publish the verified payload last. Sidecars without a payload are harmless
# after an interrupted move; a visible .enc file is always fully verified.
mv "$encrypted_partial.sha256" "$encrypted_final.sha256"
mv "$encrypted_partial.hmac" "$encrypted_final.hmac"
mv "$encrypted_partial" "$encrypted_final"

find "$destination" -maxdepth 1 -type f \
  \( -name 'froid-state-*.tar.gz.enc' \
     -o -name 'froid-state-*.tar.gz.enc.sha256' \
     -o -name 'froid-state-*.tar.gz.enc.hmac' \) \
  -mtime "+$retention_days" -delete

trap - EXIT INT TERM
rm -rf "$work"
rmdir "$lock_dir"
printf '%s\n' "Encrypted FROID backup verified: $encrypted_final"
