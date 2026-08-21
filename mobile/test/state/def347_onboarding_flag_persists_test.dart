/// DEF347 — the completion flag must be stamped when the SERVER says the
/// interview is done, not on a later UI tap.
///
/// `markComplete()` had exactly one caller: the claim-screen tap handler.
/// The server marks the session complete inside `confirmReadback`, so every
/// run had a window — confirm returns, LLM turns already spent, flag absent —
/// in which a kill, crash or eviction sent the user back into the interview
/// permanently: each cold start auto-started a fresh live greeting AND
/// overwrote the pending claim binding with a new, incomplete session id.
///
/// Only `ApiClient` is faked, following `onboarding_restart_signal_test.dart`,
/// so the real `OnboardingNotifier` is the thing under test.
library;

import 'package:ami_trade/models/onboarding.dart';
import 'package:ami_trade/services/api/api_client.dart';
import 'package:ami_trade/state/onboarding_providers.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

class _FakeApiClient extends ApiClient {
  _FakeApiClient({this.throwOnConfirm = false})
      : super(baseUrl: 'test://localhost');

  final bool throwOnConfirm;

  @override
  Future<ReadbackConfirmResponse> confirmReadback({
    required String sessionId,
    required bool confirm,
    bool restart = false,
  }) async {
    if (throwOnConfirm) throw Exception('network down');
    return const ReadbackConfirmResponse(
      completed: true,
      finalStep: 'complete',
      mandatePreview: {},
      followUpMessage: OnboardingMessage(
        author: ChatAuthorRemote.concierge,
        content: 'done',
        step: 'complete',
      ),
    );
  }
}

Future<bool?> _flag() async =>
    (await SharedPreferences.getInstance()).getBool('ami_onboarding_done');

void main() {
  setUp(() => SharedPreferences.setMockInitialValues({}));

  group('DEF347 — completion is stamped at server-confirm, not at a later tap',
      () {
    test('a successful confirmReadback persists the flag', () async {
      final notifier = OnboardingNotifier(_FakeApiClient());
      notifier.state = const OnboardingState(sessionId: 'sid-1');

      expect(await _flag(), isNull, reason: 'precondition: no flag yet');
      await notifier.confirmReadback();

      expect(
        await _flag(),
        isTrue,
        reason: 'the server is complete and the turns are spent — a kill here '
            'must not send the user back into the interview',
      );
    });

    test('a FAILED confirmReadback leaves the flag unset', () async {
      final notifier = OnboardingNotifier(_FakeApiClient(throwOnConfirm: true));
      notifier.state = const OnboardingState(sessionId: 'sid-2');

      await notifier.confirmReadback();

      expect(notifier.state.phase, OnboardingPhase.error);
      expect(
        await _flag(),
        isNull,
        reason: 'the server never completed — skipping onboarding would strand '
            'the user with no mandate',
      );
    });

    test('confirmReadback with no session id stamps nothing', () async {
      final notifier = OnboardingNotifier(_FakeApiClient());
      await notifier.confirmReadback();
      expect(await _flag(), isNull);
    });
  });
}
