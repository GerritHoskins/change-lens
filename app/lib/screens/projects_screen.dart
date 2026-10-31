// Project list and creation, plus the developer settings for the dev API connection.
import 'package:flutter/material.dart';

import '../api.dart';
import '../l10n/app_localizations.dart';
import '../services.dart';
import 'project_screen.dart';

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

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    final s = ServicesScope.of(context);
    if (!identical(s.api, _services?.api) || _services == null) {
      _services = s;
      _load();
    }
  }

  Future<void> _load() async {
    final s = ServicesScope.of(context);
    if (!s.configured) return;
    setState(() => loading = true);
    try {
      final p = await s.api.projects();
      if (!mounted) return;
      setState(() {
        projects = p;
        loading = false;
        error = null;
      });
    } on Exception catch (e) {
      if (!mounted) return;
      setState(() {
        loading = false;
        error = '$e';
      });
    }
  }

  Future<void> _create() async {
    final l = AppLocalizations.of(context);
    final name = TextEditingController(), client = TextEditingController();
    final ok = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text(l.newProject),
        content: Column(mainAxisSize: MainAxisSize.min, children: [
          TextField(key: const Key('project-name'), controller: name, decoration: InputDecoration(labelText: l.projectName)),
          TextField(controller: client, decoration: InputDecoration(labelText: l.clientLabel)),
        ]),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context, false), child: Text(l.cancel)),
          FilledButton(
              key: const Key('create-project'),
              onPressed: () => Navigator.pop(context, name.text.trim().isNotEmpty),
              child: Text(l.create)),
        ],
      ),
    );
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
    return Scaffold(
      appBar: AppBar(title: Text(l.projectsTitle), actions: [
        IconButton(
            key: const Key('settings'),
            tooltip: l.devSettings,
            icon: const Icon(Icons.settings),
            onPressed: () => Navigator.of(context).push(MaterialPageRoute(builder: (_) => const DevSettingsScreen()))),
      ]),
      floatingActionButton: s.configured
          ? FloatingActionButton.extended(
              key: const Key('new-project'), onPressed: _create, icon: const Icon(Icons.add), label: Text(l.newProject))
          : null,
      body: !s.configured
          ? Center(child: Padding(padding: const EdgeInsets.all(24), child: Text(l.notConfigured, textAlign: TextAlign.center)))
          : RefreshIndicator(
              onRefresh: _load,
              child: ListView(children: [
                if (loading) const LinearProgressIndicator(),
                if (error != null) Padding(padding: const EdgeInsets.all(16), child: Text(error!)),
                if (!loading && error == null && projects.isEmpty)
                  Padding(padding: const EdgeInsets.all(24), child: Text(l.projectsEmpty)),
                for (final p in projects)
                  ListTile(
                    title: Text(p.name),
                    subtitle: p.clientLabel == null ? null : Text(p.clientLabel!),
                    trailing: const Icon(Icons.chevron_right),
                    onTap: () => Navigator.of(context).push(MaterialPageRoute(builder: (_) => ProjectScreen(project: p))),
                  ),
              ]),
            ),
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

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    final s = ServicesScope.of(context);
    base = TextEditingController(text: s.baseUrl);
    token = TextEditingController(text: s.token);
  }

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    return Scaffold(
      appBar: AppBar(title: Text(l.devSettings)),
      body: ListView(padding: const EdgeInsets.all(16), children: [
        Text(l.devSettingsHint),
        const SizedBox(height: 16),
        TextField(
            key: const Key('base-url'),
            controller: base,
            keyboardType: TextInputType.url,
            autocorrect: false,
            decoration: InputDecoration(labelText: l.apiBaseUrl, hintText: 'http://192.168.178.51:8000')),
        TextField(
            key: const Key('token'),
            controller: token,
            obscureText: true,
            autocorrect: false,
            decoration: InputDecoration(labelText: l.devToken)),
        const SizedBox(height: 16),
        FilledButton(
          key: const Key('save-settings'),
          onPressed: () async {
            await ServicesScope.of(context).save(base.text, token.text);
            if (context.mounted) Navigator.pop(context);
          },
          child: Text(l.save),
        ),
      ]),
    );
  }
}
