// Comparison status, polled until it finishes. The report screens are I-10.
import 'dart:async';

import 'package:flutter/material.dart';

import '../api.dart';
import '../l10n/app_localizations.dart';
import '../services.dart';

class ComparisonScreen extends StatefulWidget {
  const ComparisonScreen({super.key, required this.comparisonId, this.versions = const []});

  final String comparisonId;
  final List<Version> versions;

  @override
  State<ComparisonScreen> createState() => _ComparisonScreenState();
}

class _ComparisonScreenState extends State<ComparisonScreen> {
  Comparison? comparison;
  String? error;
  Timer? timer;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (timer == null) {
      _poll();
      timer = Timer.periodic(const Duration(seconds: 2), (_) => _poll());
    }
  }

  Future<void> _poll() async {
    try {
      final c = await ServicesScope.of(context).api.comparison(widget.comparisonId);
      if (!mounted) return;
      setState(() {
        comparison = c;
        error = null;
      });
      if (c.finished) timer?.cancel();
    } on Exception catch (e) {
      if (mounted) setState(() => error = '$e');
    }
  }

  @override
  void dispose() {
    timer?.cancel();
    super.dispose();
  }

  String _label(String id) => widget.versions.where((v) => v.id == id).map((v) => v.label).firstOrNull ?? '…';

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final c = comparison;
    final status = switch (c?.status) {
      'queued' => l.comparisonQueued,
      'running' => l.comparisonRunning,
      'complete' => l.comparisonComplete,
      'partial' => l.comparisonPartial,
      'failed' => l.comparisonFailed,
      _ => '…',
    };
    return Scaffold(
      appBar: AppBar(title: Text(l.comparisonTitle)),
      body: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          if (c != null) Text(l.earlierToNewer(_label(c.earlierId), _label(c.laterId)),
              style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: 12),
          Row(children: [
            if (c == null || !c.finished) const Padding(
                padding: EdgeInsets.only(right: 12),
                child: SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2))),
            Expanded(child: Text(l.comparisonStatus(status))),
          ]),
          if (error != null) Padding(padding: const EdgeInsets.only(top: 12), child: Text(error!)),
          if (c != null && c.finished)
            Padding(padding: const EdgeInsets.only(top: 24), child: Text(l.reportComing)),
        ]),
      ),
    );
  }
}
