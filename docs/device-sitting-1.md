# Device sitting 1: iPhone

The owner's checklist for the iPhone half of task L13, with the phone checks of L27 and L28
([`tasks/launch-todo.md`](../tasks/launch-todo.md)). One sitting against the IONOS server, with synthetic
documents only. Button names are the English ones.

Fill in the `Result:` line of every step: the date, pass or fail, and what you saw. A fail becomes its own
task. The last section says where each result is recorded afterwards.

## Before you start

**Codemagic (browser)**

- [x] Build `ios-device-check` from `main` at `7e8f09a` or later, and note the build number.
      Result: 2026-11-20, pass. Build 5, started 09:44 CET from `main` at `96a77c1`, finished in 4m 44s.

**Logto console (PC browser at `http://localhost:3002`, through the SSH tunnel of runbook C4)**

- [x] Account A exists: User management → Add user, email only. Use a Gmail address you can read on the
      iPhone. Registration is off, so the email code only arrives for a user that exists.

**iPhone**

- [x] Install the build from Codemagic's install link.
- [x] Two synthetic PDFs with a text layer are in the Files app (an earlier and a newer brief).
- [x] An authenticator app is installed, for the MFA step.
- [x] The Google account of account A's address is signed in on the phone, and the phone has an Apple ID.

## 1. First launch and email sign-in (iPhone)

- [x] The sign-in screen shows three buttons in this order: Continue with Apple, Continue with Google,
      Continue with email.
      Result: 2026-11-20, pass. Screenshot at 10:22: the three buttons in this order, and under them "We email
      you a one-time code. No password."
- [x] Continue with email → enter account A's address on Logto's page → enter the code from the mail. The
      app opens the first-run onboarding.
      Result: 2026-11-20, pass. The code arrived and the app opened the onboarding.
- [x] MFA: if Logto's page offers to set up two-step verification, set it up with the authenticator app. If
      it doesn't offer it, write that down; it is then a finding.
      Result: 2026-11-20, pass. Logto offered two-step verification after the email code, and it was set up
      with the authenticator app. The Logto console lists an authenticator app and backup codes for the
      account.

## 2. Consent screen (iPhone)

- [x] After the onboarding, the screen "Share usage events?" appears, with Allow and Don't allow, nothing
      preselected and no Back. Tap **Allow**.
      Result: 2026-11-20, pass.
- [x] Close the app from the app switcher and open it again. The consent screen does not come back.
      Result: 2026-11-20, pass.
- [x] Menu (top right) → Settings → Privacy: "Share usage events" is on. Turn it off, leave Settings, open
      it again: it is still off.
      Result: 2026-11-20, pass.

## 3. A PDF comparison from the picker (iPhone)

- [x] New project → name it. Then **Compare two briefs** at the bottom of the project list, and choose the
      project.
- [x] Earlier version: Pick a PDF → label → Pick a PDF → choose the earlier PDF in Files. Newer version: the
      same with the newer PDF.
      Result (did the iOS picker open and return the file?): 2026-11-20, pass. The picker opened and returned
      both PDFs.
- [x] Answer "What is the newer version?" and tap **Start comparison**. The status screen ends at Complete
      and offers **Open report**. This also proves the worker reaches the model through the egress proxy.
      Result (time from Start to Complete): 2026-11-20, pass. About 1 minute by the clock. The api log shows
      the start at 09:51:34 UTC (`POST /projects/{project_id}/comparisons 202`) and the last status request
      at 09:52:00 UTC, with no error status. The worker's log: two parse jobs, four model calls (all `ok`) and
      "complete: 1 findings, 0 withheld, 0 unexplained", at a cost of about 0.005 of the 1.50 ceiling.
- [x] Open report → open a finding → tap a quote. The PDF page opens with the passage highlighted, and the
      card said "Highlight located". Switch to **Readable text** and back.
      Result: 2026-11-20, pass.
- [x] The M1b exit check, as worded in 05 (private): confirm one finding, correct one, dismiss one, add a
      note, and record a client approval.
      Result: 2026-11-20, pass. The report had one finding, so confirm, correct and dismiss were done on it in
      turn; the note and the client approval were recorded too.

## 4. Field messages and the kept draft (L27; iPhone)

- [x] In the project: Paste text → tap **Import** with both fields empty. A message appears under each field,
      and the sheet stays open.
      Result: 2026-11-20, pass.
