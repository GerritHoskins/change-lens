#!/bin/sh
# Umami's own role and database (landing page measurement, docs/landing-page-handoff.md), separate from
# ChangeLens and from Logto. Umami creates its tables itself at its first start, as the database's owner.
# - On an empty data volume this runs once by itself (the official image's init hook).
# - On a server that is already running, and after a change of UMAMI_DB_PASSWORD:
#     docker compose exec -u postgres postgres /docker-entrypoint-initdb.d/30-umami-database.sh
# Running it again changes nothing but the password.
set -eu

if [ "$(id -u)" = 0 ]; then
  echo "run this as the postgres user: docker compose exec -u postgres postgres /docker-entrypoint-initdb.d/30-umami-database.sh" >&2
  exit 1
fi
if [ -z "${UMAMI_DB_PASSWORD:-}" ]; then
  echo "UMAMI_DB_PASSWORD is empty: fill it in /etc/changelens/postgres.env" >&2
  exit 1
fi

# psql reads the value from the environment itself (\getenv), so it never appears on a command line.
# No CREATEROLE and no CREATEDB: the role owns one database and nothing else.
psql -v ON_ERROR_STOP=1 --username "${POSTGRES_USER:-postgres}" --dbname postgres <<'SQL'
\getenv pw UMAMI_DB_PASSWORD
SELECT 'CREATE ROLE umami LOGIN' WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'umami') \gexec
ALTER ROLE umami PASSWORD :'pw';
SELECT 'CREATE DATABASE umami OWNER umami' WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = 'umami') \gexec
REVOKE ALL ON DATABASE umami FROM PUBLIC;
SQL
