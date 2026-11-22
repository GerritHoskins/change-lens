# ChangeLens on IONOS: releases that ran once

Moved out of section F of the [runbook](README.md) to keep it under the 500-line limit. Each of these changed
the server once and is done; they stay as the record of what was run, and as the steps for a rebuilt server
that starts from older files. Commands run on the server in Bash, as root. "The app release command" is the
first command of the runbook's section F.

## The release with task L32 (once)

L32 gives the worker its own env file, moves Logto off the worker's network and gives the backup job its own
database role. The release recreates Postgres, Logto, the worker and the backup job: sign-in and the api
pause for about a minute, and a recreated container's log is gone. **Run the three server checks in
[`docs/security-review.md`](../../docs/security-review.md) first**: one of them reads Logto's log.
**Done on the server 2026-11-19**, steps 1 to 6; the base backup and a comparison from the app ran on 2026-11-20.

1. **The code.**
   ```bash
   cd /opt/changelens && git pull
   ```
2. **The worker's file.** Copies the worker's settings from `changelens.env` into `worker.env` without
   showing a value, then lists the names in the file:
   ```bash
   grep -E '^CHANGELENS_(AUTH_MODE|DATABASE_URL|S3_ENDPOINT|S3_BUCKET|S3_ACCESS_KEY|S3_SECRET_KEY|LLM|LLM_MODEL|TENANT_SPEND_CAP_EUR|GLOBAL_SPEND_CAP_EUR|COST_CEILING_EUR)=' /etc/changelens/changelens.env >> /etc/changelens/worker.env
   ```
   ```bash
   cut -d= -f1 /etc/changelens/worker.env
   ```
   Expected: the comment line, `IONOS_API_TOKEN`, `CHANGELENS_AUTH_MODE`, `CHANGELENS_DATABASE_URL`, the four
   `CHANGELENS_S3_` names and `CHANGELENS_LLM`, plus the spend caps if `changelens.env` sets them. No
   `CHANGELENS_LOGTO_` name and no `CHANGELENS_RATE_LIMIT_KEY`: the worker doesn't start with one of those.
3. **The backup role's password**, generated into both files without showing it:
   ```bash
   P=$(openssl rand -base64 32 | tr -d '/+=' | cut -c1-32) && echo "BACKUP_DB_PASSWORD=$P" >> /etc/changelens/postgres.env && sed -i -e 's/^PGUSER=.*/PGUSER=changelens_backup/' -e "s/^PGPASSWORD=.*/PGPASSWORD=$P/" /etc/changelens/backup.env; unset P
   ```
   ```bash
   grep -c ^BACKUP_DB_PASSWORD= /etc/changelens/postgres.env; grep ^PGUSER= /etc/changelens/backup.env
   ```
   Expected: `1` and `PGUSER=changelens_backup`.
4. **The release.**
   ```bash
   cd /opt/changelens/deploy/ionos && docker compose build && docker compose --profile tools run --rm migrate && docker compose up -d
   ```
5. **The backup role.** The last line must read `backup role: ready (base backups, and deleting old rows from
   the Logto audit log)`:
   ```bash
   docker compose exec -u postgres postgres /docker-entrypoint-initdb.d/20-backup-role.sh
   ```
6. **Checks.** Every service is up and none is restarting. A worker that restarts names what its file lacks
   in `docker compose logs --tail 5 worker`:
   ```bash
   docker compose ps
   ```
   The worker has no route to Logto: the last line starts with `socket.gaierror`:
   ```bash
   docker compose exec worker python -c "import socket; socket.gethostbyname('logto')"
   ```
   The backup role can connect for a base backup (one line of numbers) and prune the audit log (a number):
   ```bash
   docker compose exec backup psql "replication=true dbname=postgres" -tAX -c "IDENTIFY_SYSTEM"
   ```
   ```bash
   docker compose exec backup psql -d logto -tAX -c "SELECT changelens_prune_audit_log()"
   ```
   Then one comparison from the app completes, and within a day the backup log shows `base backup uploaded`
   (it runs 24 hours after the last one): `docker compose logs backup | grep -v 'wal shipped' | tail -n 20`.

