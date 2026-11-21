// A project as `GET /projects` lists it, with the server's summary of its most recent comparison
// (docs/api-contracts-draft.md A2). Every count is the server's; the app never derives or invents one.

/// The most recent comparison of a project. The counts are null until it has a report
/// (`complete` or `partial`); null is never shown as 0.
class LatestComparison {
  LatestComparison(Map<String, dynamic> j)
      : id = j['id'] as String,
        status = j['status'] as String,
        earlierLabel = j['earlier_label'] as String?,
        laterLabel = j['later_label'] as String?,
        createdAt = DateTime.tryParse(j['created_at'] as String? ?? ''),
        findings = j['findings'] as int?,
        needsReview = j['needs_review'] as int?,
        reviewed = j['reviewed'] as int?,
        topicCounts = j['topic_counts'] == null ? null : Map<String, int>.from(j['topic_counts'] as Map);

  final String id, status;
  final String? earlierLabel, laterLabel;
  final DateTime? createdAt;

  /// Findings the report headline counts (needs a second look plus prioritised).
  final int? findings;
  final int? needsReview, reviewed;

  /// Per topic, over the same findings as [findings].
  final Map<String, int>? topicCounts;

  bool get hasReport => findings != null && reviewed != null;
  bool get inProgress => const {'waiting_for_versions', 'queued', 'running'}.contains(status);

  /// Findings without a confirm, correct or dismiss; 0 without a report.
  int get toCheck => hasReport ? (findings! - reviewed!).clamp(0, findings!) : 0;

  String get signature => '$id|$status|$earlierLabel|$laterLabel|$findings|$needsReview|$reviewed|$topicCounts';
}

class Project {
  Project(Map<String, dynamic> j)
      : id = j['id'] as String,
        name = j['name'] as String,
        clientLabel = j['client_label'] as String?,
        comparisonCounts = Map<String, int>.from(j['comparison_counts'] as Map? ?? const {}),
        latest = j['latest_comparison'] is Map<String, dynamic>
            ? LatestComparison(j['latest_comparison'] as Map<String, dynamic>) : null;

  final String id, name;
  final String? clientLabel;
  final Map<String, int> comparisonCounts;

  /// Null when the project was never compared, or when an older server doesn't send the summary.
  final LatestComparison? latest;

  /// The latest comparison has findings nobody has reviewed yet: the home screen's "changed".
  bool get changed => (latest?.toCheck ?? 0) > 0;

  /// Everything the home screen shows; equal signatures mean a poll changed nothing.
  String get signature => '$id|$name|$clientLabel|$comparisonCounts|${latest?.signature}';
}
