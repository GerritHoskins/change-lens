# Device sitting 1: Fairphone

The owner's checklist for the Fairphone half of task L13 ([`tasks/launch-todo.md`](../tasks/launch-todo.md)).
It follows the iPhone half ([`device-sitting-1.md`](device-sitting-1.md)) and uses its account A. One sitting
against the IONOS server, with synthetic documents only. Button names are the English ones.

Fill in the `Result:` line of every step: the date, pass or fail, and what you saw. A fail becomes its own
task. The last section says where each result is recorded afterwards.

Already recorded on this phone on 2026-11-16 (runbook section E): the email code, an access-token lifetime
of 900 seconds, a new account through Google, and the "You already have an account" answer. Still open on
Android: the consent screen, a comparison on the server, MFA and account deletion.

## Before you start

**PC (local, PowerShell, in the repository folder; the phone connected by USB with USB debugging on)**

- [x] Install the debug build. It is built from `main` with sign-in and the consent screen
      (`--dart-define=CHANGELENS_LOGTO_APP_ID=…` and `--dart-define=CHANGELENS_CONSENT=true`). `-r` keeps the
      app's data if an older debug build is installed.
      ```powershell
      adb install -r app\build\app\outputs\flutter-apk\app-debug.apk
      ```
      Result: 2026-11-18, pass. Built from c156a99 (= `origin/main`) with both defines; installed on the FP5
      over USB, `Success`, `dev.changelens.app` updated 16:33. Server before the sitting: `api` 401, `auth` 200.

**Logto console (PC browser at `http://localhost:3002`, through the SSH tunnel of runbook C4)**

- [x] Account A from the iPhone sitting still exists, with Google linked (iPhone step 6).
      2026-11-18: one user with the owner's Gmail address, Google identity linked.

**Fairphone**

- [x] Two synthetic PDFs with a text layer are in the Downloads folder (an earlier and a newer brief).
      2026-11-18: `P-703-old.pdf` and `P-703-new.pdf` (ReportLab, text extracts: "P-703 (earlier version)" /
      "(newer version)"); `P-713-old/new.pdf` are there too.
- [x] The authenticator app that holds account A's two-step code is at hand (on the iPhone, or on this phone).
      2026-11-18, fail: no authenticator entry for Logto on any device, so MFA was never set up for account A
      (the iPhone MFA step did not set it up). Finding, task L30. Repeat 2026-11-20: the new account A has an
      authenticator entry (set up in the iPhone sitting that day).
- [x] The Google account of account A's address is signed in on the phone. 2026-11-18: the owner believes
      so (not checked on the phone).
