# Backup job and restore test (I-8 S7 §3.3): Postgres 16 client tools, rclone for IONOS Object Storage and
# age for encryption. Same Postgres image as the database, so pg_basebackup and the server versions match.
FROM postgres:16.16-alpine@sha256:0adbf25a9e96d38823bb813f3ac0ed41fadb665c88f1df7fe6dbfb060cbdc106

RUN apk add --no-cache rclone age \
 && mkdir -p /work /restore /etc/rclone \
 && touch /etc/rclone/rclone.conf \
 && chown postgres:postgres /work /restore

# rclone takes the remote from the RCLONE_CONFIG_IONOS_* variables; the empty file only silences a notice.
ENV RCLONE_CONFIG=/etc/rclone/rclone.conf

COPY backup.sh restore.sh fetch-wal.sh /usr/local/bin/
RUN chmod 755 /usr/local/bin/backup.sh /usr/local/bin/restore.sh /usr/local/bin/fetch-wal.sh

USER postgres
ENTRYPOINT ["/usr/local/bin/backup.sh"]
