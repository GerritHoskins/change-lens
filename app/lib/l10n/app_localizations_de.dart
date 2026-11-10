// ignore: unused_import
import 'package:intl/intl.dart' as intl;

import 'app_localizations.dart';

// ignore_for_file: type=lint

/// The translations for German (`de`).
class AppLocalizationsDe extends AppLocalizations {
  AppLocalizationsDe([String locale = 'de']) : super(locale);

  @override
  String get appTitle => 'ChangeLens';

  @override
  String get compareBriefs => 'Zwei Briefings vergleichen';

  @override
  String get compareLoadFailed =>
      'Deine Versionen konnten nicht geladen werden. Prüfe die Verbindung und versuche es erneut.';

  @override
  String get compareRejected =>
      'Der Vergleich konnte nicht angenommen werden. Prüfe beide Eingaben und versuche es erneut.';

  @override
  String get compareRetrySame =>
      'Der Eingang wurde noch nicht bestätigt. Versuche es erneut, um denselben Vergleich zu prüfen, ohne ein Duplikat anzulegen.';

  @override
  String get readyToSubmit => 'Bereit zum Senden';

  @override
  String get submittingComparison => 'Vergleich wird gesendet…';

  @override
  String get compareSubmitHint =>
      'Beim Start werden beide Eingaben zusammen gesendet. Sobald die Versionen gelesen werden, kannst du diese Ansicht verlassen.';

  @override
  String get comparePickFailed =>
      'Die PDF konnte nicht vorbereitet werden. Wähle sie erneut aus.';

  @override
  String get useText => 'Diesen Text verwenden';

  @override
  String get comparisonReading => 'Versionen werden gelesen';

  @override
  String get loadingComparison => 'Vergleich wird geladen…';

  @override
  String get settingsSaveFailed =>
      'Die Einstellungen konnten nicht gespeichert werden. Versuche es erneut.';

  @override
  String get evidenceChecking => 'Belegstellen werden geprüft…';

  @override
  String get evidenceCheckFailed =>
      'Die Belegstellen konnten nicht geprüft werden. Versuche es erneut, bevor du diesen Befund prüfst.';

  @override
  String get evidenceFallbackReview =>
      'Die Textstelle konnte in der PDF nicht markiert werden. Prüfe vor dem Bestätigen den zitierten Text.';

  @override
  String get findingChanged =>
      'Dieser Befund wurde geändert. Prüfe die aktuelle Fassung, bevor du es erneut versuchst.';

  @override
  String get topicDeadlines => 'Fristen';

  @override
  String get topicDeliverables => 'Leistungen';

  @override
  String get topicResponsibilities => 'Zuständigkeiten';

  @override
  String get topicApprovalWording => 'Freigabeformulierungen';

  @override
  String get topicBudget => 'Budget';

  @override
  String get topicOther => 'Sonstiges';

  @override
  String get topicAll => 'Alle Themen';

  @override
  String get projectsTitle => 'Projekte';

  @override
  String get projectsEmpty =>
      'Noch keine Projekte. Lege für jeden Kundenauftrag ein Projekt an.';

  @override
  String get newProject => 'Neues Projekt';

  @override
  String get projectName => 'Projektname';

  @override
  String get clientLabel => 'Kunde (optional)';

  @override
  String get create => 'Erstellen';

  @override
  String get cancel => 'Abbrechen';

  @override
  String get save => 'Speichern';

  @override
  String get retry => 'Erneut versuchen';

  @override
  String get devSettings => 'Entwicklereinstellungen';

  @override
  String get apiBaseUrl => 'API-Adresse';

  @override
  String get devToken => 'Entwicklungstoken';

  @override
  String get devSettingsHint =>
      'Entwicklungsversionen verbinden sich mit der lokalen ChangeLens-API. Das Token wird nur im geschützten Schlüsselspeicher des Geräts aufbewahrt.';

  @override
  String get notConfigured =>
      'Trage zuerst die API-Adresse und das Entwicklungstoken in den Entwicklereinstellungen ein.';

  @override
  String get versionsTitle => 'Versionen';

  @override
  String get versionsEmpty =>
      'Noch keine Versionen. Importiere zuerst das frühere Briefing und dann die neuere Version.';

  @override
  String get comparisonsTitle => 'Vergleiche';

  @override
  String get comparisonsEmpty => 'Noch keine Vergleiche.';

  @override
  String get importPaste => 'Text einfügen';

  @override
  String get importPdf => 'PDF auswählen';

  @override
  String get versionLabel => 'Bezeichnung';

