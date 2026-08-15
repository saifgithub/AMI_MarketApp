/// DEF315 — the submit button came back to life while the trade was still
/// being reconciled.
///
/// `SimNotifier.submit` set `submitting: false` the instant the POST returned,
/// and then made four more sequential round trips before the screen reflected
/// anything: `simEvaluate` (the entire resting-order sweep, with a quote
/// fan-out), the portfolio, the trades and the book — plus the journal and the
/// watchlist. For every one of them the spinner had stopped and the portfolio
/// behind the sheet was still the pre-trade one.
///
/// Reported by a user as *"the app looked like it was back to the state just
/// before the order was made."* The confusion is the symptom. The defect is
/// that the trade ticket's CTA gates on `submitting` and never on `loading`, so
/// through that whole window **the button was live** — and a second tap places
/// a second order. The server dedups only trades carrying a `verdict_ref`
/// (`_existing_trade_for_verdict`); a manual trade has no such guard.
///
/// The test asserts on the flag as seen by a LISTENER, sampled on every state
/// change, because the bug is invisible to a before/after check: `submitting`
/// is false at the end either way. What changed is whether it was ever false
/// while the reconciliation was still running.
library;

import 'package:ami_trade/models/sim.dart';
import 'package:ami_trade/models/sim_resting_order.dart';
import 'package:ami_trade/services/api/api_client.dart';
import 'package:ami_trade/state/onboarding_providers.dart';
import 'package:ami_trade/state/sim_providers.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

SimPortfolio _portfolio() => SimPortfolio(
      userId: 'u',
      portfolioId: 'p',
      startingCapital: 10000,
      currentCash: 10000,
      holdings: const [],
      totalValue: 10000,
      drawdownPct: 0,
    );

/// A server whose reconciliation calls are SLOW, which is the condition the
/// defect lives in — a fast local backend hides it entirely.
class _SlowApi extends ApiClient {
  _SlowApi() : super(baseUrl: 'test://localhost');

  final List<String> calls = [];

  @override
  Future<SimSubmitResult> simSubmit({
    required String userId,
    required String ticker,
    required String side,
    required double quantity,
    String? orderType,
    double? limitPrice,
    double? triggerPrice,
    String? tif,
    double? stop,
    double? target,
    int? horizonDays,
    String? verdictRef,
  }) async {
    calls.add('submit');
    return SimSubmitResult.fromJson({
      'ok': true,
      'resting': false,
      'trade': {
        'id': 't1',
        'user_id': userId,
        'ticker': ticker,
        'side': side,
        'quantity': quantity,
        'entry_price': 100.0,
        'status': 'open',
        'opened_at': DateTime.utc(2026, 8, 15).toIso8601String(),
      },
      'compliance': {'passed': true, 'violations': [], 'blocked_by': null},
    });
  }

  @override
  Future<void> simEvaluate(String userId) async {
    calls.add('evaluate');
    await Future<void>.delayed(const Duration(milliseconds: 40));
  }

  @override
  Future<SimPortfolio> simPortfolio(String userId) async {
    calls.add('portfolio');
    await Future<void>.delayed(const Duration(milliseconds: 40));
    return _portfolio();
  }

  @override
  Future<List<SimTrade>> simListTrades(String userId,
          {String? statusFilter}) async =>
      const [];

  @override
  Future<List<SimRestingOrder>> simRestingOrders(String userId) async => const [];
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  setUp(() => SharedPreferences.setMockInitialValues({}));

  test('submitting stays true until the screen reflects the trade', () async {
    final api = _SlowApi();
    final container = ProviderContainer(
      overrides: [apiClientProvider.overrideWithValue(api)],
    );
    addTearDown(container.dispose);

    // Sample the flag on every state change — the defect is a window, not an
    // end state, so an before/after assertion cannot see it.
    final seen = <({bool submitting, String? portfolioId})>[];
    container.listen(simNotifierProvider, (_, next) {
      seen.add((
        submitting: next.submitting,
        portfolioId: next.portfolio?.portfolioId,
      ));
    });

    await container.read(simNotifierProvider.notifier).submit(
          ticker: 'AAPL',
          side: 'buy',
          quantity: 1,
        );

    // The reconciliation ran.
    expect(api.calls, containsAll(<String>['submit', 'evaluate', 'portfolio']));

    // Not one emission may show an idle button before the portfolio has
    // arrived. That combination IS the double-submit window.
    final idleBeforeReconciled = seen
        .takeWhile((s) => s.portfolioId == null)
        .any((s) => !s.submitting);
    expect(idleBeforeReconciled, isFalse,
        reason: 'the CTA gates on `submitting`; any moment where it is false '
            'while the portfolio is still pre-trade is a live button over an '
            'order that has already been placed');

    // And it does clear at the end, on the success path.
    expect(container.read(simNotifierProvider).submitting, isFalse);
  });

  test('submitting clears even when the submit throws', () async {
    final container = ProviderContainer(
      overrides: [apiClientProvider.overrideWithValue(_ThrowingApi())],
    );
    addTearDown(container.dispose);

    final result =
        await container.read(simNotifierProvider.notifier).submit(
              ticker: 'AAPL',
              side: 'buy',
              quantity: 1,
            );

    expect(result, isNull);
    // The `finally` is the point: the flag used to be cleared on the error path
    // only by the luck of an explicit assignment in the catch block.
    expect(container.read(simNotifierProvider).submitting, isFalse);
    expect(container.read(simNotifierProvider).error, isNotNull);
  });
}

class _ThrowingApi extends ApiClient {
  _ThrowingApi() : super(baseUrl: 'test://localhost');

  @override
  Future<SimSubmitResult> simSubmit({
    required String userId,
    required String ticker,
    required String side,
    required double quantity,
    String? orderType,
    double? limitPrice,
    double? triggerPrice,
    String? tif,
    double? stop,
    double? target,
    int? horizonDays,
    String? verdictRef,
  }) async =>
      throw StateError('server said no');
}
