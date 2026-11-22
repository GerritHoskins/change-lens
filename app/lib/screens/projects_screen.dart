// Project list and creation; the account screen (I-18), or in development builds the dev settings.
import 'dart:async';
import 'package:flutter/material.dart';

import '../api.dart';
import '../auth/account_consent.dart';
import '../design/calm_controls.dart';
import '../design/calm_icons.dart';
import '../design/calm_widgets.dart';
import '../l10n/app_localizations.dart';
import '../services.dart';
import 'project_screen.dart';
import 'compare_screen.dart';
import 'projects_home.dart';
import 'report_screen.dart';
import 'onboarding_screen.dart';
import 'settings_screen.dart';

enum _ProjectsMenu { howItWorks, account, devSettings }

class ProjectsScreen extends StatefulWidget {
  const ProjectsScreen({super.key});

  @override
  State<ProjectsScreen> createState() => _ProjectsScreenState();
}

class _ProjectsScreenState extends State<ProjectsScreen> {
  List<Project> projects = [];
  String? error;
  bool loading = false;
  Services? _services;
  Api? _api;
  Timer? _timer;
  bool _fetching = false, _loaded = false;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    final s = ServicesScope.of(context);
    if (!identical(s.api, _api) || _services == null) {
      _services = s;
      _api = s.api;
      projects = [];
      _loaded = false;
      _load();
    }
    _timer ??= Timer.periodic(const Duration(seconds: 3), (_) {
      if (appInForeground() && ModalRoute.of(context)?.isCurrent == true) _load();
    });
  }

  @override
  void dispose() { _timer?.cancel(); super.dispose(); }

  Future<void> _load() async {
    final s = ServicesScope.of(context);
    if (!s.configured || _fetching) return;
    final api = s.api;
    _fetching = true;
    // Only the first load shows progress: a poll must not swap the empty state for a bar every 3 s.
    if (!_loaded) setState(() => loading = true);
    try {
      final p = await api.projects();
      if (!mounted || !identical(api, s.api)) return;
      // A poll that changed nothing rebuilds nothing.
      final same = _loaded && error == null && !loading && p.length == projects.length &&
          [for (var i = 0; i < p.length; i++) p[i].signature == projects[i].signature].every((e) => e);
      _loaded = true;
      if (same) return;
      setState(() {
        projects = p;
        loading = false;
        error = null;
      });
    } on Exception catch (e) {
      if (!mounted || !identical(api, s.api)) return;
      _loaded = true; // the error and Retry stay; later polls don't bring the progress bar back
      final message = userErrorMessage(AppLocalizations.of(context), e);
      if (!loading && error == message) return; // still offline: nothing to redraw
      setState(() {
        loading = false;
        error = message;
      });
    } finally { _fetching = false; }
  }

  Future<void> _create() async {
    final l = AppLocalizations.of(context);
    final form = GlobalKey<FormState>();
    final name = TextEditingController(), client = TextEditingController();
    final ok = await showCalmSheet<bool>(context, builder: (context) {
      void submit() { if (form.currentState!.validate()) Navigator.pop(context, true); }
      return Form(key: form, child: CalmSheet(
        title: l.newProject,
        action: l.create, actionKey: const Key('create-project'),
        onAction: submit,
        children: [
          TextFormField(key: const Key('project-name'), controller: name, autofocus: true,
            validator: calmRequired(l.requiredProjectName), autovalidateMode: AutovalidateMode.onUserInteraction,
            textInputAction: TextInputAction.next, decoration: InputDecoration(labelText: l.projectName)),
          // The keyboard's Done key on the last field creates the project, like the button.
          TextField(key: const Key('project-client'), controller: client, textInputAction: TextInputAction.done,
            onSubmitted: (_) => submit(), decoration: InputDecoration(labelText: l.clientLabel)),
        ],
      ));
    });
    final projectName = name.text.trim(), clientLabel = client.text.trim();
    if (ok != true || !mounted) return;
    try {
      await ServicesScope.of(context).api.createProject(projectName,
          clientLabel: clientLabel.isEmpty ? null : clientLabel);
      await _load();
    } on Exception catch (e) {
      if (mounted) setState(() => error = userErrorMessage(AppLocalizations.of(context), e));
    }
  }

  /// Opens the project; with [report], its latest report on top, so Back lands on the project.
  Future<void> _open(Project p, {String? report}) async {
    final l = AppLocalizations.of(context);
    final navigator = Navigator.of(context);
    final closed = navigator.push<bool>(MaterialPageRoute(
      settings: const RouteSettings(name: ProjectScreen.routeName), builder: (_) => ProjectScreen(project: p)));
    if (report != null) {
      unawaited(navigator.push(MaterialPageRoute<void>(builder: (_) => ReportScreen(comparisonId: report))));
    }
    final deleted = await closed;
    if (!mounted) return;
    await _load();
    if (!mounted || deleted == null) return;
    calmSnack(context, deleted ? l.projectDeleted : l.projectDeletionPending);
  }

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final s = ServicesScope.of(context);
    final text = Theme.of(context).textTheme;
    // Two tiles side by side need room: at large text every project is a row instead.
    final home = HomeLayout(projects, tiles: MediaQuery.textScalerOf(context).scale(10) <= 13);
    // Nothing to compare yet: creating the first project is the main action, in the pinned pill.
    final first = s.configured && !loading && error == null && projects.isEmpty;
    return Scaffold(
      // No back button here, so the title starts on the 20px gutter like the headline under it.
      appBar: AppBar(title: Text(l.appTitle), titleSpacing: 20, actions: [
        PopupMenuButton<_ProjectsMenu>(
          key: const Key('projects-menu'),
          icon: Icon(const {TargetPlatform.iOS, TargetPlatform.macOS}.contains(Theme.of(context).platform)
            ? CalmIcons.moreIOS : CalmIcons.more),
          onSelected: (item) => Navigator.of(context).push(MaterialPageRoute<void>(builder: (_) => switch (item) {
            _ProjectsMenu.howItWorks => const OnboardingScreen(mode: OnboardingMode.replay),
            _ProjectsMenu.account => SettingsScreen(session: s.auth!,
                consent: s.consentFlow ? AccountConsent(s.auth!) : null),
            _ProjectsMenu.devSettings => const DevSettingsScreen(),
          })),
          itemBuilder: (_) => [
            PopupMenuItem(key: const Key('how-it-works'), value: _ProjectsMenu.howItWorks,
              child: Text(l.onbReplayEntry)),
            // Signed-in builds never show the dev connection (ui-ux-handoff §5).
            if (s.auth != null)
              PopupMenuItem(key: const Key('account'), value: _ProjectsMenu.account, child: Text(l.settingsTitle))
            else
              PopupMenuItem(key: const Key('settings'), value: _ProjectsMenu.devSettings,
                child: Text(l.devSettings)),
          ]),
        const SizedBox(width: 8),
      ]),
      // The main action sits in the thumb zone, as on Finding and the review summary.
      bottomNavigationBar: first ? CalmPinnedBar(
        child: FilledButton.icon(key: const Key('new-project'), onPressed: _create,
          icon: const Icon(CalmIcons.add), label: Text(l.newProject)))
      : s.configured && projects.isNotEmpty ? CalmPinnedBar(
        child: FilledButton.icon(key: const Key('compare-briefs'),
          onPressed: () => Navigator.of(context).push(MaterialPageRoute(builder: (_) => const CompareScreen())),
          icon: const Icon(CalmIcons.compare), label: Text(l.compareBriefs))) : null,
      body: !s.configured
          ? Center(child: Padding(padding: const EdgeInsets.all(24), child: Text(l.notConfigured, textAlign: TextAlign.center)))
          : SafeArea(top: false, child: RefreshIndicator.adaptive(
              onRefresh: _load,
              child: ListView(
                physics: const AlwaysScrollableScrollPhysics(),
                padding: const EdgeInsets.fromLTRB(20, 8, 20, 32),
                children: [
                // With projects, the headline leads with the result; without, it names the screen.
                if (projects.isEmpty) CalmPageHeader(title: l.projectsTitle, subtitle: l.projectsIntro)
                else HomeHeadline(changed: home.changed),
                if (loading) LinearProgressIndicator(semanticsLabel: l.loading),
                if (error != null) Padding(padding: const EdgeInsets.only(bottom: 16),
                  child: CalmWarning(text: error!,
                    child: CalmTextEdge(child: TextButton(onPressed: _load, child: Text(l.retry))))),
                if (!loading && error == null && projects.isEmpty)
                  CalmCard(child: Text(l.projectsEmpty, style: text.bodyLarge)),
                // The bento (home artboard): hero, a pair of tiles, rows; `space-3` apart.
                if (home.hero case final hero?) Padding(padding: const EdgeInsets.only(bottom: 14),
                  child: HomeHero(key: Key('home-hero-${hero.id}'), project: hero,
                    onTap: () => _open(hero, report: hero.latest!.id))),
                if (home.tiles.isNotEmpty) Padding(padding: const EdgeInsets.only(bottom: 14),
                  child: IntrinsicHeight(child: Row(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
                    for (final (i, p) in home.tiles.indexed) ...[
                      if (i > 0) const SizedBox(width: 14),
                      Expanded(child: HomeTile(key: Key('home-tile-${p.id}'), project: p, onTap: () => _open(p))),
                    ],
                  ]))),
                for (final p in home.rows) Padding(padding: const EdgeInsets.only(bottom: 14),
                  child: HomeRow(key: Key('home-row-${p.id}'), project: p, onTap: () => _open(p))),
                const SizedBox(height: 6),
                if (!first) Align(alignment: AlignmentDirectional.centerStart,
                  child: CalmTextEdge(child: TextButton.icon(key: const Key('new-project'), onPressed: _create,
                    icon: const Icon(CalmIcons.add), label: Text(l.newProject)))),
              ]),
            )),
    );
  }
}

