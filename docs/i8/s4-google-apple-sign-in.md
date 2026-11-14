# I-8 S4: Google and Apple sign-in

Part of [I-8 in slices](README.md). Needs S2 and S3 merged. Check `git status` and HEAD first. This slice
has a **stop point** after step 0.

## 1. Goal

Add the two social sign-in methods as decided:

- **Apple** is native (ADR-0020). The backend exchanges the authorization code with Apple and keeps the
  Apple refresh token, encrypted, so account deletion can revoke it (03a P1, P8; AR-1 to AR-6).
- **Google** is native too, with a backend code exchange (O-19). Logto's own link prompt is never used,
  because D-8 C2 showed it links in one click without the existing method.
- A Google or Apple identity whose verified email matches an existing account gets `link_required`. The
  backend links it through the Logto Management API only after the user signs in with their existing
  method (03a P1, SA-3). A matching email alone never links (AC-26).

## 2. Step 0: how a native credential becomes a Logto session (time-boxed, half a day)

Nothing in the repository answers this yet, and D-8 deferred Apple to an HTTPS instance. The constraint:
**an Apple authorization code can be exchanged once**. If Logto exchanges it, the backend never sees the
refresh token and can't revoke it; if the backend exchanges it, Logto must accept what the backend got (for
example Apple's ID token) to create or find the Logto user and issue our API access token.

Using the local Logto in `scripts/d8-logto` (1.45.0, Google configured as in its CHECKLIST), find and
document the supported path. Candidates to check, in Logto's own documentation and by trying them:

- Logto's Experience API social verification with connector data the backend supplies (an ID token rather
  than a code);
- a token-exchange grant;
- anything else Logto documents for native social sign-in.

For each: whether Logto accepts a backend-verified ID token, whether it then issues an access token for
our API resource, whether it would auto-link by email (it must not), and which Logto version supports it.

**Stop here and report** if the only working path needs any of these, because each changes an accepted
decision and is the owner's call:

- a second route outside GUARD besides `POST /session` (I-8 acceptance says only `POST /session`);
- Logto doing the Apple code exchange (no backend refresh token, so no revocation, against ADR-0020);
- Logto's own link prompt (against O-19).

Apple can only be checked end to end on an HTTPS domain. If S7's test instance isn't up, check Google
locally, check Apple against Logto's documentation and a fake, and say which parts weren't tried live.

## 3. Build (after step 0, on the path it found)

**Code exchange.** Server-side clients for Apple (`/auth/token`, client secret signed with the `.p8` key)
and Google (token endpoint, server auth code). Verify the returned ID token's signature against the
provider's published keys, issuer, audience (our client IDs), expiry and nonce where the flow has one.
Take the email and `email_verified` only from that verified token. Secrets come from files named by the
environment (03 §6 Secrets).

**Linking** (03a P1, O-19):

1. If the identity is already on a Logto user, sign in as that user. Done.
2. If a Logto user has the same **verified** email (Management API lookup; no local email copy, overview
   decision 5), don't sign in and don't create a user. Create a pending link (provider, provider subject,
   target Logto user ID, expiry 1 hour; and the parked Apple token if any) and return `link_required`
   with the existing user's sign-in methods. Store no email.
3. The user signs in with an existing method (email code, plus TOTP when they have MFA on) and calls
   `POST /session` with the pending link's ID. The backend checks that the authenticated subject **is** the
   target user, then links the identity through the Management API. Any mismatch, expiry or reuse is
   `401 unauthenticated`, and the pending link is deleted.
4. Otherwise, create the account as in S2.

D-8 C3 found that Logto leaves no orphan user, so there's no orphan cleanup. C4 showed the link is
visible through the Management API, so the next Google or Apple sign-in returns the existing subject.

**Apple refresh token.** Encrypt with `auth/apple_tokens.py` `AppleTokenCipher` (binding the user ID, or
the provider subject while parked). Store it on the user once a user row exists (AR-2). While no user row
exists, park it in a table with a 1-hour expiry (AR-5). A maintenance job revokes expired parked tokens with
Apple and deletes them, retrying with backoff and keeping the record until Apple confirms (AR-6). The
keyring comes from a secret file; key rotation keeps old keys for decryption.

**Responses.** `POST /session` adds `status: "link_required"` with `methods` (for example `["email"]`) and
a `link_id`. Keep the rest of S2's response unchanged.

The Logto Management API credential can link identities and delete users, so it's read only by the `api`
and `retention` modules (03 §6) and never logged.

## 4. Plan documents to update

| File | Change |
|---|---|
| `docs/03-technical-design.md` §5, §6, §9.4 | `User.apple_refresh_token_enc`; the parked-token and pending-link records; the `POST /session` fields; any route step 0 required (only with the owner's approval) |
| `docs/03a-pipeline-logic.md` P1 | The flow as built, if it differs in detail from the pseudocode |
| `docs/data-inventory.md` | Parked Apple tokens and pending links: what they hold, expiry, deletion |
| `docs/06-decision-log.md` | Step 0's finding (its own row), then one change-log row for the build |

## 5. Out of scope

App screens and the native Google and Apple SDK calls in Flutter (I-18), account deletion (S5; but leave
the Apple revoke function ready for it), rate limits on these paths (S6), IONOS setup (S7).

## 6. Tests

No test reaches Apple, Google or Logto over the network: use `httpx.MockTransport` fakes.

1. **Code exchange**: a valid fake response signs in; a bad signature, wrong audience, wrong issuer,
   expired token, missing or unverified email, and a reused Apple code each fail without creating anything.
2. **Linking**: an existing verified-email match returns `link_required` and creates no user; completing
   the link as the target user links it once; completing as another user, after expiry or twice fails and
   deletes the pending link; an unverified email never matches.
3. **Apple token**: stored encrypted on the user after the first sign-in; parked when no user row exists
   and attached when the link completes; the expiry job revokes and deletes; a failed revoke keeps the
   record and retries.
4. **No leaks**: no response, log line or error body contains a code, token, provider subject or email.
5. **Gates**: backend unit and integration tests and `./scripts/ci.ps1` pass.

## 7. Receiving-agent prompt

> Work in the ChangeLens checkout on `m1-iphone`, with I-8 S1–S3 merged. Verify `git status` and HEAD.
> Read `docs/i8/README.md` and `docs/i8/s4-google-apple-sign-in.md`, then ADR-0020, the D-8 and O-19 rows in
> 06, 03 §5, §6 and §9.4, 03a P1 and P8, review-ledger items SA-3 and AR-1 to AR-7,
> `scripts/d8-logto/CHECKLIST.md`, `backend/changelens/auth/` and the S2 session code. Do step 0 first and
> stop with a written finding if the only path needs a decision listed there. Otherwise build Google and
> Apple sign-in, backend-owned linking and Apple token storage as specified, with no new dependency. Don't
> build app code, deletion routes or rate limits. Don't commit or push. Write the §6 tests, run the backend
> unit and integration tests and `./scripts/ci.ps1`, and return the evidence the overview lists or a
> precise blocker.
