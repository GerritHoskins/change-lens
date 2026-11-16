// The account's usage-events consent (D-18 tier B) for the consent screen and the Settings switch: read
// from the signed-in session, answered on the server. Nothing is stored on the device.
import '../screens/consent_screen.dart' show UsageConsent;
import 'session.dart';

class AccountConsent implements UsageConsent {
  AccountConsent(this.session);

  final AuthSession session;

  @override
  bool? get allowed => switch (session.state) {
    SignedIn(:final consent) || ReauthRequired(previous: SignedIn(:final consent)) => consent,
    _ => null,
  };

  @override
  Future<void> answer(bool allow) => session.answerUsageEvents(allow);

  @override
  void addListener(void Function() listener) => session.addListener(listener);

  @override
  void removeListener(void Function() listener) => session.removeListener(listener);
}
