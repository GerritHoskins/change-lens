import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter/widgets.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:intl/intl.dart' as intl;

import 'app_localizations_en.dart';

// ignore_for_file: type=lint

/// Callers can lookup localized strings with an instance of AppLocalizations
/// returned by `AppLocalizations.of(context)`.
///
/// Applications need to include `AppLocalizations.delegate()` in their app's
/// `localizationDelegates` list, and the locales they support in the app's
/// `supportedLocales` list. For example:
///
/// ```dart
/// import 'l10n/app_localizations.dart';
///
/// return MaterialApp(
///   localizationsDelegates: AppLocalizations.localizationsDelegates,
///   supportedLocales: AppLocalizations.supportedLocales,
///   home: MyApplicationHome(),
/// );
/// ```
///
/// ## Update pubspec.yaml
///
/// Please make sure to update your pubspec.yaml to include the following
/// packages:
///
/// ```yaml
/// dependencies:
///   # Internationalization support.
///   flutter_localizations:
///     sdk: flutter
///   intl: any # Use the pinned version from flutter_localizations
///
///   # Rest of dependencies
/// ```
///
/// ## iOS Applications
///
/// iOS applications define key application metadata, including supported
/// locales, in an Info.plist file that is built into the application bundle.
/// To configure the locales supported by your app, you’ll need to edit this
/// file.
///
/// First, open your project’s ios/Runner.xcworkspace Xcode workspace file.
/// Then, in the Project Navigator, open the Info.plist file under the Runner
/// project’s Runner folder.
///
/// Next, select the Information Property List item, select Add Item from the
/// Editor menu, then select Localizations from the pop-up menu.
///
/// Select and expand the newly-created Localizations item then, for each
/// locale your application supports, add a new item and select the locale
/// you wish to add from the pop-up menu in the Value field. This list should
/// be consistent with the languages listed in the AppLocalizations.supportedLocales
/// property.
abstract class AppLocalizations {
  AppLocalizations(String locale)
    : localeName = intl.Intl.canonicalizedLocale(locale.toString());

  final String localeName;

  static AppLocalizations of(BuildContext context) {
    return Localizations.of<AppLocalizations>(context, AppLocalizations)!;
  }

  static const LocalizationsDelegate<AppLocalizations> delegate =
      _AppLocalizationsDelegate();

  /// A list of this localizations delegate along with the default localizations
  /// delegates.
  ///
  /// Returns a list of localizations delegates containing this delegate along with
  /// GlobalMaterialLocalizations.delegate, GlobalCupertinoLocalizations.delegate,
  /// and GlobalWidgetsLocalizations.delegate.
  ///
  /// Additional delegates can be added by appending to this list in
  /// MaterialApp. This list does not have to be used at all if a custom list
  /// of delegates is preferred or required.
  static const List<LocalizationsDelegate<dynamic>> localizationsDelegates =
      <LocalizationsDelegate<dynamic>>[
        delegate,
        GlobalMaterialLocalizations.delegate,
        GlobalCupertinoLocalizations.delegate,
        GlobalWidgetsLocalizations.delegate,
      ];

  /// A list of this localizations delegate's supported locales.
  static const List<Locale> supportedLocales = <Locale>[Locale('en')];

  /// No description provided for @appTitle.
  ///
  /// In en, this message translates to:
  /// **'ChangeLens'**
  String get appTitle;

  /// No description provided for @projectsTitle.
  ///
  /// In en, this message translates to:
  /// **'Projects'**
  String get projectsTitle;

  /// No description provided for @projectsEmpty.
  ///
  /// In en, this message translates to:
  /// **'No projects yet. Create one for each client engagement.'**
  String get projectsEmpty;

  /// No description provided for @newProject.
  ///
  /// In en, this message translates to:
  /// **'New project'**
  String get newProject;

  /// No description provided for @projectName.
  ///
  /// In en, this message translates to:
  /// **'Project name'**
  String get projectName;

  /// No description provided for @clientLabel.
  ///
  /// In en, this message translates to:
  /// **'Client (optional)'**
  String get clientLabel;

  /// No description provided for @create.
  ///
  /// In en, this message translates to:
  /// **'Create'**
  String get create;

  /// No description provided for @cancel.
  ///
  /// In en, this message translates to:
  /// **'Cancel'**
  String get cancel;

  /// No description provided for @save.
  ///
  /// In en, this message translates to:
  /// **'Save'**
  String get save;

  /// No description provided for @retry.
  ///
  /// In en, this message translates to:
  /// **'Retry'**
  String get retry;

