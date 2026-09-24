/// CR227 — the trade ticket's destination selector and the mandate floor
/// that gates every destination identically.
///
/// The single assertion this file exists to prove: picking "Alpaca only"
/// cannot be used to dodge the mandate/compliance floor. Saiful's ruling that
/// makes "uncoachable" mean something is only true if a mandate violation
/// blocked on the sim leg ALSO blocks the Alpaca leg — otherwise a user who
/// wants to break their own mandate just picks a different destination.
/// `_FixedSim.preview` records whether it was called and what it answered;
/// `_RecordingAlpacaClient.submitOrder` records whether IT was called — a
/// preview that refuses must leave that second call unmade, not merely
/// unused.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/features/sim/order_pricing.dart';
import 'package:ami_trade/models/alpaca.dart';
import 'package:ami_trade/models/sim.dart';
import 'package:ami_trade/screens/sim/trade_ticket_sheet.dart';
import 'package:ami_trade/services/alpaca/alpaca_client.dart';
import 'package:ami_trade/state/alpaca_providers.dart';
import 'package:ami_trade/state/sim_providers.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

class _RecordingAlpacaClient extends AlpacaClient {
  final List<String> calls = [];

  // DEF419 — `_submitAlpacaOnly` fetches the linked account before it
  // previews, so this fixture needs `account()`/`positions()` to resolve
  // rather than hit the real (unlinked, under
  // `SharedPreferences.setMockInitialValues`) credential store and throw.
  @override
  Future<AlpacaPortfolio> account() async => const AlpacaPortfolio(
        cash: 5000,
        portfolioValue: 10000,
        equity: 10000,
        buyingPower: 5000,
      );

  @override
  Future<List<AlpacaPosition>> positions() async => const [];

  @override
  Future<AlpacaOrder> submitOrder({
    required String symbol,
    required String side,
    required double qty,
    required SimOrderType orderType,
    double? limitPrice,
    double? triggerPrice,
    SimOrderTif tif = SimOrderTif.day,
    AlpacaBracket? bracket,
  }) async {
    calls.add('$side $qty $symbol ${orderType.name}');
    return AlpacaOrder(
      id: 'o1',
      symbol: symbol,
      side: side,
      qty: qty,
      status: 'accepted',
    );
  }
}

class _FixedSim extends SimNotifier {
  _FixedSim(super.ref, SimState fixed, {this.previewResult, this.submitResult}) {
    state = fixed;
  }

  final SimPreviewResult? previewResult;
  final SimSubmitResult? submitResult;
  final List<String> previewCalls = [];
  final List<Map<String, dynamic>?> previewAccounts = [];

  @override
  Future<SimPreviewResult?> preview({
    required String ticker,
    required String side,
    required double quantity,
    SimOrderType orderType = SimOrderType.market,
    double? limitPrice,
    double? triggerPrice,
    String? verdictRef,
    Map<String, dynamic>? account,
  }) async {
    previewCalls.add('$side $quantity $ticker');
    previewAccounts.add(account);
    return previewResult;
  }