## The release with the Logto log filter (once, LR-12)

Logto prints every request line with its query string: the email address and one-time token of a sign-in.
From this release `logto/log-filter.awk` drops the query string and masks email addresses. The app release
command recreates Logto (sign-in pauses for under a minute; the old log goes). Then sign in from the app, and:
```bash
cd /opt/changelens/deploy/ionos && docker compose logs logto | grep -c -E 'login_hint|primaryEmail|one_time_token'
```
```bash
docker compose logs logto | grep -c -F '?[removed]'
```
Expected: `0`, then a number above `0` (the requests are still logged, without their query strings). Two
`0` mean an empty log: no sign-in has reached Logto yet. **Done on the server 2026-11-19.**

## Separate storage keys (once, LR-13)

Until this is done both sides share the account owner's key, which reaches both buckets: a compromised api
or worker could delete the backups. Every key of one IONOS user has the same access, so each side gets a
user of its own and a bucket policy. **Done on the server 2026-11-19**, all ten steps.

1. **A group.** In the IONOS DCD as the account owner: **Menu** > **Management** > **Users & Groups**, tab
   **Groups**: create the group `changelens-storage` and tick **Use Object Storage** under **Privileges**.
2. **Two users.** Tab **Users**, **+ Create**: first name, last name, email, password, **Create**. One user
   for the app and one for the backup job, each with an email address of its own. Add both to the group
   (its tab **Members**).
3. **A key for each user.** Select the user in the **Users** list, tab **Object Storage Keys**, **+ Generate
   Key**, **OK**. The row shows the access key only: the round **?** icon at its right end opens a dialog with
   **Key** and **Secret** (64 characters: click into the field, Ctrl+A, Ctrl+C). The **Object Storage** link
   in the same tab shows the user's **Canonical User ID**.