- [x] If the app opens signed in from an earlier check: Menu (top right) → Settings → **Sign out**.
      2026-11-18, after the install: the app opened signed in, on the first-run onboarding ("Schritt 1 von
      6"; the phone was set to German, then switched to English). Settings showed account A's address. The
      onboarding state is stored on the server, so account A had not finished onboarding although the iPhone
      sitting was done (its results are not written down yet). Finding, task L30. Skipped the onboarding, signed out.

## 1. Sign-in screen and email sign-in (Fairphone)

- [x] The sign-in screen shows two buttons in this order: Continue with Google, Continue with email. There
      is no Continue with Apple on Android.
      Result: 2026-11-18, pass.
- [x] Continue with email → enter account A's address on Logto's page → enter the code from the mail.
      Result: 2026-11-18, pass. The code arrived and was accepted.
- [x] MFA: Logto's page asks for the authenticator code before it returns to the app. If it doesn't ask,
      write that down; it is then a finding.
      Result: 2026-11-18, fail. Not asked; account A has no MFA set up (see Before you start). Finding.
      Repeat 2026-11-20 (new account A with two-step verification, debug build from `main` at `b4cbea6`):
      pass. The authenticator code was asked for after the mail code, by the owner's report.
- [x] The app opens the project list directly. The onboarding and the consent screen do not appear, because
      account A answered both on the iPhone, and the project from the iPhone sitting is there.
      Result: 2026-11-18, pass (onboarding was skipped on this phone just before, see Before you start).
      Repeat 2026-11-20 (new account A, onboarding finished on the iPhone that day): pass, the project list
      opened directly. The api log has no `PUT /me/onboarding` since the install.
- [x] Menu → Settings: the line "Access token lifetime: 900 s" shows (debug builds only).
      Result: 2026-11-18, pass.

## 2. Google sign-in with the linked account (Fairphone)

- [x] Settings → **Sign out**. The sign-in screen says "You're signed out." 2026-11-18, pass.
      2026-11-20 (task L34, debug build from `main` at `b4cbea6`, Chrome 157): after a sign-out, Continue with
      email asked for the address and the mail code again. The api log has the sign-in before it (22:10:16 UTC)
      and no completed sign-in after it; the owner stopped there.
- [x] Continue with Google, with account A's Gmail address. It signs in directly, because the link was
      completed on the iPhone. Settings says "Signed in with Google", with account A's address.
      Result (was the authenticator code asked for with Google?): 2026-11-18, pass. No authenticator code
      asked for (account A has no MFA).

## 3. A PDF comparison from the picker (Fairphone)

- [x] New project → name it. Then **Compare two briefs** at the bottom of the project list, and choose the
      project.
- [x] Earlier version: Pick a PDF → label → Pick a PDF → choose the earlier PDF in Downloads. Newer version:
      the same with the newer PDF.
      Result (did the Android picker open and return the file?): 2026-11-18, pass. `P-703-old.pdf` and
      `P-703-new.pdf` returned.
- [x] Answer "What is the newer version?" and tap **Start comparison**. The status screen ends at Complete
      and offers **Open report**.
      Result (time from Start to Complete): 2026-11-18, pass. Under 1 minute.
- [x] Open report → open a finding → tap a quote. The PDF page opens with the passage highlighted, and the
      card said "Highlight located". Switch to **Readable text** and back.
      Result: 2026-11-18, pass.
- [x] The M1b exit check, as worded in 05 (private): confirm one finding, correct one, dismiss one, add a
      note, and record a client approval.
      Result: 2026-11-18, pass. All five done.

## 4. Field messages, background and TalkBack (L27 and L28; Fairphone)

The same checks as steps 4 and 5 of the iPhone sitting, on Android.

- [x] In the project: Paste text → tap **Import** with both fields empty. A message appears under each field,
      and the sheet stays open.
      Result: 2026-11-18, pass.
- [x] Turn on Airplane mode. Paste text → label and text → Import. The sheet opens again with your label, your
      text and the reason. Turn Airplane mode off and tap Import: the version appears once.
      Result: 2026-11-18, pass.
- [x] Start a second comparison. On the status screen go to the Home screen, wait a minute, and return. The
      status catches up within a few seconds.
      Result: 2026-11-18, pass.
- [x] Turn TalkBack on (Settings app → Accessibility → TalkBack). Open a quote in **Readable text**: TalkBack
      says "Marked passage: …" before the page text. Switch to **PDF page**: it says "PDF page N. Marked
      passage: …".
      Result: 2026-11-18, pass. Both announcements as written.
- [x] Turn TalkBack off.

## 5. Account deletion, then the consent screen on a new account (Fairphone, then the Logto console)

Account A is deleted here. Do this section last, after every other check that needs it on either phone.

- [x] Menu → Settings → **Delete account** → confirm. The app returns to the sign-in screen with "Your
      account and all its projects were deleted." (or the notice that the last copies finish in the
      background).
      Result (which notice): 2026-11-18, pass. "Your account and all its projects were deleted."
- [x] Logto console: User management no longer lists account A.
      Result: 2026-11-18, pass.
- [x] Continue with email, with account A's address. No code arrives, because the user is gone and
      registration is off.
      Result: 2026-11-18, pass. No code arrived.
- [x] Continue with Google, with the same Gmail address. A new account starts: the onboarding appears, and
      the project list is empty afterwards.
      Result: 2026-11-18, pass.
- [x] After the onboarding, the screen "Share usage events?" appears, with Allow and Don't allow, nothing
      preselected and no Back. Tap **Don't allow**.
      Result: 2026-11-18, pass for the screen. **Allow** was tapped instead of Don't allow.
- [x] Close the app from the recent-apps view and open it again. The consent screen does not come back.
      Result: 2026-11-18, pass.
- [x] Menu → Settings → Privacy: "Share usage events" is off. Turn it on, leave Settings, open it again: it
      is still on. Turn it off again: this is the withdrawal.
      Result: 2026-11-18, pass as reported. Because Allow was tapped, the switch started on rather than off;
      the change persisted across leaving Settings, and it was turned off at the end (the withdrawal).
- [x] Delete account → confirm, and check in the Logto console that the Google account is gone too.
      Result: 2026-11-18, pass. Gone from the console.

## Not covered in this sitting

- Sign in with Apple is iOS only.
- Completing the account link happened on the iPhone (step 6 there). On this phone the link already exists,
  so only the direct Google sign-in is seen.
- A release build signs with a different key, and Google sign-in needs its own Android OAuth client for that
  key. That belongs to L25.
- The limits listed in the iPhone checklist (request time limit, background polling) apply here as well.

## Where the results go

| Steps | Recorded in |
|---|---|
| 1, 2, 5 (sign-in methods, MFA, token lifetime, deletion) | Runbook [`deploy/ionos/README.md`](../deploy/ionos/README.md) section E, and the M2 exit row in 06 (private) |
| 5 (consent) | The manual check of Task 2 in [`tasks/todo.md`](../tasks/todo.md) |
| 3 (PDF picker, comparison, review) | The M1b exit row in 06 (private); the Android lines of AC-12 to AC-15, AC-24 and AC-25 in [`docs/verification.md`](verification.md) |
| 4 (field messages, TalkBack) | Rows A2, A6 and A8 in [`docs/ui-ux-audit.md`](ui-ux-audit.md); tasks L27 and L28 |
