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

  @override
  Future<AlpacaOrder> submitOrder({
    required String symbol,
    required String side,
    required double qty,
  }) async {
    calls.add('$side $qty $symbol');
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

  @override
  Future<SimPreviewResult?> preview({
    required String ticker,
    required String side,
    required double quantity,
    String? verdictRef,
  }) async {
    previewCalls.add('$side $quantity $ticker');
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
}) async {
  await t.binding.setSurfaceSize(const Size(390, 1600));
  addTearDown(() => t.binding.setSurfaceSize(null));
  late _FixedSim sim;
  await t.pumpWidget(ProviderScope(
    overrides: [
      simNotifierProvider.overrideWith((ref) {
        sim = _FixedSim(ref, SimState(portfolio: _portfolio()),
            previewResult: previewResult, submitResult: submitResult);
        return sim;
      }),
      alpacaLinkedProvider.overrideWith((ref) async => alpacaLinked),
      if (alpacaClient != null)
        alpacaClientProvider.overrideWithValue(alpacaClient),
    ],
    child: MaterialApp(
      localizationsDelegates: AppLocalizations.localizationsDelegates,
      supportedLocales: AppLocalizations.supportedLocales,
      home: Scaffold(
          body: SingleChildScrollView(
              child: const TradeTicketSheet(tickerPrefill: 'AAPL'))),
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
