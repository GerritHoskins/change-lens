# Security review before launch

Task L22 (D-9). The findings of the review of 2026-11-18, with their state. Fixed findings also have a row
in [`review-ledger.md`](review-ledger.md); open ones get theirs when they are fixed or accepted. The tasks
named here are in [`tasks/launch-todo.md`](../tasks/launch-todo.md). The incident runbook is
[`incident-runbook.md`](incident-runbook.md).

## Review of 2026-11-18

Method: four read-only reviews of the code on `main` (tenancy and sign-in; documents, model and queue;
logging, secrets and deployment; the mobile app), each finding then checked against the code. Nothing was
checked on the server or on a device. No way was found for one account to read or change another's data, no
route without authentication, no secret in the repository and no SQL built from input.

Fixed in the same change (rows in [`review-ledger.md`](review-ledger.md)): LR-1 (high), LR-2 (medium), LR-5 to LR-9 (low). Fixed afterwards: LR-3 (task L31, 2026-11-18), LR-4 (task L32, 2026-11-18) and LR-12 (2026-11-19); LR-4 and LR-12 take effect on the server with the releases in runbook F.

Medium, open unless the last column says fixed:

| ID | Finding | Checked how | Next |
|---|---|---|---|
| LR-3 | A deleted account can be re-created: deletion clears the sign-in subject, and a token issued before the deletion stays valid for up to 15 minutes. `POST /session` with it creates a new account that nobody can sign in to or delete afterwards | Read in `0004_account_deletion.py`, `0003_rls.py` and `api/session.py` | Fixed in task L31: before a first sign-in creates an account, the api asks Logto whether the user still exists |
| LR-4 | The worker holds the Logto Management credential and can reach Logto directly, although 03 §6 limits both to the api and retention. The PDF parser runs with resource caps but the worker's user and network, so a parser exploit would reach every account. Listed as a known gap in the runbook | Read in `compose.yaml`, `config.py` and `pipeline/sandbox.py` | Fixed in task L32: the worker reads its own env file and doesn't start with the credential, Logto is on no network the worker is on, and the parse child can't read the worker's environment or memory or start a process. The child keeps the worker's network, without a credential |
| LR-10 | No bound per account on uploads, stored bytes or queued work, and one worker serves one queue in order: one account can keep everyone else waiting and fill the disk without any model cost. Uploads are also held in memory with no limit on how many run at once | Read in `api/routes.py`, `api/comparisons.py`, `api/app.py`; the remaining cost of one hostile comparison was measured at about 3 s | Task L33 |
| LR-11 | Android: signing out relies on a private browser tab, which the pinned plugin requests but the phone's browser may not honour. Where it doesn't, "Continue with email" after sign-out can enter without a code | Read in the plugin source (`flutter_web_auth_2` 5.1.0) and `auth/logto.dart` | Task L34 |
| LR-12 | Logto's own output records request lines, which carry email addresses and one-time sign-in tokens in query strings | Server check of 2026-11-19: 24 such lines in Logto's log. Reproduced in Docker with the pinned image: Logto prints every request line with its full query string | Fixed 2026-11-19: Logto's output passes through `deploy/ionos/logto/log-filter.awk`, which drops the query string of a request line and masks email addresses before Docker stores the line. Checked in Docker: no test value left in the log, a stop still takes under a second, a crash message still arrives, and without the filter file Logto doesn't stay up. Not reviewed: what else Logto may print |
| LR-13 | The backup job connects as the Postgres superuser and has unrestricted internet access. If the documents bucket and the backup bucket share one key, each key can read or delete the other's objects | Read in `backup.env.example` and `compose.yaml`. Server check of 2026-11-19: both sides use the same key | Partly fixed in task L32: the job connects as its own role, which may take base backups and call one function that prunes Logto's audit log. Still open: the shared key, which the owner replaces by one IONOS user and one bucket policy per side (runbook F, "Separate storage keys"; on 2026-11-19 both users, their keys and both bucket policies were set up at IONOS, and the server still runs on the owner's key until the new keys are entered and pass the runbook's check), and the job's internet access |