  /// No description provided for @devSettings.
  ///
  /// In en, this message translates to:
  /// **'Developer settings'**
  String get devSettings;

  /// No description provided for @apiBaseUrl.
  ///
  /// In en, this message translates to:
  /// **'API address'**
  String get apiBaseUrl;

  /// No description provided for @devToken.
  ///
  /// In en, this message translates to:
  /// **'Dev token'**
  String get devToken;

  /// No description provided for @devSettingsHint.
  ///
  /// In en, this message translates to:
  /// **'Development builds talk to the local ChangeLens API. The token is kept in the device keychain only.'**
  String get devSettingsHint;

  /// No description provided for @notConfigured.
  ///
  /// In en, this message translates to:
  /// **'Set the API address and dev token in developer settings first.'**
  String get notConfigured;

  /// No description provided for @versionsTitle.
  ///
  /// In en, this message translates to:
  /// **'Versions'**
  String get versionsTitle;

  /// No description provided for @versionsEmpty.
  ///
  /// In en, this message translates to:
  /// **'No versions yet. Import the earlier brief first, then the newer one.'**
  String get versionsEmpty;

  /// No description provided for @comparisonsTitle.
  ///
  /// In en, this message translates to:
  /// **'Comparisons'**
  String get comparisonsTitle;

  /// No description provided for @comparisonsEmpty.
  ///
  /// In en, this message translates to:
  /// **'No comparisons yet.'**
  String get comparisonsEmpty;

  /// No description provided for @importPaste.
  ///
  /// In en, this message translates to:
  /// **'Paste text'**
  String get importPaste;

  /// No description provided for @importPdf.
  ///
  /// In en, this message translates to:
  /// **'Pick a PDF'**
  String get importPdf;

  /// No description provided for @versionLabel.
  ///
  /// In en, this message translates to:
  /// **'Label'**
  String get versionLabel;

  /// No description provided for @versionLabelHint.
  ///
  /// In en, this message translates to:
  /// **'For example \"Brief v1, 3 Oct\"'**
  String get versionLabelHint;

  /// No description provided for @pasteHint.
  ///
  /// In en, this message translates to:
  /// **'Paste the brief or the update here'**
  String get pasteHint;

  /// No description provided for @upload.
  ///
  /// In en, this message translates to:
  /// **'Import'**
  String get upload;

  /// No description provided for @uploading.
  ///
  /// In en, this message translates to:
  /// **'Importing…'**
  String get uploading;

  /// No description provided for @importFailed.
  ///
  /// In en, this message translates to:
  /// **'Import failed: {reason}'**
  String importFailed(String reason);

  /// No description provided for @originalsNote.
  ///
  /// In en, this message translates to:
  /// **'Imported versions are kept exactly as imported and cannot be edited. Import a new version instead.'**
  String get originalsNote;

  /// No description provided for @statusUploaded.
  ///
  /// In en, this message translates to:
  /// **'Waiting to be read'**
  String get statusUploaded;

  /// No description provided for @statusParsed.
  ///
  /// In en, this message translates to:
  /// **'Ready'**
  String get statusParsed;

  /// No description provided for @statusRejected.
  ///
  /// In en, this message translates to:
  /// **'Rejected: {reason}'**
  String statusRejected(String reason);

  /// No description provided for @warningsCount.
  ///
  /// In en, this message translates to:
  /// **'{count, plural, =1{1 warning} other{{count} warnings}}'**
  String warningsCount(int count);

  /// No description provided for @compare.
  ///
  /// In en, this message translates to:
  /// **'Compare two versions'**
  String get compare;

  /// No description provided for @compareNeedsTwo.
  ///
  /// In en, this message translates to:
  /// **'Import at least two versions that are ready to compare.'**
  String get compareNeedsTwo;

  /// No description provided for @confirmTitle.
  ///
  /// In en, this message translates to:
  /// **'Confirm the comparison'**
  String get confirmTitle;

  /// No description provided for @confirmIntro.
  ///
  /// In en, this message translates to:
  /// **'ChangeLens never guesses the order from upload time or file names. Choose it yourself.'**
  String get confirmIntro;

  /// No description provided for @earlierVersion.
  ///
  /// In en, this message translates to:
  /// **'Earlier version'**
  String get earlierVersion;

  /// No description provided for @newerVersion.
  ///
  /// In en, this message translates to:
  /// **'Newer version'**
  String get newerVersion;

  /// No description provided for @chooseVersion.
  ///
  /// In en, this message translates to:
  /// **'Choose a version'**
  String get chooseVersion;

