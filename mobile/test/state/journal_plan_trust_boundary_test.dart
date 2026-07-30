/// DEF173 — the journal retention cap must come from the authenticated
/// user's own mandate, never from a client-supplied argument with a
/// default.
///
/// Before this fix, `JournalNotifier.refresh({String plan = 'trial_trader'})`
/// took the plan as a parameter with a default, and every real call site in
/// the app called `refresh()` without ever supplying one — so the retention
/// window, "older entries" count, and retention caveat were always computed
/// against `trial_trader`, regardless of who was signed in. A Floor Pass
/// user could be shown a caveat belonging to a different plan.
///
/// Proven here against the real `JournalNotifier` and `MandateNotifier`
/// (only `ApiClient` is faked) that:
///   1. A signed-in user on a non-default plan gets THAT plan's retention,
///      not `trial_trader`'s (the acceptance-criteria case).
///   2. The plan is not accepted as a parameter at all any more — it is
///      derived from `mandateNotifierProvider` every call.
///   3. If the mandate has not loaded yet, `refresh()` does not guess: it
///      makes no network call rather than fetching under the wrong plan.
library;

import 'package:ami_trade/models/journal.dart';
import 'package:ami_trade/models/mandate.dart';
import 'package:ami_trade/services/api/api_client.dart';
import 'package:ami_trade/state/journal_providers.dart';
import 'package:ami_trade/state/mandate_providers.dart';
import 'package:ami_trade/state/onboarding_providers.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

/// Records every `plan` it was called with and hands back a retention
/// window keyed to that plan — 'trial_trader' => 30, 'floor_pass' => 7 —
/// so a test can prove which plan actually reached the wire.
class _RecordingApiClient extends ApiClient {
  _RecordingApiClient() : super(baseUrl: 'test://localhost');

  final List<String> planCallsSeen = [];

  static const _retentionByPlan = {
    'trial_trader': 30,
    'floor_pass': 7,
  };

  @override
  Future<JournalListResponse> listJournal({
    required String userId,
    required String plan,
    String? entryType,
    String? ticker,
    String? q,
    int limit = 100,
  }) async {
    planCallsSeen.add(plan);
    return JournalListResponse(
      entries: const [],
      total: 0,
      retentionDays: _retentionByPlan[plan],
    );
  }
}

/// Never touches the network — its state is set directly, mirroring the
/// `_ScriptedMandateNotifier` pattern used elsewhere for this exact reason.
class _FixedMandateNotifier extends MandateNotifier {
  _FixedMandateNotifier(super.ref, UserMandate? initial) {
    state = MandateState(mandate: initial);
  }

  @override
  Future<void> refresh() async {} // no-op: state is fixed for the test
}

UserMandate _mandate({required String plan}) => UserMandate(
      userId: 'u1',
      version: 1,
      displayName: 'Trader',
      locale: 'en',
      timezone: 'UTC',
      primaryGoal: 'long_term_wealth',
      horizon: 'long',
      path: 'long_horizon',
      riskScore: 3,
      riskComponents: const RiskComponents(
        drawdownResponse: 3,
        regretAsymmetry: 0,
        concentrationTolerance: 3,
      ),
      maxDrawdownPct: 30,
      learningStyle: 'quick',
      compliance: const ComplianceFlags(),
      plan: plan,
      creditBalance: 75,
    );

void main() {
  setUp(() {
    SharedPreferences.setMockInitialValues({});
  });

  group('DEF173 — journal retention plan is derived, not client-supplied', () {
    test('a Floor Pass user gets Floor Pass retention, not trial_trader\'s',
        () async {
      final fakeApi = _RecordingApiClient();
      final container = ProviderContainer(overrides: [
        apiClientProvider.overrideWithValue(fakeApi),
        mandateNotifierProvider.overrideWith(
          (ref) => _FixedMandateNotifier(ref, _mandate(plan: 'floor_pass')),
        ),
      ]);
      addTearDown(container.dispose);

      // Reads the notifier (its own `Future.microtask(refresh)` — the same
      // one every real screen relies on, no call site passes a plan) then
      // drains the event queue rather than calling refresh() a second time,
      // which would race the provider's own auto-refresh.
      container.read(journalNotifierProvider.notifier);
      await pumpEventQueue();

      expect(fakeApi.planCallsSeen, isNotEmpty);
      expect(fakeApi.planCallsSeen.toSet(), {'floor_pass'},
          reason: 'every call must use the real plan, never trial_trader');
      expect(
        container.read(journalNotifierProvider).retentionDays,
        7,
        reason: 'Floor Pass retention, not the old trial_trader default of 30',
      );
    });

    test('no mandate loaded yet => no network call, no guessed plan',
        () async {
      final fakeApi = _RecordingApiClient();
      final container = ProviderContainer(overrides: [
        apiClientProvider.overrideWithValue(fakeApi),
        mandateNotifierProvider.overrideWith(
          (ref) => _FixedMandateNotifier(ref, null),
        ),
      ]);
      addTearDown(container.dispose);

      container.read(journalNotifierProvider.notifier);
      await pumpEventQueue();

      expect(fakeApi.planCallsSeen, isEmpty);
      expect(container.read(journalNotifierProvider).retentionLoaded, isFalse);
    });
  });
}
