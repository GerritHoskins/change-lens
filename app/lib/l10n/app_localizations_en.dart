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
  String earlierToNewer(String earlier, String newer) {
    return '$earlier → $newer';
  }

  @override
  String get privacyCover => 'ChangeLens';

  @override
  String get openReport => 'Open report';

  @override
  String get reportTitle => 'Report';

  @override
  String get allDifferencesTitle => 'All differences';

  @override
  String selectedSummary(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$count other differences',
      one: '1 other difference',
      zero: 'no other differences',
    );
    return 'Selected summary — $_temp0, including presentation-only edits';
  }

  @override
  String get showAllDifferences => 'Show all differences';

  @override
  String get groupPrioritised => 'Changes';

  @override
  String get groupNeedsReview => 'Needs your review';

  @override
  String get groupOther => 'Other findings';

  @override
  String get noPrioritised => 'No material changes found.';

  @override
  String withheld(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$count findings withheld: their evidence could not be checked.',
      one: '1 finding withheld: its evidence could not be checked.',
    );
    return '$_temp0';
  }

  @override
  String get warningPartial =>
      'Some content could not be processed, so this report may be incomplete.';

  @override
  String get warningHidden =>
      'A document contains hidden text. It was left out of the comparison.';

  @override
  String get warningCeiling =>
      'The cost limit was reached; some explanations use standard wording.';

  @override
  String get unexplainedTitle => 'Other text differences';

  @override
  String get unexplainedHint =>
      'Text that differs but that no finding explains, such as headings or greetings. Check them if in doubt.';

  @override
  String get presentationTitle => 'Moved or reformatted';

  @override
  String get typeAdded => 'Added';

  @override
  String get typeChanged => 'Changed';

  @override
  String get typeRemoved => 'Not in the replacement';

  @override
  String get typeNotAddressed => 'Not addressed';

  @override
  String get typeUncertain => 'Uncertain';

  @override
  String get typeEquivalent => 'Reworded';

  @override
  String get catDeliverable => 'Deliverable';

  @override
  String get catQuantity => 'Amount or quantity';

  @override
  String get catDate => 'Date or deadline';

  @override
  String get catOwner => 'Responsibility';

  @override
  String get catApproval => 'Approval step';

  @override
  String get catOther => 'Other';

  @override
  String get catStructure => 'Structure';

  @override
  String get sideEarlier => 'Earlier';

  @override
  String get sideNewer => 'Newer';

  @override
  String get findingTitle => 'Finding';

  @override
  String get evidenceTitle => 'Evidence';

  @override
  String get showInDocument => 'Show in document';

  @override
  String get reviewConfirmed => 'Confirmed by you';

  @override
  String get reviewCorrected => 'Corrected by you';

  @override
  String get reviewDismissed => 'Dismissed by you';

  @override
  String get notReviewed => 'Not reviewed yet';

  @override
  String get actionConfirm => 'Confirm';

  @override
  String get actionCorrect => 'Correct';

  @override
  String get actionDismiss => 'Dismiss';

  @override
  String get actionNote => 'Add note';

  @override
  String get noteLabel => 'Note';

  @override
  String get correctTitle => 'Correct this finding';

  @override
  String get correctHint =>
      'Your correction is saved as a new revision. The original finding is kept.';

  @override
  String get changeTypeLabel => 'Change type';

  @override
  String get categoryLabel => 'Category';

  @override
  String get explanationLabel => 'Explanation';

  @override
  String get historyTitle => 'History';

  @override
  String revisionLabel(int n) {
    return 'Revision $n';
  }

  @override
  String notesCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$count notes',
      one: '1 note',
    );
    return '$_temp0';
  }

  @override
  String get approvalTitle => 'Client approval';

  @override
  String get approvalRecorded =>
      'Client approval recorded (not verified by ChangeLens)';

  @override
  String get approvalNone => 'No client approval recorded.';

  @override
  String get approvalHint =>
      'Record only what someone stated, for example a pasted e-mail. Reviewing a finding never records approval.';

  @override
  String get recordApproval => 'Record client approval';

  @override
  String get approvalEvidence => 'Evidence, for example an e-mail excerpt';

  @override
  String get approvalStatedBy => 'Stated by';

  @override
  String approvalStatedOn(String date) {
    return 'Stated on $date';
  }

  @override
  String approvalLine(String by, String date) {
    return '$by, $date';
  }

  @override
  String get highlightFallback =>
      'The highlight could not be placed in the PDF, so the parsed text is shown.';

  @override
  String loadFailed(String reason) {
    return 'Could not load: $reason';
  }

  @override
  String saveFailed(String reason) {
    return 'Could not save: $reason';
  }
}