- [x] Turn on Airplane mode. Paste text → label and text → Import. The sheet opens again with your label, your
      text and the reason. Turn Airplane mode off and tap Import: the version appears once.
      Result: 2026-11-20, pass on the repeat. With the label `retest-1`: the import in Airplane mode reopened
      the sheet, and one tap afterwards gave one version and one `POST /projects/{project_id}/versions 201`
      in the api log (11:06:40 UTC). The first run had no such request in the log.
- [x] Settings app → Accessibility → Display & Text Size → Larger Text, largest size. Repeat the empty
      Import. The message under Label is readable next to the character counter. Set the size back.
      Result: 2026-11-20, pass.

## 5. Background and VoiceOver (L28; iPhone)

- [x] Start a second comparison. On the status screen go to the Home screen, wait a minute, and return. The
      status catches up within a few seconds.
      Result: 2026-11-20, pass.
- [x] Turn VoiceOver on (Settings app → Accessibility → VoiceOver). Open a quote in **Readable text**:
      VoiceOver says "Marked passage: …" before the page text.
      Result: 2026-11-20, pass.
- [x] Switch to **PDF page**: VoiceOver says "PDF page N. Marked passage: …".
      Result: 2026-11-20, pass.
- [x] With VoiceOver still on, repeat the empty Import from step 4. The first field message is spoken once,
      not twice.
      Result: 2026-11-20, pass.
- [x] Turn VoiceOver off.

## 6. Google and the account link (iPhone)

- [x] Menu → Settings → **Sign out**. The sign-in screen says "You're signed out."
- [x] Continue with Google, with account A's Gmail address. The app shows "You already have an account" and
      offers only Continue with email.
      Result: 2026-11-20, not testable as set up. Google signed in directly, into another account: Logto
      holds an older test user (created 2026-11-18) that this Google identity is linked to and that has no
      two-step verification, so no link step and no authenticator code were due. Account A (created today,
      two-step verification on) has no Google identity, and its address is not the Google account's, so the
      link step can't arise with it. To be repeated once the older test user is gone and account A carries
      the Google account's address.
      Repeat, 2026-11-20, with the Google identity no longer linked to any user: Google's own sheet appeared three times, then the app showed "You already have an account"
      with Continue with email and a button for another method: pass. The api log has `social sign-in:
      link_required` with `POST /session 200` at 15:44:10 and 15:45:20 UTC. Three Google sheets for one
      sign-in is a finding of its own.
      Second repeat, 2026-11-20, pass, now with account A: the linked test user was deleted in the app
      (`DELETE /me 204` at 16:05:38 UTC), account A got the Google account's address in the Logto console,
      and Continue with Google gave `social sign-in: link_required` at 16:07:02 UTC.
- [x] Continue with email → code (and the authenticator code, if MFA is set up). You are signed in.
      Result (was the authenticator code asked for?): 2026-11-20, in part. A later email sign-in as account A
      (11:02:38 UTC, `POST /session 200` in the api log) asked for the authenticator code after the mail
      code. That it completes a pending Google link is untested (see the step above).
      Repeat, 2026-11-20, pass: the email sign-in after the link screen signed in, and the api log has
      `social sign-in: identity linked` with `POST /session 200` at 15:55:51 UTC. Logto did not ask for an
      authenticator code; it offered to set up two-step verification, and that was skipped. The app then
      showed the onboarding and the consent screen again (`PUT /me/onboarding 200` and `PUT /me/consent 200`
      at 15:57 UTC). So the Google identity was linked to a user without two-step verification that had not
      been through the onboarding, not to the account of steps 1 to 5. The user list afterwards confirms it:
      the link went to a test user created on 2026-11-16 that had never signed in before. The older test
      user of 2026-11-18 is gone, and account A still has its own address, no Google identity and its two
      two-step factors.
      Second repeat, 2026-11-20, pass, with account A: `social sign-in: identity linked` at 16:08:10 UTC.
      The user list afterwards shows account A with the Google identity and its two two-step factors, and
      the test user of 2026-11-16 gone.
