# Device sitting 2: iPhone

The owner's checklist for the iPhone checks that are open after sitting 1
([`device-sitting-1.md`](device-sitting-1.md)). One sitting against the IONOS server, with synthetic documents
only. Button names are the English ones. It covers three things:

- the iPhone half of Checkpoint B ([`tasks/launch-todo.md`](../tasks/launch-todo.md)): a new user signs up,
  compares and deletes the account;
- the screens that changed after build 6 and were never seen on an iPhone: the Projects home, the three kinds
  of message, the onboarding and the keyboard;
- Logto's hosted pages, for the lines of [`logto-branding-plan.md`](logto-branding-plan.md) §5 that were not
  run.

Fill in the `Result:` line of every step: the date, pass or fail, and what you saw. A fail becomes its own
task. Take a screenshot where a step says so. The last section says where each result is recorded afterwards.
After the sitting the api log is read for the lines the steps name; a step that reaches the server counts as
passed once the log shows it.

## Before you start

**Codemagic (browser)**

Each run is a paid macOS build, so start it once. The webhook stays off; nothing starts a build but these
steps.

- [ ] Open `https://codemagic.io/apps` and open the app `change-lens`.
- [ ] **Start new build**. Branch: `main`. Workflow: `ios-device-check` (shown as "App ad hoc IPA for owner
      device checks"). Leave the environment variables as they are, so the consent screen is in the build.
- [ ] **Start new build** in the dialog. Wait until the build has finished; builds 5 and 6 took about five
      minutes.
      Result (build number, commit, duration): `main` must be at `ad339bd` or later.

**Logto console (PC browser at `http://localhost:3002`, through the SSH tunnel of runbook C4)**

- [ ] Account B exists: User management → Add user, email only. Use an address you can read on the iPhone and
      that is not a Logto user yet, for example a plus address of account A's. Account B is for section 6; it
      has no two-step verification.
- [ ] Account A still exists, with its authenticator app.

**iPhone**

- [ ] Install the build from Codemagic's install link, as in sitting 1. It installs over build 6.
- [ ] Two synthetic PDFs with a text layer are in the Files app (an earlier and a newer brief).
- [ ] The phone has an Apple ID. ChangeLens is not listed under Settings app → your name → Sign in with Apple
      (sitting 1 ended that way).
- [ ] The phone is in light mode and the text size is the default.
- [ ] If the app opens signed in: Menu (top right) → Settings → **Sign out**.

## 1. A new user signs up and compares (Checkpoint B; iPhone)

Registration by email is off, so a new user on the iPhone comes in with Apple.

- [ ] Continue with Apple. A new account starts: the onboarding appears.
      Result (did a Logto page appear between Apple's sheet and the app, and which?):
- [ ] Onboarding: go forward to step 2, then swipe from the left edge of the screen. The onboarding goes one
      step back and does not close. Go through to the end.
      Result:
- [ ] In the onboarding step that shows two briefs, the newer one is filled lime with dark text.
      Result:
- [ ] The screen "Share usage events?" appears, with Allow and Don't allow, nothing preselected. Tap either.
      Result (which one you tapped):
- [ ] The Projects screen is empty. Its headline reads "Nothing new to check." and, in grey, "Compare two
      briefs to see what moved."
      Result:
- [ ] New project → name it. Then **Compare two briefs**, choose the project, pick the earlier and the newer
      PDF from Files, answer "What is the newer version?" and tap **Start comparison**. The status screen ends
      at Complete and offers **Open report**.
      Result (time from Start to Complete):
- [ ] Open report → open a finding → tap a quote. The PDF page opens with the passage highlighted.
      Result:

Expected in the api log: "logto user created", `POST /session 200`,
`POST /projects/{project_id}/comparisons 202`, and the worker's "complete: N findings" line.

## 2. The Projects home (iPhone)

Still as the new user of section 1. Don't review any finding before the first step.

- [ ] Go back to Projects. The headline reads "1 brief changed." and "Let's see what moved." Under it is one
      wide lime block for the project: its name, the two version labels with an arrow between them, a large
      number with "thing moved" or "things moved", up to two white pills with topic counts (for example
      "1 deadline"), and a dark round arrow button. Screenshot.
      Result (the number, and the pills word for word):
- [ ] Tap the lime block. The report opens.
      Result:
- [ ] New project, without a comparison. On Projects it is a plain row that says "No comparison yet".
      Result:
- [ ] Start a comparison in that project and in a third project, one right after the other (the same two PDFs
      will do), and go back to Projects while they run. Two square tiles appear side by side; each says
      "Reading …" or "Comparing…". Screenshot.
      Result (what each tile said):
- [ ] When both have finished, the headline counts the projects that have findings nobody reviewed. The most
      recent of them is the lime block; the other two are tiles with a number and "to check".
      Result (headline, and which project is the lime block):
- [ ] Open the lime block's project and confirm every finding. Back on Projects that project is no longer
      lime, it says "All checked", and the headline counts one less.
      Result:
- [ ] Settings app → Accessibility → Display & Text Size → Larger Text, largest size. On Projects the headline
      is not cut off, and the pills keep their text inside. Screenshot. Set the size back.
      Result:
- [ ] Settings app → Display & Brightness → Dark. The lime block stays lime with dark text; the tiles and rows
      are dark. Screenshot. Switch back to light.
      Result:
- [ ] Turn VoiceOver on and touch the lime block. It is read as one button: the project, the two versions,
      how many things moved, the topics, how many to check, and "Open the report". Turn VoiceOver off.
      Result:

## 3. Error, warning and info messages (iPhone)

Each kind has its own colour and its own icon: an error is red with a circled "!", a warning is amber with a
triangle, an info message is blue with a circled "i". Do the steps in light mode with a screenshot each, then
switch to dark mode (Settings app → Display & Brightness → Dark) and repeat the first four, again with a
screenshot each.

- [ ] **Warning banner.** Compare two briefs → choose a project with versions → choose the same version as the
      earlier and as the newer one. An amber banner with a triangle says "Choose two different versions."
      Result (light):
      Result (dark):
- [ ] **Error snackbar.** Open a report → open a finding that is not reviewed yet. Turn on Airplane mode and
      tap the confirm button. A red bar with a circled "!" appears at the bottom: "Could not save: ChangeLens
      can't be reached. Check your connection and try again."
      Result (light):
      Result (dark):
- [ ] **Error banner.** Still in Airplane mode: go back to Projects and open a project. A red banner with a
      circled "!" and **Retry** appears. Turn Airplane mode off and tap Retry: the project loads.
      Result (light; the banner's text):
      Result (dark):
- [ ] **Info banner.** Menu → Settings → **Sign out**. The sign-in screen shows "You're signed out." in a blue
      banner with a circled "i".
      Result (light):
      Result (dark):
- [ ] **Sign-in without a connection.** On the sign-in screen, turn on Airplane mode and tap Continue with
      Google. Note what appears: a red banner (expected: "Sign-in isn't reachable right now. Check your
      connection and try again." or "Sign-in didn't work. …", perhaps with a line "Code: …"), or nothing.
      Turn Airplane mode off. Which of these appears is not settled from the code; nothing here is a fail
      unless the app hangs.
      Result (the text, word for word, and the code if there is one):
- [ ] Continue with Apple. It signs in to the account of section 1, without the onboarding, and the projects
      are there.
      Result:
- [ ] **Info snackbar.** Delete one project (the one without unreviewed findings). A dark bar with a circled
      "i" says "Project deleted." or "Project hidden. Its data is being deleted."
      Result (which text):
- [ ] If any finding or quote showed "A PDF highlight could not be placed. Review the quoted text before
      confirming.", it was amber with a triangle. This can't be produced on purpose; write "not seen" if it
      did not come up.
      Result:

## 4. The keyboard closes (iPhone)

On 2026-11-21 the iPhone kept a keyboard over Projects that nothing could close, after the app had been left
while a field had focus.

- [ ] Compare two briefs → choose a project → Pick a PDF → tap the label field, so the keyboard is up → Pick a
      PDF → choose a file in Files. Back in the app, go back to Projects. No keyboard is over Projects.
      Result:
- [ ] New project → tap the name field, so the keyboard is up → go to the Home screen → return to the app.
      The keyboard either belongs to the name field or is gone. Close the sheet and look at Projects: no
      keyboard.
      Result:

## 5. The new user deletes the account (Checkpoint B; iPhone, then the Logto console)

- [ ] Menu → Settings → **Delete account** → confirm. The app returns to the sign-in screen with "Your account
      and all its projects were deleted." (or the notice that the last copies finish in the background).
      Result (which notice, its colour and its icon):
- [ ] Logto console: User management no longer lists the Apple account.
      Result:
- [ ] Settings app → your name → Sign in with Apple: ChangeLens is not listed.
      Result:

Expected in the api log: "account deletion: apple token revoked", "account deletion complete" and
`DELETE /me 204`.

## 6. Logto's pages (iPhone, account B)

The pages open in the system browser sheet and follow the iPhone's language; the app does not set it yet
(§4.6 of the branding plan). Start in light mode.

- [ ] Continue with email. Logto's sign-in page shows the ChangeLens mark, not Logto's.
      Result (the page's language):
- [ ] Enter account B's address. On the code page, enter a wrong code once: the error message is red and
      readable. Then enter the code from the mail.
      Result:
- [ ] Logto offers to set up two-step verification, on a page with the ChangeLens mark and a skip button.
      Screenshot, then skip. The app opens the onboarding. If the page is not offered, write that down.
      Result:
- [ ] Finish the onboarding and the consent screen, then Menu → Settings → Sign out.
- [ ] Settings app → Display & Brightness → Dark. Continue with email as account B again: the sign-in page,
      the code page and the two-step setup page are dark, the mark is the light-on-dark one, and all text is
      readable. Screenshot each. Skip again.
      Result:
- [ ] Sign out. Settings app → Larger Text, largest size. Continue with email: every field and button on the
      sign-in and code pages can be reached, by scrolling if needed. Close the sheet, and set the size and
      light mode back.
      Result:
- [ ] Sign in as account B once more and delete the account in the app (Menu → Settings → Delete account), so
      no test user is left. The Logto console no longer lists account B.
      Result:

## Not covered in this sitting

- The Fairphone half of Checkpoint B. It needs no Apple hardware: a debug build from the PC, with Google as
  the new user's sign-in.
- Logto's pages in the iPhone's other language (it means changing the phone's language), on Android, the
  contrast figures and the comparison with the design canvas (§5 of the branding plan).
- The legal links (L23) and the release-build inspection (L25): sitting 3, with the Mac.
- A finding with the text fallback can't be produced on purpose (section 3, last step).

## Where the results go

| Steps | Recorded in |
|---|---|
| 1 and 5 (new user: sign-up, comparison, deletion) | Checkpoint B in [`tasks/launch-todo.md`](../tasks/launch-todo.md) and [`tasks/launch-plan.md`](../tasks/launch-plan.md); the M2 exit row in 06 (private) |
| 2 (Projects home) and 4 (keyboard) | This file; a fail becomes a task in [`tasks/launch-todo.md`](../tasks/launch-todo.md) |
| 3 (messages) | The device check in [`noticeable-messages-handoff.md`](noticeable-messages-handoff.md) |
| 6 (Logto's pages) | The status lines and §5 of [`logto-branding-plan.md`](logto-branding-plan.md) |
