// ChangeLens app shell (05 I-9): projects, versions, import by paste or PDF, and the order and
// scope confirmation. Portrait only on phones in v1 (06). UI strings come from lib/l10n.
// Builds with `--dart-define=CHANGELENS_LOGTO_APP_ID=...` sign in to an account (I-18); others use
// the dev settings.
import 'package:flutter/material.dart';
import 'package:flutter/foundation.dart' show LicenseRegistry, LicenseEntryWithLineBreaks;
import 'package:flutter/services.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:pdfrx/pdfrx.dart';

import 'auth/logto.dart';
import 'auth/session.dart';
import 'l10n/app_localizations.dart';
import 'design/calm_theme.dart';
import 'screens/account_gate.dart';
import 'services.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  LicenseRegistry.addLicense(() async* {
    yield LicenseEntryWithLineBreaks(['Roboto'], await rootBundle.loadString('assets/fonts/OFL.txt'));
  });
  await SystemChrome.setPreferredOrientations([DeviceOrientation.portraitUp]);
  await pdfrxFlutterInitialize(); // evidence view (I-10)
  final store = SecureSettingsStore();
  final config = AuthConfig.fromEnvironment();
  final services = Services(store, PlatformDocumentPicker(),
    auth: config == null ? null : AuthSession(config, store));
  await services.picker.purge(); // leftovers from an interrupted import (03a P10, AC-25)
  await services.load();
  services.auth?.restore(); // the gate waits on it
  runApp(ChangeLensApp(services: services));
}

class ChangeLensApp extends StatelessWidget {
  const ChangeLensApp({super.key, required this.services, this.home = const AccountGate(),
    this.themeMode = ThemeMode.system, this.locale});

  final Services services;
  final Widget home;
  final ThemeMode themeMode;
  final Locale? locale;

  @override
  Widget build(BuildContext context) => ServicesScope(
        services: services,
        child: MaterialApp(
          onGenerateTitle: (context) => AppLocalizations.of(context).appTitle,
          theme: calmTheme(Brightness.light),
          darkTheme: calmTheme(Brightness.dark),
          themeMode: themeMode,
          locale: locale,
          localizationsDelegates: const [
            AppLocalizations.delegate,
            GlobalMaterialLocalizations.delegate,
            GlobalWidgetsLocalizations.delegate,
            GlobalCupertinoLocalizations.delegate,
          ],
          supportedLocales: AppLocalizations.supportedLocales,
          builder: (context, child) => PrivacyCover(child: child!),
          home: home,
        ),
      );
}

/// Covers the screen while the app is inactive, so the app-switcher snapshot shows no document (03a P10).
class PrivacyCover extends StatefulWidget {
  const PrivacyCover({super.key, required this.child});

  final Widget child;

  @override
  State<PrivacyCover> createState() => _PrivacyCoverState();
}

class _PrivacyCoverState extends State<PrivacyCover> with WidgetsBindingObserver {
  bool covered = false;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) =>
      setState(() => covered = state != AppLifecycleState.resumed);

  @override
  Widget build(BuildContext context) => Stack(children: [
        ExcludeSemantics(excluding: covered, child: widget.child),
        if (covered)
          Positioned.fill(
            child: ColoredBox(
              color: Theme.of(context).colorScheme.surface,
              child: Center(child: Text(AppLocalizations.of(context).privacyCover,
                  style: Theme.of(context).textTheme.headlineMedium)),
            ),
          ),
      ]);
}
