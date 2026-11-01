# D-8 Logto check: local kit

Backlog 05 D-8, ADR-0020, AC-26, review items AR-4 and AR-7. A throwaway Logto on this PC answers the five
D-8 questions before anything is deployed on IONOS. Results go into one decision-log row (06). About 2–3 hours.

Use test identities only: an email address you control and a Google account with that same address.
Labels in Logto's console may differ slightly between versions; record what you actually see.

## 0. Start

```powershell
cd scripts\d8-logto
docker compose up -d --wait
```

| Address | What |
|---|---|
| http://localhost:3002 | Admin console. The first visit creates the admin account. |
| http://localhost:3001 | Sign-in pages and OIDC endpoints |
| http://localhost:8025 | Mailpit inbox: every one-time code lands here |

Stop and delete everything afterwards: `docker compose down -v`.

## 1. Set up (about 30 minutes)

1. **Admin account.** Open the console and create the admin account (local only).
2. **Email connector.** Connectors → Email and SMS → **SMTP**. Host `mailpit`, port `1025`, no auth, no TLS,
   from `noreply@changelens.test`. Add a template for each usage type (sign-in, register, forgot password,
   generic) containing `{{code}}`. Send a test email and check that it arrives in Mailpit.
3. **Sign-up and sign-in.** Sign-in experience → Sign-up and sign-in. Identifier: email address. Verification:
   verification code (no password). Sign-in: email with verification code.
4. **Google.** Connectors → Social → Google. You need an OAuth client in Google Cloud (type "Web application"),
   with the redirect URI the connector page shows, for example `http://localhost:3001/callback/<connector-id>`.
   Add Google to the sign-in experience.
   - Apple is **not** tested here: Sign in with Apple needs an HTTPS domain, and v1 uses the native flow with
     the backend code exchange (I-8). Note it as "deferred to the IONOS test instance".
5. **Management API access.** Applications → create a **Machine-to-machine** app, assign the role with
   Logto Management API access, and note its App ID and App secret. In Git Bash:
   ```bash
   ID='<app id>'; SECRET='<app secret>'
   TOKEN=$(curl -s -u "$ID:$SECRET" http://localhost:3001/oidc/token \
     -d grant_type=client_credentials -d resource=https://default.logto.app/api -d scope=all \
     | python -c "import sys,json;print(json.load(sys.stdin)['access_token'])")
   api() { curl -s -H "Authorization: Bearer $TOKEN" "http://localhost:3001/api$1"; echo; }
   api /users | python -m json.tool | head -40     # should list no users yet
   ```
   The token lasts about an hour; run the `TOKEN=` line again when calls return 401.
6. **Version.** `docker compose exec logto sh -c "grep '\"version\"' packages/core/package.json"`. Expect 1.45.0
   (later than 1.37.1; checked when the kit was built).

Use **Live preview** on the Sign-in experience page for every sign-in below: it signs in to Logto's demo app,
which shows the user and their identities afterwards.

## 2. The five checks

### C1. MFA in the open-source edition (ADR-0020; AC-26)

1. Look for **Multi-factor auth** in the console. Record which factors it offers (TOTP, WebAuthn/passkey,
   backup codes, email or SMS codes).
2. Turn on TOTP and backup codes, and set the policy so users must set up MFA.
3. Sign in with email code in Live preview. Record whether Logto asks you to set up TOTP, and whether the next
   sign-in asks for the TOTP code.

**Pass:** at least TOTP plus backup codes work in this image without a licence. **If not**, AC-26 needs an owner
decision before I-8 (ADR-0020).

### C2. Automatic linking is off, and linking needs the existing method (AC-22, AC-26)

1. Find the setting for **automatic account linking** of social identities (Sign-in experience → social
   sign-in, or similar). Turn it **off**. Record its name and default.
2. User A: sign up with your email by code. Note A's user ID: `api "/users?search=%25<your email>%25"`.
3. Sign out. Sign in with **Google** using the same email address.
4. Record exactly what Logto shows: a prompt to link to the existing account, a choice to create a new account,
   or a direct sign-in into A.
5. If there is a link prompt, record whether it **requires** signing in with the email code (and MFA, if on)
   before it links, or whether one click links.

**Pass:** no direct sign-in into A, and a link only after the email code (plus MFA). If Logto's prompt does not
enforce this, record "backend links via Management API" (ADR-0020 fallback); that is a finding, not a blocker.

### C3. Orphan user after `link_required` (AR-4)

1. Repeat C2 step 3, but at the prompt **close the window** without linking.
2. `api "/users"`. Record the number of users and whether a second user now holds the Google identity.
3. If a "create new account" choice was offered in C2, try it once and record the result in the same way.
4. Complete the link once (C2 step 5). Record whether any extra user disappears or stays.

**Record:** whether `link_required` leaves an orphan Logto user, and when it would go away. 03a P1 already plans
to delete it when the link completes or after 1 hour; this check says whether that code is needed.

### C4. Is a link made by Logto's prompt visible to the backend? (AR-7)

1. After a link made through Logto's prompt (C2), run `api "/users/<A's id>"`.
2. Record whether `identities` now contains `google` with its user ID.
3. Sign in again with Google and look at the user details in Live preview. Record whether the subject (`sub`)
   is A's user ID.

**Pass:** the identity shows up on A through the Management API, so the backend can attach the parked Apple token
(AR-7). If it does not, the backend keeps revoking the parked token (safe, as planned).

### C5. Retention and token defaults (03 §6; I-13 data inventory)

Record each default before changing anything:

| Item | Where to look | Record | v1 needs |
|---|---|---|---|
| Access token lifetime | API resources → (create a test resource) → token expiration | default | at most 15 minutes |
| Refresh token lifetime and rotation | Applications → a native app → refresh token settings | default | rotation on |
| Sign-in session lifetime | OIDC or sign-in experience settings, if shown | default | — |
| Audit log retention | Audit logs; then the SQL below | how far back logs go, any setting | stated in I-13 |
| Personal data per user | `api "/users/<A's id>"` and the SQL below | fields stored (email, identities, IP, user agent, timestamps) | listed in I-13 |

```powershell
docker compose exec postgres psql -U logto -d logto -c "select count(*), min(created_at) from logs;"
docker compose exec postgres psql -U logto -d logto -c "\dt"
```

## 3. Record the results

Fill in and paste into the decision log (06) as one row, then tell Claude to commit it:

| Check | Result | Notes |
|---|---|---|
| Version | 1.45.0 | |
| C1 MFA in the open-source edition | pass / fail | factors offered: |
| C2 Automatic linking off; link needs the existing method | pass / fail / backend fallback | what the prompt does: |
| C3 Orphan user after link_required | none / orphan stays / orphan removed on link | |
| C4 Link visible to the backend | yes / no | |
| C5 Defaults | | access token, refresh token, logs, user data |
| Apple | deferred to the IONOS test instance | |

D-8 also covers the IONOS side (03 §1.2 and §6): the server against the minimum spec, Postgres point-in-time
recovery retention, encryption at rest, and the IONOS DPA. Those checks happen on IONOS, not with this kit.
