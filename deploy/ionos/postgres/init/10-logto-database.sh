#!/bin/sh
# Runs once, on an empty data volume (the official image's init hook).
# - Creates Logto's own role and database, separate from ChangeLens (I-8 S7 §3.3).
# - Allows replication connections for the backup job's pg_basebackup over the internal network.
# ChangeLens's two roles come from `bootstrap-roles` (README step C3), not from here.
set -eu

: "${LOGTO_DB_PASSWORD:?set LOGTO_DB_PASSWORD in postgres.env}"

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname postgres \
     -v pw="$LOGTO_DB_PASSWORD" <<'SQL'
CREATE ROLE logto LOGIN PASSWORD :'pw';
CREATE DATABASE logto OWNER logto;
REVOKE ALL ON DATABASE logto FROM PUBLIC;
SQL

echo "host replication postgres all scram-sha-256" >> "$PGDATA/pg_hba.conf"
