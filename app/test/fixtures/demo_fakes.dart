// Fakes for the demo limit, wall and feedback (docs/demo-wall-handoff.md): `GET /me/demo`,
// `POST /me/demo-feedback` and a refused comparison start, in front of the synthetic Cedar scenario.
// Never imported by the production entry point; no test reaches a network.
import 'dart:async';
import 'dart:convert';

import 'package:changelens/api.dart';
import 'package:changelens/demo.dart';
import 'package:changelens/services.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

import 'calm_scenario.dart';

/// The server's demo object: [remaining] of [limit] left.
Map<String, dynamic> demoJson({int limit = 3, int remaining = 3, int inFlight = 0, bool submitted = false,
    bool discount = false}) => {
  'limit': limit, 'used': limit - remaining - inFlight, 'in_flight': inFlight, 'remaining': remaining,
  'feedback': {'submitted': submitted, 'discount_offered': discount},
};

class DemoBackend {
  DemoBackend([this.demo]);

  final cedar = CedarScenario();
  final requests = <http.Request>[];

  /// What `GET /me/demo` answers; null answers 404, as a server without the route does.
  Map<String, dynamic>? demo;

  /// 201 stores the answer; 409 is `already_answered`; anything else fails.
  int feedbackStatus = 201;
  final feedback = <Map<String, dynamic>>[];

  /// While set, a feedback request waits for it: the "Sending…" state can be looked at.
  Completer<void>? hold;

  /// The server refuses a new comparison with `demo_limit_reached` (the app's state was out of date).
  bool refuseStart = false;

  static http.Response _json(Object value, [int status = 200]) => http.Response(jsonEncode(value), status,
    headers: {'content-type': 'application/json; charset=utf-8'});

  Future<http.Response> handle(http.Request request) async {
    final path = request.url.path;
    if (path == '/me/demo') {
      requests.add(request);
      return demo == null ? _json({'code': 'not_found'}, 404) : _json(demo!);
    }
    if (path == '/me/demo-feedback') {
      requests.add(request);
      await hold?.future;
      if (feedbackStatus == 409) return _json({'code': 'already_answered'}, 409);
      if (feedbackStatus != 201) return _json({'code': 'internal_error'}, feedbackStatus);
      feedback.add(jsonDecode(request.body) as Map<String, dynamic>);
      demo = {...demo!, 'feedback': {...demo!['feedback'] as Map<String, dynamic>, 'submitted': true}};
      return _json(demo!, 201);
    }
    if (refuseStart && request.method == 'POST' && path == '/projects/cedar/comparisons') {
      requests.add(request);
      return _json({'code': 'demo_limit_reached', 'used': 3, 'in_flight': 0, 'limit': 3}, 403);
    }
    return cedar.handle(request);
  }

  Api get api => Api('https://synthetic.invalid', 'synthetic-offline', client: MockClient(handle));

  /// A development-build [Services] (no account session): it asks `GET /me/demo` with the first list.
  Future<Services> services() async {
    final services = Services(CedarSettings(), CedarPicker(), apiFactory: (base, token) =>
      Api(base, token, client: MockClient(handle)));
    await services.load();
    return services;
  }

  /// A controller that already holds [demo], as after `POST /session`.
  DemoController controller() => DemoController(() => api)..adopt(demo);
}
