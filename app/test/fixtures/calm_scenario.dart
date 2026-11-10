// Synthetic Cedar brief scenario shared by layout checks and isolated native previews.
// This file is never imported by the production entry point.
import 'dart:convert';

import 'package:changelens/api.dart';
import 'package:changelens/services.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

const cedarProject = {'id': 'cedar', 'name': 'Cedar website', 'client_label': 'Northstar Studio',
  'comparison_counts': {'partial': 1}};
const cedarVersions = [
  {'id': 'v2', 'label': 'Brief v2', 'kind': 'text', 'status': 'parsed'},
  {'id': 'v3', 'label': 'Brief v3', 'kind': 'text', 'status': 'parsed'},
];
const cedarEarlier = 'The project budget is €4,800 excluding VAT.\nFinal files are due on 20 November 2026.\nThe website includes five pages.';
const cedarNewer = 'The project budget is €6,200 excluding VAT.\nFinal files are due on 27 November 2026.\nThe website includes seven pages.';

Map<String, dynamic> cedarEvidence(String side, String quote, {int? page}) => {
  'side': side, 'quote': quote,
  'locator': {'page': page, 'char_start': 0, 'char_end': quote.length},
};

class CedarScenario {
  final requests = <http.Request>[];
  final findings = <Map<String, dynamic>>[
    {'id': 'budget', 'change_type': 'changed', 'category': 'budget', 'topic': 'budget',
      'group': 'prioritised', 'revision': 1, 'explanation': 'Project budget increased.',
      'evidence': [cedarEvidence('earlier', 'The project budget is €4,800 excluding VAT.', page: 2),
        cedarEvidence('later', 'The project budget is €6,200 excluding VAT.', page: 2)]},
    {'id': 'deadline', 'change_type': 'changed', 'category': 'date_deadline', 'topic': 'deadlines',
      'group': 'prioritised', 'revision': 1, 'explanation': 'Final delivery moved.',
      'evidence': [cedarEvidence('earlier', 'Final files are due on 20 November 2026.', page: 3),
        cedarEvidence('later', 'Final files are due on 27 November 2026.', page: 3)]},
    {'id': 'hosting', 'change_type': 'uncertain', 'category': 'responsibility_owner', 'topic': 'responsibilities',
      'group': 'needs_review', 'revision': 1, 'explanation': 'Responsibility for hosting is unclear.',
      'evidence': [cedarEvidence('earlier', 'Hosting is provided by the client.', page: 4)]},
  ];
  final reviews = <Map<String, dynamic>>[];
  Map<String, dynamic> get reportJson => {
    'status': 'partial', 'earlier_id': 'v2', 'later_id': 'v3', 'scope': 'partial', 'findings': findings,
    'summary': {'selected': true, 'prioritised': 2, 'other_differences': 1}, 'withheld_count': 0,
    'unexplained_differences': [cedarEvidence('later', 'Please send the source files.')],
    'presentation_only': [], 'warnings': <Map<String, String>>[],
  };
  Report get report => Report(reportJson);
  final comparison = {'id': 'cedar-comparison', 'earlier_id': 'v2', 'later_id': 'v3',
    'scope': 'partial', 'status': 'partial'};

  Future<http.Response> handle(http.Request request) async {
    requests.add(request);
    final path = request.url.path;
    http.Response json(Object value, [int status = 200]) => http.Response(jsonEncode(value), status,
      headers: {'content-type': 'application/json; charset=utf-8'});
    if (path.endsWith('/opened')) return http.Response('', 204);
    if (path == '/projects') return json({'projects': [cedarProject]});
    if (path == '/projects/cedar/versions') return json({'versions': cedarVersions});
    if (path == '/projects/cedar/comparisons') {
      return request.method == 'GET' ? json({'comparisons': [comparison]}) : json(comparison, 201);
    }
    if (path == '/comparisons/cedar-comparison') return json(comparison);
    if (path == '/comparisons/cedar-comparison/findings') return json(reportJson);
    if (path.startsWith('/versions/')) {
      final id = path.split('/')[2];
      if (path.endsWith('/text')) {
        final lines = (id == 'v2' ? cedarEarlier : cedarNewer).split('\n');
        return json({'pages': ['Cedar website brief', lines.first, lines.skip(1).join('\n'),
          'Hosting is provided by the client.']});
      }
      return json(cedarVersions.firstWhere((v) => v['id'] == id));
    }
    if (path.startsWith('/findings/')) {
      final id = path.split('/')[2];
      final finding = findings.firstWhere((f) => f['id'] == id);
      if (request.method == 'POST' && path.endsWith('/reviews')) {
        final body = jsonDecode(request.body) as Map<String, dynamic>;
        final review = {...body, 'at': '2026-11-07T12:00:00Z'};
        reviews.add(review);
        finding['review'] = review;
        return json({'finding': finding, 'review': review}, 201);
      }
      return json({...finding, 'revisions': [finding], 'reviews': reviews, 'client_approvals': []});
    }
    return json({'code': 'not_found'}, 404);
  }

  Future<Services> services() async {
    final services = Services(CedarSettings(), CedarPicker(), apiFactory: (base, token) =>
      Api(base, token, client: MockClient(handle)));
    await services.load();
    return services;
  }
}

class CedarSettings implements SettingsStore {
  final values = {'api_base_url': 'https://synthetic.invalid', 'dev_token': 'synthetic-offline'};
  @override
  Future<String?> read(String key) async => values[key];
  @override
  Future<void> write(String key, String value) async { values[key] = value; }
}

class CedarPicker implements DocumentPicker {
  @override
  Future<PickedDocument?> pickPdf() async => null;
  @override
  Future<void> purge() async {}
}
