// L35 (iPhone sitting, 2026-11-20): the sign-in browser opens although a provider sheet has only just
// closed, and Google's sheet shows once on iOS. Both run against stand-ins for the plugins.
import 'package:changelens/auth/logto.dart';
import 'package:changelens/auth/providers.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:google_sign_in/google_sign_in.dart';

void main() {
  group('sign-in browser', () {
    final url = Uri.parse('https://auth.test/oidc/auth?one_time_token=ott');
    late DateTime now;
    late List<Duration> waits;
    late List<Uri> opened;

    /// A browser whose attempts end as [outcomes] say: a String is the redirect, anything else is thrown.
    /// Each attempt takes [takes] on the clock.
    SystemWebAuthenticator browser(List<Object> outcomes, {Duration takes = Duration.zero}) {
      now = DateTime(2026, 11, 20, 12);
      waits = [];
      opened = [];
      return SystemWebAuthenticator(
        clock: () => now,
        wait: (d) async => waits.add(d),
        open: (u, scheme) async {
          opened.add(u);
          now = now.add(takes);
          final outcome = outcomes[opened.length - 1];
          if (outcome is String) return outcome;
          throw outcome;
        });
    }

    PlatformException failure(String code) => PlatformException(code: code);

    test('a browser that fails to open at once is opened again with the same URL', () async {
      final b = browser([failure('ACQUIRE_ROOT_VIEW_CONTROLLER_FAILED'), 'app://callback?code=c']);
      expect(await b.authenticate(url, 'app'), 'app://callback?code=c');
      expect(opened, [url, url]);
      expect(waits, [SystemWebAuthenticator.retryDelays.first]);
    });

    test('it gives up after the last retry, with the code of the last failure', () async {
      final b = browser([failure('ACQUIRE_ROOT_VIEW_CONTROLLER_FAILED'), failure('EUNKNOWN'), failure('EUNKNOWN')]);
      await expectLater(b.authenticate(url, 'app'),
        throwsA(isA<AuthFailed>().having((e) => e.code, 'code', 'browser_EUNKNOWN')));
      expect(opened, hasLength(SystemWebAuthenticator.retryDelays.length + 1));
      expect(waits, SystemWebAuthenticator.retryDelays);
    });

    test('a failure after the browser was open is not retried', () async {
      final b = browser([failure('EUNKNOWN'), 'app://callback?code=c'], takes: const Duration(seconds: 5));
      await expectLater(b.authenticate(url, 'app'),
        throwsA(isA<AuthFailed>().having((e) => e.code, 'code', 'browser_EUNKNOWN')));
      expect(opened, hasLength(1));
      expect(waits, isEmpty);
    });

    test('closing the browser is a cancellation and is never retried', () async {
      final b = browser([failure('CANCELED'), 'app://callback?code=c']);
      await expectLater(b.authenticate(url, 'app'), throwsA(isA<AuthCancelled>()));
      expect(opened, hasLength(1));
    });
  });

  group('Google server code', () {
    const scopes = ['openid', 'email'];
    late List<List<String>> asked;

    /// Answers each request for a server code in turn: a String or null is returned, anything else thrown.
    Future<String?> Function(List<String>) google(List<Object?> answers) {
      asked = [];
      return (requested) async {
        asked.add(requested);
        final answer = answers[asked.length - 1];
        if (answer is String?) return answer;
        throw answer;
      };
    }

    test('iOS takes the code of the sign-in itself, without asking for a scope again', () async {
      expect(await googleServerCode(google(['code-1']), ios: true, scopes: scopes), 'code-1');
      expect(asked, [<String>[]]);
    });

    test('iOS asks with the scopes when the sign-in left no code', () async {
      expect(await googleServerCode(google([null, 'code-2']), ios: true, scopes: scopes), 'code-2');
      expect(asked, [<String>[], scopes]);
    });

    test('iOS asks with the scopes when the first request fails', () async {
      const error = GoogleSignInException(code: GoogleSignInExceptionCode.unknownError);
      expect(await googleServerCode(google([error, 'code-3']), ios: true, scopes: scopes), 'code-3');
      expect(asked, [<String>[], scopes]);
      final plugin = PlatformException(code: 'channel-error');
      expect(await googleServerCode(google([plugin, 'code-3b']), ios: true, scopes: scopes), 'code-3b');
      expect(asked, [<String>[], scopes]);
    });

    test('a cancellation is passed on, not answered with a second sheet', () async {
      const cancelled = GoogleSignInException(code: GoogleSignInExceptionCode.canceled);
      await expectLater(googleServerCode(google([cancelled, 'code-4']), ios: true, scopes: scopes),
        throwsA(isA<GoogleSignInException>()));
      expect(asked, hasLength(1));
    });

    test('Android asks once, with the scopes', () async {
      expect(await googleServerCode(google(['code-5']), ios: false, scopes: scopes), 'code-5');
      expect(asked, [scopes]);
    });
  });
}
