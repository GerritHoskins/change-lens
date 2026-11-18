# ChangeLens app (I-9, I-10, I-18)

The Flutter app for iOS and Android, with the permanent identifier `dev.changelens.app`. It is portrait only on phones in v1. This build covers the app shell:
- projects and their versions;
- import by pasting text or picking a PDF;
- the order and scope confirmation that starts a comparison;
- a status screen for the comparison;
- the report (I-10): material changes first, then *Needs your review*, and a *Selected summary* line that opens every difference, including text no finding explains and moved or reformatted text;
- a finding screen with its evidence, review actions (confirm, correct, dismiss, note), history and a separate client-approval record;
- the evidence view: a PDF opens with the quote highlighted (pdfrx); if the PDF text at the stored offsets is not the quote, or the version is plain text, the parsed text is shown with the span marked.

- account screens (I-18): sign-in by email code, Google or Sign in with Apple (iOS), the `link_required` prompt, onboarding on first launch until the account has completed it, sign-out and in-app account deletion.

Camera, photo-library and share-sheet import come with I-16.

## Sign-in (I-18)

A build with `--dart-define=CHANGELENS_LOGTO_APP_ID=<Logto native app ID>` signs in to an account; a build without it is a development build that uses the developer settings below. Production defaults: API `https://api.pixeltronic.dev`, Logto `https://auth.pixeltronic.dev` (override with `CHANGELENS_API` and `CHANGELENS_LOGTO`).

- **Email code**: Logto's own sign-in page in an ephemeral system browser session (PKCE, redirect `dev.changelens.app://callback`), where MFA applies. The app asks for the API resource and keeps only the Logto refresh token, in the Keychain or Keystore (AC-25); the 15-minute access token stays in memory.
- **Google and Apple** are native (O-19, ADR-0020): the app gets the provider's authorization code and sends it to `POST /session` without a bearer. The backend exchanges it and answers with a Logto one-time token, which the app redeems in Logto's sign-in, or with `link_required`. Apple gets the lowercase hex SHA-256 of a random nonce; the backend gets the raw nonce. Sign in with Apple is offered on iOS only.
- **`link_required`**: the app shows only the account's existing methods; after one of them signs in, `POST /session` with the `link_id` links the new identity. A mismatch ends the link (AC-26).
- **Start**: refresh, then `POST /session`; onboarding opens until `completed`, resuming at the saved step, and saves each step and completion with `PUT /me/onboarding` (O-23). An ended session returns to sign-in (O-22).
- **Account → Delete account**: `DELETE /me`; 204 and 202 both sign out.
- Google's Android client exists for the debug signing key only. A release build (Play or Codemagic signing key) needs its own Android OAuth client with that key's SHA-1 before Google sign-in works there.

## Rules this build enforces

- **AC-12.** Confirming a finding is a review. Recording a client approval is a separate action, stored separately and labelled "Client approval recorded (not verified by ChangeLens)". The app never says a change was approved or agreed.
- **AC-14.** Nothing starts until the user picks the earlier and the newer version and the scope of the newer one. Nothing is preselected, and the order never comes from upload time or file names.
- **AC-15.** Imported versions are immutable. The app has no edit or delete action; a change means importing a new version. A correction to a finding is saved as a new revision; the original stays in its history.
- **AC-25.**
  - Document bytes are read into memory, uploaded and dropped.
  - The file picker's cached copies are purged after every import, whether it succeeded, failed or was cancelled, and again on start.
  - Android backup and device transfer are off for app data.
  - A privacy cover hides the screen in the app switcher.
- **Localisation.** UI strings live in `lib/l10n/app_en.arb` (English); German comes with I-21.

## Run against the local dev API

1. Start the backend as described in `../backend/README.md` §1–3, and note the dev token.
2. Start the app on a device or emulator:
   ```powershell
   cd app
   flutter run
   ```
3. In the app, open **⚙ Developer settings** and enter the API address and the dev token. The token is kept in the Keychain or Keystore only.
   - Android over USB: run `adb reverse tcp:8000 tcp:8000`, then use `http://127.0.0.1:8000`.
   - iPhone, or any phone on the home Wi-Fi: start the API with `--lan`, then use `http://<PC Wi-Fi IP>:8000`. The PC's Wi-Fi must be set to Private, and the firewall must allow TCP 8000 from the local subnet. Use this only on your own home network.

## Checks

```powershell
flutter analyze
flutter test        # widget tests for AC-9, AC-10, AC-12..15, AC-18, AC-24..26 against a mocked API and IdP
flutter build apk --debug
```

Codemagic runs the same checks in `app-android-check` and `app-ios-compile-check` (`../codemagic.yaml`), started by hand. A pull request that changes `ios/` is also compiled by the GitHub job `ios-compile`.