4. **A policy on each bucket.** **Menu** > **Backup & Storage** > **Object Storage**, tab **Buckets**, **Show
   user-owned buckets**. On `changelens-originals`: **Bucket settings** > **Access management** > **Bucket
   Policy** > **Edit**, paste the policy below with the app user's Canonical User ID in place of `<canonical
   user id>`, **Save**. Then the same on `changelens-backups`, with the backup user's ID and
   `changelens-backups` in both `Resource` values. IONOS saves a policy that still holds the placeholder, and
   that policy lets nobody in; it refuses one that names another bucket (`MalformedPolicy: Invalid resource`).
   ```json
   {"Version": "2012-10-17", "Statement": [{"Effect": "Allow", "Action": "s3:*",
     "Principal": {"CanonicalUser": ["<canonical user id>"]},
     "Resource": ["arn:aws:s3:::changelens-originals", "arn:aws:s3:::changelens-originals/*"]}]}
   ```
   Buckets listed under **Show contract-owned buckets** take the user's **Contract User ID** instead, as
   `"Principal": {"AWS": ["arn:aws:iam:::user/<contract user id>"]}`.

5. **On the server, keep the old files** until the checks have passed:
   ```bash
   cd /etc/changelens && cp -p changelens.env changelens.env.old-key && cp -p worker.env worker.env.old-key && cp -p backup.env backup.env.old-key
   ```
6. **The app user's key** into `changelens.env` and `worker.env`. Paste each value alone and press Enter; the
   secret key isn't shown. A value with a space in it (a wrong paste) changes nothing. It ends with `changed`:
   ```bash
   read -rp 'App access key: ' K && read -rsp 'App secret key: ' S && echo; if printf '%s\n%s\n' "$K" "$S" | grep -qvE '^[^[:space:]|&\]{16,}$'; then echo 'not changed: a value is empty or is not a key'; else sed -i -e "s|^CHANGELENS_S3_ACCESS_KEY=.*|CHANGELENS_S3_ACCESS_KEY=$K|" -e "s|^CHANGELENS_S3_SECRET_KEY=.*|CHANGELENS_S3_SECRET_KEY=$S|" /etc/changelens/changelens.env /etc/changelens/worker.env && echo 'changed'; fi; unset K S
   ```
7. **The backup user's key** into `backup.env`:
   ```bash
   read -rp 'Backup access key: ' K && read -rsp 'Backup secret key: ' S && echo; if printf '%s\n%s\n' "$K" "$S" | grep -qvE '^[^[:space:]|&\]{16,}$'; then echo 'not changed: a value is empty or is not a key'; else sed -i -e "s|^RCLONE_CONFIG_IONOS_ACCESS_KEY_ID=.*|RCLONE_CONFIG_IONOS_ACCESS_KEY_ID=$K|" -e "s|^RCLONE_CONFIG_IONOS_SECRET_ACCESS_KEY=.*|RCLONE_CONFIG_IONOS_SECRET_ACCESS_KEY=$S|" /etc/changelens/backup.env && echo 'changed'; fi; unset K S
   ```
8. **Try the new keys before any service uses them.** One-off containers read the changed files; the
   running services keep the old key until step 9. Each command must print `own bucket: ok`, then a line
   naming `AccessDenied` (the other side's bucket). The app user's key:
   ```bash
   cd /opt/changelens/deploy/ionos && docker compose run --rm --no-deps -T api python -c "import os; from changelens.storage import S3ObjectStore as S; e = os.environ; b = e['CHANGELENS_S3_BUCKET']; a = (e['CHANGELENS_S3_ENDPOINT'], e['CHANGELENS_S3_ACCESS_KEY'], e['CHANGELENS_S3_SECRET_KEY']); S(*a, b).client.list_objects_v2(Bucket=b, MaxKeys=1); print('own bucket: ok'); S(*a, 'changelens-backups').client.list_objects_v2(Bucket='changelens-backups', MaxKeys=1)" 2>&1 | grep -oE '^own bucket: ok|An error occurred \([A-Za-z]+\)'
   ```
   The backup user's key (it writes and deletes one small test object):
   ```bash
   docker compose run --rm --no-deps -T --entrypoint sh backup -c '{ echo key-test | rclone rcat --s3-no-check-bucket --retries 1 "ionos:$BACKUP_BUCKET/key-test" && rclone deletefile --s3-no-check-bucket --retries 1 "ionos:$BACKUP_BUCKET/key-test" && echo "own bucket: ok"; rclone lsf --s3-no-check-bucket --retries 1 ionos:changelens-originals; } 2>&1 | grep -oE "own bucket: ok|api error [A-Za-z]+" | uniq' 2>/dev/null
   ```
   `SignatureDoesNotMatch` is a wrong secret key (step 6 or 7 again). `AccessDenied` without `own bucket: ok`
   is a policy that doesn't name this user (step 4). Go on only when both are as expected.
9. **Restart with the new keys.** The api pauses for a few seconds; afterwards every service is up. Then one
   comparison from the app completes, the key check in `docs/security-review.md` prints `different keys`,
   and within a day the backup log shows `base backup uploaded` (the command that ends the L32 release):
   ```bash
   docker compose up -d --force-recreate api worker retention backup && sleep 40 && docker compose ps
   ```
10. **Afterwards.** The checks passed: remove the old files. The owner's key stays active at IONOS, because
    it owns the buckets, and is on the server nowhere:
    ```bash
    rm /etc/changelens/changelens.env.old-key /etc/changelens/worker.env.old-key /etc/changelens/backup.env.old-key
    ```
    A service doesn't come up: put the old files back, then run the restart of step 9 again:
    ```bash
    cd /etc/changelens && mv changelens.env.old-key changelens.env && mv worker.env.old-key worker.env && mv backup.env.old-key backup.env
    ```

## The backup job behind the egress proxy (once, LR-13)

Until this release the backup job is on the `outbound` network and can reach any host. From it the job is on
`data` only, with no route out: rclone uploads through the egress proxy, which lets HTTPS through to the hosts
in `/etc/changelens/egress-allowlist.txt` and nothing else. The backup job is recreated and its log starts
again; nothing else in this change needs a restart. The restore test is unchanged. Checked in Docker on
2026-11-21 with this `compose.yaml` and made-up keys: before the change the container connected to
`1.1.1.1:443` and to `example.com`; after it neither, and the storage host answered through the proxy.

**Done on the server on 2026-11-21**, with the checkout at `93d3e84`. The backup job was recreated; the proxy
was not restarted. Step 4 printed `rc=1`. Step 5 printed `rc=1`, and the proxy logged `TCP_DENIED/403` for
`CONNECT example.com:443`. Step 6 listed 6 base backups. Step 7 showed `backup started` at 16:04:33 UTC and
`wal shipped=1` at 16:07:34 UTC, with no `wal upload failed`. Step 1's line was not in the output that was
kept; step 6 shows that the proxy lets the job's storage host through. The run of the release command that
was kept found the backup job already running and started the api, the worker and retention again. Not looked
at: the proxy's own log line for the storage host.

Two hours after the release `docker compose ps` showed all eight services up: the api (healthy), the worker,
retention and the backup job two hours old, Caddy six hours, Postgres and Logto two days (both healthy) and
the proxy five days. The first base backup through the proxy followed on 2026-11-22: `base backup uploaded`
at 07:47:18 UTC, one second after it was tried, then `remote objects older than 30 days deleted` and `logto
audit entries deleted=0` at 07:47:27 UTC. Between the release and that check (12:45 UTC) the job logged no
failed upload, and its last shipped segment was two seconds old.

1. **Before: the job's storage host is on the allow-list.** Prints the host and `on the list`:
   ```bash
   H=$(sed -n 's|^RCLONE_CONFIG_IONOS_ENDPOINT=https://||p' /etc/changelens/backup.env | tr -d '/\r') && grep -qxF "$H" /etc/changelens/egress-allowlist.txt && echo "$H: on the list" || echo "$H: missing"
   ```
   `missing`: add the host as a line of its own to `/etc/changelens/egress-allowlist.txt`, then
   `cd /opt/changelens/deploy/ionos && docker compose restart egress` (the proxy reads the list at start).
2. **The release:** the app release command.
3. **Both are up**, and the backup job was created just now:
   ```bash
   docker compose ps backup egress
   ```
4. **No route out.** Prints `rc=1`:
   ```bash
   docker compose exec -T backup sh -c 'nc -z -w 5 1.1.1.1 443; echo rc=$?'
   ```
5. **A host off the list is refused by the proxy.** Prints `rc=1`, then a line with `TCP_DENIED/403` and
   `CONNECT example.com:443`:
   ```bash
   docker compose exec -T backup sh -c 'rclone lsf --retries 1 --low-level-retries 1 --contimeout 8s --timeout 10s --http-url https://example.com :http: >/dev/null 2>&1; echo rc=$?'
   ```
   ```bash
   docker compose exec -T egress grep -F 'example.com' /var/log/squid/access.log | tail -n 1
   ```
6. **The job's own bucket is reachable.** Prints the number of base backups in it, above `0`:
   ```bash
   docker compose exec -T backup sh -c 'rclone lsf --s3-no-check-bucket --retries 1 "ionos:$BACKUP_BUCKET/base/" | wc -l'
   ```
7. **The job ships.** Within about ten minutes the log shows `started` and then `wal shipped=…`, and no
   `wal upload failed`; a day later `base backup uploaded` (the command that ends the L32 release):
   ```bash
   docker compose logs --since 15m backup | tail -n 5
   ```

`wal upload failed` keeps appearing: nothing is lost, the segments wait in the archive volume and the monitor
mails after 30 minutes. Step 1 again first. Back to the file before this release, then `git checkout
compose.yaml` once the cause is found:
```bash
git -C /opt/changelens show d97bbdc:deploy/ionos/compose.yaml > /opt/changelens/deploy/ionos/compose.yaml && docker compose up -d backup
```
