# Device sitting 1: iPhone

The owner's checklist for the iPhone half of task L13, with the phone checks of L27 and L28
([`tasks/launch-todo.md`](../tasks/launch-todo.md)). One sitting against the IONOS server, with synthetic
documents only. Button names are the English ones.

Fill in the `Result:` line of every step: the date, pass or fail, and what you saw. A fail becomes its own
task. The last section says where each result is recorded afterwards.

## Before you start

**Codemagic (browser)**

- [ ] Build `ios-device-check` from `main` at `7e8f09a` or later, and note the build number.
      Result:

**Logto console (PC browser at `http://localhost:3002`, through the SSH tunnel of runbook C4)**

- [ ] Account A exists: User management → Add user, email only. Use a Gmail address you can read on the
      iPhone. Registration is off, so the email code only arrives for a user that exists.

**iPhone**

- [ ] Install the build from Codemagic's install link.
- [ ] Two synthetic PDFs with a text layer are in the Files app (an earlier and a newer brief).
- [ ] An authenticator app is installed, for the MFA step.
- [ ] The Google account of account A's address is signed in on the phone, and the phone has an Apple ID.

## 1. First launch and email sign-in (iPhone)

- [ ] The sign-in screen shows three buttons in this order: Continue with Apple, Continue with Google,
      Continue with email.
      Result:
- [ ] Continue with email → enter account A's address on Logto's page → enter the code from the mail. The
      app opens the first-run onboarding.
      Result:
- [ ] MFA: if Logto's page offers to set up two-step verification, set it up with the authenticator app. If
      it doesn't offer it, write that down; it is then a finding.
      Result:

## 2. Consent screen (iPhone)

- [ ] After the onboarding, the screen "Share usage events?" appears, with Allow and Don't allow, nothing
      preselected and no Back. Tap **Allow**.
      Result:
- [ ] Close the app from the app switcher and open it again. The consent screen does not come back.
      Result:
- [ ] Menu (top right) → Settings → Privacy: "Share usage events" is on. Turn it off, leave Settings, open
      it again: it is still off.
      Result:

## 3. A PDF comparison from the picker (iPhone)

- [ ] New project → name it. Then **Compare two briefs** at the bottom of the project list, and choose the
      project.
- [ ] Earlier version: Pick a PDF → label → Pick a PDF → choose the earlier PDF in Files. Newer version: the
      same with the newer PDF.
      Result (did the iOS picker open and return the file?):
- [ ] Answer "What is the newer version?" and tap **Start comparison**. The status screen ends at Complete
      and offers **Open report**. This also proves the worker reaches the model through the egress proxy.
      Result (time from Start to Complete):
- [ ] Open report → open a finding → tap a quote. The PDF page opens with the passage highlighted, and the
      card said "Highlight located". Switch to **Readable text** and back.
      Result:
- [ ] The M1b exit check, as worded in 05 (private): confirm one finding, correct one, dismiss one, add a
      note, and record a client approval.
      Result:

## 4. Field messages and the kept draft (L27; iPhone)

- [ ] In the project: Paste text → tap **Import** with both fields empty. A message appears under each field,
      and the sheet stays open.
      Result:
- [ ] Turn on Airplane mode. Paste text → label and text → Import. The sheet opens again with your label, your
      text and the reason. Turn Airplane mode off and tap Import: the version appears once.
      Result:
- [ ] Settings app → Accessibility → Display & Text Size → Larger Text, largest size. Repeat the empty
      Import. The message under Label is readable next to the character counter. Set the size back.
      Result:

## 5. Background and VoiceOver (L28; iPhone)

- [ ] Start a second comparison. On the status screen go to the Home screen, wait a minute, and return. The
      status catches up within a few seconds.
      Result:
- [ ] Turn VoiceOver on (Settings app → Accessibility → VoiceOver). Open a quote in **Readable text**:
      VoiceOver says "Marked passage: …" before the page text.
      Result:
- [ ] Switch to **PDF page**: VoiceOver says "PDF page N. Marked passage: …".
      Result:
- [ ] With VoiceOver still on, repeat the empty Import from step 4. The first field message is spoken once,
      not twice.
      Result:
- [ ] Turn VoiceOver off.

## 6. Google and the account link (iPhone)

- [ ] Menu → Settings → **Sign out**. The sign-in screen says "You're signed out."
- [ ] Continue with Google, with account A's Gmail address. The app shows "You already have an account" and
      offers only Continue with email.
      Result:
- [ ] Continue with email → code (and the authenticator code, if MFA is set up). You are signed in.
      Result (was the authenticator code asked for?):
- [ ] Sign out. Continue with Google again. This time it signs in directly. Settings says "Signed in with
      Google", with account A's address, and the project from step 3 is there.
      Result (was the authenticator code asked for with Google?):
- [ ] Menu → Settings: note the line under "Signed in with …", if there is one. A build with task L29
      says "Your sign-in is stored on this iPhone only. …". A build without L29 has no such line.
      Result (the line, word for word, or "no line"):
- [ ] While signed in: delete the app, install it again from the Codemagic link and open it. Note whether
      you are still signed in. A build with L29 shows the sign-in screen. A build without L29 is expected
      to be still signed in; that is the known gap, not a new finding.
      Result:

## 7. Sign in with Apple and account deletion (iPhone, then the Logto console)

- [ ] If you are still signed in, sign out. Continue with Apple, with an Apple ID whose address is not
      account A's. A new account starts: the onboarding and the consent screen appear again, and the project list is empty.
      Result:
- [ ] Menu → Settings → **Delete account** → confirm. The app returns to the sign-in screen with "Your
      account and all its projects were deleted." (or the notice that the last copies finish in the
      background).
      Result (which notice):
- [ ] Logto console: User management no longer lists the Apple account.
      Result:
- [ ] Settings app → your name → Sign in with Apple: note whether ChangeLens is still listed. The backend
      revokes the Apple token on deletion.
      Result:
- [ ] Continue with Apple once more: it starts as a new account, with the onboarding. Delete it again.
      Result:

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
