# ChangeLens on IONOS: deployment runbook (I-8 S7)

[S7 handoff](../../docs/i8/s7-ionos-deployment.md), ADR-0020, 03 §1.2 and §6. Everything runs on one IONOS Cloud
Cube (4 vCPU, 8 GB RAM) in Germany: Caddy (TLS), Postgres 16, Logto, and the ChangeLens `api`, `worker` and
`retention` processes. Originals and encrypted backups go to IONOS Object Storage; one-time codes go out
through IONOS SMTP. **Nothing here opens sign-ups**: that waits for S1–S6 being merged and the release gates in
05 (I-13, I-17, I-20).

| File | What |
|---|---|
| `compose.yaml` | All services, networks and volumes; images pinned by digest |
| `changelens.Dockerfile` | The backend image (hash-pinned wheels, non-root, read-only filesystem) |
| `Caddyfile` | TLS for `api.pixeltronic.dev` and `auth.pixeltronic.dev`; no access log |
| `postgres/init/` | Logto's database and the replication rule for backups (first start only) |
| `squid/squid.conf` | The worker's egress proxy: HTTPS to the allow-listed hosts only |
| `backup/` | WAL shipping, daily base backup, 30-day expiry, Logto audit-log pruning, restore test |
| `monitor.sh` | Host cron job: endpoints, containers, backups, disk, global spend cap; alert mail |
| `env/*.example` | One template per secret file in `/etc/changelens/` |

Commands in B–F run on the server in Bash, as root, unless a step says otherwise. Secrets go into
`/etc/changelens/` and your password manager, never into the repository, a ticket or a chat.

## A. Accounts and settings (no server work)

1. **DNS.** A records `api.pixeltronic.dev` and `auth.pixeltronic.dev` → the cube's public IPv4. **Done
   2026-11-15:** Cloudflare, DNS only, reserved IP `212.132.90.61`.
2. **IONOS answers for D-8**, with the date: the DPA covers the Cube, Object Storage and mail; encryption at
   rest for the Cube's disk and Object Storage; both in Germany. Docs answered 2026-11-15: the Cloud AVV covers
   Cube and Object Storage, the mail AVV covers Mail Basic/Business (keep both; contracts before 2022-07-19 may
   need it accepted separately); storage stays in the chosen German location, but the AVVs allow EU/EEA and
   qualified third-country processing (support, metadata), so record "stored in Germany", not "processed only
   in Germany". Still open: the Cube's volume encryption (AES-XTS 256 applies only to volumes created after the
   feature launched; ask IONOS support for this volume, by its ID) and the bucket encryption check in A3.
3. **Object Storage in Frankfurt** (**done 2026-11-15**) (`s3.eu-central-1.ionoscloud.com`; the backend signs for region
   `eu-central-1`): bucket `changelens-originals` (private, versioning **off**) and bucket `changelens-backups`
   (private, versioning off, lifecycle rule: delete after 30 days). One access key for the app and, if IONOS
   lets you scope keys per bucket, a second one for backups. **Encryption:** the backend uploads originals
   without an encryption header, so turn on default encryption (SSE-S3, AES-256) on `changelens-originals`;
   backups are already `age`-encrypted. After C7, check one uploaded object shows `ServerSideEncryption:
   AES256` (in the DCD object details, or `aws s3api head-object` with the app key).
4. **IONOS mailbox** `noreply@pixeltronic.dev` with SPF, DKIM and DMARC records as IONOS shows them. **Done
   2026-11-16:** MX, SPF, DKIM (`s1-ionos`, `s2-ionos`) and DMARC resolve in Cloudflare.
5. **Google Cloud** OAuth clients (web, iOS `dev.changelens.app`, Android `dev.changelens.app` + SHA-1) and
   **Apple** (Sign in with Apple on the App ID, a Services ID, a `.p8` key with its Key ID and your Team ID).
   These are for S4; nothing below needs them yet.

## B. Prepare the server

