#!/bin/sh
# Backup job (I-8 S7 §3.3), one long-running loop:
# - every minute: encrypt each archived WAL segment with age and upload it, then delete the local copy;
# - once a day: an encrypted base backup (pg_basebackup), deletion of remote objects older than 30 days,
#   and deletion of Logto audit-log entries older than 30 days (D-8 C5: the open-source build never prunes).
# Together the base backups and WAL give point-in-time recovery for up to 30 days (03 §6 Retention).
# Logs say what ran and how many items, never row content. Status timestamps live in /work/state for the
# host monitor (monitor.sh).
set -u
: "${AGE_RECIPIENT:?}" "${BACKUP_BUCKET:?}" "${PGPASSWORD:?}" "${PGHOST:?}" "${PGUSER:?}"

REMOTE="ionos:${BACKUP_BUCKET}"
STATE=/work/state
DAY=86400
RETENTION_DAYS=30
mkdir -p "$STATE"

log() { echo "$(date -u +%FT%TZ) backup $*"; }
mark() { date +%s > "$STATE/$1"; }
seconds_since() {
  [ -f "$STATE/$1" ] || { echo 999999999; return; }
  echo $(( $(date +%s) - $(cat "$STATE/$1") ))
}
upload() { rclone copyto --s3-no-check-bucket --retries 3 "$1" "$2"; }

ship_wal() {
  shipped=0
  for f in /wal-archive/*; do
    [ -f "$f" ] || continue
    name=$(basename "$f")
    if age -r "$AGE_RECIPIENT" -o "/work/$name.age" "$f" && upload "/work/$name.age" "$REMOTE/wal/$name.age"; then
      rm -f "/work/$name.age" "$f"
      shipped=$((shipped + 1))
    else
      rm -f "/work/$name.age"
      log "wal upload failed; will retry"
      return 1
    fi
  done
  mark last-wal-ok
  [ "$shipped" -eq 0 ] || log "wal shipped=$shipped"
}

base_backup() {
  ts=$(date -u +%Y%m%dT%H%M%SZ)
  dir="/work/base-$ts"
  if pg_basebackup -D "$dir" -Ft -z -X fetch --checkpoint=fast --no-password \
     && tar -C "$dir" -cf - . | age -r "$AGE_RECIPIENT" -o "/work/base-$ts.tar.age" \
     && upload "/work/base-$ts.tar.age" "$REMOTE/base/$ts.tar.age"; then
    mark last-base-ok
    log "base backup uploaded name=$ts"
  else
    log "base backup failed; will retry in an hour"
  fi
  rm -rf "$dir" "/work/base-$ts.tar.age"
}

expire_remote() {
  if rclone delete --s3-no-check-bucket --min-age "${RETENTION_DAYS}d" "$REMOTE"; then
    mark last-expire-ok
    log "remote objects older than ${RETENTION_DAYS} days deleted"
  else
    log "remote expiry failed"
  fi
}

prune_logto_audit() {
  count=$(psql -d logto -tAX -v ON_ERROR_STOP=1 -c \
    "WITH d AS (DELETE FROM logs WHERE created_at < now() - interval '${RETENTION_DAYS} days' RETURNING 1) SELECT count(*) FROM d")
  if [ $? -eq 0 ]; then
    mark last-audit-prune-ok
    log "logto audit entries deleted=$count"
  else
    log "logto audit pruning failed"
  fi
}

log "started"
while true; do
  ship_wal || true
  if [ "$(seconds_since last-base-ok)" -ge "$DAY" ] && [ "$(seconds_since last-base-try)" -ge 3600 ]; then
    mark last-base-try
    base_backup
    expire_remote
    prune_logto_audit
  fi
  sleep 60
done
