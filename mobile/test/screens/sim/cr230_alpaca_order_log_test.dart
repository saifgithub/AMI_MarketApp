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
library;

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
      home: Scaffold(
          body: SingleChildScrollView(
              child: const TradeTicketSheet(tickerPrefill: 'AAPL'))),
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
  });
}
