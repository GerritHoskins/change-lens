#!/bin/sh
# The backup job's own database role (LR-13). It may take base backups (REPLICATION) and have old rows deleted
# from Logto's audit log, and nothing else, so the job no longer connects as the superuser.
# - On an empty data volume this runs once by itself (the official image's init hook). Logto's tables don't
#   exist yet then, so it runs a second time after Logto's first start (README step C3).
# - On a server that is already running, and after a change of BACKUP_DB_PASSWORD (README F):
#     docker compose exec -u postgres postgres /docker-entrypoint-initdb.d/20-backup-role.sh
# Running it again changes nothing but the password.
set -eu

if [ "$(id -u)" = 0 ]; then
  echo "run this as the postgres user: docker compose exec -u postgres postgres /docker-entrypoint-initdb.d/20-backup-role.sh" >&2
  exit 1
fi
if [ -z "${BACKUP_DB_PASSWORD:-}" ]; then
  echo "BACKUP_DB_PASSWORD is empty: fill it in /etc/changelens/postgres.env" >&2
  exit 1
fi

# psql reads the value from the environment itself (\getenv), so it never appears on a command line.
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname postgres <<'SQL'
\getenv pw BACKUP_DB_PASSWORD
SELECT 'CREATE ROLE changelens_backup' WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'changelens_backup') \gexec
ALTER ROLE changelens_backup LOGIN REPLICATION NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS PASSWORD :'pw';
SQL

# pg_basebackup over the internal network. The keyword `all` in the image's own rule doesn't cover replication.
RULE="host replication changelens_backup all scram-sha-256"
grep -qxF "$RULE" "$PGDATA/pg_hba.conf" || echo "$RULE" >> "$PGDATA/pg_hba.conf"

# The role gets no right on Logto's tables. It may call one function, which deletes audit-log rows older than
# 30 days (the same 30 as RETENTION_DAYS in backup/backup.sh) and returns their number. The function runs as
# the table's owner, because Logto's row-level security hides every row from any other role.
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname logto <<'SQL'
SELECT pg_reload_conf() \gset
GRANT CONNECT ON DATABASE logto TO changelens_backup;
SELECT to_regclass('public.logs') IS NOT NULL AS has_logs \gset
\if :has_logs
CREATE OR REPLACE FUNCTION public.changelens_prune_audit_log() RETURNS bigint
  LANGUAGE sql SECURITY DEFINER SET search_path = pg_catalog AS $$
    WITH gone AS (DELETE FROM public.logs WHERE created_at < now() - interval '30 days' RETURNING 1)
    SELECT count(*) FROM gone
  $$;
ALTER FUNCTION public.changelens_prune_audit_log() OWNER TO logto;
REVOKE ALL ON FUNCTION public.changelens_prune_audit_log() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.changelens_prune_audit_log() TO changelens_backup;
\echo backup role: ready (base backups, and deleting old rows from the Logto audit log)
\else
\echo backup role: ready for base backups. Logto has no tables yet: run this script again after its first start.
\endif
SQL