- [x] Sign out. Continue with Google again. This time it signs in directly. Settings says "Signed in with
      Google", with account A's address, and the project from step 3 is there.
      Result (was the authenticator code asked for with Google?): 2026-11-20, **fail**. Google's own sheet
      appeared twice, then the app stayed on the sign-in screen with "You're signed out." and "Sign-in didn't
      work. Try again, or choose another method." (screenshot at 11:20). The logs: five Google sign-ins got a
      one-time token (10:16:18 to 10:19:39 UTC). The first two opened Logto's page and were signed in within
      two seconds, into the older test user. After the last three the app never requested Logto's page
      (10:18:53: token issued, no `GET /oidc/auth`), so the fault is in the app, between receiving the token
      and opening the sign-in browser. Whether Logto asks for the authenticator code with Google is untested.
      Repeat, 2026-11-20, in part: Google signed in directly, without the link screen (api log: "one-time
      token issued" at 15:58:24 UTC and the signed-in `POST /session 200` at 15:58:25). It signed in to the
      user linked in the step above, which has no projects and no two-step verification, so the project
      from step 3 was not there and no authenticator code was due. Whether Logto asks for the authenticator
      code with Google stays untested. Google's own sheet appeared twice. Settings said "Signed in with
      Google" and showed the line "Your sign-in is stored on this iPhone only. …", so that line is also
      there after the reinstall and a new sign-in (task L29).
      Second repeat, 2026-11-20, with account A: Continue with Google got a one-time token at 16:08:49 UTC
      without the link screen, and **Logto asked for the authenticator code** (the owner's report). So a
      Google sign-in to an account with two-step verification is asked for the second factor. After the
      code the owner was signed in and the project from step 3 was there (the owner's report; the pasted log
      ends at the token). Pass on this repeat. The failed sign-ins of the morning and the repeated Google
      sheet stay findings, each with its own task.
- [x] Menu → Settings: note the line under "Signed in with …", if there is one. A build with task L29
      says "Your sign-in is stored on this iPhone only. …". A build without L29 has no such line.
      Result (the line, word for word, or "no line"): 2026-11-20, pass. "Your sign-in is stored on this
      iPhone only. It can be read once the iPhone has been unlocked after a restart, and it is not
      synchronised with iCloud."
- [x] While signed in: delete the app, install it again from the Codemagic link and open it. Note whether
      you are still signed in. A build with L29 shows the sign-in screen. A build without L29 is expected
      to be still signed in; that is the known gap, not a new finding.
      Result: 2026-11-20, pass. The reinstalled app (build 5, with L29) opened on the sign-in screen, not
      signed in.

## 7. Sign in with Apple and account deletion (iPhone, then the Logto console)

- [x] If you are still signed in, sign out. Continue with Apple, with an Apple ID whose address is not
      account A's. A new account starts: the onboarding and the consent screen appear again, and the project list is empty.
      Result: 2026-11-20, pass, with Hide My Email. The api log at 11:10:53 UTC: "logto user created",
      "one-time token issued", then "apple token attached" and `POST /session 200`.
- [x] Menu → Settings → **Delete account** → confirm. The app returns to the sign-in screen with "Your
      account and all its projects were deleted." (or the notice that the last copies finish in the
      background).
      Result (which notice): 2026-11-20, pass. "Your account and all its projects were deleted." The api log
      at 11:11:33 UTC: "account deletion: apple token revoked", "account deletion complete", `DELETE /me 204`.
- [x] Logto console: User management no longer lists the Apple account.
      Result: 2026-11-20, pass, as the owner reported it; the database listing was not looked at for this step.
- [x] Settings app → your name → Sign in with Apple: note whether ChangeLens is still listed. The backend
      revokes the Apple token on deletion.
      Result: 2026-11-20, pass: ChangeLens was no longer listed.
- [x] Continue with Apple once more: it starts as a new account, with the onboarding. Delete it again.
      Result: 2026-11-20, pass.

Account A stays for the Fairphone half of L13.

## Not covered in this sitting

- The request time limit (30 seconds) can't be produced by hand: Airplane mode fails at once. It is covered
  by widget tests only.
- That polling really stops in the background is not visible on the phone; step 5 only shows that the
  screen recovers.
- The access-token lifetime is shown in debug builds only. It was recorded on Android on 2026-11-16.
- The legal links (L23) and the release-build inspection (L25) are sitting 2.

## Where the results go

| Steps | Recorded in |
|---|---|
| 1, 6, 7 (sign-in methods, MFA, link, deletion) | Runbook [`deploy/ionos/README.md`](../deploy/ionos/README.md) section E, and the M2 exit row in 06 (private) |
| 2 (consent) | The manual check of Task 2 in [`tasks/todo.md`](../tasks/todo.md) |
| 3 (PDF picker, comparison, review) | The M1b exit row in 06 (private); the iPhone lines of AC-12 to AC-15, AC-24 and AC-25 in [`docs/verification.md`](verification.md) |
| 4, 5 (field messages, VoiceOver) | Rows A2, A6 and A8 in [`docs/ui-ux-audit.md`](ui-ux-audit.md); tasks L27 and L28 |
| 6, last two steps (Settings line, reinstall) | Task L29 in [`tasks/launch-todo.md`](../tasks/launch-todo.md) |
