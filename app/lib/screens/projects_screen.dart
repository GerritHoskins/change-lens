// Project list and creation; the account screen (I-18), or in development builds the dev settings.
import 'dart:async';
import 'package:flutter/material.dart';

import '../api.dart';
import '../design/calm_controls.dart';
import '../design/calm_icons.dart';
import '../design/calm_theme.dart';
import '../design/calm_widgets.dart';
import '../l10n/app_localizations.dart';
import '../services.dart';
import 'project_screen.dart';
import 'compare_screen.dart';
import 'comparison_screen.dart';
import 'onboarding_screen.dart';
import 'account_screen.dart';

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
  bool _fetching = false;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    final s = ServicesScope.of(context);
    if (!identical(s.api, _api) || _services == null) {
      _services = s;
      _api = s.api;
      projects = [];
      _load();
    }
    _timer ??= Timer.periodic(const Duration(seconds: 3), (_) {
      if (ModalRoute.of(context)?.isCurrent == true) _load();
    });
  }

  @override
  void dispose() { _timer?.cancel(); super.dispose(); }

  Future<void> _load() async {
    final s = ServicesScope.of(context);
    if (!s.configured || _fetching) return;
    final api = s.api;
    _fetching = true;
    setState(() => loading = projects.isEmpty);
    try {
      final p = await api.projects();
      if (!mounted || !identical(api, s.api)) return;
      setState(() {
        projects = p;
        loading = false;
        error = null;
      });
    } on Exception catch (e) {
      if (!mounted || !identical(api, s.api)) return;
      setState(() {
        loading = false;
        error = '$e';
      });
    } finally { _fetching = false; }
  }

  Future<void> _create() async {
    final l = AppLocalizations.of(context);
    final name = TextEditingController(), client = TextEditingController();
    final ok = await showCalmSheet<bool>(context, builder: (context) => CalmSheet(
      title: l.newProject,
      action: l.create, actionKey: const Key('create-project'),
      onAction: () => Navigator.pop(context, name.text.trim().isNotEmpty),
      children: [
        TextField(key: const Key('project-name'), controller: name, autofocus: true,
          textInputAction: TextInputAction.next, decoration: InputDecoration(labelText: l.projectName)),
        TextField(controller: client, decoration: InputDecoration(labelText: l.clientLabel)),
      ],
    ));
    if (ok != true || !mounted) return;
    try {
      await ServicesScope.of(context).api.createProject(name.text.trim(),
          clientLabel: client.text.trim().isEmpty ? null : client.text.trim());
      await _load();
    } on Exception catch (e) {
      setState(() => error = '$e');
    }
  }

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final s = ServicesScope.of(context);
    final colors = CalmColors.of(context);
    final text = Theme.of(context).textTheme;
    return Scaffold(
      appBar: AppBar(title: Text(l.appTitle), actions: [
        PopupMenuButton<_ProjectsMenu>(
          key: const Key('projects-menu'),
          icon: Icon(const {TargetPlatform.iOS, TargetPlatform.macOS}.contains(Theme.of(context).platform)
            ? CalmIcons.moreIOS : CalmIcons.more),
          onSelected: (item) => Navigator.of(context).push(MaterialPageRoute<void>(builder: (_) => switch (item) {
            _ProjectsMenu.howItWorks => const OnboardingScreen(mode: OnboardingMode.replay),
            _ProjectsMenu.account => AccountScreen(session: s.auth!),
            _ProjectsMenu.devSettings => const DevSettingsScreen(),
          })),
          itemBuilder: (_) => [
            PopupMenuItem(key: const Key('how-it-works'), value: _ProjectsMenu.howItWorks,
              child: Text(l.onbReplayEntry)),
            // Signed-in builds never show the dev connection (ui-ux-handoff §5).
            if (s.auth != null)
              PopupMenuItem(key: const Key('account'), value: _ProjectsMenu.account, child: Text(l.account))
            else
              PopupMenuItem(key: const Key('settings'), value: _ProjectsMenu.devSettings,
                child: Text(l.devSettings)),
          ]),
        const SizedBox(width: 8),
      ]),
      body: !s.configured
          ? Center(child: Padding(padding: const EdgeInsets.all(24), child: Text(l.notConfigured, textAlign: TextAlign.center)))
          : SafeArea(top: false, child: RefreshIndicator(
              onRefresh: _load,
              child: ListView(
                physics: const AlwaysScrollableScrollPhysics(),
                padding: const EdgeInsets.fromLTRB(20, 8, 20, 32),
                children: [
                CalmPageHeader(title: l.projectsTitle, subtitle: l.projectsIntro),
                if (loading) const LinearProgressIndicator(),
                if (error != null) Padding(padding: const EdgeInsets.only(bottom: 16),
                  child: CalmWarning(text: error!, child: TextButton(onPressed: _load, child: Text(l.retry)))),
                if (projects.isNotEmpty) Padding(padding: const EdgeInsets.only(bottom: 24),
                  child: FilledButton.icon(key: const Key('compare-briefs'),
                    onPressed: () => Navigator.of(context).push(MaterialPageRoute(builder: (_) => const CompareScreen())),
                    icon: const Icon(CalmIcons.compare), label: Text(l.compareBriefs))),
                if (!loading && error == null && projects.isEmpty)
                  CalmCard(color: colors.soft, child: Text(l.projectsEmpty, style: text.bodyLarge)),
                for (final p in projects)
                  Material(color: Colors.transparent, child: InkWell(
                    borderRadius: BorderRadius.circular(CalmRadius.md),
                    onTap: () async {
                      final deleted = await Navigator.of(context).push<bool>(
                        MaterialPageRoute(builder: (_) => ProjectScreen(project: p)));
                      if (!mounted) return;
                      await _load();
                      if (!context.mounted || deleted == null) return;
                      ScaffoldMessenger.of(context).showSnackBar(SnackBar(
                        content: Text(deleted ? l.projectDeleted : l.projectDeletionPending)));
                    },
                    child: Container(
                      padding: const EdgeInsets.symmetric(vertical: 20, horizontal: 4),
                      decoration: BoxDecoration(border: Border(bottom: BorderSide(color: colors.line))),
                      child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
                        Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                          Text(p.name, style: text.titleMedium),
                          if (p.clientLabel != null) Padding(padding: const EdgeInsets.only(top: 5),
                            child: Text(p.clientLabel!, style: text.bodyMedium?.copyWith(color: colors.muted))),
                          if (p.comparisonCounts.isNotEmpty) Padding(padding: const EdgeInsets.only(top: 8),
                            child: Text([
                              for (final entry in p.comparisonCounts.entries)
                                '${comparisonStatusLabel(l, entry.key)} (${entry.value})',
                            ].join(' · '), style: text.bodyMedium?.copyWith(color: colors.muted))),
                        ])),
                        const SizedBox(width: 12),
                        Icon(CalmIcons.chevronRight, color: colors.muted),
                      ]),
                    ),
                  )),
                const SizedBox(height: 20),
                Align(alignment: AlignmentDirectional.centerStart,
                  child: TextButton.icon(key: const Key('new-project'), onPressed: _create,
                    icon: const Icon(CalmIcons.add), label: Text(l.newProject))),
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
      body: ListView(padding: const EdgeInsets.all(16), children: [
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
