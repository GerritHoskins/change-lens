# Incident runbook

Task L22 (D-9; 03 §6). What the owner does when personal data or the service is compromised, or may be.

**Status: draft of 2026-11-18. Not rehearsed, and not legally reviewed.** Section 10 lists what is still
missing. The commands are for the IONOS deployment of [`deploy/ionos/README.md`](../deploy/ionos/README.md)
("the runbook" below). Every command block says where it runs: **Server** is the cube over SSH, **Local** is
the owner's PC.

## 1. What counts

| Kind | Examples |
|---|---|
| Personal data breach (GDPR Art. 4(12)): a security breach that leads to the destruction, loss, alteration, unauthorised disclosure of, or access to, personal data | One account sees another account's project. A stolen server login. A backup or database copy outside the owner's control. Lost data that no backup restores. A leaked key that gives access to the database, the document bucket or Logto |
| Security incident without a known breach yet | A secret in a commit (GitGuardian alert). An unexpected sign-in to the server, GitHub, IONOS, Codemagic, Apple or Google account. Unexplained model costs. A dependency with a published exploit for something the server exposes |
| Outage only | The server or a container is down and no data left the system. Follow the runbook, not this file |

When in doubt, treat it as a breach until section 4 says otherwise. The personal data held is listed in
[`data-inventory.md`](data-inventory.md): email addresses and sign-in records in Logto, and the documents,
quotes and review notes users import, which can name their clients.

## 2. Who is told, and by when

At launch the owner is the controller for all of it (privacy policy, section 1). There is one person: the
owner decides, acts and notifies.

| Who | When | Deadline | How |
|---|---|---|---|
| The data protection authority of the owner's federal state | Every personal data breach, unless it is unlikely to result in a risk to the people affected | 72 hours after becoming aware (Art. 33(1)). Later only with the reasons for the delay. Facts that are still missing can follow in stages (Art. 33(4)) | The authority's online breach form. Its name and address are filled in with L23, from the same entry as the privacy policy |
| The affected users | The breach is likely to result in a high risk to them (Art. 34), for example readable documents or a usable session reached someone else | Without undue delay | Email to the address the account signs in with, in plain language: what happened, what it can mean for them, what was done, what they should do, and the contact address (Art. 34(2)) |
| A business customer with a processor agreement (Art. 28) | Any breach that touches their data | Without undue delay (Art. 33(2)), so they can meet their own 72 hours | The contact named in the agreement. None exists at launch; this row applies from the first such agreement |
| IONOS | Their server, object storage, model service or mailbox is involved, or their logs are needed | At once | The IONOS customer account's support channel |
| Apple, Google, GitHub, Codemagic | A signing key, the Sign in with Apple key, the Google client secret or an account of theirs is exposed | The same day | Revoke and reissue in the respective console |

"Aware" means reasonably certain that personal data was compromised, not the first suspicion (EDPB
Guidelines 9/2022 on breach notification). Write down the time of that moment: the 72 hours run from it.
A short first look to reach that certainty is allowed; waiting is not.

Nothing is published and no user is told before sections 3 and 4 are done, except where waiting would harm
them.

## 3. First hour: keep the evidence, then contain

Log in first.

**Local** (PowerShell):

```powershell
ssh root@<cube-ip>
```

**Server**, in this order. Step 1 comes before any restart: recreating a container discards its log.

1. Save the logs:
   ```bash
   D=/root/incident-$(date -u +%Y%m%dT%H%MZ) && mkdir -m 700 "$D" && cd /opt/changelens/deploy/ionos && docker compose logs --no-color --timestamps > "$D/compose.log" && docker compose ps -a > "$D/ps.txt" && echo "$D"
   ```
2. Save who signed in to the server:
   ```bash
   last -Faiw > "$D/last.txt"; journalctl -u ssh --since "-14 days" --no-pager > "$D/ssh.log"
   ```
