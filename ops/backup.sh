#!/usr/bin/env bash
# Backup criptografado do estado do FROID (dados de aplicação + Postgres).
#
# Uso (no servidor Hetzner, dentro de ~/froid-project):
#   FROID_BACKUP_PASSPHRASE='uma-senha-forte' ops/backup.sh
#
# Recomendado via cron diário (ver docs/comandos-hetzner). O arquivo gerado é
# cifrado com AES-256 (openssl) — só pode ser restaurado com a mesma senha.
#
# Restauração:
#   openssl enc -d -aes-256-cbc -pbkdf2 -in ARQUIVO.tar.gz.enc \
#     -pass pass:"$FROID_BACKUP_PASSPHRASE" | tar xz -C /destino
set -euo pipefail

PROJECT_DIR="${FROID_PROJECT_DIR:-$HOME/froid-project}"
DATA_DIR="${FROID_DATA_DIR:-$PROJECT_DIR/data}"
OUT_DIR="${FROID_BACKUP_DIR:-$HOME/froid-backups}"
KEEP_DAYS="${FROID_BACKUP_KEEP_DAYS:-14}"
STAMP="$(date +%Y%m%d-%H%M%S)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

if [ -z "${FROID_BACKUP_PASSPHRASE:-}" ]; then
  echo "ERRO: defina FROID_BACKUP_PASSPHRASE (senha de criptografia do backup)." >&2
  exit 1
fi

mkdir -p "$OUT_DIR"

# 1) Estado de aplicação (relatórios, identidade, DuckDB, Chroma, uploads).
if [ -d "$DATA_DIR" ]; then
  echo "Copiando dados de aplicação..."
  cp -a "$DATA_DIR" "$TMP/data"
fi

# 2) Dump do Postgres (apenas se o serviço multitenant estiver ativo).
if docker compose -f "$PROJECT_DIR/docker-compose.yml" ps --services 2>/dev/null | grep -q '^froid-postgres$'; then
  if docker compose -f "$PROJECT_DIR/docker-compose.yml" ps froid-postgres 2>/dev/null | grep -q 'Up'; then
    echo "Gerando dump do Postgres..."
    docker compose -f "$PROJECT_DIR/docker-compose.yml" exec -T froid-postgres \
      sh -c 'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' > "$TMP/postgres.sql" || \
      echo "AVISO: falha no dump do Postgres (seguindo com o restante)."
  fi
fi

# 3) Empacota e cifra (AES-256, PBKDF2).
ARCHIVE="$OUT_DIR/froid-backup-$STAMP.tar.gz.enc"
tar czf - -C "$TMP" . | \
  openssl enc -aes-256-cbc -pbkdf2 -salt -pass pass:"$FROID_BACKUP_PASSPHRASE" \
  -out "$ARCHIVE"
chmod 600 "$ARCHIVE"
echo "Backup criado: $ARCHIVE"

# 4) Retenção local: remove backups mais antigos que KEEP_DAYS.
find "$OUT_DIR" -name 'froid-backup-*.tar.gz.enc' -mtime "+$KEEP_DAYS" -delete 2>/dev/null || true

# 5) (Opcional) Envio off-site. Configure FROID_OFFSITE_DEST como destino rsync
#    (ex.: Hetzner Storage Box: u123456@u123456.your-storagebox.de:backups/).
if [ -n "${FROID_OFFSITE_DEST:-}" ]; then
  echo "Enviando off-site para $FROID_OFFSITE_DEST ..."
  rsync -a "$ARCHIVE" "$FROID_OFFSITE_DEST" && echo "Off-site OK." || \
    echo "AVISO: envio off-site falhou."
fi

echo "Concluído."
