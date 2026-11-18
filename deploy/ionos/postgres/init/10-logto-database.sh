#!/bin/sh
# Runs once, on an empty data volume (the official image's init hook).
# Creates Logto's own role and database, separate from ChangeLens (I-8 S7 §3.3).
# ChangeLens's two roles come from `bootstrap-roles` (README step C3), not from here; the backup job's role
# comes from 20-backup-role.sh.
set -eu

if [ -z "${LOGTO_DB_PASSWORD:-}" ]; then
  echo "LOGTO_DB_PASSWORD is empty: fill it in /etc/changelens/postgres.env" >&2
  exit 1
fi

# psql reads the value from the environment itself (\getenv), so it never appears on a command line.
# CREATEROLE: Logto's seed creates its own tenant role (logto_tenant_logto). On Postgres 16 a CREATEROLE role
# can only manage the roles it creates, so it can't touch postgres or the ChangeLens roles.
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname postgres <<'SQL'
\getenv pw LOGTO_DB_PASSWORD
CREATE ROLE logto LOGIN CREATEROLE PASSWORD :'pw';
CREATE DATABASE logto OWNER logto;
REVOKE ALL ON DATABASE logto FROM PUBLIC;
SQL
