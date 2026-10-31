# ChangeLens app (I-9, I-10)

The Flutter app for iOS and Android, with the permanent identifier `dev.changelens.app`. It is portrait only on phones in v1. This build covers the app shell:
- projects and their versions;
- import by pasting text or picking a PDF;
- the order and scope confirmation that starts a comparison;
- a status screen for the comparison;
- the report (I-10): material changes first, then *Needs your review*, and a *Selected summary* line that opens every difference, including text no finding explains and moved or reformatted text;
- a finding screen with its evidence, review actions (confirm, correct, dismiss, note), history and a separate client-approval record;
- the evidence view: a PDF opens with the quote highlighted (pdfrx); if the PDF text at the stored offsets is not the quote, or the version is plain text, the parsed text is shown with the span marked.

Sign-in comes with I-18, and camera, photo-library and share-sheet import with I-16.

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
flutter test        # widget tests for AC-9, AC-10, AC-12..15, AC-18, AC-24 and AC-25 against a mocked API
flutter build apk --debug
```

Codemagic runs the same checks in `app-android-check` and `app-ios-compile-check` (`../codemagic.yaml`).