Server checks for the owner (results go into the table above):

**Local** (PowerShell):

```powershell
ssh root@<cube-ip>
```

**Server:**

```bash
cd /opt/changelens/deploy/ionos && docker compose logs logto | grep -c -E 'login_hint|primaryEmail|one_time_token'
```

```bash
grep -c '^CHANGELENS_TRUSTED_PROXIES=' /etc/changelens/changelens.env
```

```bash
A=$(grep '^CHANGELENS_S3_ACCESS_KEY=' /etc/changelens/changelens.env | cut -d= -f2); B=$(grep '^RCLONE_CONFIG_IONOS_ACCESS_KEY_ID=' /etc/changelens/backup.env | cut -d= -f2); [ "$A" = "$B" ] && echo "same key" || echo "different keys"
```

Expected: `0` (LR-12 does not apply), `1`, and `different keys`. The last command compares the two key IDs
without printing them. Results of 2026-11-19, before the release with task L32: `24`, `1` and `same key`, so
LR-12 and LR-13 both apply. Repeat the first command after the release with the log filter and the third
after the key split.

Open, low. Each is fixed, scheduled or accepted by the owner before L22 closes:

| ID | Finding |
|---|---|
| LR-14 | The egress proxy matches an allowed host name by reverse DNS for a raw IP address, so a compromised worker could tunnel to its own server. Fix: `dstdomain -n` in `squid.conf`, tested against the pinned image |
| LR-15 | A failed restore test or an interrupted base backup can leave an unencrypted database copy in a local volume |
| LR-16 | An exception outside the request and job handlers prints a full traceback, past the log scrubber |
| LR-17 | A point-in-time restore brings back accounts and projects deleted after that time, and nothing outside the database records those deletions (data inventory, backup row) |
| LR-18 | Start-up accepts an `http://` storage endpoint, a missing trusted-proxy setting and the development rate-limit key in deployed mode |
| LR-19 | No container but the worker (since task L32) drops capabilities or sets `no-new-privileges`; Caddy, Logto and the proxy run with image defaults; retention sees the Google secret it never uses |
| LR-20 | A removed Logto signing key stays trusted until a token with an unknown key arrives. The incident runbook now says to restart the api after a key change |
| LR-21 | Logto's Management API is reachable through the public address; a token protects it |
| LR-22 | `user_by_identity` trusts Logto's filter without checking that the returned user holds the identity; `user_by_email` does check. Not changed blind: the shape of Logto's answer has to be confirmed first |
| LR-23 | Google and Apple sign-in create accounts while registration is described as off (O-21). Owner's intent decides |
| LR-24 | Android: the app-switcher cover depends on timing; nothing sets `FLAG_SECURE` or disables the recents screenshot |
| LR-25 | The sign-in redirect uses a custom scheme, so a malicious Android app could imitate the app's sign-in. PKCE and the state check stop plain code theft |
| LR-26 | A request that times out but succeeds on the server is shown as a definite failure (consent, account deletion) |
| LR-27 | 03a P10 says documents are cleared from memory when the app goes to the background; the app only shows the cover |
| LR-28 | The iOS build carries the local-network allowance and its usage text for the development server; release builds don't check that the server addresses are `https` |
| LR-29 | The model-written explanation, shown as a finding's headline, is checked only for numbers and removal words, so text in the newer brief can steer its wording |
| LR-30 | A sentence that occurs twice and loses one copy produces no finding and no unexplained difference; the block counts as moved |
| LR-31 | Text drawn as vector outlines or as an annotation on a page that has a text layer is neither read nor warned about |
| LR-32 | A model request the provider rejects keeps its cost reservation, and a text block longer than one request is not split; a few accounts could reach the global spend cap with reservations alone |
| LR-33 | Another site shares the parent domain and the same Caddy; its configuration is on the server only and was not reviewed |

Not covered: Logto's own configuration and behaviour, the live server (file modes, firewall, bucket
policies), plugin internals beyond the browser plugin, and known-vulnerability data for the pinned versions
(the weekly audit covers Python).