class DevSettingsScreen extends StatefulWidget {
  const DevSettingsScreen({super.key});

  @override
  State<DevSettingsScreen> createState() => _DevSettingsScreenState();
}

class _DevSettingsScreenState extends State<DevSettingsScreen> {
  late final TextEditingController base, token;
  bool initialized = false, saving = false;
  String? error;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (initialized) return;
    initialized = true;
    final s = ServicesScope.of(context);
    base = TextEditingController(text: s.baseUrl);
    token = TextEditingController(text: s.token);
  }

  @override
  void dispose() { base.dispose(); token.dispose(); super.dispose(); }

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    return Scaffold(
      appBar: AppBar(title: Text(l.devSettings)),
      body: ListView(padding: const EdgeInsets.fromLTRB(20, 8, 20, 24), children: [
        Text(l.devSettingsHint),
        const SizedBox(height: 16),
        const SizedBox(height: 12),
        TextField(
            key: const Key('base-url'),
            controller: base,
            keyboardType: TextInputType.url,
            autocorrect: false,
            decoration: InputDecoration(labelText: l.apiBaseUrl, hintText: 'http://192.168.178.51:8000')),
        const SizedBox(height: 12),
        TextField(
            key: const Key('token'),
            controller: token,
            obscureText: true,
            autocorrect: false,
            decoration: InputDecoration(labelText: l.devToken)),
        const SizedBox(height: 16),
        if (error != null) Text(error!),
        FilledButton(
          key: const Key('save-settings'),
          onPressed: saving ? null : () async {
            setState(() { saving = true; error = null; });
            try {
              await ServicesScope.of(context).save(base.text, token.text);
              if (context.mounted) Navigator.pop(context);
            } on Exception {
              if (mounted) setState(() { saving = false; error = l.settingsSaveFailed; });
            }
          },
          child: Semantics(liveRegion: true, child: Text(saving ? l.saving : l.save)),
        ),
      ]),
    );
  }
}
