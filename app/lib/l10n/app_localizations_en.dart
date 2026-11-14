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
  String get compareBriefs => 'Compare two briefs';

  @override
  String get compareLoadFailed =>
      'Could not load your versions. Check your connection and try again.';

  @override
  String get compareRejected =>
      'The comparison could not be accepted. Check both inputs, then try again.';

  @override
  String get compareRetrySame =>
      'The submission has not been confirmed. Retry to check the same comparison without creating a duplicate.';

  @override
  String get readyToSubmit => 'Ready to send';

  @override
  String get submittingComparison => 'Sending comparison…';

  @override
  String get compareSubmitHint =>
      'Start sends both inputs together. You can leave this screen once the comparison is reading.';

  @override
  String get comparePickFailed =>
      'The PDF could not be prepared. Try picking it again.';

  @override
  String get useText => 'Use this text';

  @override
  String get comparisonReading => 'Reading versions';

  @override
  String get loadingComparison => 'Loading comparison…';

  @override
  String get settingsSaveFailed =>
      'Settings could not be saved. Please try again.';

  @override
  String get evidenceChecking => 'Checking the source passages…';

  @override
  String get evidenceCheckFailed =>
      'The source passages could not be checked. Retry before reviewing this finding.';

  @override
  String get evidenceFallbackReview =>
      'A PDF highlight could not be placed. Review the quoted text before confirming.';

  @override
  String get findingChanged =>
      'This finding changed. Review the current revision before trying again.';

  @override
  String get topicDeadlines => 'Deadlines';

  @override
  String get topicDeliverables => 'Deliverables';

  @override
  String get topicResponsibilities => 'Responsibilities';

  @override
  String get topicApprovalWording => 'Approval wording';

  @override
  String get topicBudget => 'Budget';

  @override
  String get topicOther => 'Other';

  @override
  String get topicAll => 'All topics';

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
      'Unmentioned items are not addressed. This does not confirm whether they still apply.';

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
  String get comparisonFailedDetails =>
      'This comparison could not be completed. Start a new comparison to try again.';

  @override
  String get comparisonCostStopped =>
      'The cost limit was reached, so processing has stopped.';

  @override
  String get comparisonLoadFailed =>
      'Comparison details could not be loaded. Check your connection and retry.';

  @override
  String comparisonInputRejected(String label, String reason) {
    return '“$label” could not be read: $reason';
  }

  @override
  String get parseNoTextLayer =>
      'the PDF has no selectable text. Use a text-based PDF or paste the text.';

  @override
  String get parseMalformedPdf =>
      'the PDF could not be opened. Export it again or paste the text.';

  @override
  String get parseTooManyPages =>
      'the PDF exceeds the page limit. Choose a shorter document.';

  @override
  String get parseTooManyWords =>
      'the document exceeds the word limit. Choose a shorter document.';

  @override
  String get parseTooManyBytes =>
      'the file exceeds the size limit. Choose a smaller file.';

  @override
  String get parseTooMuchText =>
      'the PDF contains too much text. Choose a shorter document.';

  @override
  String get parseNotUtf8 =>
      'the text encoding is unsupported. Paste the text or save it as UTF-8.';

  @override
  String get parseUnsupported =>
      'this file type is unsupported. Use pasted text or a PDF with selectable text.';

  @override
  String get parseTimeout =>
      'reading the document took too long. Try a simpler or shorter document.';

  @override
  String get parseMemoryLimit =>
      'the document is too complex to read. Try a simpler or shorter document.';

  @override
  String get parseFailed =>
      'the document could not be processed. Export it again or paste the text.';

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
  String get contentLoadFailed =>
      'This content could not be opened. Check your connection and retry.';

  @override
  String get deleteProject => 'Delete project';

  @override
  String deleteProjectConfirmation(String name) {
    return 'This cannot be undone. Delete “$name” and its documents, comparisons and reviews?';
  }

  @override
  String get deletingProject => 'Deleting project…';

  @override
  String get deleteProjectFailed =>
      'Deletion could not be confirmed. Retry to check and finish deleting the project.';

  @override
  String get retryDeleteProject => 'Retry deletion';

  @override
  String get projectDeleted => 'Project deleted.';

  @override
  String get projectDeletionPending =>
      'Project hidden. Its data is being deleted.';

  @override
  String saveFailed(String reason) {
    return 'Could not save: $reason';
  }

  @override
  String get projectsIntro => 'Compare briefs. Check the source.';

  @override
  String get swapVersions => 'Swap earlier and newer';

  @override
  String get comparisonReturnHint =>
      'You can leave this screen and return to the comparison from its project.';

  @override
  String get returnToProjects => 'Back to projects';

  @override
  String get reportHeading => 'What changed';

  @override
  String reviewProgress(int reviewed, int total) {
    return 'Your review · $reviewed of $total';
  }

  @override
  String get reviewAcrossTopics => 'Across all topics';

  @override
  String get noTopicChanges => 'No material changes in this topic.';

  @override
  String get sourceUnavailable => 'Source label unavailable';

  @override
  String evidencePage(int page) {
    return 'Page $page';
  }

  @override
  String get yourReview => 'Your review';

  @override
  String get confirmAndNext => 'Confirm and next';

  @override
  String findingPosition(int position, int total) {
    return 'Finding $position of $total';
  }

  @override
  String get evidenceModePdf => 'Highlight located';

  @override
  String get evidenceModeFallback => 'Text fallback';

  @override
  String get evidenceModeText => 'Text-only source';

  @override
  String get readableText => 'Readable text';

  @override
  String get pdfPage => 'PDF page';

  @override
  String get saving => 'Saving…';

  @override
  String get onbSkip => 'Skip';

  @override
  String get onbNext => 'Next';

  @override
  String onbStep(int current, int total) {
    return 'Step $current of $total';
  }

  @override
  String get onbExample => 'Example';

  @override
  String get onbDone => 'Done';

  @override
  String get onbReplayEntry => 'How ChangeLens works';

  @override
  String get onbContextTitle => 'You set the order and the scope';

  @override
  String get onbContextScope => 'Then say what the newer version is:';

  @override
  String get onbContextNote => 'Missing items are never reported as cancelled.';

  @override
  String get onbEvidenceTitle => 'Every change shows its source';

  @override
  String get onbEvidenceBody =>
      'Each finding quotes the passage from both versions. “Show in document” opens the source, and on a PDF page the passage is highlighted. Quotes are checked against the source before they\'re shown.';

  @override
  String get onbReviewTitle => 'Your review isn\'t client approval';

  @override
  String get onbReviewBody =>
      'Confirm, correct or dismiss each finding. That records that you checked it, nothing more.';

  @override
  String get onbReviewApproval =>
      'If the client approves something, record it separately in their words, for example a pasted e-mail. ChangeLens doesn\'t verify it.';

  @override
  String get onbStartTitle => 'Ready for your first comparison';

  @override
  String get onbStartInputs =>
      'Pasted text, or a PDF with selectable text. Scanned PDFs can\'t be read.';

  @override
  String onbStartLimits(int words, int pages, int megabytes) {
    final intl.NumberFormat wordsNumberFormat =
        intl.NumberFormat.decimalPattern(localeName);
    final String wordsString = wordsNumberFormat.format(words);

    return 'Up to about $wordsString words per version. PDFs up to $pages pages and $megabytes MB.';
  }

  @override
  String get onbStartOnline =>
      'An internet connection. Documents aren\'t stored on this device.';

  @override
  String get onbStartLanguage =>
      'So far, comparisons have been tested on English briefs only.';

  @override
  String defInfo(String term) {
    return 'About $term';
  }

  @override
  String get defScopeComplete =>
      'Items missing from it are reported as “Not in the replacement”. That never means an obligation is cancelled.';

  @override
  String get defScopePartial =>
      'Items it doesn\'t mention are reported as “Not addressed”: neither removed nor reconfirmed.';

  @override
  String get defScopeUnknown =>
      'Missing items are marked “Uncertain” and go to “Needs your review”.';

  @override
  String get defChangeTypesTitle => 'Change types';

  @override
  String get defAdded => 'New in the newer version.';

  @override
  String get defChanged =>
      'Different in the two versions. Both values are shown.';

  @override
  String get defRemoved =>
      'Missing from a complete replacement. This doesn\'t mean it is cancelled.';

  @override
  String get defNotAddressed =>
      'A partial update didn\'t mention it. It is neither removed nor reconfirmed.';

  @override
  String get defUncertain => 'ChangeLens can\'t tell. Check it yourself.';

  @override
  String get defReworded => 'Same meaning, different wording.';

  @override
  String get defEvidenceTitle => 'How a passage was found';

  @override
  String get defModePdf => 'The passage is highlighted on the PDF page.';

  @override
  String get defModeFallback =>
      'The highlight couldn\'t be placed on the page, so the parsed text is shown. Check the quote before you confirm.';

  @override
  String get defModeText =>
      'This version has no PDF page, so only the text is shown.';

  @override
  String get defSummaryTitle => 'Selected summary';

  @override
  String get defSummaryBody =>
      'The report shows a selection of changes. It isn\'t a complete list: “All differences” shows everything else, including presentation-only edits and text no finding explains.';

  @override
  String get close => 'Close';

  @override
  String get onbIntroTitle => 'Compare two versions of a brief';

  @override
  String get onbIntroBody =>
      'ChangeLens reads the earlier and the newer version and shows the changes it finds, each with the passage it comes from.';

  @override
  String get onbIntroGoal =>
      'Catch a changed requirement before you deliver the wrong thing.';

  @override
  String get onbIntroAlt =>
      'Illustration: an earlier and a newer brief become one list of changes.';

  @override
  String get onbScopeLineComplete =>
      'Complete replacement: what\'s missing counts as “Not in the replacement”.';

  @override
  String get onbScopeLinePartial =>
      'Partial update: what it doesn\'t mention counts as “Not addressed”.';

  @override
  String get onbScopeLineUnknown =>
      'Not sure: what\'s missing goes to “Needs your review”.';

  @override
  String get onbContextAlt =>
      'Illustration: an earlier version above a newer version, which can be swapped.';

  @override
  String get onbUncertainTitle => 'When ChangeLens can\'t tell';

  @override
  String get onbUncertainBody =>
      'The finding goes to “Needs your review” and gets the ? mark. A topic filter never hides it.';

  @override
  String get onbUncertainSummary =>
      'The report is a selection. “All differences” shows everything else, including presentation-only edits.';

  @override
  String get onbReviewAlt =>
      'Example: a finding confirmed by you, with no client approval recorded.';

  @override
  String get onbStartLine =>
      'Paste text or pick a PDF with selectable text. You need to be online.';

  @override
  String get onbImportLink => 'What can I import?';

  @override
  String get onbStart => 'Start';

  @override
  String get importSheetTitle => 'What can I import?';

  @override
  String onbReviewApprovalLabel(String label) {
    return 'It\'s then shown as “$label”.';
  }

  @override
  String get onbStartTitleReplay => 'Before you compare';

  @override
  String get onbStartNext => 'Next: create a project and compare two briefs.';
}
