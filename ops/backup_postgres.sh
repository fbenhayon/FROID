#!/bin/sh
set -eu

# Defaults to the existing Hetzner PostgreSQL container. Override the name for
# another homologation host without creating a second database service.
postgres_container=${FROID_POSTGRES_CONTAINER:-froid-postgres-1}
docker inspect "$postgres_container" >/dev/null

umask 077
mkdir -p backups/postgres
backup_name="froid-$(date -u +%Y%m%dT%H%M%SZ).dump"
temporary="backups/postgres/${backup_name}.partial"
final="backups/postgres/${backup_name}"

test ! -e "$temporary"
test ! -e "$final"

cleanup() {
  rm -f "$temporary"
}
trap cleanup EXIT INT TERM

docker exec "$postgres_container" sh -ceu \
  'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --format=custom --no-owner --no-acl' \
  > "$temporary"
test -s "$temporary"
docker exec -i "$postgres_container" pg_restore --list < "$temporary" >/dev/null
mv "$temporary" "$final"
sha256sum "$final" > "${final}.sha256"
trap - EXIT INT TERM

test -s "backups/postgres/$backup_name"
test -s "backups/postgres/$backup_name.sha256"
printf '%s\n' "Backup verified: backups/postgres/$backup_name"