  /// No description provided for @sameVersion.
  ///
  /// In en, this message translates to:
  /// **'Choose two different versions.'**
  String get sameVersion;

  /// No description provided for @scopeQuestion.
  ///
  /// In en, this message translates to:
  /// **'What is the newer version?'**
  String get scopeQuestion;

  /// No description provided for @scopeComplete.
  ///
  /// In en, this message translates to:
  /// **'Complete replacement'**
  String get scopeComplete;

  /// No description provided for @scopeCompleteHint.
  ///
  /// In en, this message translates to:
  /// **'A full brief that replaces the earlier one.'**
  String get scopeCompleteHint;

  /// No description provided for @scopePartial.
  ///
  /// In en, this message translates to:
  /// **'Partial update'**
  String get scopePartial;

  /// No description provided for @scopePartialHint.
  ///
  /// In en, this message translates to:
  /// **'Changes some items; everything else still stands.'**
  String get scopePartialHint;

  /// No description provided for @scopeUnknown.
  ///
  /// In en, this message translates to:
  /// **'Not sure'**
  String get scopeUnknown;

  /// No description provided for @scopeUnknownHint.
  ///
  /// In en, this message translates to:
  /// **'It is unclear whether the rest still stands.'**
  String get scopeUnknownHint;

  /// No description provided for @startComparison.
  ///
  /// In en, this message translates to:
  /// **'Start comparison'**
  String get startComparison;

  /// No description provided for @confirmMissing.
  ///
  /// In en, this message translates to:
  /// **'Choose both versions and the scope to continue.'**
  String get confirmMissing;

  /// No description provided for @comparisonTitle.
  ///
  /// In en, this message translates to:
  /// **'Comparison'**
  String get comparisonTitle;

  /// No description provided for @comparisonStatus.
  ///
  /// In en, this message translates to:
  /// **'Status: {status}'**
  String comparisonStatus(String status);

  /// No description provided for @comparisonQueued.
  ///
  /// In en, this message translates to:
  /// **'Queued'**
  String get comparisonQueued;

  /// No description provided for @comparisonRunning.
  ///
  /// In en, this message translates to:
  /// **'Processing'**
  String get comparisonRunning;

  /// No description provided for @comparisonComplete.
  ///
  /// In en, this message translates to:
  /// **'Complete'**
  String get comparisonComplete;

  /// No description provided for @comparisonPartial.
  ///
  /// In en, this message translates to:
  /// **'Partial: some content could not be processed'**
  String get comparisonPartial;

  /// No description provided for @comparisonFailed.
  ///
  /// In en, this message translates to:
  /// **'Failed'**
  String get comparisonFailed;

  /// No description provided for @earlierToNewer.
  ///
  /// In en, this message translates to:
  /// **'{earlier} → {newer}'**
  String earlierToNewer(String earlier, String newer);

  /// No description provided for @privacyCover.
  ///
  /// In en, this message translates to:
  /// **'ChangeLens'**
  String get privacyCover;

  /// No description provided for @openReport.
  ///
  /// In en, this message translates to:
  /// **'Open report'**
  String get openReport;

  /// No description provided for @reportTitle.
  ///
  /// In en, this message translates to:
  /// **'Report'**
  String get reportTitle;

  /// No description provided for @allDifferencesTitle.
  ///
  /// In en, this message translates to:
  /// **'All differences'**
  String get allDifferencesTitle;

  /// No description provided for @selectedSummary.
  ///
  /// In en, this message translates to:
  /// **'Selected summary — {count, plural, =0{no other differences} =1{1 other difference} other{{count} other differences}}, including presentation-only edits'**
  String selectedSummary(int count);

  /// No description provided for @showAllDifferences.
  ///
  /// In en, this message translates to:
  /// **'Show all differences'**
  String get showAllDifferences;

  /// No description provided for @groupPrioritised.
  ///
  /// In en, this message translates to:
  /// **'Changes'**
  String get groupPrioritised;

  /// No description provided for @groupNeedsReview.
  ///
  /// In en, this message translates to:
  /// **'Needs your review'**
  String get groupNeedsReview;

  /// No description provided for @groupOther.
  ///
  /// In en, this message translates to:
  /// **'Other findings'**
  String get groupOther;

  /// No description provided for @noPrioritised.
  ///
  /// In en, this message translates to:
  /// **'No material changes found.'**
  String get noPrioritised;

  /// No description provided for @withheld.
  ///
  /// In en, this message translates to:
  /// **'{count, plural, =1{1 finding withheld: its evidence could not be checked.} other{{count} findings withheld: their evidence could not be checked.}}'**
  String withheld(int count);

