// I-10 widget tests against a mocked API: the report groups and summary line (AC-10, AC-13), the
// unexplained and presentation-only lists (AC-18), review actions that never record approval and
// approval that is never a review (AC-12), corrections as new revisions (AC-15) and the parsed-text
// evidence view (AC-9).
import 'dart:convert';

import 'package:changelens/api.dart';
import 'package:changelens/main.dart';
import 'package:changelens/screens/evidence_screen.dart';
import 'package:changelens/screens/finding_header.dart';
import 'package:changelens/screens/finding_screen.dart';
import 'package:changelens/screens/report_screen.dart';
import 'package:changelens/services.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

import 'app_test.dart' show FakePicker, MemoryStore;

Map<String, dynamic> ev(String side, String quote, int start) =>
    {'side': side, 'quote': quote, 'locator': {'page': null, 'char_start': start, 'char_end': start + quote.length}};

Map<String, dynamic> finding(String id, String type, String category, String group, List<Map<String, dynamic>> evidence,
        {int revision = 1, Map<String, dynamic>? review, bool approval = false}) =>
    {'id': id, 'change_type': type, 'category': category, 'group': group, 'evidence': evidence,
     'explanation': 'Explanation of $id.', 'uncertainty': null, 'note': null, 'priority': 0, 'revision': revision,
     'supersedes_id': null, 'review': review, 'notes': 0, 'client_approval_recorded': approval};

const earlierText = 'Budget: EUR 12,000\nHosting is provided by the client';
const laterText = 'Budget: EUR 15,000\nCopywriting is included';

class ReportBackend {
  final requests = <http.Request>[];
  late var findings = [
    finding('f1', 'changed', 'quantity', 'prioritised', [ev('earlier', 'Budget: EUR 12,000', 0), ev('later', 'Budget: EUR 15,000', 0)]),
    finding('f2', 'uncertain', 'deliverable', 'needs_review', [ev('earlier', 'Hosting is provided by the client', 19)]),
    finding('f3', 'equivalent', 'deliverable', 'other', [ev('earlier', 'Logo', 0), ev('later', 'Logo', 0)]),
  ];
  final reviews = <Map<String, dynamic>>[];
  final approvals = <Map<String, dynamic>>[];

  Future<http.Response> handle(http.Request r) async {
    requests.add(r);
    final p = r.url.path;
    if (r.method == 'POST' && RegExp(r'^/(comparisons/c1|versions/v[12])/opened$').hasMatch(p)) {
      return http.Response('', 204);
    }
    if (r.method == 'GET' && p == '/comparisons/c1/findings') {
      return http.Response(jsonEncode({
        'status': 'partial', 'earlier_id': 'v1', 'later_id': 'v2', 'findings': findings,
        'summary': {'selected': true, 'prioritised': 1, 'other_differences': 5}, 'withheld_count': 2,
        'unexplained_differences': [ev('later', 'Hi,', 40)], 'presentation_only': [ev('later', '* Logo', 50)],
        'warnings': [{'code': 'hidden_text'}],
      }), 200);
    }
    final m = RegExp(r'^/findings/(\w+)(/reviews|/client-approvals)?$').firstMatch(p);
    if (m != null) {
      final f = findings.firstWhere((x) => x['id'] == m.group(1), orElse: () => {});
      if (f.isEmpty) return http.Response('{"code":"not_found"}', 404);
      if (r.method == 'GET') {
        return http.Response(jsonEncode({...f, 'revisions': [f], 'reviews': reviews, 'client_approvals': approvals}), 200);
      }
      final body = jsonDecode(r.body) as Map<String, dynamic>;
      if (m.group(2) == '/client-approvals') {
        approvals.add({...body, 'id': 'a1', 'finding_id': f['id']});
        return http.Response(jsonEncode(approvals.last), 201);
      }
      final review = {'action': body['action'], 'note': body['note'], 'dismissal_reason': body['dismissal_reason'],
        'at': '2026-10-31T10:00:00Z'};
      reviews.add(review);
      var current = {...f, 'review': review};
      if (body['correction'] != null) {
        current = {...current, ...(body['correction'] as Map), 'id': '${f['id']}r2', 'revision': 2};
        findings = [for (final x in findings) x['id'] == f['id'] ? current : x];
      }
      return http.Response(jsonEncode({'review': review, 'finding': current}), 201);
    }
    if (r.method == 'GET' && p == '/versions/v1/text') {
      return http.Response(jsonEncode({'id': 'v1', 'kind': 'text', 'pages': [earlierText], 'blocks': []}), 200);
    }
    return http.Response('{"code":"not_found"}', 404);
  }

  Iterable<String> posts() => requests.where((r) => r.method == 'POST').map((r) => r.url.path);
}

final versions = [
  Version({'id': 'v1', 'label': 'Brief v1', 'kind': 'text', 'status': 'parsed', 'parse_warnings': []}),
  Version({'id': 'v2', 'label': 'Brief v2', 'kind': 'text', 'status': 'parsed', 'parse_warnings': []}),
];

Future<ReportBackend> pump(WidgetTester tester, Widget home) async {
  final backend = ReportBackend();
  final store = MemoryStore()
    ..values['api_base_url'] = 'http://dev.test'
    ..values['dev_token'] = 'dev-token-0123456789';
  final services = Services(store, FakePicker(null),
      apiFactory: (base, token) => Api(base, token, client: MockClient(backend.handle)));
  await services.load();
  tester.view.physicalSize = const Size(800, 2400); // whole report on screen; ListView builds lazily
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.reset);
  await tester.pumpWidget(ChangeLensApp(services: services, home: home));
  await tester.pumpAndSettle();
  return backend;
}

Future<Report> loadReport(ReportBackend b) async =>
    Api('http://dev.test', 'dev-token-0123456789', client: MockClient(b.handle)).report('c1');

