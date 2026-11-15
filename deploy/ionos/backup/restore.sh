#!/bin/sh
# Restore test (I-8 S7 §3.3): restores the newest base backup plus archived WAL into a scratch data directory
# inside this container, runs Postgres on a local socket only (never on the network, so a restored database
# can't serve traffic), checks that both databases came back, prints counts only, and deletes the copy.
#
#   docker compose --profile tools run --rm restore-test                      # newest state
#   docker compose --profile tools run --rm restore-test '2026-12-01 10:00:00+00'  # point in time
#
# Needs the private backup key at /etc/changelens/backup-identity.txt on the host for the duration of the test
# (README step D2); remove it afterwards.
set -eu
: "${BACKUP_BUCKET:?}"
[ -r /run/backup-identity.txt ] || { echo "restore: /etc/changelens/backup-identity.txt is missing"; exit 1; }

REMOTE="ionos:${BACKUP_BUCKET}"
TARGET="${1:-}"
DATA=/restore/data
DL=/restore/dl
SOCK=/tmp
PORT=5433
started=$(date -u +%FT%TZ)

rm -rf "$DATA" "$DL"
mkdir -p "$DATA" "$DL"
chmod 700 "$DATA"

base=$(rclone lsf --s3-no-check-bucket "$REMOTE/base/" | sort | tail -n 1)
[ -n "$base" ] || { echo "restore: no base backup in $REMOTE/base/"; exit 1; }
echo "restore: base backup $base"
rclone copyto --s3-no-check-bucket "$REMOTE/base/$base" "$DL/base.tar.age"
age -d -i /run/backup-identity.txt "$DL/base.tar.age" | tar -C "$DL" -xf -
tar -C "$DATA" -xzf "$DL/base.tar.gz"
# -X fetch puts the WAL into base.tar.gz; -X stream would have written pg_wal.tar.gz next to it.
mkdir -p "$DATA/pg_wal"
[ ! -f "$DL/pg_wal.tar.gz" ] || tar -C "$DATA/pg_wal" -xzf "$DL/pg_wal.tar.gz"
rm -rf "$DL"

cat >> "$DATA/postgresql.auto.conf" <<CONF
restore_command = '/usr/local/bin/fetch-wal.sh %f %p'
archive_mode = off
listen_addresses = ''
unix_socket_directories = '$SOCK'
port = $PORT
recovery_target_action = 'promote'
CONF
[ -z "$TARGET" ] || echo "recovery_target_time = '$TARGET'" >> "$DATA/postgresql.auto.conf"
touch "$DATA/recovery.signal"

pg_ctl -D "$DATA" -l /tmp/restore.log -w -t 3600 start
q() { psql -h "$SOCK" -p "$PORT" -U postgres -tAX -v ON_ERROR_STOP=1 "$@"; }
while [ "$(q -d postgres -c 'select pg_is_in_recovery()')" = "t" ]; do sleep 2; done

check() {  # label, database, query: print a count or a value; any failure fails the test
  value=$(q -d "$2" -c "$3") || { echo "restore: FAILED at $1"; pg_ctl -D "$DATA" -m fast -w stop; exit 1; }
  echo "restore: $1 $value"
}
check "changelens schema" changelens "select version_num from alembic_version"
for t in users memberships projects source_versions comparisons account_deletions; do
  check "changelens.$t rows" changelens "select count(*) from $t"
done
check "logto.users rows" logto "select count(*) from users"
echo "restore: recovery target ${TARGET:-latest}"

pg_ctl -D "$DATA" -m fast -w stop
rm -rf "$DATA"
echo "RESTORE OK started=$started finished=$(date -u +%FT%TZ) base=$base"