  /// No description provided for @warningPartial.
  ///
  /// In en, this message translates to:
  /// **'Some content could not be processed, so this report may be incomplete.'**
  String get warningPartial;

  /// No description provided for @warningHidden.
  ///
  /// In en, this message translates to:
  /// **'A document contains hidden text. It was left out of the comparison.'**
  String get warningHidden;

  /// No description provided for @warningCeiling.
  ///
  /// In en, this message translates to:
  /// **'The cost limit was reached; some explanations use standard wording.'**
  String get warningCeiling;

  /// No description provided for @unexplainedTitle.
  ///
  /// In en, this message translates to:
  /// **'Other text differences'**
  String get unexplainedTitle;

  /// No description provided for @unexplainedHint.
  ///
  /// In en, this message translates to:
  /// **'Text that differs but that no finding explains, such as headings or greetings. Check them if in doubt.'**
  String get unexplainedHint;

  /// No description provided for @presentationTitle.
  ///
  /// In en, this message translates to:
  /// **'Moved or reformatted'**
  String get presentationTitle;

  /// No description provided for @typeAdded.
  ///
  /// In en, this message translates to:
  /// **'Added'**
  String get typeAdded;

  /// No description provided for @typeChanged.
  ///
  /// In en, this message translates to:
  /// **'Changed'**
  String get typeChanged;

  /// No description provided for @typeRemoved.
  ///
  /// In en, this message translates to:
  /// **'Not in the replacement'**
  String get typeRemoved;

  /// No description provided for @typeNotAddressed.
  ///
  /// In en, this message translates to:
  /// **'Not addressed'**
  String get typeNotAddressed;

  /// No description provided for @typeUncertain.
  ///
  /// In en, this message translates to:
  /// **'Uncertain'**
  String get typeUncertain;

  /// No description provided for @typeEquivalent.
  ///
  /// In en, this message translates to:
  /// **'Reworded'**
  String get typeEquivalent;

  /// No description provided for @catDeliverable.
  ///
  /// In en, this message translates to:
  /// **'Deliverable'**
  String get catDeliverable;

  /// No description provided for @catQuantity.
  ///
  /// In en, this message translates to:
  /// **'Amount or quantity'**
  String get catQuantity;

  /// No description provided for @catDate.
  ///
  /// In en, this message translates to:
  /// **'Date or deadline'**
  String get catDate;

  /// No description provided for @catOwner.
  ///
  /// In en, this message translates to:
  /// **'Responsibility'**
  String get catOwner;

  /// No description provided for @catApproval.
  ///
  /// In en, this message translates to:
  /// **'Approval step'**
  String get catApproval;

  /// No description provided for @catOther.
  ///
  /// In en, this message translates to:
  /// **'Other'**
  String get catOther;

  /// No description provided for @catStructure.
  ///
  /// In en, this message translates to:
  /// **'Structure'**
  String get catStructure;

  /// No description provided for @sideEarlier.
  ///
  /// In en, this message translates to:
  /// **'Earlier'**
  String get sideEarlier;

  /// No description provided for @sideNewer.
  ///
  /// In en, this message translates to:
  /// **'Newer'**
  String get sideNewer;

  /// No description provided for @findingTitle.
  ///
  /// In en, this message translates to:
  /// **'Finding'**
  String get findingTitle;

  /// No description provided for @evidenceTitle.
  ///
  /// In en, this message translates to:
  /// **'Evidence'**
  String get evidenceTitle;

  /// No description provided for @showInDocument.
  ///
  /// In en, this message translates to:
  /// **'Show in document'**
  String get showInDocument;

  /// No description provided for @reviewConfirmed.
  ///
  /// In en, this message translates to:
  /// **'Confirmed by you'**
  String get reviewConfirmed;

  /// No description provided for @reviewCorrected.
  ///
  /// In en, this message translates to:
  /// **'Corrected by you'**
  String get reviewCorrected;

  /// No description provided for @reviewDismissed.
  ///
  /// In en, this message translates to:
  /// **'Dismissed by you'**
  String get reviewDismissed;

  /// No description provided for @notReviewed.
  ///
  /// In en, this message translates to:
  /// **'Not reviewed yet'**
  String get notReviewed;

  /// No description provided for @actionConfirm.
  ///
  /// In en, this message translates to:
  /// **'Confirm'**
  String get actionConfirm;

  /// No description provided for @actionCorrect.
  ///
  /// In en, this message translates to:
  /// **'Correct'**
  String get actionCorrect;