3. Contain, with the smallest step that stops the harm:

   | Situation | Command | Effect |
   |---|---|---|
   | Data may be reaching someone it shouldn't | `docker compose stop caddy` | Everything is offline at once, including the other site this Caddy serves (runbook G) |
   | Only the API is in doubt | `docker compose stop api` | The app shows a connection error; sign-in pages still load |
   | Model costs run away | `docker compose stop worker` | No model call is made; comparisons wait in the queue. To keep the worker for parsing only, set `CHANGELENS_GLOBAL_SPEND_CAP_EUR=0` in `/etc/changelens/worker.env` and `/etc/changelens/changelens.env` and run `docker compose up -d` instead |
   | A deletion or retention run misbehaves | `docker compose stop retention` | No scheduled deletion runs; restart it within a day, because deletions that are due then wait |

   Do not run `docker compose down` and do not rebuild until section 4 is done.

4. Replace every secret that may have been read. Each has its own row in section 8.

An access token that was already issued stays valid until it expires, at most 15 minutes later. Stopping
`api` is the only immediate cut for all sessions.

After replacing Logto's signing keys, restart `api` (`docker compose restart api`): it keeps the old key
set until a token with an unknown key arrives (L22, LR-20).

## 4. Assess, within 24 hours

Answer these in the incident record (section 6). "Not known yet" is an answer; say when it will be known.

1. What happened, and when did it start and stop?
2. Which stores of the data inventory were reachable: the application database, Logto's database, the
   document bucket, the backup bucket, the server's disk, a device?
3. Which accounts and how many? Whose data else, such as clients named in a brief?
4. Could the data be read (unencrypted, or with a key that was also exposed), changed, or only lost?
5. Is it still going on?
6. What is the likely consequence for the people affected?

Where the facts are:

| Source | What it shows | Limit |
|---|---|---|
| `compose.log` from section 3 | Method, route template, status and IDs per request; job and model-usage lines. No document text | Gone when a container is recreated |
| Logto audit log (table `logs` in the `logto` database) | Sign-in and verification events with user ID, IP address and user agent | Entries older than 30 days are deleted daily |
| The application database | Which projects, sources and comparisons exist, with their timestamps and the deletion receipts | Shows state, not who read what |
| IONOS customer account | Logins to the account; object storage settings | Depends on what IONOS records |
| HetrixTools | When the two public addresses were up or down | Nothing about content |
| GitHub and GitGuardian | Pushes, workflow runs, secret alerts | — |

No document content goes into the incident record or into a message to anyone. Counts, IDs and times are
enough.

## 5. Decide and notify

| Finding from section 4 | Authority | Users |
|---|---|---|
| No personal data was reachable | No. Record the reasoning (section 6) | No |
| Data was reachable, but only encrypted, and the key was not exposed (for example a copy of an `age`-encrypted backup) | Usually no: unlikely to result in a risk. Record the reasoning | No |
| Account data or documents of at least one user were readable by someone else, or were lost for good | Yes, within the 72 hours | Yes if the risk to them is high: readable documents, or a session or sign-in someone else could use |
| Unsure after 24 hours | Yes, as a first notice in stages | Decide again when the facts are in |

The notice to the authority contains (Art. 33(3)): what happened, with the kinds and rough numbers of people
and records; the contact address for questions; the likely consequences; what was done and what is planned.

## 6. The record

Every breach is recorded, also one that isn't notified (Art. 33(5)). One dated file per incident, in the
owner's private documents folder beside the decision log (06). It is never committed to this public
repository. The 06 row for the incident links to it.

Fields: when the owner became aware and how; the answers of section 4; the decision of section 5 with its
reasons; who was notified, when, and a copy of each message; every containment and recovery step with its
time; what changes afterwards.

The folder from section 3 is the evidence. Copy it to the PC, into the same private folder, then delete it
from the server.

**Local** (PowerShell; replace `<folder>` with the name the server printed and `<private-folder>` with the
folder that holds 06):

```powershell
scp -r root@<cube-ip>:/root/<folder> "<private-folder>\incidents\"
```

**Server:**

