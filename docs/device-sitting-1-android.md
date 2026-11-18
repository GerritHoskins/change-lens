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

- [ ] Install the debug build. It is built from `main` with sign-in and the consent screen
      (`--dart-define=CHANGELENS_LOGTO_APP_ID=…` and `--dart-define=CHANGELENS_CONSENT=true`). `-r` keeps the
      app's data if an older debug build is installed.
      ```powershell
      adb install -r app\build\app\outputs\flutter-apk\app-debug.apk
      ```
      Result:

**Logto console (PC browser at `http://localhost:3002`, through the SSH tunnel of runbook C4)**

- [ ] Account A from the iPhone sitting still exists, with Google linked (iPhone step 6).

**Fairphone**

- [ ] Two synthetic PDFs with a text layer are in the Downloads folder (an earlier and a newer brief).
- [ ] The authenticator app that holds account A's two-step code is at hand (on the iPhone, or on this phone).
- [ ] The Google account of account A's address is signed in on the phone.
- [ ] If the app opens signed in from an earlier check: Menu (top right) → Settings → **Sign out**.

## 1. Sign-in screen and email sign-in (Fairphone)

- [ ] The sign-in screen shows two buttons in this order: Continue with Google, Continue with email. There
      is no Continue with Apple on Android.
      Result:
- [ ] Continue with email → enter account A's address on Logto's page → enter the code from the mail.
      Result:
- [ ] MFA: Logto's page asks for the authenticator code before it returns to the app. If it doesn't ask,
      write that down; it is then a finding.
      Result:
- [ ] The app opens the project list directly. The onboarding and the consent screen do not appear, because
      account A answered both on the iPhone, and the project from the iPhone sitting is there.
      Result:
- [ ] Menu → Settings: the line "Access token lifetime: 900 s" shows (debug builds only).
      Result:

## 2. Google sign-in with the linked account (Fairphone)

- [ ] Settings → **Sign out**. The sign-in screen says "You're signed out."
- [ ] Continue with Google, with account A's Gmail address. It signs in directly, because the link was
      completed on the iPhone. Settings says "Signed in with Google", with account A's address.
      Result (was the authenticator code asked for with Google?):

## 3. A PDF comparison from the picker (Fairphone)

- [ ] New project → name it. Then **Compare two briefs** at the bottom of the project list, and choose the
      project.
- [ ] Earlier version: Pick a PDF → label → Pick a PDF → choose the earlier PDF in Downloads. Newer version:
      the same with the newer PDF.
      Result (did the Android picker open and return the file?):
- [ ] Answer "What is the newer version?" and tap **Start comparison**. The status screen ends at Complete
      and offers **Open report**.
      Result (time from Start to Complete):
- [ ] Open report → open a finding → tap a quote. The PDF page opens with the passage highlighted, and the
      card said "Highlight located". Switch to **Readable text** and back.
      Result:
- [ ] The M1b exit check, as worded in 05 (private): confirm one finding, correct one, dismiss one, add a
      note, and record a client approval.
      Result:

## 4. Field messages, background and TalkBack (L27 and L28; Fairphone)

The same checks as steps 4 and 5 of the iPhone sitting, on Android.

- [ ] In the project: Paste text → tap **Import** with both fields empty. A message appears under each field,
      and the sheet stays open.
      Result:
- [ ] Turn on Airplane mode. Paste text → label and text → Import. The sheet opens again with your label, your
      text and the reason. Turn Airplane mode off and tap Import: the version appears once.
      Result:
- [ ] Start a second comparison. On the status screen go to the Home screen, wait a minute, and return. The
      status catches up within a few seconds.
      Result:
- [ ] Turn TalkBack on (Settings app → Accessibility → TalkBack). Open a quote in **Readable text**: TalkBack
      says "Marked passage: …" before the page text. Switch to **PDF page**: it says "PDF page N. Marked
      passage: …".
      Result:
- [ ] Turn TalkBack off.

## 5. Account deletion, then the consent screen on a new account (Fairphone, then the Logto console)

Account A is deleted here. Do this section last, after every other check that needs it on either phone.

- [ ] Menu → Settings → **Delete account** → confirm. The app returns to the sign-in screen with "Your
      account and all its projects were deleted." (or the notice that the last copies finish in the
      background).
      Result (which notice):
- [ ] Logto console: User management no longer lists account A.
      Result:
- [ ] Continue with email, with account A's address. No code arrives, because the user is gone and
      registration is off.
      Result:
- [ ] Continue with Google, with the same Gmail address. A new account starts: the onboarding appears, and
      the project list is empty afterwards.
      Result:
- [ ] After the onboarding, the screen "Share usage events?" appears, with Allow and Don't allow, nothing
      preselected and no Back. Tap **Don't allow**.
      Result:
- [ ] Close the app from the recent-apps view and open it again. The consent screen does not come back.
      Result:
- [ ] Menu → Settings → Privacy: "Share usage events" is off. Turn it on, leave Settings, open it again: it
      is still on. Turn it off again: this is the withdrawal.
      Result:
- [ ] Delete account → confirm, and check in the Logto console that the Google account is gone too.
      Result:

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
