// The demo period (docs/demo-wall-handoff.md): the account's limit of comparisons and its one feedback
// form. The state comes from `POST /session` (`demo`) and `GET /me/demo`. A server that sends none (an
// older one) or a limit that is off (`limit: null`) means no demo line and no wall anywhere.
// Feedback never gives a comparison back. Its free text goes to the API and nowhere else: never to a log,
// never to device storage.
import 'package:flutter/foundation.dart';

import 'api.dart';

/// The landing page with the early-bird list. The app has no way to open a browser, so the wall shows
/// the address and copies the link.
const demoLandingHost = 'changelens.pixeltronic.dev';

String demoLandingUrl(String languageCode) =>
    'https://$demoLandingHost/${languageCode == 'de' ? 'de/' : ''}';

/// "What is missing" answers; `other` needs its text.
const demoMissingCodes = ['screenshot_import', 'more_file_types', 'share_report', 'better_accuracy',
  'faster_results', 'team', 'other'];

/// Answers to the monthly price question, in the form's order.
const demoPriceCodes = ['eur_0', 'eur_5', 'eur_10', 'eur_15', 'eur_over_15', 'not_sure'];

/// Lengths the server enforces for the two text fields, after trimming.
const demoOtherMin = 20, demoTextMax = 500;

class DemoState {
  const DemoState({required this.limit, required this.used, required this.inFlight, required this.remaining,
    required this.feedbackSubmitted, required this.discountOffered});

  /// Null for anything that is not the documented object with a limit: the app then shows nothing.
  static DemoState? fromJson(Object? json) {
    if (json is! Map) return null;
    final limit = json['limit'], used = json['used'], inFlight = json['in_flight'], remaining = json['remaining'];
    if (limit is! int || limit < 1 || used is! int || remaining is! int) return null;
    final feedback = json['feedback'];
    return DemoState(limit: limit, used: used, inFlight: inFlight is int ? inFlight : 0,
      remaining: remaining < 0 ? 0 : remaining,
      feedbackSubmitted: feedback is Map && feedback['submitted'] == true,
      discountOffered: feedback is Map && feedback['discount_offered'] == true);
  }

  /// Comparisons per account for its lifetime.
  final int limit;

  /// Finished comparisons (complete or partial); failed ones don't count.
  final int used;

  /// Started and not finished: they hold a place until they end.
  final int inFlight;
  final int remaining;
  final bool feedbackSubmitted;

  /// The server's switch for the one sentence about a discount for feedback. Off: not a word about it.
  final bool discountOffered;

  bool get atLimit => remaining <= 0;

  DemoState copyWith({int? remaining, bool? feedbackSubmitted}) => DemoState(limit: limit, used: used,
    inFlight: inFlight, remaining: remaining ?? this.remaining,
    feedbackSubmitted: feedbackSubmitted ?? this.feedbackSubmitted, discountOffered: discountOffered);
}

/// One filled-in feedback form.
class DemoFeedback {
  const DemoFeedback({required this.missing, this.missingOther, this.anythingElse, required this.price});

  final String missing, price;
  final String? missingOther, anythingElse;

  Map<String, dynamic> toJson() {
    final other = missingOther?.trim() ?? '', more = anythingElse?.trim() ?? '';
    return {'missing': missing, 'missing_other': missing == 'other' ? other : null,
      'anything_else': more.isEmpty ? null : more, 'price': price};
  }
}

/// The signed-in account's demo state, for the demo line, the wall, the form and Settings.
class DemoController extends ChangeNotifier {
  DemoController(this._api);

  final Api Function() _api;
  DemoState? _state;
  int _generation = 0;

  /// Null: no demo (limit off, an older server, or not known yet). Nothing is shown then.
  DemoState? get state => _state;

  bool get atLimit => _state?.atLimit ?? false;

  void _set(DemoState? next) {
    _generation++;
    _state = next;
    notifyListeners();
  }

  /// The `demo` object of `POST /session`.
  void adopt(Object? json) => _set(DemoState.fromJson(json));

  /// Signed out, or another account: nothing of the previous one stays.
  void clear() {
    if (_state != null) _set(null);
  }

  /// `GET /me/demo`. A failure keeps what is known; a server without the route means no demo.
  Future<void> refresh() async {
    final generation = _generation;
    try {
      final json = await _api().demo();
      if (generation == _generation) _set(DemoState.fromJson(json));
    } on ApiException catch (e) {
      if (e.status == 404 && generation == _generation) clear();
    } on Exception {
      // offline: the next refresh tries again
    }
  }

  /// The API refused a start with `demo_limit_reached`: what the app knew was out of date.
  void limitReached() {
    if (_state case final current?) _set(current.copyWith(remaining: 0));
  }

  /// Sends the form once. Already answered (on another device, say) counts as sent. Throws when it
  /// couldn't be sent; the caller keeps the entries.
  Future<void> sendFeedback(DemoFeedback feedback) async {
    try {
      final next = DemoState.fromJson(await _api().sendDemoFeedback(feedback.toJson()));
      _set(next ?? _state?.copyWith(feedbackSubmitted: true));
    } on ApiException catch (e) {
      if (e.status != 409 || e.code != 'already_answered') rethrow;
      _set(_state?.copyWith(feedbackSubmitted: true));
    }
  }
}
