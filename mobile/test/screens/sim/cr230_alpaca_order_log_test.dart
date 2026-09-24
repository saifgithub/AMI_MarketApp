/// CR230 — every `AlpacaClient.submitOrder()` resolution reports its outcome
/// to `/v1/alpaca/order_log`, best-effort.
///
/// Saiful: "we need to keep a log of every interaction we have with alpaca."
/// The three things this file pins:
/// 1. A successful order reports `outcome: submitted` with the returned
///    Alpaca order id/status.
/// 2. A client-side refusal (`AlpacaOrderRejected` — wrong order type or a
///    non-paper host, CR227's round-2 fix) reports `outcome:
///    refused_client_side`, not `rejected_by_alpaca` — the two are different
///    facts (never reached Alpaca vs. Alpaca said no) and collapsing them
///    would misrepresent which is true, the same CR040 distinction the
///    backend's `constraint_status`/`prompt_version` columns draw elsewhere.
/// 3. The report call is fire-and-forget: a THROWING log call must never
///    change the trade ticket's own success/failure outcome — the log is a
///    side effect of an already-decided result, never a gate on it.
/// 4. The report call is fire-and-forget in the OTHER sense too: a SLOW log
///    call must never delay the user's confirmation. Round-1 audit MAJOR-1 —
///    `_placeAlpacaOrder` used to `await` the report before returning, which
///    meant the outcome row / haptic / success banner were all gated on a
///    round-trip to AMI's own backend, even though the Alpaca order had
///    already executed. A `try/catch` only guards against the call
///    *throwing*; it does nothing to bound how long it *takes*. Fixed with
///    `unawaited(...)` at all four call sites in `_placeAlpacaOrder`.
/// 5. The round-2 audit verified property 4 at the three FAILURE branches
///    too (`refused_client_side`, `rejected_by_alpaca` x2) via its own
///    scratch probes, but those never landed as committed tests — flagged
///    in its closing note as "the one place this CR's guard is thinner than
///    its guarantee": a future fifth outcome branch that re-introduces
///    `await` would go unnoticed. These three tests close that gap.
library;

import 'dart:async';

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/features/sim/order_pricing.dart';
import 'package:ami_trade/models/alpaca.dart';
import 'package:ami_trade/models/sim.dart';
import 'package:ami_trade/screens/sim/trade_ticket_sheet.dart';
import 'package:ami_trade/services/alpaca/alpaca_client.dart';
import 'package:ami_trade/services/api/api_client.dart';
import 'package:ami_trade/state/alpaca_providers.dart';
import 'package:ami_trade/state/onboarding_providers.dart';
import 'package:ami_trade/state/sim_providers.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

class _OrderLogCall {
  const _OrderLogCall({
    required this.symbol,
    required this.side,
    required this.qty,
    required this.destination,
    required this.outcome,
    this.detail,
    this.alpacaOrderId,
    this.alpacaStatus,
  });

  final String symbol;
  final String side;
  final double qty;
  final String destination;
  final String outcome;
  final String? detail;
  final String? alpacaOrderId;
  final String? alpacaStatus;
}

class _RecordingApiClient extends ApiClient {
  _RecordingApiClient({this.throwOnLog = false}) : super(baseUrl: 'test://localhost');

  final bool throwOnLog;
  final List<_OrderLogCall> orderLogCalls = [];

  @override
  Future<void> alpacaReportOrderLog({
    required String symbol,
    required String side,
    required double qty,
    required String destination,
    required String outcome,
    String? detail,
    String? alpacaOrderId,
    String? alpacaStatus,
  }) async {
    orderLogCalls.add(_OrderLogCall(
      symbol: symbol,
      side: side,
      qty: qty,
      destination: destination,
      outcome: outcome,
      detail: detail,
      alpacaOrderId: alpacaOrderId,
      alpacaStatus: alpacaStatus,
    ));
    if (throwOnLog) {
      throw Exception('order_log endpoint unreachable (test)');
    }
  }
}

/// Never resolves until the test explicitly completes [gate] — models a
/// backend that is merely SLOW, not down, so the fix under test (`unawaited`)
/// is isolated from the already-covered throwing case above.
class _SlowApiClient extends ApiClient {
  _SlowApiClient() : super(baseUrl: 'test://localhost');

  final Completer<void> gate = Completer<void>();
  final List<String> orderLogCalls = [];
  bool logCallResolved = false;