1. **Harden SSH and the firewall.** Confirm that key login works first. **Done 2026-11-16 except the
   `sshd_config` change:** password login stays on until key login from the PC works.
   ```bash
   apt update && apt -y full-upgrade && apt -y install unattended-upgrades ufw git age
   ```
   ```bash
   dpkg-reconfigure -plow unattended-upgrades
   ```
   In `/etc/ssh/sshd_config` set `PasswordAuthentication no` and `PermitRootLogin prohibit-password`, then:
   ```bash
   systemctl restart ssh
   ```
   ```bash
   ufw default deny incoming && ufw allow from <your-ip> to any port 22 proto tcp && ufw allow 80/tcp && ufw allow 443/tcp && ufw allow 443/udp && ufw enable
   ```
   Docker publishes ports past `ufw`; that's why only Caddy publishes public ports and Logto's admin port is
   bound to `127.0.0.1`.
2. **Docker.** **Done 2026-11-16.**
   ```bash
   curl -fsSL https://get.docker.com | sh
   ```
3. **The code.** Add a read-only deploy key to the GitHub repository, then: **Done 2026-11-16** (key
   `/root/.ssh/changelens_deploy`, set as the clone's `core.sshCommand`).
   ```bash
   git clone git@github.com:GerritHoskins/change-lens.git /opt/changelens && cd /opt/changelens && git checkout m1-iphone
   ```
4. **Secret files.** Copy each template, then fill it in with `nano`:
   ```bash
   install -d -m 700 /etc/changelens && cd /opt/changelens/deploy/ionos/env && for f in *.example; do install -m 600 "$f" "/etc/changelens/${f%.example}"; done
   ```
   Generate each password with `openssl rand -base64 32 | tr -d '/+=' | cut -c1-32` and the rate-limit key
   with `openssl rand -hex 32`. Fill `postgres.env`, `admin.env`, `logto.env`, `caddy.env`, `backup.env`,
   `worker.env` (the IONOS model key), `egress-allowlist.txt` and `monitor.env` now; `changelens.env` except
   the two `CHANGELENS_LOGTO_M2M_*` values, which come in C5.
5. **Check that no template placeholder is left** (prints nothing when done; the M2M values are expected
   until C5):
   ```bash
   grep -n '=$\|<[a-z]*>' /etc/changelens/*.env
   ```
6. **Backup key.** The private half never stays on the server:
   ```bash
   age-keygen -o /root/backup-identity.txt
   ```
   Copy the `# public key: age1…` value into `AGE_RECIPIENT` in `/etc/changelens/backup.env`. Store the
   whole file's content in your password manager, then delete it:
   ```bash
   cat /root/backup-identity.txt && shred -u /root/backup-identity.txt
   ```

## C. First start

**Done 2026-11-16** on the cube (C1–C7; the worker hasn't used the egress proxy yet, so its allow-list is
unchecked until the first comparison).

All from `/opt/changelens/deploy/ionos`:
```bash
cd /opt/changelens/deploy/ionos
```

1. **Build and start Postgres.**
   ```bash
   docker compose build && docker compose up -d --wait postgres
   ```
2. **ChangeLens roles and schema** (S3: owner and app roles; RLS).
   ```bash
   docker compose --profile tools run --rm bootstrap-roles
   ```
   ```bash
   docker compose --profile tools run --rm migrate
   ```
3. **Everything else.** The api and retention restart until Logto has a signing key and Caddy has a
   certificate; that's expected for the first minutes.
   ```bash
   docker compose up -d
   ```
   ```bash
   docker compose ps
   ```
   **Logto's tenant roles.** On the first start Logto's seed creates `logto_tenant_logto` and one
   `logto_tenant_logto_<tenant>` login role per tenant, then connects as those. The init script revokes `CONNECT`
   on the `logto` database from `PUBLIC`, so Logto's status check returns 500 (`CheckMyDatabase`) until they get
   it. Once, after the first start (affects the `logto` database only):
   ```bash
   docker compose exec postgres psql -U postgres -v ON_ERROR_STOP=1 -c "GRANT CONNECT ON DATABASE logto TO logto_tenant_logto" -c "DO \$\$DECLARE r text; BEGIN FOR r IN SELECT rolname FROM pg_roles WHERE rolname LIKE 'logto_tenant_logto_%' LOOP EXECUTE format('GRANT CONNECT ON DATABASE logto TO %I', r); END LOOP; END\$\$"
   ```
   ```bash
   docker compose restart logto && sleep 45 && docker compose ps logto
   ```
   Logto shows `healthy`. (Done 2026-11-16 on the cube, together with `ALTER ROLE logto CREATEROLE`, which
   the init script now sets on a fresh volume.)
4. **Logto admin console**, from your PC through an SSH tunnel (it is never public).
   ```powershell
   ssh -N -L 3002:127.0.0.1:3002 root@<cube-ip>
   ```
   ```bash
   ssh -N -L 3002:127.0.0.1:3002 root@<cube-ip>
   ```
   Open http://localhost:3002, create the admin account (password manager), then configure, in this order
   (console labels can differ slightly between Logto versions):
   1. **Signing key: RSA.** Tenant settings → Signing keys → OIDC private keys → rotate, type **RSA**, then
      remove the old key once the new one is active. The backend accepts RS256, PS256 and ES256 only; Logto's
      default elliptic-curve key may be P-384, which it rejects.
   2. **Email.** Connectors → Email and SMS → SMTP: host and port as IONOS shows them (usually
      `smtp.ionos.de`, 587, STARTTLS), user `noreply@pixeltronic.dev`, its password, from address the same.
      A template per usage type containing `{{code}}`. Send a test mail. D-8 gotcha: an empty `auth: {}` is
      saved as no field; fill the user and password.
   3. **Sign-in experience.** Identifier: email address; verification: code; no password. Automatic account
      linking off (O-19: the backend links).
   4. **MFA.** TOTP and backup codes on, policy "users may set up MFA" (offered, not forced; 03a P1).
   5. **API resource.** API resources → create, identifier `https://api.pixeltronic.dev`, access token
      lifetime **900** seconds (D-8 C5 found 3600 by default).
   6. **Refresh tokens.** On the app that I-18 will use (Native app): refresh token rotation on.
5. **Management API access.** Applications → Machine-to-machine → create, assign the role with Logto
   Management API access. Put its App ID and secret into `CHANGELENS_LOGTO_M2M_APP_ID` and
   `CHANGELENS_LOGTO_M2M_APP_SECRET` in `/etc/changelens/changelens.env`, then:
   ```bash
   docker compose up -d --force-recreate api worker retention
   ```
6. **Smoke test** (from your PC). Expect `401`, then `200`, then a timeout or refusal:
   ```powershell
   curl.exe -s -o NUL -w "%{http_code}`n" https://api.pixeltronic.dev/projects; curl.exe -s -o NUL -w "%{http_code}`n" https://auth.pixeltronic.dev/oidc/.well-known/openid-configuration; curl.exe -s -m 5 http://<cube-ip>:3002
   ```
   ```bash
   curl -s -o /dev/null -w '%{http_code}\n' https://api.pixeltronic.dev/projects; curl -s -o /dev/null -w '%{http_code}\n' https://auth.pixeltronic.dev/oidc/.well-known/openid-configuration; curl -s -m 5 http://<cube-ip>:3002
   ```
7. **Storage and model reachability** from the worker, through the proxy (no document leaves the server):
   ```bash
   docker compose logs --tail 20 worker
   ```
   ```bash
   docker compose exec egress tail -n 20 /var/log/squid/access.log
   ```
   The worker logs no storage error at start (it checks the bucket); the proxy log shows `TCP_TUNNEL/200`
   only for allow-listed hosts and `TCP_DENIED/403` for anything else. If IONOS rejects the `eu-central-1` signature, record it and stop: the backend's region is fixed.

## D. Backups, restore test and monitoring

**Done 2026-11-16:** backups and WAL shipping run, restore test passed (E), monitor cron set, alert mail received.
Still open: D3's outside uptime check and D4's calendar entry.

1. **Backups run.** Within a few minutes the log shows `started`, `wal shipped=…`, `base backup uploaded`,
   `logto audit entries deleted=…`:
   ```bash
   docker compose logs --tail 30 backup
   ```
   If pruning fails, check the table name once (Logto keeps its audit log in `logs`):
   ```bash
   docker compose exec postgres psql -U postgres -d logto -c '\d logs'
   ```
2. **Restore test** (03 §6; record the date and the `RESTORE OK` line). Put the private key back for the
   test only: paste the password-manager content into the file, run, then delete it. The file belongs to uid 70
   (`postgres` in the backup image), which the test runs as; owned by root it reports the file as missing.
   ```bash
   install -m 600 -o 70 /dev/null /etc/changelens/backup-identity.txt && nano /etc/changelens/backup-identity.txt
   ```
   ```bash
   docker compose --profile tools run --rm restore-test
   ```
   ```bash
   shred -u /etc/changelens/backup-identity.txt
   ```
   The restored copy runs on a local socket inside the test container only, so it can't serve traffic. A
   restore for real must also replay pending deletions before the api starts (data inventory).
3. **Monitor.** Every 10 minutes as root:
   ```bash
   chmod 700 /opt/changelens/deploy/ionos/monitor.sh && (crontab -l 2>/dev/null; echo '*/10 * * * * /opt/changelens/deploy/ionos/monitor.sh') | crontab -
   ```
   Test the alert mail once by stopping a container for 10 minutes (`docker compose stop retention`, then
   `docker compose start retention`). The monitor can't report the server itself being down: add an outside
   uptime check on both domains (a new processor only sees the URLs; record it in the data inventory).
4. **Patch reminder.** A calendar entry: check Logto, PDFium (`pypdfium2`), Caddy, Postgres and Ubuntu
   security releases weekly; apply within 7 days (03 §6).

## E. Evidence for the decision-log row (06)

Record each with its date:

- [ ] A2's IONOS answers (DPA, encryption at rest, region), including support's answer on the Cube volume
- [ ] an uploaded original showing `ServerSideEncryption: AES256`
- [x] the restore test's `RESTORE OK` line: 2026-11-16, `RESTORE OK started=2026-11-16T09:21:57Z
      finished=2026-11-16T09:22:04Z base=20261116T074356Z.tar.age`, schema `0005_limits`; `logto.users rows 1`
      came from WAL replay (the admin account was created after the 07:43 base backup)
- [x] the admin console unreachable from outside: 2026-11-16, `212.132.90.61:3002` timed out; `api` 401,
      `auth` 200 (C6)
- [ ] a one-time code delivered through IONOS SMTP (Logto's test mail, then a real sign-in). 2026-11-16: the
      monitor's alert mail arrived through IONOS SMTP; a real sign-in code is still open
- [ ] the first `logto audit entries deleted=` line
- [ ] after the app signs in (I-18) or S4: a real access token's `exp − iat` = 900, MFA with a test account,
      Google and Apple on S4's path
- [ ] `docs/data-inventory.md`: IONOS SMTP, Logto's database and audit logs, the backup bucket (encrypted,
      30 days), the outside uptime check

## F. Updates

App release:
```bash
cd /opt/changelens && git pull && cd deploy/ionos && docker compose build && docker compose --profile tools run --rm migrate && docker compose up -d
```
Logto upgrade: change the image tag and digest in `compose.yaml`, then run its database alteration before
starting the new version:
```bash
docker compose pull logto && docker compose run --rm --entrypoint sh logto -c "npm run cli db alteration deploy <new-version>" && docker compose up -d logto
```

## Known gaps

- `python -m changelens.api --lan` prints a warning about the dev token at start; it doesn't apply in `logto`
  mode. A `--host` option would remove it.
- `Settings.from_env` in `logto` mode requires the Logto Management credential and the rate-limit key in every
  process, so the worker holds them too, although only the api and retention use them (03 §6 wants them
  limited to those two).
- Secrets reach the processes as environment variables from root-only files, not as files; `docker inspect`
  shows them to root.
- The images' OS packages (`apt`/`apk`) aren't hash-pinned; the base images and Python wheels are.
- Python 3.10 reached end of life in October 2026 (no more security fixes); moving to 3.12 needs new wheel pins.