void main() {
  testWidgets('AC-10/13: material changes first, needs review apart, a selected-summary line', (tester) async {
    await pump(tester, ReportScreen(comparisonId: 'c1', versions: versions));
    expect(find.text('5 more differences, including moved or reformatted text'), findsOneWidget);
    expect(find.text('Changes'), findsOneWidget);
    expect(find.textContaining('Needs your review · '), findsOneWidget);
    // What needs the user's judgement comes before the certain changes.
    expect(tester.getTopLeft(find.textContaining('Needs your review · ')).dy,
      lessThan(tester.getTopLeft(find.text('Changes')).dy));
    expect(find.textContaining('Budget: EUR 15,000'), findsOneWidget);
    expect(find.textContaining('Hosting is provided'), findsOneWidget);
    expect(find.textContaining('Explanation of f3'), findsNothing); // "other" is behind the summary link
    expect(find.textContaining('2 findings withheld'), findsOneWidget);
    expect(find.textContaining('hidden text'), findsOneWidget);
    expect(find.textContaining('may be incomplete'), findsOneWidget);
  });

  testWidgets('AC-13/18: all differences lists other findings, unexplained and moved text', (tester) async {
    await pump(tester, ReportScreen(comparisonId: 'c1', versions: versions));
    await tester.tap(find.textContaining('more differences'));
    await tester.pumpAndSettle();
    expect(find.text('Other findings'), findsOneWidget);
    expect(find.textContaining('Explanation of f3'), findsOneWidget);
    final vertical = find.byWidgetPredicate((widget) => widget is Scrollable && widget.axisDirection == AxisDirection.down);
    await tester.scrollUntilVisible(find.textContaining('Other text differences (1)'), 200, scrollable: vertical);
    await tester.tap(find.textContaining('Other text differences (1)'));
    await tester.pumpAndSettle();
    expect(find.text('Hi,'), findsOneWidget);
    await tester.scrollUntilVisible(find.textContaining('Moved or reformatted (1)'), 200, scrollable: vertical);
    await tester.tap(find.textContaining('Moved or reformatted (1)'));
    await tester.pumpAndSettle();
    expect(find.text('* Logo'), findsOneWidget);
  });

  testWidgets('AC-12: confirming is a review only; recording approval is a separate record only', (tester) async {
    final backend = ReportBackend();
    final report = await loadReport(backend);
    report.findings.removeWhere((finding) => finding.id != 'f1'); // last finding stays for the separate approval action
    final b = await pump(tester, FindingScreen(comparisonId: 'c1', findingId: 'f1', report: report, versions: versions));
    await tester.tap(find.byKey(const Key('review-confirm')));
    await tester.pumpAndSettle();
    expect(b.posts(), ['/comparisons/c1/opened', '/findings/f1/reviews']);
    expect(jsonDecode(b.requests.lastWhere((r) => r.method == 'POST').body), containsPair('action', 'confirmed'));
    expect(find.text('Confirmed by you'), findsWidgets);
    expect(find.text('No client approval recorded.'), findsOneWidget);

    await tester.scrollUntilVisible(find.text('Record client approval'), 200,
      scrollable: find.descendant(of: find.byType(CustomScrollView), matching: find.byType(Scrollable)));
    await tester.tap(find.text('Record client approval'));
    await tester.pumpAndSettle();
    await tester.enterText(find.byKey(const Key('approval-evidence')), 'Mail: fine by us.');
    await tester.enterText(find.byKey(const Key('approval-by')), 'Client contact');
    await tester.tap(find.text('Save'));
    await tester.pumpAndSettle();
    expect(b.posts(), ['/comparisons/c1/opened', '/findings/f1/reviews', '/findings/f1/client-approvals']);
    expect(find.text('Client approval recorded (not verified by ChangeLens)'), findsOneWidget);
    for (final word in ['Approved', 'approved', 'Agreed', 'agreed']) {
      expect(find.textContaining(RegExp('\\b$word\\b')), findsNothing);
    }
  });

  testWidgets('AC-15: a correction is sent as a correction and the screen follows the new revision', (tester) async {
    final backend = ReportBackend();
    final report = await loadReport(backend);
    final b = await pump(tester, FindingScreen(comparisonId: 'c1', findingId: 'f1', report: report, versions: versions));
    await tester.tap(find.text('Correct'));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('category-field')));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Other').last);
    await tester.pumpAndSettle();
    await tester.tap(find.text('Save'));
    await tester.pumpAndSettle();
    final post = b.requests.lastWhere((r) => r.method == 'POST' && r.url.path.endsWith('/reviews'));
    expect(jsonDecode(post.body), {'action': 'corrected', 'note': null, 'correction': {'category': 'other_material'},
      'evidence_mode': {'before': 'text_only', 'after': 'text_only'}, 'page_opened': false});
    expect(b.requests.last.url.path, '/findings/f1r2'); // reloaded the new revision
    // The new revision's topic is the title; the label doesn't repeat it.
    expect(find.widgetWithText(FindingHeader, 'Other'), findsOneWidget);
    expect(find.text('Changed'), findsOneWidget);
  });

  testWidgets('AC-9: text evidence is shown in the parsed text with the exact span marked', (tester) async {
    final e = Evidence(ev('earlier', 'Hosting is provided by the client', 19));
    await pump(tester, EvidenceScreen(version: versions[0], evidence: e));
    final rich = tester.widget<SelectableText>(find.byType(SelectableText));
    final spans = (rich.textSpan!.children!).cast<TextSpan>();
    expect(spans.map((s) => s.text).join(), earlierText);
    expect(spans[1].text, 'Hosting is provided by the client');
    expect(spans[1].style?.backgroundColor, isNotNull);
  });
}
