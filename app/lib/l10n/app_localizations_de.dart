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
  String get compareNeedsProject => 'Wähle zuerst ein Projekt.';

  @override
  String get compareNeedsEarlier =>
      'Wähle die frühere Version oder füge sie hinzu.';

  @override
  String get compareNeedsNewer =>
      'Wähle die neuere Version oder füge sie hinzu.';

  @override
  String get compareNeedsScope => 'Gib an, was die neuere Version ist.';

  @override
  String get dismissNeedsReason => 'Wähle zuerst einen Grund.';

  @override
  String get comparePickFailed =>
      'Die PDF konnte nicht vorbereitet werden. Wähle sie erneut aus.';

  @override
  String get useText => 'Diesen Text verwenden';

  @override
  String get comparisonReading => 'Versionen werden gelesen';

  @override
  String get loading => 'Wird geladen…';

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
      'Die Stelle ließ sich auf der Seite nicht markieren. Diese Zitate stammen aus dem ausgelesenen Text.';

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
  String get requiredVersionLabel => 'Gib dieser Version eine Bezeichnung.';

  @override
  String get requiredPastedText => 'Füge zuerst den Text ein.';

  @override
  String get requiredProjectName => 'Gib einen Projektnamen ein.';

  @override
  String get requiredNote => 'Schreibe zuerst die Notiz.';

  @override
  String get requiredApprovalEvidence => 'Gib den Nachweis ein.';

  @override
  String get requiredApprovalBy => 'Gib an, wer es mitgeteilt hat.';

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
  String get comparisonQueued => 'In der Warteschlange';

  @override
  String get comparisonRunning => 'Wird verarbeitet';

  @override
  String get comparisonComplete => 'Abgeschlossen';

  @override
  String get comparisonPartial => 'Einige Inhalte konnten nicht gelesen werden';

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
      other:
          '$count weitere Unterschiede, auch verschobener oder neu formatierter Text',
      one: '1 weiterer Unterschied, auch verschobener oder neu formatierter Text',
      zero: 'Keine weiteren Unterschiede',
    );
    return '$_temp0';
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
      'Die Stelle ließ sich auf der Seite nicht markieren. Dieses Zitat stammt aus dem ausgelesenen Text.';

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
  String reportCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$count Änderungen',
      one: '1 Änderung',
      zero: 'Keine Änderungen',
    );
    return '$_temp0';
  }

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

  @override
  String get onbSkip => 'Überspringen';

  @override
  String get onbNext => 'Weiter';

  @override
  String onbStep(int current, int total) {
    return 'Schritt $current von $total';
  }

  @override
  String get onbExample => 'Beispiel';

  @override
  String get onbDone => 'Fertig';

  @override
  String get onbReplayEntry => 'So funktioniert ChangeLens';

  @override
  String get onbContextTitle => 'Du legst Reihenfolge und Umfang fest';

  @override
  String get onbContextScope => 'Gib dann an, was die neuere Version ist:';

  @override
  String get onbContextNote => 'Fehlendes gilt nie als gestrichen.';

  @override
  String get onbEvidenceTitle => 'Jede Änderung zeigt ihre Quelle';

  @override
  String get onbEvidenceBody =>
      'Jeder Befund zitiert beide Versionen. „Im Dokument anzeigen“ öffnet die Quelle, bei PDFs mit markierter Stelle. Zitate werden vorher mit der Quelle abgeglichen.';

  @override
  String get onbReviewTitle => 'Deine Prüfung ist keine Kundenfreigabe';

  @override
  String get onbReviewBody =>
      'Bestätige, korrigiere oder verwirf jeden Befund. Das heißt nur: Du hast ihn geprüft.';

  @override
  String get onbReviewApproval =>
      'Gibt der Kunde etwas frei, dokumentiere es getrennt, etwa als eingefügte E-Mail.';

  @override
  String get onbStartTitle => 'Bereit für deinen ersten Vergleich';

  @override
  String get onbStartInputs =>
      'Eingefügten Text oder ein PDF mit auswählbarem Text. Gescannte PDFs können nicht gelesen werden.';

  @override
  String onbStartLimits(int words, int pages, int megabytes) {
    final intl.NumberFormat wordsNumberFormat =
        intl.NumberFormat.decimalPattern(localeName);
    final String wordsString = wordsNumberFormat.format(words);

    return 'Bis etwa $wordsString Wörter pro Version. PDFs bis $pages Seiten und $megabytes MB.';
  }

  @override
  String get onbStartOnline =>
      'Eine Internetverbindung. Dokumente werden nicht auf diesem Gerät gespeichert.';

  @override
  String get onbStartLanguage =>
      'Vergleiche wurden bisher nur mit englischen Briefings getestet.';

  @override
  String defInfo(String term) {
    return 'Mehr zu $term';
  }

  @override
  String get defScopeComplete =>
      'Was darin fehlt, wird als „In der Ersatzversion nicht enthalten“ gemeldet. Das heißt nie, dass eine Verpflichtung gestrichen ist.';

  @override
  String get defScopePartial =>
      'Was sie nicht erwähnt, wird als „Nicht angesprochen“ gemeldet: weder entfernt noch bestätigt.';

  @override
  String get defScopeUnknown =>
      'Fehlende Punkte werden als „Unklar“ markiert und landen unter „Von dir zu prüfen“.';

  @override
  String get defChangeTypesTitle => 'Änderungsarten';

  @override
  String get defAdded => 'Neu in der neueren Version.';

  @override
  String get defChanged =>
      'In beiden Versionen unterschiedlich. Beide Werte werden angezeigt.';

  @override
  String get defRemoved =>
      'Fehlt in einem vollständigen Ersatz. Das heißt nicht, dass es gestrichen ist.';

  @override
  String get defNotAddressed =>
      'Eine teilweise Aktualisierung erwähnt es nicht. Es ist weder entfernt noch bestätigt.';

  @override
  String get defUncertain =>
      'ChangeLens kann es nicht sicher erkennen. Prüfe es selbst.';

  @override
  String get defReworded => 'Gleiche Bedeutung, andere Formulierung.';

  @override
  String get defEvidenceTitle => 'Wie eine Textstelle gefunden wurde';

  @override
  String get defModePdf => 'Die Textstelle ist auf der PDF-Seite markiert.';

  @override
  String get defModeFallback =>
      'Die Markierung konnte nicht auf der Seite platziert werden, daher wird der ausgelesene Text gezeigt. Prüfe das Zitat, bevor du bestätigst.';

  @override
  String get defModeText =>
      'Diese Version hat keine PDF-Seite, daher wird nur der Text gezeigt.';

  @override
  String get defSummaryTitle => 'Ausgewählte Zusammenfassung';

  @override
  String get defSummaryBody =>
      'Der Bericht zeigt eine Auswahl der Änderungen. Er ist keine vollständige Liste: „Alle Unterschiede“ zeigt alles Weitere, auch reine Darstellungsänderungen und Text, den kein Befund erklärt.';

  @override
  String get close => 'Schließen';

  @override
  String get onbIntroTitle => 'Vergleiche zwei Versionen eines Briefings';

  @override
  String get onbIntroBody =>
      'ChangeLens liest die frühere und die neuere Version und zeigt die gefundenen Änderungen, jede mit der Textstelle, aus der sie stammt.';

  @override
  String get onbIntroGoal =>
      'Bemerke eine geänderte Anforderung, bevor du das Falsche lieferst.';

  @override
  String get onbIntroAlt =>
      'Illustration: Aus einem früheren und einem neueren Briefing wird eine Liste der Änderungen.';

  @override
  String get onbScopeLineComplete =>
      'Vollständiger Ersatz: Fehlendes gilt als „In der Ersatzversion nicht enthalten“.';

  @override
  String get onbScopeLinePartial =>
      'Teilweise Aktualisierung: Nicht Erwähntes gilt als „Nicht angesprochen“.';

  @override
  String get onbScopeLineUnknown =>
      'Nicht sicher: Fehlendes landet unter „Von dir zu prüfen“.';

  @override
  String get onbContextAlt =>
      'Illustration: eine frühere Version über einer neueren Version, die sich tauschen lassen.';

  @override
  String get onbUncertainTitle => 'Wenn ChangeLens es nicht sicher erkennt';

  @override
  String get onbUncertainBody =>
      'Der Befund landet unter „Von dir zu prüfen“ und bekommt das ?-Zeichen. Ein Themenfilter blendet ihn nie aus.';

  @override
  String get onbUncertainSummary =>
      'Der Bericht ist eine Auswahl. „Alle Unterschiede“ zeigt alles Weitere, auch reine Darstellungsänderungen.';

  @override
  String get onbReviewAlt =>
      'Beispiel: ein von dir bestätigter Befund, ohne dokumentierte Kundenfreigabe.';

  @override
  String get onbStartLine =>
      'Füge Text ein oder wähle ein PDF mit auswählbarem Text. Du musst online sein.';

  @override
  String get onbImportLink => 'Was kann ich importieren?';

  @override
  String get onbStart => 'Starten';

  @override
  String get importSheetTitle => 'Was kann ich importieren?';

  @override
  String onbReviewApprovalLabel(String label) {
    return 'Sie erscheint dann als „$label“.';
  }

  @override
  String get onbStartTitleReplay => 'Bevor du vergleichst';

  @override
  String get onbStartNext =>
      'Als Nächstes: Lege ein Projekt an und vergleiche zwei Briefings.';

  @override
  String get signInTitle => 'Bei ChangeLens anmelden';

  @override
  String get signInIntro =>
      'Deine Projekte und Vergleiche gehören zu deinem Konto. Wähle, wie du dich anmeldest.';

  @override
  String get signInApple => 'Weiter mit Apple';

  @override
  String get signInGoogle => 'Weiter mit Google';

  @override
  String get signInEmail => 'Weiter mit E-Mail';

  @override
  String get signInEmailHint =>
      'Wir schicken dir einen Einmalcode per E-Mail. Kein Passwort.';

  @override
  String get signInWorking => 'Anmeldung läuft …';

  @override
  String get signInUnavailable =>
      'Die Anmeldung ist gerade nicht erreichbar. Prüfe deine Verbindung und versuche es erneut.';

  @override
  String get signInFailed =>
      'Die Anmeldung hat nicht geklappt. Versuche es erneut oder wähle eine andere Methode.';

  @override
  String signInFailureCode(String code) {
    return 'Code: $code';
  }

  @override
  String get signInRejected =>
      'Mit dieser Anmeldung ist kein ChangeLens-Konto möglich. Wähle eine andere Methode.';

  @override
  String get signedOutExpired =>
      'Deine Sitzung ist abgelaufen. Melde dich erneut an, um weiterzumachen.';

  @override
  String get signedOutDone => 'Du bist abgemeldet.';

  @override
  String get accountDeletedNotice =>
      'Dein Konto und alle seine Projekte wurden gelöscht.';

  @override
  String get accountDeletionPendingNotice =>
      'Dein Konto ist gelöscht. Die letzten gespeicherten Kopien werden im Hintergrund entfernt.';

  @override
  String get linkFailedNotice =>
      'Die Konten wurden nicht verknüpft. Melde dich mit deiner bisherigen Methode an oder beginne neu.';

  @override
  String get linkTitle => 'Du hast schon ein Konto';

  @override
  String linkBody(String provider) {
    return 'Zu dieser E-Mail gibt es schon ein ChangeLens-Konto. Um die Anmeldung mit $provider hinzuzufügen, melde dich einmal wie gewohnt an. Danach verknüpfen wir $provider.';
  }

  @override
  String get linkCancel => 'Andere Methode wählen';

  @override
  String get linkAppleElsewhere =>
      'Dieses Konto meldet sich auch mit Apple an. Nutze dafür ein iPhone oder iPad.';

  @override
  String get providerApple => 'Apple';

  @override
  String get providerGoogle => 'Google';

  @override
  String get restoringSession => 'Dein Konto wird geöffnet …';

  @override
  String get sessionOffline =>
      'ChangeLens erreicht dein Konto gerade nicht. Prüfe deine Verbindung.';

  @override
  String get account => 'Konto';

  @override
  String accountSignedInAs(String email) {
    return 'Angemeldet als $email';
  }

  @override
  String get accountSignedIn => 'Du bist angemeldet.';

  @override
  String get signOut => 'Abmelden';

  @override
  String get deleteAccount => 'Konto löschen';

  @override
  String get deleteAccountIntro =>
      'Wenn du dein Konto löschst, werden alle Projekte, Dokumente, Vergleiche und Prüfungen entfernt, ebenso die damit verknüpften Anmeldemethoden. Das lässt sich nicht rückgängig machen.';

  @override
  String get deleteAccountConfirmTitle => 'Konto löschen?';

  @override
  String get deleteAccountConfirmBody =>
      'Alles in ChangeLens wird gelöscht: alle Projekte, Dokumente, Vergleiche und Prüfungen. Du kannst das nicht rückgängig machen.';

  @override
  String get deleteAccountFailed =>
      'Das Konto wurde nicht gelöscht. Prüfe deine Verbindung und versuche es erneut.';

  @override
  String get deletingAccount => 'Wird gelöscht …';

  @override
  String get signInPromise =>
      'Was hat sich geändert, und was davon ist wichtig?';

  @override
  String get signInPromiseBody =>
      'Vergleiche zwei Versionen eines Kundenbriefings und sieh jede Änderung neben der Textstelle, aus der sie stammt.';

  @override
  String signInCancelled(String method) {
    return 'Die Anmeldung mit $method wurde abgebrochen. Wähle eine Methode, um es erneut zu versuchen.';
  }

  @override
  String get sessionExpiredTitle => 'Erneut anmelden';

  @override
  String get sessionExpiredBody =>
      'Deine Sitzung ist abgelaufen. Melde dich erneut an, um weiterzumachen.';

  @override
  String sessionLastMethod(String method) {
    return 'Zuletzt hast du dich mit $method angemeldet.';
  }

  @override
  String get sessionOtherMethods => 'Andere Anmeldemethoden';

  @override
  String linkDone(String method) {
    return '$method ist jetzt mit deinem Konto verknüpft.';
  }

  @override
  String get onbResumed => 'Weiter an der Stelle, an der du aufgehört hast.';

  @override
  String get consentTitle => 'Nutzungsereignisse teilen?';

  @override
  String get consentBody =>
      'Wenn du es erlaubst, sendet die App Nutzungsereignisse an ChangeLens: welche Bildschirme du öffnest, welche Berichtsfilter du nutzt und wie lange dein erster Vergleich dauert. Niemals Dokumentinhalte.';

  @override
  String get consentDefault =>
      'Ohne deine Erlaubnis wird nichts gesendet. Du kannst das später in den Einstellungen ändern.';

  @override
  String get consentAllow => 'Erlauben';

  @override
  String get consentDecline => 'Nicht erlauben';

  @override
  String get settingsTitle => 'Einstellungen';

  @override
  String get settingsAccount => 'Konto';

  @override
  String settingsSignedInWith(String method) {
    return 'Angemeldet mit $method';
  }

  @override
  String get settingsKeychainOk =>
      'Deine Anmeldung ist nur auf diesem iPhone gespeichert. Sie ist lesbar, sobald das iPhone nach einem Neustart entsperrt wurde, und wird nicht mit iCloud synchronisiert.';

  @override
  String settingsKeychainDiffers(String found) {
    return 'Die auf diesem iPhone gespeicherte Anmeldung ist nicht wie vorgesehen geschützt ($found).';
  }

  @override
  String get settingsPrivacy => 'Datenschutz';

  @override
  String get settingsUsageEvents => 'Nutzungsereignisse teilen';

  @override
  String get settingsUsageEventsHint =>
      'Welche Bildschirme du öffnest, welche Berichtsfilter du nutzt und wie lange dein erster Vergleich dauert. Niemals Dokumentinhalte.';

  @override
  String get providerEmail => 'E-Mail';

  @override
  String get dismissTitle => 'Warum verwirfst du diesen Befund?';

  @override
  String get dismissLead =>
      'Verwerfen hält nur deine Prüfung fest. Der Befund bleibt ausgegraut im Bericht.';

  @override
  String get dismissReasonReworded => 'Nur umformuliert, nichts zu tun';

  @override
  String get dismissReasonWrongPassage => 'Zitiert die falsche Stelle';

  @override
  String get dismissReasonIrrelevant => 'Für die Arbeit nicht relevant';

  @override
  String get dismissReasonOther => 'Anderer Grund';

  @override
  String get dismissNote => 'Notiz (optional)';

  @override
  String get dismissAndNext => 'Verwerfen und weiter';

  @override
  String dismissReasonLine(String reason) {
    return 'Grund: $reason';
  }

  @override
  String get completeTitle => 'Alle Befunde geprüft';

  @override
  String get completeLead => 'Deine Prüfung dieses Vergleichs:';

  @override
  String get completeConfirmed => 'Bestätigt';

  @override
  String get completeCorrected => 'Korrigiert';

  @override
  String get completeDismissed => 'Verworfen';

  @override
  String get completeNotApproval =>
      'Das ist deine eigene Prüfung, keine Kundenfreigabe. Kundenfreigaben dokumentierst du je Befund, in den Worten des Kunden.';

  @override
  String get completeBack => 'Zurück zum Projekt';

  @override
  String get consentSaveFailed =>
      'Deine Antwort wurde nicht gespeichert. Prüfe deine Verbindung und versuche es erneut.';

  @override
  String get historyLead =>
      'Neueste zuerst, in der Reihenfolge, die du beim Vergleichen festgelegt hast.';

  @override
  String get historyEmptyTitle => 'Noch keine Versionen';

  @override
  String get historyEmptyBody =>
      'Vergleiche zwei Versionen des Briefings, um den Verlauf zu beginnen. Sie erscheinen hier in der Reihenfolge, die du festlegst, nie nach Upload-Zeitpunkt oder Dateiname.';

  @override
  String get historyForkNote =>
      'Diese Versionen wurden jeweils mit einer früheren verglichen, aber nicht miteinander. Daher wird keine als neuer gezeigt.';

  @override
  String get historyBothWays =>
      'Du hast diese Versionen in beide Richtungen verglichen. Ihre Reihenfolge ist daher offen.';

  @override
  String get historyNotCompared => 'Noch nicht verglichen';

  @override
  String get historyNotComparedLead =>
      'Ihr Platz ist erst bekannt, wenn du sie vergleichst.';

  @override
  String historyVersionA11y(String label, String meta) {
    return '$label, $meta. Von dieser Version aus vergleichen';
  }

  @override
  String historyLinkA11y(
    String earlier,
    String newer,
    String scope,
    String status,
  ) {
    return 'Vergleich von $earlier mit der neueren Version $newer. $scope. $status';
  }

  @override
  String get historyCompareFrom => 'Ab hier vergleichen';

  @override
  String get errorConnection =>
      'ChangeLens ist nicht erreichbar. Prüfe deine Verbindung und versuche es erneut.';

  @override
  String get errorSignedOut =>
      'Deine Anmeldung ist abgelaufen. Melde dich erneut an, um weiterzumachen.';

  @override
  String get errorNotFound =>
      'Das gibt es nicht mehr. Es wurde vielleicht gelöscht.';

  @override
  String get errorRejected =>
      'Das wurde nicht angenommen. Prüfe deine Eingabe und versuche es erneut.';

  @override
  String get errorServer =>
      'Bei ChangeLens ist ein Problem aufgetreten. Versuche es gleich noch einmal.';

  @override
  String homeHeadline(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$count Briefings geändert.',
      one: '1 Briefing geändert.',
    );
    return '$_temp0';
  }

  @override
  String get homeHeadlineLead => 'Sieh dir an, was sich geändert hat.';

  @override
  String get homeQuiet => 'Nichts Neues zu prüfen.';

  @override
  String get homeQuietLead =>
      'Vergleiche zwei Briefings und sieh, was sich geändert hat.';

  @override
  String homeMovedUnit(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: 'Änderungen',
      one: 'Änderung',
    );
    return '$_temp0';
  }

  @override
  String homeToCheck(int count) {
    return '$count zu prüfen';
  }

  @override
  String get homeToCheckUnit => 'zu prüfen';

  @override
  String get homeAllChecked => 'Alles geprüft';

  @override
  String get homeNotCompared => 'Noch kein Vergleich';

  @override
  String homeReading(String label) {
    return '$label wird gelesen …';
  }

  @override
  String get homeComparing => 'Wird verglichen …';

  @override
  String get homeFailed => 'Vergleich fehlgeschlagen';

  @override
  String homeSecondLook(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$count von dir zu prüfen',
      one: '1 von dir zu prüfen',
    );
    return '$_temp0';
  }

  @override
  String homePairA11y(String earlier, String newer) {
    return '$earlier verglichen mit dem neueren $newer';
  }

  @override
  String get homeOpenReport => 'Bericht öffnen';

  @override
  String homeTopicDeadlines(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$count Fristen',
      one: '1 Frist',
    );
    return '$_temp0';
  }

  @override
  String homeTopicDeliverables(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$count Leistungen',
      one: '1 Leistung',
    );
    return '$_temp0';
  }

  @override
  String homeTopicResponsibilities(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$count Zuständigkeiten',
      one: '1 Zuständigkeit',
    );
    return '$_temp0';
  }

  @override
  String homeTopicApprovalWording(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$count Freigabeformulierungen',
      one: '1 Freigabeformulierung',
    );
    return '$_temp0';
  }

  @override
  String homeTopicBudget(int count) {
    return '$count Budget';
  }

  @override
  String homeTopicOther(int count) {
    return '$count Sonstiges';
  }

  @override
  String get historyCompareAgain => 'Erneut vergleichen';

  @override
  String historyComparisonDone(String earlier, String newer, String status) {
    return 'Vergleich von $earlier mit $newer: $status';
  }

  @override
  String get comparisonFailedShort =>
      'Dieser Vergleich konnte nicht abgeschlossen werden.';

  @override
  String evidenceMarkedA11y(String quote) {
    return 'Markierte Stelle: $quote';
  }

  @override
  String evidencePdfMarkedA11y(int page, String quote) {
    return 'PDF-Seite $page. Markierte Stelle: $quote';
  }

  @override
  String evidencePdfUnmarkedA11y(int page, String quote) {
    return 'PDF-Seite $page. Die Stelle ist auf dieser Seite nicht markiert: $quote';
  }

  @override
  String get kindPdf => 'PDF';

  @override
  String get kindText => 'Eingefügter Text';

  @override
  String demoLine(int remaining, int limit) {
    return 'Demo · $remaining von $limit Vergleichen übrig';
  }

  @override
  String demoWallTitle(int limit) {
    return 'Deine $limit Demo-Vergleiche sind aufgebraucht';
  }

  @override
  String demoWallTitleInFlight(int limit) {
    return 'Deine $limit Demo-Vergleiche sind belegt';
  }

  @override
  String get demoWallBody =>
      'Das ist die Demo-Phase. Die Vollversion kommt bald. Deine Berichte, Befunde und der Verlauf bleiben verfügbar.';

  @override
  String get demoWallInFlight =>
      'Ein Vergleich läuft noch. Schlägt er fehl, zählt er nicht und du kannst einen neuen starten.';

  @override
  String get demoWallDiscount =>
      'Für dein Feedback bekommst du den Early-Bird-Rabatt, einen pro Person.';

  @override
  String get demoGiveFeedback => 'Feedback geben';

  @override
  String get demoFeedbackSent => 'Dein Feedback wurde gesendet. Danke.';

  @override
  String get demoListTitle => 'Auf die Early-Bird-Liste';

  @override
  String get demoListBody =>
      'Die Liste findest du auf unserer Website. Öffne diese Adresse im Browser:';

  @override
  String get demoCopyLink => 'Link kopieren';

  @override
  String get demoLinkCopied => 'Link kopiert';

  @override
  String get demoFeedbackTitle => 'Demo-Feedback';

  @override
  String get demoFeedbackIntro => 'Zwei Fragen, einmal pro Konto gesendet.';

  @override
  String get demoMissingQuestion => 'Was fehlt, oder was sollte besser sein?';

  @override
  String get demoMissingChoose => 'Antwort wählen';

  @override
  String get demoMissingScreenshotImport =>
      'Screenshots oder Fotos importieren';

  @override
  String get demoMissingMoreFileTypes => 'Mehr Dateitypen, zum Beispiel Word';

  @override
  String get demoMissingShareReport => 'Einen Bericht teilen oder exportieren';

  @override
  String get demoMissingBetterAccuracy => 'Genauere Befunde';

  @override
  String get demoMissingFasterResults => 'Schnellere Ergebnisse';

  @override
  String get demoMissingTeam => 'Zusammenarbeit im Team';

  @override
  String get demoMissingOther => 'Etwas anderes';

  @override
  String get demoMissingOtherLabel => 'Was ist es?';

  @override
  String demoMissingOtherHint(int min) {
    return 'Mindestens $min Zeichen.';
  }

  @override
  String get demoAnythingElse => 'Noch etwas?';

  @override
  String get demoAnythingElseHint =>
      'Optional. Bitte füge keinen Text aus deinen Dokumenten ein.';

  @override
  String get demoPriceQuestion =>
      'Was würdest du pro Monat für die Vollversion zahlen?';

  @override
  String get demoPlan =>
      'Die Vollversion, für eine Person: 20 Vergleiche im Monat, eingefügter Text oder PDFs mit auswählbarem Text, Belegstellen aus der Quelle, Prüfung und Projektverlauf.';

  @override
  String get demoPriceNothing => 'Nichts';

  @override
  String get demoPrice5 => '5 €';

  @override
  String get demoPrice10 => '10 €';

  @override
  String get demoPrice15 => '15 €';

  @override
  String get demoPriceOver15 => 'Mehr als 15 €';

  @override
  String get demoPriceNotSure => 'Weiß ich nicht';

  @override
  String get demoPriceNote =>
      'Das ist eine Frage, kein Angebot. Es wird nichts berechnet.';

  @override
  String get demoSend => 'Feedback senden';

  @override
  String get demoSending => 'Wird gesendet…';

  @override
  String get demoNeedsMissing => 'Wähle zuerst, was fehlt.';

  @override
  String demoNeedsOther(int min) {
    return 'Beschreibe mit mindestens $min Zeichen, was fehlt.';
  }

  @override
  String get demoNeedsPrice => 'Wähle einen Betrag.';

  @override
  String get demoSendHint =>
      'Wird einmal gesendet. Danach kannst du es nicht mehr ändern.';

  @override
  String get demoSendFailed =>
      'Dein Feedback konnte nicht gesendet werden. Deine Eingaben sind noch da. Versuche es erneut.';

  @override
  String get demoDone => 'Fertig';

  @override
  String get settingsDemo => 'Demo';
}