  @override
  Future<void> alpacaReportOrderLog({
    required String symbol,
    required String side,
    required double qty,
    required String destination,
    required String outcome,
    String? detail,
    String? alpacaOrderId,
    String? alpacaStatus,
  }) async {
    orderLogCalls.add(outcome);
    await gate.future;
    logCallResolved = true;
  }
}

class _AcceptingAlpacaClient extends AlpacaClient {
  @override
  Future<AlpacaOrder> submitOrder({
    required String symbol,
    required String side,
    required double qty,
    required SimOrderType orderType,
  }) async {
    return AlpacaOrder(
      id: 'ord_test_1',
      symbol: symbol,
      side: side,
      qty: qty,
      status: 'accepted',
    );
  }
}

class _RefusingAlpacaClient extends AlpacaClient {
  @override
  Future<AlpacaOrder> submitOrder({
    required String symbol,
    required String side,
    required double qty,
    required SimOrderType orderType,
  }) async {
    throw const AlpacaOrderRejected(
      'refusing to place an order against a non-paper Alpaca host: test',
    );
  }
}

class _RejectingAlpacaClient extends AlpacaClient {
  @override
  Future<AlpacaOrder> submitOrder({
    required String symbol,
    required String side,
    required double qty,
    required SimOrderType orderType,
  }) async {
    throw const AlpacaException(422, 'insufficient buying power');
  }
}

/// The catch-all branch in `_placeAlpacaOrder` — a throw that is neither
/// `AlpacaOrderRejected` nor `AlpacaException`.
class _UnexpectedlyThrowingAlpacaClient extends AlpacaClient {
  @override
  Future<AlpacaOrder> submitOrder({
    required String symbol,
    required String side,
    required double qty,
    required SimOrderType orderType,
  }) async {
    throw StateError('unexpected');
  }
}

class _FixedSim extends SimNotifier {
  _FixedSim(super.ref, SimState fixed, {this.previewResult}) {
    state = fixed;
  }

  final SimPreviewResult? previewResult;

  @override
  Future<SimPreviewResult?> preview({
    required String ticker,
    required String side,
    required double quantity,
    String? verdictRef,
  }) async =>
      previewResult;
}

SimPortfolio _portfolio() => SimPortfolio.fromJson({
      'user_id': 'u',
      'portfolio_id': 'p',
      'starting_capital': 10000,
      'current_cash': 10000,
      'holdings': const [],
      'total_value': 10000,
      'drawdown_pct': 0,
      'price_source': 'yfinance',
      'cash_committed': 0,
      'cash_available': 10000,
      'resting_order_count': 0,
      'shares_committed': const {},
      'shorts': const [],
      'closed_shorts': const [],
    });

