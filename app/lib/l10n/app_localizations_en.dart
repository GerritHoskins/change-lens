// ignore: unused_import
import 'package:intl/intl.dart' as intl;

import 'app_localizations.dart';

// ignore_for_file: type=lint

/// The translations for English (`en`).
class AppLocalizationsEn extends AppLocalizations {
  AppLocalizationsEn([String locale = 'en']) : super(locale);

  @override
  String get appTitle => 'ChangeLens';

  @override
  String get projectsTitle => 'Projects';

  @override
  String get projectsEmpty =>
      'No projects yet. Create one for each client engagement.';

  @override
  String get newProject => 'New project';

  @override
  String get projectName => 'Project name';

  @override
  String get clientLabel => 'Client (optional)';

  @override
  String get create => 'Create';

  @override
  String get cancel => 'Cancel';

  @override
  String get save => 'Save';

  @override
  String get retry => 'Retry';

  @override
  String get devSettings => 'Developer settings';

  @override
  String get apiBaseUrl => 'API address';

  @override
  String get devToken => 'Dev token';

  @override
  String get devSettingsHint =>
      'Development builds talk to the local ChangeLens API. The token is kept in the device keychain only.';

  @override
  String get notConfigured =>
      'Set the API address and dev token in developer settings first.';

  @override
  String get versionsTitle => 'Versions';

  @override
  String get versionsEmpty =>
      'No versions yet. Import the earlier brief first, then the newer one.';

  @override
  String get comparisonsTitle => 'Comparisons';

  @override
  String get comparisonsEmpty => 'No comparisons yet.';

  @override
  String get importPaste => 'Paste text';

  @override
  String get importPdf => 'Pick a PDF';

  @override
  String get versionLabel => 'Label';

  @override
  String get versionLabelHint => 'For example \"Brief v1, 3 Oct\"';

  @override
  String get pasteHint => 'Paste the brief or the update here';

  @override
  String get upload => 'Import';

  @override
  String get uploading => 'Importing…';

  @override
  String importFailed(String reason) {
    return 'Import failed: $reason';
  }

  @override
  String get originalsNote =>
      'Imported versions are kept exactly as imported and cannot be edited. Import a new version instead.';

  @override
  String get statusUploaded => 'Waiting to be read';

  @override
  String get statusParsed => 'Ready';

  @override
  String statusRejected(String reason) {
    return 'Rejected: $reason';
  }

  @override
  String warningsCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$count warnings',
      one: '1 warning',
    );
    return '$_temp0';
  }

  @override
  String get compare => 'Compare two versions';

  @override
  String get compareNeedsTwo =>
      'Import at least two versions that are ready to compare.';

  @override
  String get confirmTitle => 'Confirm the comparison';

  @override
  String get confirmIntro =>
      'ChangeLens never guesses the order from upload time or file names. Choose it yourself.';

  @override
  String get earlierVersion => 'Earlier version';

  @override
  String get newerVersion => 'Newer version';

  @override
  String get chooseVersion => 'Choose a version';

  @override
  String get sameVersion => 'Choose two different versions.';

  @override
  String get scopeQuestion => 'What is the newer version?';

  @override
  String get scopeComplete => 'Complete replacement';

  @override
  String get scopeCompleteHint => 'A full brief that replaces the earlier one.';

  @override
  String get scopePartial => 'Partial update';

  @override
  String get scopePartialHint =>
      'Changes some items; everything else still stands.';

  @override
  String get scopeUnknown => 'Not sure';

  @override
  String get scopeUnknownHint => 'It is unclear whether the rest still stands.';

  @override
  String get startComparison => 'Start comparison';

  @override
  String get confirmMissing =>
      'Choose both versions and the scope to continue.';

  @override
  String get comparisonTitle => 'Comparison';

  @override
  String comparisonStatus(String status) {
    return 'Status: $status';
  }

  @override
  String get comparisonQueued => 'Queued';

  @override
  String get comparisonRunning => 'Processing';

  @override
  String get comparisonComplete => 'Complete';

  @override
  String get comparisonPartial =>
      'Partial: some content could not be processed';

  @override
  String get comparisonFailed => 'Failed';

  @override
  String get reportComing => 'The report screens come in the next build.';

  @override
  String earlierToNewer(String earlier, String newer) {
    return '$earlier → $newer';
  }

  @override
  String get privacyCover => 'ChangeLens';
}