```bash
rm -rf /root/<folder>
```

The logs contain IP addresses and account IDs, so they are personal data themselves: keep them as long as
the incident is open and the authority may ask, then delete them. The record stays.

## 7. Recover

1. Fix the cause, or remove the exposed path, before anything goes back online.
2. If data was changed or lost, restore from the backups: runbook D2 describes the restore. A restore for
   real must replay the deletions that happened after the backup before `api` starts
   ([`data-inventory.md`](data-inventory.md), backup row), or deleted documents and accounts come back.
3. Bring the services back.

   **Server:**
   ```bash
   cd /opt/changelens/deploy/ionos && docker compose up -d && docker compose ps
   ```
4. Check from outside: the HetrixTools monitors are green, and a test account signs in and opens a project.
5. Complete the record and the notices that were sent in stages.

## 8. Secrets and where each is replaced

Replace a secret when it was, or may have been, readable. After changing a file in `/etc/changelens/`,
restart the services that read it (`docker compose up -d`).

| Secret | Kept in | Replaced where | Note |
|---|---|---|---|
| Server login (SSH key, root) | The owner's PC | IONOS console and `~/.ssh/authorized_keys` on the server | Check for unknown keys and users first |
| Postgres passwords (superuser, owner, app, Logto, backup) | `postgres.env`, `admin.env`, `changelens.env`, `worker.env`, `logto.env`, `backup.env` | `ALTER ROLE … PASSWORD` in Postgres, then the files | Each of the six files names one or more of them. The backup role's: change it in `postgres.env` and `backup.env`, run `docker compose up -d`, then the role script (runbook F) |
| Object storage keys (documents; backups) | `changelens.env` and `worker.env`; `backup.env` | IONOS console | Each side's key belongs to an IONOS user of its own, let into one bucket by a bucket policy (`deploy/ionos/one-off-releases.md`, "Separate storage keys"; on the server since 2026-11-19, LR-13). The account owner's key reaches both buckets and is kept off the server |
| Model key `IONOS_API_TOKEN` | `worker.env` | IONOS console | Only the worker reads it |
| Logto Management credential | `changelens.env` | Logto console, the machine-to-machine app (runbook C5) | It can link identities and delete users. The api and retention read it; the worker doesn't start when it is given it |
| `CHANGELENS_RATE_LIMIT_KEY` | `changelens.env` | A new random value | Counters start again |
| Google client secret, Apple `.p8` key | `/etc/changelens/signin/` | Google Cloud console; Apple Developer account (runbook C8) | Revoke the old Apple key there |
| Apple-token keyring | `/etc/changelens/signin/apple-token-keys.json` | Add a new key and keep the old ones for decryption (03 §6) | Removing an old key makes stored tokens unreadable |
| Backup key (`age`) | The private half is in the owner's password manager, never on the server | A new key pair; the public half goes into `backup.env` (runbook B6) | Backups made before stay readable with the old key only; they expire after 30 days |
| Mail password | `monitor.env` and Logto's mail connector | IONOS mail settings | — |
| GitHub, Codemagic, IONOS, Apple and Google account logins | The owner's password manager | Each account's security page | Also end other sessions and check access tokens there |
| App signing keys (Android upload key, Apple distribution certificate) | Codemagic | Play Console key reset; Apple Developer account | A new Android upload key needs Google's support |

## 9. Afterwards

Within 14 days of closing the incident: add a row to [`review-ledger.md`](review-ledger.md) (the fault and
its fix, without personal data), update the data inventory if a store or processor behaved differently from
its row, and correct this runbook where it was wrong or slow.

## 10. Still missing

- The supervisory authority's name, its breach form and its phone number (with L23; the privacy policy has
  the same open entry).
- The contact address users are given (the privacy mailbox of L23).
- A rehearsal: walk through sections 3 to 6 once with an invented incident, and time it.
- The legal review's view of sections 2 and 5 (L4). This file is not legal advice.
- Whether IONOS records access to the object storage buckets, and how to get those records.