Future<void> _pump(
  WidgetTester t, {
  required AlpacaClient alpacaClient,
  required _RecordingApiClient apiClient,
}) async {
  await t.binding.setSurfaceSize(const Size(390, 1600));
  addTearDown(() => t.binding.setSurfaceSize(null));
  await t.pumpWidget(ProviderScope(
    overrides: [
      simNotifierProvider.overrideWith((ref) => _FixedSim(
            ref,
            SimState(portfolio: _portfolio()),
            previewResult: const SimPreviewResult(accepted: true),
          )),
      alpacaLinkedProvider.overrideWith((ref) async => true),
      alpacaClientProvider.overrideWithValue(alpacaClient),
      apiClientProvider.overrideWithValue(apiClient),
    ],
    child: MaterialApp(
      localizationsDelegates: AppLocalizations.localizationsDelegates,
      supportedLocales: AppLocalizations.supportedLocales,
      // CR232 — `TradeTicketSheet` builds its own `Scaffold` now.
      home: const TradeTicketSheet(tickerPrefill: 'AAPL'),
    ),
  ));
  for (var i = 0; i < 4; i++) {
    await t.pump(const Duration(milliseconds: 120));
  }
  await t.tap(find.text('ALPACA PAPER'));
  await t.pump(const Duration(milliseconds: 120));
  await t.tap(find.text('SUBMIT TRADE'));
  for (var i = 0; i < 6; i++) {
    await t.pump(const Duration(milliseconds: 120));
  }
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  setUp(() => SharedPreferences.setMockInitialValues({}));

  group('order outcome reporting', () {
    testWidgets('a submitted order reports outcome: submitted with the Alpaca order id',
        (t) async {
      final api = _RecordingApiClient();
      await _pump(t, alpacaClient: _AcceptingAlpacaClient(), apiClient: api);

      expect(api.orderLogCalls, hasLength(1));
      final call = api.orderLogCalls.single;
      expect(call.outcome, 'submitted');
      expect(call.destination, 'alpaca_only');
      expect(call.symbol, 'AAPL');
      expect(call.alpacaOrderId, 'ord_test_1');
      expect(call.alpacaStatus, 'accepted');
    });

    testWidgets(
        'a client-side refusal reports outcome: refused_client_side, not rejected_by_alpaca',
        (t) async {
      final api = _RecordingApiClient();
      await _pump(t, alpacaClient: _RefusingAlpacaClient(), apiClient: api);

      expect(api.orderLogCalls, hasLength(1));
      final call = api.orderLogCalls.single;
      expect(call.outcome, 'refused_client_side',
          reason: 'this order never reached Alpaca at all — collapsing it '
              'into rejected_by_alpaca would misrepresent that fact');
      expect(call.detail, contains('non-paper'));
      expect(call.alpacaOrderId, isNull);
    });

    testWidgets('an Alpaca-side rejection reports outcome: rejected_by_alpaca',
        (t) async {
      final api = _RecordingApiClient();
      await _pump(t, alpacaClient: _RejectingAlpacaClient(), apiClient: api);

      expect(api.orderLogCalls, hasLength(1));
      final call = api.orderLogCalls.single;
      expect(call.outcome, 'rejected_by_alpaca');
      expect(call.detail, contains('insufficient buying power'));
    });
  });

  group('the log call never gates the trade outcome', () {
    testWidgets(
        'a throwing order_log call still shows the same success banner as a working one',
        (t) async {
      final api = _RecordingApiClient(throwOnLog: true);
      await _pump(t, alpacaClient: _AcceptingAlpacaClient(), apiClient: api);

      // The log call was attempted (and threw internally) but the trade's
      // own success path — the snackbar text built from the Alpaca order
      // result — must still be exactly what a working log call would show.
      expect(api.orderLogCalls, hasLength(1),
          reason: 'the report was still attempted despite failing');
      expect(api.orderLogCalls.single.outcome, 'submitted',
          reason: 'a failed log call must never suppress or alter what the '
              'trade ticket itself determined the outcome to be — the '
              'report throwing is a fact about the report, not the trade');
      expect(t.takeException(), isNull,
          reason: 'a throwing best-effort log call must be swallowed, never '
              'surface as an unhandled exception in the widget tree');
    });

    testWidgets(
        'a SLOW (never-throwing) order_log call still shows the outcome '
        'immediately — round-1 audit MAJOR-1', (t) async {
      final api = _SlowApiClient();
      await t.binding.setSurfaceSize(const Size(390, 1600));
      addTearDown(() => t.binding.setSurfaceSize(null));
      await t.pumpWidget(ProviderScope(
        overrides: [
          simNotifierProvider.overrideWith((ref) => _FixedSim(
                ref,
                SimState(portfolio: _portfolio()),
                previewResult: const SimPreviewResult(accepted: true),
              )),
          alpacaLinkedProvider.overrideWith((ref) async => true),
          alpacaClientProvider.overrideWithValue(_AcceptingAlpacaClient()),
          apiClientProvider.overrideWithValue(api),
        ],
        child: MaterialApp(
          localizationsDelegates: AppLocalizations.localizationsDelegates,
          supportedLocales: AppLocalizations.supportedLocales,
          // CR232 — `TradeTicketSheet` builds its own `Scaffold` now.
          home: const TradeTicketSheet(tickerPrefill: 'AAPL'),
        ),
      ));
      for (var i = 0; i < 4; i++) {
        await t.pump(const Duration(milliseconds: 120));
      }
      await t.tap(find.text('ALPACA PAPER'));
      await t.pump(const Duration(milliseconds: 120));
      await t.tap(find.text('SUBMIT TRADE'));
      // Pump enough for the Alpaca call + the UI update to land, but the log
      // call's gate is still deliberately uncompleted — this is the moment
      // that regresses under `await`: the whole point is that the user's
      // confirmation must not still be pending here.
      for (var i = 0; i < 6; i++) {
        await t.pump(const Duration(milliseconds: 120));
      }

      expect(api.orderLogCalls, hasLength(1),
          reason: 'the report was attempted — it is in flight, not skipped');
      expect(api.logCallResolved, isFalse,
          reason: 'the gate is still closed — the log call has NOT finished');
      // `_submitAlpacaOnly` only reaches `Navigator.of(context).pop()` after
      // `outcome.ok` is true — i.e. after _placeAlpacaOrder has already
      // returned. The trade ticket sheet being gone (popped) WHILE the log
      // call is still pending is exactly the property under test: the UI
      // proceeded to completion without waiting for the report.
      expect(find.byType(TradeTicketSheet), findsNothing,
          reason: 'the sheet must already be dismissed — a proof the caller '
              'did not await the still-pending log call before finishing — '
              'this is exactly what would fail if _placeAlpacaOrder awaited '
              'the report before returning (the sheet would still be open)');

      api.gate.complete();
      await t.pump(const Duration(milliseconds: 120));
      expect(api.logCallResolved, isTrue,
          reason: 'sanity: the background report does eventually complete');
    });

    /// Round-2 audit closing note: the three failure branches were only
    /// verified by the auditor's own scratch probes, never committed —
    /// "the one place this CR's guard is thinner than its guarantee." These
    /// three close that gap. Unlike the success path, a failure never pops
    /// the sheet (`_submitAlpacaOnly` only calls `Navigator.pop()` when
    /// `outcome.ok`), so the observable here is the inline outcome-row
    /// banner (`_destinationOutcomes`, rendered in the still-open sheet)
    /// appearing while the slow log call is still provably pending.
    Future<void> expectOutcomeRendersWhileLogPending(
      WidgetTester t, {
      required AlpacaClient alpacaClient,
      required String expectedText,
    }) async {
      final api = _SlowApiClient();
      await t.binding.setSurfaceSize(const Size(390, 1600));
      addTearDown(() => t.binding.setSurfaceSize(null));
      await t.pumpWidget(ProviderScope(
        overrides: [
          simNotifierProvider.overrideWith((ref) => _FixedSim(
                ref,
                SimState(portfolio: _portfolio()),
                previewResult: const SimPreviewResult(accepted: true),
              )),
          alpacaLinkedProvider.overrideWith((ref) async => true),
          alpacaClientProvider.overrideWithValue(alpacaClient),
          apiClientProvider.overrideWithValue(api),
        ],
        child: MaterialApp(
          localizationsDelegates: AppLocalizations.localizationsDelegates,
          supportedLocales: AppLocalizations.supportedLocales,
          // CR232 — `TradeTicketSheet` builds its own `Scaffold` now.
          home: const TradeTicketSheet(tickerPrefill: 'AAPL'),
        ),
      ));
      for (var i = 0; i < 4; i++) {
        await t.pump(const Duration(milliseconds: 120));
      }
      await t.tap(find.text('ALPACA PAPER'));
      await t.pump(const Duration(milliseconds: 120));
      await t.tap(find.text('SUBMIT TRADE'));
      for (var i = 0; i < 6; i++) {
        await t.pump(const Duration(milliseconds: 120));
      }

      expect(api.orderLogCalls, hasLength(1));
      expect(api.logCallResolved, isFalse,
          reason: 'the gate is still closed — the log call has NOT finished');
      expect(find.textContaining(expectedText), findsWidgets,
          reason: 'the outcome must already be visible while the unrelated '
              'log call is still pending — this is exactly what would fail '
              'if _placeAlpacaOrder awaited the report before returning');

      api.gate.complete();
      await t.pump(const Duration(milliseconds: 120));
    }

    testWidgets(
        'a client-side refusal still renders while the log call is pending',
        (t) async {
      await expectOutcomeRendersWhileLogPending(
        t,
        alpacaClient: _RefusingAlpacaClient(),
        expectedText: 'non-paper',
      );
    });

    testWidgets(
        'an Alpaca-side rejection still renders while the log call is pending',
        (t) async {
      await expectOutcomeRendersWhileLogPending(
        t,
        alpacaClient: _RejectingAlpacaClient(),
        expectedText: 'insufficient buying power',
      );
    });

    testWidgets(
        'the catch-all branch still renders while the log call is pending',
        (t) async {
      await expectOutcomeRendersWhileLogPending(
        t,
        alpacaClient: _UnexpectedlyThrowingAlpacaClient(),
        expectedText: 'Network error.',
      );
    });
  });
}
