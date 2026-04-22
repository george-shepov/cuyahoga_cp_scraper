#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKUP_ROOT="${BACKUP_ROOT:-$ROOT_DIR/backups}"
STAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP_DIR="$BACKUP_ROOT/$STAMP"
mkdir -p "$BACKUP_DIR"

# Load environment for DB credentials.
if [[ -f "$ROOT_DIR/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT_DIR/.env"
  set +a
fi

POSTGRES_CONTAINER="${POSTGRES_CONTAINER:-cuyahoga_postgres}"
MONGODB_CONTAINER="${MONGODB_CONTAINER:-cuyahoga_mongodb}"
POSTGRES_DB="${POSTGRES_DB:-cuyahoga_cases}"
POSTGRES_USER="${POSTGRES_USER:-cuyahoga}"
POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-changeme}"
MONGO_USER="${MONGO_USER:-cuyahoga}"
MONGO_PASSWORD="${MONGO_PASSWORD:-changeme}"

# App data backup.
tar -czf "$BACKUP_DIR/out.tar.gz" -C "$ROOT_DIR" out || true
tar -czf "$BACKUP_DIR/logs.tar.gz" -C "$ROOT_DIR" logs || true

# PostgreSQL dump.
docker exec "$POSTGRES_CONTAINER" sh -c "PGPASSWORD=\"$POSTGRES_PASSWORD\" pg_dump -U \"$POSTGRES_USER\" \"$POSTGRES_DB\"" > "$BACKUP_DIR/postgres.sql"
gzip "$BACKUP_DIR/postgres.sql"

# MongoDB dump.
docker exec "$MONGODB_CONTAINER" sh -c "mongodump --username \"$MONGO_USER\" --password \"$MONGO_PASSWORD\" --authenticationDatabase admin --db cuyahoga_cases --archive" > "$BACKUP_DIR/mongodb.archive"
gzip "$BACKUP_DIR/mongodb.archive"

cat > "$BACKUP_DIR/manifest.txt" <<EOF
created_at=$STAMP
hostname=$(hostname)
files=$(ls -1 "$BACKUP_DIR" | wc -l)
EOF

echo "Backup complete: $BACKUP_DIR"
