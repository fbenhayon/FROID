#!/bin/sh
set -eu

if [ "$#" -ne 1 ]; then
  printf '%s\n' "Usage: $0 /absolute/path/froid-state-*.tar.gz.enc" >&2
  exit 2
fi
: "${FROID_BACKUP_ENCRYPTION_PASSPHRASE:?backup encryption passphrase is required}"
: "${FROID_BACKUP_INTEGRITY_KEY:?backup integrity key is required}"

encrypted=$1
test -f "$encrypted"
test -f "$encrypted.sha256"
test -f "$encrypted.hmac"

expected_hmac=$(cat "$encrypted.hmac")
actual_hmac=$(openssl dgst -sha256 -hmac "$FROID_BACKUP_INTEGRITY_KEY" "$encrypted" | awk '{print $NF}')
test -n "$expected_hmac"
test "$actual_hmac" = "$expected_hmac"
expected_sha256=$(cat "$encrypted.sha256")
actual_sha256=$(sha256sum "$encrypted" | awk '{print $1}')
test -n "$expected_sha256"
test "$actual_sha256" = "$expected_sha256"

umask 077
work=$(mktemp -d /tmp/froid-backup-verify.XXXXXX)
cleanup() { rm -rf "$work"; }
trap cleanup EXIT INT TERM

openssl enc -d -aes-256-cbc -pbkdf2 -iter 250000 \
  -in "$encrypted" -out "$work/bundle.tar.gz" \
  -pass env:FROID_BACKUP_ENCRYPTION_PASSPHRASE
tar -xzf "$work/bundle.tar.gz" -C "$work"
test -s "$work/postgres-legacy.dump"
test -s "$work/postgres-tenant.dump"
test -s "$work/application-data.tar.gz"
test -s "$work/deployment.env"
test -s "$work/manifest.txt"
docker exec -i "${FROID_POSTGRES_CONTAINER:-froid-postgres-1}" pg_restore --list \
  < "$work/postgres-legacy.dump" >/dev/null
docker exec -i "${FROID_POSTGRES_CONTAINER:-froid-postgres-1}" pg_restore --list \
  < "$work/postgres-tenant.dump" >/dev/null
tar -tzf "$work/application-data.tar.gz" >/dev/null

printf '%s\n' "FROID encrypted backup integrity and contents: OK"
