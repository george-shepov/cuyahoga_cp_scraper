#!/usr/bin/env bash
set -euo pipefail

# Create a dedicated Postgres database and role for the cuyahoga dataset.
# This will NOT modify the existing `legal_assistant` database.
# Usage example (you need a superuser with CREATE DATABASE privileges):
# PGPASSWORD=adminpw ./scripts/create_cuyahoga_db.sh --db cuyahoga_criminal_cases --owner cuy_user --owner-pw 'securepw'

HOST=${POSTGRES_HOST:-localhost}
PORT=${POSTGRES_PORT:-5432}
SUPERUSER=${PG_SUPERUSER:-postgres}
SUPERPW=${PGPASSWORD:-}

DB_NAME="${DB_NAME:-cuyahoga_criminal_cases}"
DB_OWNER="${DB_OWNER:-cuy_cases_user}"
DB_OWNER_PW="${DB_OWNER_PW:-password}"

usage(){
  cat <<EOF
Usage: PGPASSWORD=superpw $0 [--db name] [--owner name] [--owner-pw pw]
Environment:
  POSTGRES_HOST, POSTGRES_PORT, PGPASSWORD (or PGPASSWORD passed on command)
You must run this script with credentials for a Postgres user that can CREATE ROLE and CREATE DATABASE.
EOF
  exit 1
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --db) DB_NAME="$2"; shift 2;;
    --owner) DB_OWNER="$2"; shift 2;;
    --owner-pw) DB_OWNER_PW="$2"; shift 2;;
    -h|--help) usage;;
    *) echo "Unknown arg $1"; usage;;
  esac
done

if [ -z "$SUPERPW" ]; then
  echo "Warning: PGPASSWORD not set. You will be prompted for the superuser password by psql if required."
fi

PSQL_SUPER="psql -h $HOST -p $PORT -U $SUPERUSER -v ON_ERROR_STOP=1"

# 1) Create role if not exists (or update password)
echo "Ensuring role '$DB_OWNER' exists (or update password)"
$PSQL_SUPER -c "DO $$ BEGIN IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '${DB_OWNER}') THEN CREATE ROLE \"${DB_OWNER}\" LOGIN PASSWORD '${DB_OWNER_PW}'; ELSE ALTER ROLE \"${DB_OWNER}\" WITH LOGIN PASSWORD '${DB_OWNER_PW}'; END IF; END$$;"

# 2) Create database if not exists and set owner to the new role
echo "Ensuring database '$DB_NAME' exists and is owned by '$DB_OWNER'"
EXISTS=$($PSQL_SUPER -tAc "SELECT 1 FROM pg_database WHERE datname='${DB_NAME}'")
if [ "$EXISTS" = '1' ]; then
  echo "Database ${DB_NAME} already exists; skipping creation."
else
  $PSQL_SUPER -c "CREATE DATABASE \"${DB_NAME}\" OWNER \"${DB_OWNER}\";"
  echo "Database ${DB_NAME} created."
fi

# 3) Grant common privileges to owner (owner already has privileges by creation)
echo "Granting CONNECT to role ${DB_OWNER} (if needed)"
$PSQL_SUPER -d "$DB_NAME" -c "GRANT CONNECT ON DATABASE \"${DB_NAME}\" TO \"${DB_OWNER}\";"
$PSQL_SUPER -d "$DB_NAME" -c "GRANT USAGE ON SCHEMA public TO \"${DB_OWNER}\";"
$PSQL_SUPER -d "$DB_NAME" -c "GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO \"${DB_OWNER}\";"

cat <<EOF
Done.
Database: ${DB_NAME}
Owner: ${DB_OWNER}
To connect as owner:
  PGPASSWORD='${DB_OWNER_PW}' psql -h ${HOST} -p ${PORT} -U ${DB_OWNER} -d ${DB_NAME}
EOF