  @override
  Future<SimSubmitResult?> submit({
    required String ticker,
    required String side,
    required double quantity,
    SimOrderType orderType = SimOrderType.market,
    double? limitPrice,
    double? triggerPrice,
    SimOrderTif tif = SimOrderTif.day,
    double? stop,
    double? target,
    int? horizonDays,
    String? verdictRef,
  }) async {
    state = state.copyWith(lastSubmit: submitResult);
    return submitResult;
  }
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

Future<_FixedSim> _pump(
  WidgetTester t, {
  required bool alpacaLinked,
  SimPreviewResult? previewResult,
  SimSubmitResult? submitResult,
  _RecordingAlpacaClient? alpacaClient,
  // Auditor round-1 MAJOR-1 — the resting-order-book probe must be
  // controllable per test, since the selector-hiding fix only engages when
  // this backend capability is on (the LIMIT/STOP picker itself is gated on
  // it, `trade_ticket_sheet.dart`'s `state.restingOrdersSupported`).
  bool restingOrdersSupported = false,
}) async {
  await t.binding.setSurfaceSize(const Size(390, 1600));
  addTearDown(() => t.binding.setSurfaceSize(null));
  late _FixedSim sim;
  await t.pumpWidget(ProviderScope(
    overrides: [
      simNotifierProvider.overrideWith((ref) {
        sim = _FixedSim(
            ref,
            SimState(
                portfolio: _portfolio(),
                restingOrdersSupported: restingOrdersSupported),
            previewResult: previewResult,
            submitResult: submitResult);
        return sim;
      }),
      alpacaLinkedProvider.overrideWith((ref) async => alpacaLinked),
      if (alpacaClient != null)
        alpacaClientProvider.overrideWithValue(alpacaClient),
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
  return sim;
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  setUp(() => SharedPreferences.setMockInitialValues({}));

  group('destination selector visibility', () {
    testWidgets('hidden when Alpaca is not linked', (t) async {
      await _pump(t, alpacaLinked: false);
      expect(find.text('DESTINATION'), findsNothing);
    });

    testWidgets('shown when Alpaca is linked', (t) async {
      await _pump(t, alpacaLinked: true);
      expect(find.text('DESTINATION'), findsOneWidget);
      expect(find.text('AMI SIM'), findsOneWidget);
      expect(find.text('ALPACA PAPER'), findsOneWidget);
      expect(find.text('BOTH'), findsOneWidget);
    });

    testWidgets(
        'CR233 — stays visible once a LIMIT order type is picked, now that '
        'AlpacaClient.submitOrder() supports it', (t) async {
      // CR227 round-1 audit (MAJOR-1) found that AlpacaClient.submitOrder()
      // had no order-type parameter at all and hard-coded a market order, so
      // a LIMIT/STOP ticket routed to Alpaca silently filled immediately
      // instead of resting. The fix at the time was to hide this selector
      // for any non-market order type (see this file's git history for the
      // test that used to assert exactly the opposite of this one). CR233
      // gave submitOrder() the other order types natively
      // (buildAlpacaOrderPayload/validateAlpacaOrder in alpaca_client.dart),
      // so the destination lock came off order type — see
      // TradeTicketSheet's `_destinationLocked`, which now only locks on
      // coverTicker/sellTicker.
      await _pump(t, alpacaLinked: true, restingOrdersSupported: true);
      expect(find.text('DESTINATION'), findsOneWidget);

      await t.tap(find.text('LIMIT'));
      for (var i = 0; i < 3; i++) {
        await t.pump(const Duration(milliseconds: 120));
      }

      expect(find.text('DESTINATION'), findsOneWidget,
          reason: 'CR233 — a LIMIT order can now be routed to Alpaca, so '
              'the destination selector must stay available');
    });

    testWidgets('defaults to AMI Sim — an unpicked selector changes nothing',
        (t) async {
      final sim = await _pump(
        t,
        alpacaLinked: true,
        submitResult: SimSubmitResult.fromJson({
          'ok': true,
          'trade': {
            'id': 't1', 'user_id': 'u', 'ticker': 'AAPL', 'side': 'buy',
            'quantity': 1.0, 'entry_price': 100.0, 'status': 'open',
            'opened_at': '2026-09-22T00:00:00Z',
          },
          'resting': false,
          'compliance': {'passed': true},
        }),
      );
      await t.tap(find.text('SUBMIT TRADE'));
      for (var i = 0; i < 6; i++) {
        await t.pump(const Duration(milliseconds: 120));
      }
      expect(sim.previewCalls, isEmpty,
          reason: 'AMI Sim is the default destination — no preview call, '
              'exactly today\'s behavior');
    });
  });

  group('mandate floor gates the Alpaca-only leg identically to sim', () {
    testWidgets(
        'a mandate-blocking preview leaves the Alpaca order call unmade',
        (t) async {
      final alpaca = _RecordingAlpacaClient();
      final sim = await _pump(
        t,
        alpacaLinked: true,
        alpacaClient: alpaca,
        previewResult: const SimPreviewResult(
          accepted: false,
          violations: ['exceeds sector limit'],
          blockedBy: 'sector_limit',
        ),
      );
      await t.tap(find.text('ALPACA PAPER'));
      await t.pump(const Duration(milliseconds: 120));
      await t.tap(find.text('SUBMIT TRADE'));
      for (var i = 0; i < 6; i++) {
        await t.pump(const Duration(milliseconds: 120));
      }

      expect(sim.previewCalls, hasLength(1),
          reason: 'the Alpaca-only leg must run the same mandate/compliance '
              'preflight the sim leg runs, via /v1/sim/preview');
      expect(alpaca.calls, isEmpty,
          reason: 'a refused preview must leave the Alpaca order call '
              'entirely unmade — "uncoachable" is not bypassed by picking a '
              'different destination');
      expect(find.textContaining('exceeds sector limit'), findsOneWidget,
          reason: 'the same violation sentence the sim path would show');
    });

    testWidgets('an accepted preview places the Alpaca order', (t) async {
      final alpaca = _RecordingAlpacaClient();
      final sim = await _pump(
        t,
        alpacaLinked: true,
        alpacaClient: alpaca,
        previewResult: const SimPreviewResult(accepted: true),
      );
      await t.tap(find.text('ALPACA PAPER'));
      await t.pump(const Duration(milliseconds: 120));
      await t.tap(find.text('SUBMIT TRADE'));
      for (var i = 0; i < 6; i++) {
        await t.pump(const Duration(milliseconds: 120));
      }

      expect(sim.previewCalls, hasLength(1));
      expect(alpaca.calls, hasLength(1),
          reason: 'an accepted preview clears the Alpaca leg to place');
      expect(alpaca.calls.single, contains('AAPL'));
    });
  });
}
