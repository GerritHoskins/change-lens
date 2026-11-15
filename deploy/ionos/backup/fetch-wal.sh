#!/bin/sh
# restore_command for the restore test: fetch one archived WAL segment and decrypt it to the path Postgres asks
# for. A missing segment (the end of the archive, or a .history file that never existed) exits non-zero, which
# Postgres treats as "no more WAL".
set -u
f="$1"
target="$2"
tmp="/tmp/$f.age"
rclone copyto --s3-no-check-bucket "ionos:${BACKUP_BUCKET}/wal/$f.age" "$tmp" 2>/dev/null || exit 1
age -d -i /run/backup-identity.txt -o "$target" "$tmp" || { rm -f "$tmp"; exit 1; }
rm -f "$tmp"
