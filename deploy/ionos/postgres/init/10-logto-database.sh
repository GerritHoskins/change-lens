#!/bin/sh
# Runs once, on an empty data volume (the official image's init hook).
# - Creates Logto's own role and database, separate from ChangeLens (I-8 S7 §3.3).
# - Allows replication connections for the backup job's pg_basebackup over the internal network.
# ChangeLens's two roles come from `bootstrap-roles` (README step C3), not from here.
set -eu

if [ -z "${LOGTO_DB_PASSWORD:-}" ]; then
  echo "LOGTO_DB_PASSWORD is empty: fill it in /etc/changelens/postgres.env" >&2
  exit 1
fi

# psql reads the value from the environment itself (\getenv), so it never appears on a command line.
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname postgres <<'SQL'
\getenv pw LOGTO_DB_PASSWORD
CREATE ROLE logto LOGIN PASSWORD :'pw';
CREATE DATABASE logto OWNER logto;
REVOKE ALL ON DATABASE logto FROM PUBLIC;
SQL

echo "host replication postgres all scram-sha-256" >> "$PGDATA/pg_hba.conf"
