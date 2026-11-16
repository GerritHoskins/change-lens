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
   2026-11-15:** Cloudflare, DNS only, the Cube's reserved IP.
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
   These are for S4 and step C8 only.

## B. Prepare the server

1. **Harden SSH and the firewall.** Confirm that key login works first. **Done 2026-11-16.** The image's
   `sshd_config` sets `PermitRootLogin no`, so the settings live in drop-ins that load first:
   `/etc/ssh/sshd_config.d/00-changelens.conf` and `01-changelens-nopass.conf`. `sshd -T` shows
   `passwordauthentication no`, and a password attempt is refused with `Permission denied (publickey)`.
   ```bash
   apt update && apt -y full-upgrade && apt -y install unattended-upgrades ufw git age
   ```
   ```bash
   dpkg-reconfigure -plow unattended-upgrades
   ```
   Set `PermitRootLogin prohibit-password` and `PasswordAuthentication no` in a drop-in, which overrides
   the main file:
   ```bash
   printf 'PermitRootLogin prohibit-password\nPasswordAuthentication no\n' > /etc/ssh/sshd_config.d/00-changelens.conf && sshd -t && systemctl reload ssh
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
8. **Native Google and Apple sign-in** (I-8 S4; needs A5 and revision `0006_social_sign_in`, so run F's app
   release first). Never add Google or Apple as a social connector in Logto: the backend does the code
   exchange and links accounts itself, and a Logto connector would bring back Logto's one-click link. The
   C5 role must cover `POST /api/one-time-tokens` and the user endpoints; full Management API access does.
   1. **The folder**, readable by the containers' user (uid 10001) and no one else but root:
      ```bash
      install -d -m 750 -o root -g 10001 /etc/changelens/signin
      ```
   2. **The files.**
      - **Google's web client secret.** Google Cloud no longer shows an existing secret: on the web client
        (Google Auth Platform → Clients), use **Add secret**, copy it with the copy icon, then paste it here,
        at a prompt that shows nothing and keeps it out of the shell history, and press Enter:
        ```bash
        read -rs S && printf '%s\n' "$S" > /etc/changelens/signin/google-client-secret && unset S
        ```
        Check its shape without printing it: one line, `xxxxxx-` and 28 more characters, 36 bytes. An empty
        file or a different length means the paste didn't land:
        ```bash
        sed 's/[A-Za-z0-9]/x/g' /etc/changelens/signin/google-client-secret | cat -A; wc -c < /etc/changelens/signin/google-client-secret
        ```
        Then ask Google directly. `invalid_grant` means the secret is accepted (only the made-up code is
        refused); `invalid_client` means a wrong secret or one from another project's client:
        ```bash
        curl -s https://oauth2.googleapis.com/token -d grant_type=authorization_code -d code=not-a-real-code -d client_id=<google-web-client-id> --data-urlencode "client_secret=$(cat /etc/changelens/signin/google-client-secret)" -d redirect_uri=
        ```
      - **Apple's `.p8` key**, copied from your PC (PowerShell there, not on the server):
        ```powershell
        scp "$env:USERPROFILE\Downloads\AuthKey_<KEY_ID>.p8" root@<cube-ip>:/etc/changelens/signin/apple-signin.p8
        ```
      - **The keyring** for stored Apple refresh tokens (a fresh random 32-byte key), and the owner and mode of
        all three files:
        ```bash
        printf '{"active":"k1","keys":{"k1":"%s"}}\n' "$(openssl rand 32 | basenc --base64url | tr -d '=')" > /etc/changelens/signin/apple-token-keys.json && chown root:10001 /etc/changelens/signin/* && chmod 640 /etc/changelens/signin/*
        ```
        Keep a copy of `apple-token-keys.json` (`cat` it once) in your password manager: without it, stored
        Apple tokens can't be revoked when an account is deleted. To rotate, add a key and move `active`; never
        remove an old one.
   3. **The settings.** Uncomment the Google and Apple lines in `/etc/changelens/changelens.env` (a file made
      from an older template doesn't have them: copy them from `env/changelens.env.example`) and fill in the
      client ID, Team ID and Key ID (all of a provider's lines or none), then:
      ```bash
      docker compose up -d --force-recreate api worker retention
      ```
   4. **Check.** No start error in `docker compose logs --tail 20 api retention`, then a made-up code must be
      refused by the provider: `401` means configured, `422` means that provider is still off, and `503`
      means the provider refused our client ID, secret or key (or couldn't be reached):
      ```bash
      for p in google apple; do curl -s -o /dev/null -w "$p %{http_code}\n" -X POST -H 'content-type: application/json' -d "{\"provider\":\"$p\",\"code\":\"not-a-real-code\"}" https://api.pixeltronic.dev/session; done
      ```
      If the api restarts with `… file cannot be read`, check what the container sees; it must list all three
      files as `0 10001` (the image's user is uid and gid 10001):
      ```bash
      docker compose run --rm --no-deps --entrypoint ls api -ln /run/signin
      ```
      A real sign-in needs the app (I-18); record it in E.

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
- [x] the admin console unreachable from outside: 2026-11-16, `<cube-ip>:3002` timed out; `api` 401,
      `auth` 200 (C6)
- [x] a one-time code delivered through IONOS SMTP (Logto's test mail, then a real sign-in). 2026-11-16: the
      monitor's alert mail and Logto's connector test mail arrived; the app's (I-18) email sign-in code arrived
      at a Gmail inbox. Registration stays off (O-21): Logto answers a code request for an unknown email with
      200 and sends nothing, so owner and test users are added first in the console (User management → Add
      user, email only)
- [ ] the first `logto audit entries deleted=` line
- [x] C8 sign-in configured: 2026-11-16, a made-up code answered `google 401` and `apple 401`; Google's token
      endpoint answered `invalid_grant` with the web client's secret; api healthy, retention without errors
      after the restart. The first start crash-looped (`Google client secret file cannot be read`): the image's
      user had a system group, not 10001, fixed in `changelens.Dockerfile` (commit e191ad5)
- [ ] after the app signs in (I-18) or S4: a real access token's `exp − iat` = 900, MFA with a test account,
      Google and Apple on S4's path. 2026-11-16: `exp − iat` = 900 s on a production token after email sign-in
      (Android, Fairphone 5, debug build's account screen); onboarding saved per step and completed. Google on
      Android: a new account signed in through `POST /session` and Logto's one-time token (audit log
      `Interaction.SignIn.Verification.OneTimeToken.Submit`); Google with the email account's address answered
      `link_required` (the app's "You already have an account")
- [ ] `docs/data-inventory.md`: IONOS SMTP, Logto's database and audit logs, the backup bucket (encrypted,
      30 days), the outside uptime check

## F. Updates

App release:
```bash
cd /opt/changelens && git pull && cd deploy/ionos && docker compose build && docker compose --profile tools run --rm migrate && docker compose up -d
```
Logto upgrade (not part of an app release): change the image tag and digest in `compose.yaml` first, then run
its database alteration before starting the new version. The command reads the version from `compose.yaml`
and stops if it finds none:
```bash
V=$(grep -o 'svhd/logto:[0-9][0-9.]*' compose.yaml | cut -d: -f2) && [ -n "$V" ] && echo "Logto $V" && docker compose pull logto && docker compose run --rm --entrypoint sh logto -c "npm run cli db alteration deploy $V" && docker compose up -d logto
```

## G. Sharing the cube with another site

Only one process can own ports 80 and 443. On the cube, this Caddy also serves `avatar.pixeltronic.dev`
(profile-ai, compose project `deploy`, network `deploy_avatar`). That setup lives on the server only, outside the
repository, so `git pull` never touches it:

| Server file | What |
|---|---|
| `/opt/changelens/deploy/ionos/compose.override.yaml` | Loaded by compose automatically: mounts the files below and joins Caddy to `deploy_avatar` as `172.30.5.2` (the address profile-ai trusts as its proxy) |
| `/etc/changelens/caddy/Caddyfile` | Two lines: `import /etc/caddy/changelens.caddy` (this folder's Caddyfile, global options first), then `import /etc/caddy/avatar.caddy` |
| `/etc/changelens/caddy/avatar.caddy` | A copy of profile-ai's `deploy/Caddyfile` site block |

The global options here (no request details in Caddy's log) cover the avatar site too. A change to the avatar
block: edit `avatar.caddy`, then `docker compose restart caddy`. In profile-ai's `deploy` folder start only
`docker compose up -d app backup`; its own Caddy (`deploy-caddy-1`) is stopped with restart off, and starting
it would clash on the ports and on `172.30.5.2`.

Taking over from another Caddy (done 2026-11-16): a container keeps a fixed network address while stopped, so
disconnect the old one from the shared network before starting this one:
```bash
docker stop deploy-caddy-1 && docker update --restart=no deploy-caddy-1 && docker network disconnect deploy_avatar deploy-caddy-1 && docker compose up -d
```
Back to the old one:
```bash
docker compose stop caddy && docker network disconnect deploy_avatar changelens-caddy-1; docker network connect --ip 172.30.5.2 deploy_avatar deploy-caddy-1 && docker start deploy-caddy-1 && docker update --restart=unless-stopped deploy-caddy-1
```

## Known gaps

- `python -m changelens.api --lan` prints a warning about the dev token at start; it doesn't apply in `logto`
  mode. A `--host` option would remove it.
- `Settings.from_env` in `logto` mode requires the Logto Management credential and the rate-limit key in every
  process, so the worker holds them too, although only the api and retention use them (03 §6 wants them
  limited to those two).
- Secrets reach the processes as environment variables from root-only files, not as files; `docker inspect`
  shows them to root. Only the sign-in secrets (C8) are files.
- The images' OS packages (`apt`/`apk`) aren't hash-pinned; the base images and Python wheels are.
- Python 3.10 reached end of life in October 2026 (no more security fixes); moving to 3.12 needs new wheel pins.