  @override
  String get versionLabelHint => 'Zum Beispiel „Briefing v1, 3. Okt.“';

  @override
  String get pasteHint => 'Füge hier das Briefing oder die Aktualisierung ein';

  @override
  String get upload => 'Importieren';

  @override
  String get uploading => 'Wird importiert…';

  @override
  String importFailed(String reason) {
    return 'Import fehlgeschlagen: $reason';
  }

  @override
  String get originalsNote =>
      'Importierte Versionen bleiben unverändert und können nicht bearbeitet werden. Importiere stattdessen eine neue Version.';

  @override
  String get statusUploaded => 'Wartet auf das Einlesen';

  @override
  String get statusParsed => 'Bereit';

  @override
  String statusRejected(String reason) {
    return 'Abgelehnt: $reason';
  }

  @override
  String warningsCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$count Warnungen',
      one: '1 Warnung',
    );
    return '$_temp0';
  }

  @override
  String get compare => 'Zwei Versionen vergleichen';

  @override
  String get compareNeedsTwo =>
      'Importiere mindestens zwei Versionen, die für den Vergleich bereit sind.';

  @override
  String get confirmTitle => 'Vergleich bestätigen';

  @override
  String get confirmIntro =>
      'ChangeLens leitet die Reihenfolge nie aus dem Upload-Zeitpunkt oder den Dateinamen ab. Lege sie selbst fest.';

  @override
  String get earlierVersion => 'Frühere Version';

  @override
  String get newerVersion => 'Neuere Version';

  @override
  String get chooseVersion => 'Version auswählen';

  @override
  String get sameVersion => 'Wähle zwei unterschiedliche Versionen.';

  @override
  String get scopeQuestion => 'Was ist die neuere Version?';

  @override
  String get scopeComplete => 'Vollständiger Ersatz';

  @override
  String get scopeCompleteHint =>
      'Ein vollständiges Briefing, das die frühere Version ersetzt.';

  @override
  String get scopePartial => 'Teilweise Aktualisierung';

  @override
  String get scopePartialHint =>
      'Nicht erwähnte Punkte werden nicht behandelt. Das bestätigt nicht, ob sie weiterhin gelten.';

  @override
  String get scopeUnknown => 'Nicht sicher';

  @override
  String get scopeUnknownHint =>
      'Es ist unklar, ob die übrigen Punkte weiterhin gelten.';

  @override
  String get startComparison => 'Vergleich starten';

  @override
  String get confirmMissing =>
      'Wähle beide Versionen und den Umfang aus, um fortzufahren.';

  @override
  String get comparisonTitle => 'Vergleich';

  @override
  String comparisonStatus(String status) {
    return 'Status: $status';
  }

  @override
  String get comparisonQueued => 'In der Warteschlange';

  @override
  String get comparisonRunning => 'Wird verarbeitet';

  @override
  String get comparisonComplete => 'Abgeschlossen';

  @override
  String get comparisonPartial =>
      'Teilweise: Einige Inhalte konnten nicht verarbeitet werden';

  @override
  String get comparisonFailed => 'Fehlgeschlagen';

  @override
  String get comparisonFailedDetails =>
      'Dieser Vergleich konnte nicht abgeschlossen werden. Starte einen neuen Vergleich, um es erneut zu versuchen.';

  @override
  String get comparisonCostStopped =>
      'Das Kostenlimit wurde erreicht. Die Verarbeitung wurde deshalb gestoppt.';

  @override
  String get comparisonLoadFailed =>
      'Die Vergleichsdetails konnten nicht geladen werden. Prüfe die Verbindung und versuche es erneut.';

  @override
  String comparisonInputRejected(String label, String reason) {
    return '„$label“ konnte nicht gelesen werden: $reason';
  }

  @override
  String get parseNoTextLayer =>
      'Die PDF enthält keinen auswählbaren Text. Verwende eine textbasierte PDF oder füge den Text ein.';

  @override
  String get parseMalformedPdf =>
      'Die PDF konnte nicht geöffnet werden. Exportiere sie erneut oder füge den Text ein.';

  @override
  String get parseTooManyPages =>
      'Die PDF überschreitet das Seitenlimit. Wähle ein kürzeres Dokument.';

  @override
  String get parseTooManyWords =>
      'Das Dokument überschreitet das Wortlimit. Wähle ein kürzeres Dokument.';

  @override
  String get parseTooManyBytes =>
      'Die Datei überschreitet das Größenlimit. Wähle eine kleinere Datei.';

  @override
  String get parseTooMuchText =>
      'Die PDF enthält zu viel Text. Wähle ein kürzeres Dokument.';

  @override
  String get parseNotUtf8 =>
      'Die Textkodierung wird nicht unterstützt. Füge den Text ein oder speichere ihn als UTF-8.';

  @override
  String get parseUnsupported =>
      'Dieser Dateityp wird nicht unterstützt. Füge Text ein oder verwende eine PDF mit auswählbarem Text.';

  @override
  String get parseTimeout =>
      'Das Lesen des Dokuments hat zu lange gedauert. Versuche es mit einem einfacheren oder kürzeren Dokument.';

  @override
  String get parseMemoryLimit =>
      'Das Dokument ist zu komplex. Versuche es mit einem einfacheren oder kürzeren Dokument.';

  @override
  String get parseFailed =>
      'Das Dokument konnte nicht verarbeitet werden. Exportiere es erneut oder füge den Text ein.';

  @override
  String earlierToNewer(String earlier, String newer) {
    return '$earlier → $newer';
  }

  @override
  String get privacyCover => 'ChangeLens';

  @override
  String get openReport => 'Bericht öffnen';

  @override
  String get reportTitle => 'Bericht';

  @override
  String get allDifferencesTitle => 'Alle Unterschiede';

  @override
  String selectedSummary(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$count weitere Unterschiede',
      one: '1 weiterer Unterschied',
      zero: 'keine weiteren Unterschiede',
    );
    return 'Ausgewählte Zusammenfassung – $_temp0, einschließlich reiner Darstellungsänderungen';
  }

  @override
  String get showAllDifferences => 'Alle Unterschiede anzeigen';

  @override
  String get groupPrioritised => 'Änderungen';

  @override
  String get groupNeedsReview => 'Von dir zu prüfen';

  @override
  String get groupOther => 'Weitere Befunde';

  @override
  String get noPrioritised => 'Keine wesentlichen Änderungen gefunden.';

  @override
  String withheld(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other:
          '$count Befunde zurückgehalten: Ihre Belegstellen konnten nicht geprüft werden.',
      one: '1 Befund zurückgehalten: Seine Belegstellen konnten nicht geprüft werden.',
    );
    return '$_temp0';
  }

  @override
  String get warningPartial =>
      'Einige Inhalte konnten nicht verarbeitet werden. Dieser Bericht kann daher unvollständig sein.';

  @override
  String get warningHidden =>
      'Ein Dokument enthält verborgenen Text. Er wurde beim Vergleich ausgelassen.';

  @override
  String get warningCeiling =>
      'Das Kostenlimit wurde erreicht. Einige Erläuterungen verwenden Standardformulierungen.';

  @override
  String get unexplainedTitle => 'Weitere Textunterschiede';

  @override
  String get unexplainedHint =>
      'Textunterschiede, die keinem Befund zugeordnet sind, etwa Überschriften oder Anreden. Prüfe sie im Zweifel.';

  @override
  String get presentationTitle => 'Verschoben oder neu formatiert';

  @override
  String get typeAdded => 'Hinzugefügt';

  @override
  String get typeChanged => 'Geändert';

  @override
  String get typeRemoved => 'In der Ersatzversion nicht enthalten';

  @override
  String get typeNotAddressed => 'Nicht angesprochen';

  @override
  String get typeUncertain => 'Unklar';

  @override
  String get typeEquivalent => 'Umformuliert';

  @override
  String get catDeliverable => 'Leistung';

  @override
  String get catQuantity => 'Umfang oder Menge';

  @override
  String get catDate => 'Datum oder Frist';

  @override
  String get catOwner => 'Zuständigkeit';

  @override
  String get catApproval => 'Freigaberegelung';

  @override
  String get catOther => 'Sonstiges';

  @override
  String get catStructure => 'Struktur';

  @override
  String get sideEarlier => 'Früher';

  @override
  String get sideNewer => 'Neuer';

  @override
  String get findingTitle => 'Befund';

  @override
  String get evidenceTitle => 'Belegstellen';

  @override
  String get showInDocument => 'Im Dokument anzeigen';

  @override
  String get reviewConfirmed => 'Von dir bestätigt';

  @override
  String get reviewCorrected => 'Von dir korrigiert';

  @override
  String get reviewDismissed => 'Von dir verworfen';

  @override
  String get notReviewed => 'Noch nicht geprüft';

  @override
  String get actionConfirm => 'Bestätigen';

  @override
  String get actionCorrect => 'Korrigieren';

  @override
  String get actionDismiss => 'Verwerfen';

  @override
  String get actionNote => 'Notiz hinzufügen';

  @override
  String get noteLabel => 'Notiz';

  @override
  String get correctTitle => 'Diesen Befund korrigieren';

  @override
  String get correctHint =>
      'Deine Korrektur wird als neue Fassung gespeichert. Der ursprüngliche Befund bleibt erhalten.';

  @override
  String get changeTypeLabel => 'Art der Änderung';

  @override
  String get categoryLabel => 'Kategorie';

  @override
  String get explanationLabel => 'Erläuterung';

  @override
  String get historyTitle => 'Verlauf';

  @override
  String revisionLabel(int n) {
    return 'Fassung $n';
  }

  @override
  String notesCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$count Notizen',
      one: '1 Notiz',
    );
    return '$_temp0';
  }

  @override
  String get approvalTitle => 'Kundenfreigabe';

  @override
  String get approvalRecorded =>
      'Kundenfreigabe dokumentiert (von ChangeLens nicht überprüft)';

  @override
  String get approvalNone => 'Keine Kundenfreigabe dokumentiert.';

  @override
  String get approvalHint =>
      'Dokumentiere nur, was jemand mitgeteilt hat, zum Beispiel eine eingefügte E-Mail. Das Prüfen eines Befunds dokumentiert niemals eine Freigabe.';

  @override
  String get recordApproval => 'Kundenfreigabe dokumentieren';

  @override
  String get approvalEvidence => 'Nachweis, zum Beispiel ein E-Mail-Auszug';

  @override
  String get approvalStatedBy => 'Mitgeteilt von';

  @override
  String approvalStatedOn(String date) {
    return 'Mitgeteilt am $date';
  }

  @override
  String approvalLine(String by, String date) {
    return '$by, $date';
  }

  @override
  String get highlightFallback =>
      'Die Textstelle konnte in der PDF nicht markiert werden. Deshalb wird der ausgelesene Text angezeigt.';

  @override
  String loadFailed(String reason) {
    return 'Laden fehlgeschlagen: $reason';
  }

  @override
  String get contentLoadFailed =>
      'Dieser Inhalt konnte nicht geöffnet werden. Prüfe deine Verbindung und versuche es erneut.';

  @override
  String get deleteProject => 'Projekt löschen';

  @override
  String deleteProjectConfirmation(String name) {
    return 'Dies kann nicht rückgängig gemacht werden. „$name“ mit allen Dokumenten, Vergleichen und Prüfungen löschen?';
  }

  @override
  String get deletingProject => 'Projekt wird gelöscht…';

  @override
  String get deleteProjectFailed =>
      'Die Löschung konnte nicht bestätigt werden. Versuche es erneut, um sie zu prüfen und abzuschließen.';

  @override
  String get retryDeleteProject => 'Löschung erneut versuchen';

  @override
  String get projectDeleted => 'Projekt gelöscht.';

  @override
  String get projectDeletionPending =>
      'Projekt ausgeblendet. Die Daten werden gelöscht.';

  @override
  String saveFailed(String reason) {
    return 'Speichern fehlgeschlagen: $reason';
  }

  @override
  String get projectsIntro => 'Briefings vergleichen. Quellen prüfen.';

  @override
  String get swapVersions => 'Frühere und neuere Version tauschen';

  @override
  String get comparisonReturnHint =>
      'Du kannst diese Ansicht verlassen und den Vergleich später im Projekt wieder öffnen.';

  @override
  String get returnToProjects => 'Zurück zu den Projekten';

  @override
  String get reportHeading => 'Was sich geändert hat';

  @override
  String reviewProgress(int reviewed, int total) {
    return 'Deine Prüfung · $reviewed von $total';
  }

  @override
  String get reviewAcrossTopics => 'Über alle Themen hinweg';

  @override
  String get noTopicChanges => 'Keine wesentlichen Änderungen in diesem Thema.';

  @override
  String get sourceUnavailable => 'Quellenbezeichnung nicht verfügbar';

  @override
  String evidencePage(int page) {
    return 'Seite $page';
  }

  @override
  String get yourReview => 'Deine Prüfung';

  @override
  String get confirmAndNext => 'Bestätigen und weiter';

  @override
  String findingPosition(int position, int total) {
    return 'Änderung $position von $total';
  }

  @override
  String get evidenceModePdf => 'Textstelle markiert';

  @override
  String get evidenceModeFallback => 'Textansicht als Ersatz';

  @override
  String get evidenceModeText => 'Reine Textquelle';

  @override
  String get readableText => 'Lesbare Textansicht';

  @override
  String get pdfPage => 'PDF-Seite';

  @override
  String get saving => 'Wird gespeichert…';
}