  /// No description provided for @actionDismiss.
  ///
  /// In en, this message translates to:
  /// **'Dismiss'**
  String get actionDismiss;

  /// No description provided for @actionNote.
  ///
  /// In en, this message translates to:
  /// **'Add note'**
  String get actionNote;

  /// No description provided for @noteLabel.
  ///
  /// In en, this message translates to:
  /// **'Note'**
  String get noteLabel;

  /// No description provided for @correctTitle.
  ///
  /// In en, this message translates to:
  /// **'Correct this finding'**
  String get correctTitle;

  /// No description provided for @correctHint.
  ///
  /// In en, this message translates to:
  /// **'Your correction is saved as a new revision. The original finding is kept.'**
  String get correctHint;

  /// No description provided for @changeTypeLabel.
  ///
  /// In en, this message translates to:
  /// **'Change type'**
  String get changeTypeLabel;

  /// No description provided for @categoryLabel.
  ///
  /// In en, this message translates to:
  /// **'Category'**
  String get categoryLabel;

  /// No description provided for @explanationLabel.
  ///
  /// In en, this message translates to:
  /// **'Explanation'**
  String get explanationLabel;

  /// No description provided for @historyTitle.
  ///
  /// In en, this message translates to:
  /// **'History'**
  String get historyTitle;

  /// No description provided for @revisionLabel.
  ///
  /// In en, this message translates to:
  /// **'Revision {n}'**
  String revisionLabel(int n);

  /// No description provided for @notesCount.
  ///
  /// In en, this message translates to:
  /// **'{count, plural, =1{1 note} other{{count} notes}}'**
  String notesCount(int count);

  /// No description provided for @approvalTitle.
  ///
  /// In en, this message translates to:
  /// **'Client approval'**
  String get approvalTitle;

  /// No description provided for @approvalRecorded.
  ///
  /// In en, this message translates to:
  /// **'Client approval recorded (not verified by ChangeLens)'**
  String get approvalRecorded;

  /// No description provided for @approvalNone.
  ///
  /// In en, this message translates to:
  /// **'No client approval recorded.'**
  String get approvalNone;

  /// No description provided for @approvalHint.
  ///
  /// In en, this message translates to:
  /// **'Record only what someone stated, for example a pasted e-mail. Reviewing a finding never records approval.'**
  String get approvalHint;

  /// No description provided for @recordApproval.
  ///
  /// In en, this message translates to:
  /// **'Record client approval'**
  String get recordApproval;

  /// No description provided for @approvalEvidence.
  ///
  /// In en, this message translates to:
  /// **'Evidence, for example an e-mail excerpt'**
  String get approvalEvidence;

  /// No description provided for @approvalStatedBy.
  ///
  /// In en, this message translates to:
  /// **'Stated by'**
  String get approvalStatedBy;

  /// No description provided for @approvalStatedOn.
  ///
  /// In en, this message translates to:
  /// **'Stated on {date}'**
  String approvalStatedOn(String date);

  /// No description provided for @approvalLine.
  ///
  /// In en, this message translates to:
  /// **'{by}, {date}'**
  String approvalLine(String by, String date);

  /// No description provided for @highlightFallback.
  ///
  /// In en, this message translates to:
  /// **'The highlight could not be placed in the PDF, so the parsed text is shown.'**
  String get highlightFallback;

  /// No description provided for @loadFailed.
  ///
  /// In en, this message translates to:
  /// **'Could not load: {reason}'**
  String loadFailed(String reason);

  /// No description provided for @saveFailed.
  ///
  /// In en, this message translates to:
  /// **'Could not save: {reason}'**
  String saveFailed(String reason);
}

class _AppLocalizationsDelegate
    extends LocalizationsDelegate<AppLocalizations> {
  const _AppLocalizationsDelegate();

  @override
  Future<AppLocalizations> load(Locale locale) {
    return SynchronousFuture<AppLocalizations>(lookupAppLocalizations(locale));
  }

  @override
  bool isSupported(Locale locale) =>
      <String>['en'].contains(locale.languageCode);

  @override
  bool shouldReload(_AppLocalizationsDelegate old) => false;
}

AppLocalizations lookupAppLocalizations(Locale locale) {
  // Lookup logic when only language code is specified.
  switch (locale.languageCode) {
    case 'en':
      return AppLocalizationsEn();
  }

  throw FlutterError(
    'AppLocalizations.delegate failed to load unsupported locale "$locale". This is likely '
    'an issue with the localizations generation tool. Please file an issue '
    'on GitHub with a reproducible sample app and the gen-l10n configuration '
    'that was used.',
  );
}
