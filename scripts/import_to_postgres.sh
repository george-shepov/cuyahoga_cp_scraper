#!/usr/bin/env bash
set -euo pipefail

# One-shot Postgres import script
# Usage example:
# PGPASSWORD=supersecret ./scripts/import_to_postgres.sh --db cuyahoga_cases --user cuy_user --pass secret --csv out/cases_export.csv

PGHOST=${PGHOST:-localhost}
PGPORT=${PGPORT:-5432}
PG_SUPERUSER=${PG_SUPERUSER:-$USER}

# defaults
DB_NAME="${DB_NAME:-cuyahoga_cases}"
DB_USER="${DB_USER:-cuy_user}"
DB_PASS="${DB_PASS:-password}"
CSV_PATH="${CSV_PATH:-out/cases_export.csv}"
SCHEMA_FILE="${SCHEMA_FILE:-out/sql/schema_postgres.sql}"

usage(){
  echo "Usage: PGPASSWORD=adminpw $0 [--db name] [--user name] [--pass pw] [--csv path] [--schema path]"
  exit 1
}

# simple arg parse
while [[ $# -gt 0 ]]; do
  case "$1" in
    --db) DB_NAME="$2"; shift 2;;
    --user) DB_USER="$2"; shift 2;;
    --pass) DB_PASS="$2"; shift 2;;
    --csv) CSV_PATH="$2"; shift 2;;
    --schema) SCHEMA_FILE="$2"; shift 2;;
    -h|--help) usage;;
    *) echo "Unknown arg $1"; usage;;
  esac
done

if [ ! -f "$CSV_PATH" ]; then
  echo "CSV not found: $CSV_PATH" >&2
  exit 2
fi
if [ ! -f "$SCHEMA_FILE" ]; then
  echo "Schema file not found: $SCHEMA_FILE" >&2
  exit 2
fi

# psql command helper (runs as superuser or provided PG_SUPERUSER)
PSQL_SUPER="psql -h $PGHOST -p $PGPORT -U $PG_SUPERUSER -v ON_ERROR_STOP=1"
PSQL_DB="psql -h $PGHOST -p $PGPORT -U $PG_SUPERUSER -d $DB_NAME -v ON_ERROR_STOP=1"

export PGPASSWORD=${PGPASSWORD:-$PGPASSWORD}

# 1) create role if not exists
echo "Creating role/user $DB_USER (if needed)"
$PSQL_SUPER -c "DO $$ BEGIN IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '${DB_USER}') THEN CREATE ROLE \"${DB_USER}\" LOGIN PASSWORD '${DB_PASS}'; ELSE ALTER ROLE \"${DB_USER}\" WITH LOGIN PASSWORD '${DB_PASS}'; END IF; END$$;"

# 2) create database if not exists
echo "Creating database $DB_NAME (if needed)"
$PSQL_SUPER -c "SELECT 1 FROM pg_database WHERE datname='${DB_NAME}'" | grep -q 1 || $PSQL_SUPER -c "CREATE DATABASE \"${DB_NAME}\" OWNER \"${DB_USER}\""

# 3) load schema (as superuser)
echo "Loading schema $SCHEMA_FILE into $DB_NAME"
$PSQL_DB -f "$SCHEMA_FILE"

# 4) create a staging table and import CSV using \copy (client-side COPY) -- this avoids requiring superuser
STAGING_TABLE="cases_staging"

echo "Creating staging table $STAGING_TABLE and importing CSV"
$PSQL_DB <<SQL
BEGIN;
DROP TABLE IF EXISTS ${STAGING_TABLE};
CREATE TABLE ${STAGING_TABLE} (
  case_id TEXT,
  year TEXT,
  status TEXT,
  arrested_date TEXT,
  earliest_capias_date TEXT,
  metadata_json TEXT,
  example_json_path TEXT
);
\copy ${STAGING_TABLE} FROM '${CSV_PATH}' WITH CSV HEADER;

-- Upsert into final table, casting types
INSERT INTO cases(case_id, year, status, arrested_date, earliest_capias_date, metadata_json, example_json_path)
SELECT
  case_id,
  NULLIF(year,'')::int,
  status,
  NULLIF(arrested_date,'')::date,
  NULLIF(earliest_capias_date,'')::date,
  (CASE WHEN metadata_json IS NULL OR metadata_json = '' THEN NULL ELSE metadata_json::jsonb END),
  example_json_path
FROM ${STAGING_TABLE}
ON CONFLICT (case_id) DO UPDATE SET
  year = EXCLUDED.year,
  status = EXCLUDED.status,
  arrested_date = EXCLUDED.arrested_date,
  earliest_capias_date = EXCLUDED.earliest_capias_date,
  metadata_json = EXCLUDED.metadata_json,
  example_json_path = EXCLUDED.example_json_path;

DROP TABLE IF EXISTS ${STAGING_TABLE};
COMMIT;
SQL

echo "Import complete. Granting connect/usage to ${DB_USER}"
$PSQL_SUPER -d "$DB_NAME" -c "GRANT CONNECT ON DATABASE \"${DB_NAME}\" TO \"${DB_USER}\";"
$PSQL_SUPER -d "$DB_NAME" -c "GRANT USAGE ON SCHEMA public TO \"${DB_USER}\";"
$PSQL_SUPER -d "$DB_NAME" -c "GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO \"${DB_USER}\";"

echo "Done. Database: $DB_NAME, user: $DB_USER. Use: psql -h $PGHOST -p $PGPORT -U $DB_USER -d $DB_NAME"
