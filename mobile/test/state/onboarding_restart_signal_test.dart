/// DEF160 (mobile half) — "Restart onboarding" must actually replace the
/// caller's mandate for a signed-in user, and must NEVER do so for a plain
/// first-time interview. The backend already honours an explicit `restart`
/// flag (`onboarding.py::confirm_readback`, guarded by DEF060's re-auth-
/// replay check on the backend side, out of scope here); before this fix
/// `OnboardingNotifier.confirmReadback` never sent it, so Floor's "Restart
/// onboarding" control silently replayed the same preview-only path a
/// brand-new install gets — the exact bug this row documents.
///
/// Only `ApiClient` is faked, mirroring the `_RecordingApiClient` pattern in
/// `journal_plan_trust_boundary_test.dart` (DEF173) — proven against the
/// real `OnboardingNotifier`, not a rewritten stand-in.
library;

import 'package:ami_trade/models/onboarding.dart';
import 'package:ami_trade/services/api/api_client.dart';
import 'package:ami_trade/state/onboarding_providers.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

/// Records every `restart` value `confirmReadback` was called with.
class _RecordingApiClient extends ApiClient {
  _RecordingApiClient() : super(baseUrl: 'test://localhost');

  final List<bool> restartCallsSeen = [];

  @override
  Future<ReadbackConfirmResponse> confirmReadback({
    required String sessionId,
    required bool confirm,
    bool restart = false,
  }) async {
    restartCallsSeen.add(restart);
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

void main() {
  setUp(() {
    SharedPreferences.setMockInitialValues({});
  });

  group('DEF160 — the restart signal reaches confirmReadback', () {
    test('a plain (non-restart) session sends restart: false', () async {
      final api = _RecordingApiClient();
      final notifier = OnboardingNotifier(api);
      // Mirrors what a real start()/submitAnswer() run leaves behind by the
      // time the user reaches readback — the boundary under test is
      // confirmReadback's own logic, not the conversation that gets there.
      notifier.state = const OnboardingState(sessionId: 'sid-1');

      await notifier.confirmReadback();

      expect(
        api.restartCallsSeen,
        equals([false]),
        reason: 'a brand-new interview must never carry the restart signal',
      );
    });

    test(
      'a restart session (Floor "Restart onboarding") sends restart: true',
      () async {
        final api = _RecordingApiClient();
        final notifier = OnboardingNotifier(api);
        notifier.state = const OnboardingState(
          sessionId: 'sid-2',
          isRestart: true,
        );

        await notifier.confirmReadback();

        expect(
          api.restartCallsSeen,
          equals([true]),
          reason: 'this IS the case DEF160 exists for — retaking the '
              'interview from Floor must replace the existing mandate',
        );
      },
    );

    test('reset() defaults isRestart to false (every existing call site)',
        () async {
      final notifier = OnboardingNotifier(_RecordingApiClient());
      await notifier.reset();
      expect(notifier.state.isRestart, isFalse);
    });

    test('reset(isRestart: true) is threaded into state', () async {
      final notifier = OnboardingNotifier(_RecordingApiClient());
      await notifier.reset(isRestart: true);
      expect(notifier.state.isRestart, isTrue);
    });

    test('copyWith preserves isRestart unless explicitly overridden',
        () async {
      // Regression guard for the specific way this class of bug hides:
      // copyWith() runs on every phase transition during the interview
      // (submitAnswer, confirmReadback's own state updates). If isRestart
      // were left out of copyWith's field list, the very first
      // `state.copyWith(...)` after reset(isRestart: true) would silently
      // drop back to the constructor default (false) before
      // confirmReadback ever reads it.
      const restarted = OnboardingState(sessionId: 'sid-3', isRestart: true);
      final after = restarted.copyWith(currentStep: 'goal');
      expect(after.isRestart, isTrue);
    });
  });
}
