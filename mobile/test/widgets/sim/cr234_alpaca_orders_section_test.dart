/// CR234 — widget-level coverage for `AlpacaOpenOrdersSection` /
/// `AlpacaHistorySection` (the Portfolio Orders/History tabs' Alpaca halves).
///
/// Saiful: "I am not seeing orders from alpaca in the orders section after
/// putting a limit buy." These pin: the section renders only when linked,
/// shows Alpaca rows labelled ALPACA PAPER with type/side/qty/price/status/
/// bracket legs, degrades loudly (never an empty list) when the fetch fails,
/// and the cancel flow (confirm -> DELETE -> refresh -> best-effort audit
/// report) works end to end against fakes.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/alpaca.dart';
import 'package:ami_trade/services/alpaca/alpaca_client.dart';
import 'package:ami_trade/services/api/api_client.dart';
import 'package:ami_trade/state/alpaca_providers.dart';
import 'package:ami_trade/state/onboarding_providers.dart';
import 'package:ami_trade/widgets/sim/alpaca_orders_section.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

class _OrderLogCall {
  const _OrderLogCall({required this.outcome, required this.alpacaOrderId});
  final String outcome;
  final String? alpacaOrderId;
}

class _RecordingApiClient extends ApiClient {
  _RecordingApiClient() : super(baseUrl: 'test://localhost');
  final List<_OrderLogCall> calls = [];

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
    calls.add(_OrderLogCall(outcome: outcome, alpacaOrderId: alpacaOrderId));
  }
}

class _FixedOrdersAlpacaClient extends AlpacaClient {
  _FixedOrdersAlpacaClient({this.openOrders = const [], this.closedOrders = const []});
  final List<AlpacaOrder> openOrders;
  final List<AlpacaOrder> closedOrders;
  final List<String> cancelledIds = [];
  bool throwOnCancel = false;

  @override
  Future<List<AlpacaOrder>> orders({
    String status = 'open',
    int? limit,
    bool nested = true,
  }) async {
    return status == 'open' ? openOrders : closedOrders;
  }

  @override
  Future<void> cancelOrder(String orderId) async {
    if (throwOnCancel) {
      throw const AlpacaException(422, 'order already filled');
    }
    cancelledIds.add(orderId);
  }
}

class _ThrowingOrdersAlpacaClient extends AlpacaClient {
  @override
  Future<List<AlpacaOrder>> orders({
    String status = 'open',
    int? limit,
    bool nested = true,
  }) async {
    throw const AlpacaException(500, 'boom');
  }
}

Future<void> _pumpOpenOrders(
  WidgetTester t, {
  required AlpacaClient alpacaClient,
  ApiClient? apiClient,
}) async {
  await t.pumpWidget(ProviderScope(
    overrides: [
      alpacaLinkedProvider.overrideWith((ref) async => true),
      alpacaClientProvider.overrideWithValue(alpacaClient),
      if (apiClient != null) apiClientProvider.overrideWithValue(apiClient),
    ],
    child: MaterialApp(
      localizationsDelegates: AppLocalizations.localizationsDelegates,
      supportedLocales: AppLocalizations.supportedLocales,
      home: const Scaffold(body: AlpacaOpenOrdersSection()),
    ),
  ));
  for (var i = 0; i < 4; i++) {
    await t.pump(const Duration(milliseconds: 60));
  }
}

Future<void> _pumpHistory(
  WidgetTester t, {
  required AlpacaClient alpacaClient,
}) async {
  await t.pumpWidget(ProviderScope(
    overrides: [
      alpacaLinkedProvider.overrideWith((ref) async => true),
      alpacaClientProvider.overrideWithValue(alpacaClient),
    ],
    child: MaterialApp(
      localizationsDelegates: AppLocalizations.localizationsDelegates,
      supportedLocales: AppLocalizations.supportedLocales,
      home: const Scaffold(body: AlpacaHistorySection()),
    ),
  ));
  for (var i = 0; i < 4; i++) {
    await t.pump(const Duration(milliseconds: 60));
  }
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  group('AlpacaOpenOrdersSection — gating', () {
    testWidgets('renders nothing when no Alpaca account is linked', (t) async {
      await t.pumpWidget(ProviderScope(
        overrides: [
          alpacaLinkedProvider.overrideWith((ref) async => false),
          alpacaClientProvider.overrideWithValue(_FixedOrdersAlpacaClient(
            openOrders: [
              const AlpacaOrder(
                  id: 'o1', symbol: 'AAPL', side: 'buy', qty: 10, status: 'new'),
            ],
          )),
        ],
        child: MaterialApp(
          localizationsDelegates: AppLocalizations.localizationsDelegates,
          supportedLocales: AppLocalizations.supportedLocales,
          home: const Scaffold(body: AlpacaOpenOrdersSection()),
        ),
      ));
      for (var i = 0; i < 4; i++) {
        await t.pump(const Duration(milliseconds: 60));
      }
      expect(find.text('ALPACA PAPER'), findsNothing);
      expect(find.textContaining('AAPL'), findsNothing);
    });
  });

  group('AlpacaOpenOrdersSection — rendering', () {
    testWidgets('shows an AMI/Alpaca-labelled row with type/side/qty/status',
        (t) async {
      await _pumpOpenOrders(
        t,
        alpacaClient: _FixedOrdersAlpacaClient(openOrders: [
          const AlpacaOrder(
            id: 'ord_1',
            symbol: 'ASML',
            side: 'buy',
            qty: 10,
            status: 'new',
            type: 'limit',
            limitPrice: 1700.00,
            timeInForce: 'gtc',
          ),
        ]),
      );

      // One "ALPACA PAPER" is the section heading, one is the per-row
      // destination chip — both use the literal, un-localized label.
      expect(find.text('ALPACA PAPER'), findsNWidgets(2));
      expect(find.textContaining('BUY 10 ASML'), findsOneWidget);
      expect(find.textContaining('LMT \$1700.00'), findsOneWidget);
      expect(find.text('NEW'), findsOneWidget);
      expect(find.text('GTC'), findsOneWidget);
    });

    testWidgets('shows bracket stop/target legs under the parent order',
        (t) async {
      await _pumpOpenOrders(
        t,
        alpacaClient: _FixedOrdersAlpacaClient(openOrders: [
          AlpacaOrder(
            id: 'ord_1',
            symbol: 'ASML',
            side: 'buy',
            qty: 10,
            status: 'new',
            type: 'limit',
            limitPrice: 1700.00,
            legs: const [
              AlpacaOrder(
                  id: 'leg_stop',
                  symbol: 'ASML',
                  side: 'sell',
                  qty: 10,
                  status: 'held',
                  stopPrice: 1619.15),
              AlpacaOrder(
                  id: 'leg_target',
                  symbol: 'ASML',
                  side: 'sell',
                  qty: 10,
                  status: 'held',
                  limitPrice: 1946.42),
            ],
          ),
        ]),
      );

      expect(find.textContaining('Stop \$1619.15'), findsOneWidget);
      expect(find.textContaining('Target \$1946.42'), findsOneWidget);
    });

    testWidgets('empty open-orders list shows the "no orders" copy, not blank',
        (t) async {
      await _pumpOpenOrders(t, alpacaClient: _FixedOrdersAlpacaClient());
      expect(find.text('ALPACA PAPER'), findsOneWidget);
      expect(find.text('No open Alpaca orders'), findsOneWidget);
    });

    testWidgets(
        'CR040 — a fetch failure shows a visible error row, never an empty list',
        (t) async {
      await _pumpOpenOrders(t, alpacaClient: _ThrowingOrdersAlpacaClient());
      expect(find.text("Couldn't load Alpaca orders"), findsOneWidget);
      expect(find.text('No open Alpaca orders'), findsNothing);
    });
  });

  group('AlpacaOpenOrdersSection — cancel flow', () {
    testWidgets(
        'confirm -> DELETE -> refresh -> best-effort audit report', (t) async {
      final client = _FixedOrdersAlpacaClient(openOrders: [
        const AlpacaOrder(
          id: 'ord_1',
          symbol: 'ASML',
          side: 'buy',
          qty: 10,
          status: 'new',
          type: 'limit',
          limitPrice: 1700.00,
        ),
      ]);
      final api = _RecordingApiClient();
      await _pumpOpenOrders(t, alpacaClient: client, apiClient: api);

      await t.tap(find.text('CANCEL ORDER'));
      await t.pump(const Duration(milliseconds: 60));
      // Confirm dialog now open — tap the destructive confirm button (also
      // labelled CANCEL ORDER, so two matches now).
      expect(find.text('CANCEL ORDER'), findsNWidgets(2));
      await t.tap(find.text('CANCEL ORDER').last);
      for (var i = 0; i < 4; i++) {
        await t.pump(const Duration(milliseconds: 60));
      }

      expect(client.cancelledIds, ['ord_1']);
      expect(api.calls, hasLength(1));
      expect(api.calls.single.outcome, 'cancelled');
      expect(api.calls.single.alpacaOrderId, 'ord_1');
      expect(find.text('Alpaca order cancelled.'), findsOneWidget);
    });

    testWidgets('a lost race (already filled) shows a failure snackbar, still refreshes',
        (t) async {
      final client = _FixedOrdersAlpacaClient(openOrders: [
        const AlpacaOrder(
          id: 'ord_1',
          symbol: 'ASML',
          side: 'buy',
          qty: 10,
          status: 'new',
        ),
      ])..throwOnCancel = true;
      final api = _RecordingApiClient();
      await _pumpOpenOrders(t, alpacaClient: client, apiClient: api);

      await t.tap(find.text('CANCEL ORDER'));
      await t.pump(const Duration(milliseconds: 60));
      await t.tap(find.text('CANCEL ORDER').last);
      for (var i = 0; i < 4; i++) {
        await t.pump(const Duration(milliseconds: 60));
      }

      expect(find.textContaining("Couldn't cancel"), findsOneWidget);
      expect(api.calls.single.outcome, 'rejected_by_alpaca');
    });

    testWidgets('a closed order (filled) offers no cancel action', (t) async {
      await _pumpOpenOrders(
        t,
        alpacaClient: _FixedOrdersAlpacaClient(openOrders: [
          const AlpacaOrder(
              id: 'ord_1',
              symbol: 'AAPL',
              side: 'buy',
              qty: 10,
              status: 'filled'),
        ]),
      );
      expect(find.text('CANCEL ORDER'), findsNothing);
    });
  });

  group('AlpacaHistorySection', () {
    testWidgets('shows closed Alpaca orders labelled ALPACA PAPER', (t) async {
      await _pumpHistory(
        t,
        alpacaClient: _FixedOrdersAlpacaClient(closedOrders: [
          const AlpacaOrder(
            id: 'ord_2',
            symbol: 'NVDA',
            side: 'buy',
            qty: 5,
            status: 'filled',
            type: 'limit',
            limitPrice: 120.0,
            filledQty: 5,
            filledAvgPrice: 119.8,
          ),
        ]),
      );
      // One "ALPACA PAPER" is the section heading, one is the per-row
      // destination chip.
      expect(find.text('ALPACA PAPER'), findsNWidgets(2));
      expect(find.textContaining('BUY 5 NVDA'), findsOneWidget);
      expect(find.text('FILLED'), findsOneWidget);
      expect(find.textContaining('5 of 5 filled'), findsOneWidget);
      expect(find.text('CANCEL ORDER'), findsNothing,
          reason: 'a closed order in History must never offer a cancel action');
    });

    testWidgets('empty closed-orders list renders nothing (not a second empty state)',
        (t) async {
      await _pumpHistory(t, alpacaClient: _FixedOrdersAlpacaClient());
      expect(find.text('ALPACA PAPER'), findsNothing);
    });

    testWidgets('CR040 — a fetch failure shows the history error row', (t) async {
      await _pumpHistory(t, alpacaClient: _ThrowingOrdersAlpacaClient());
      expect(find.text("Couldn't load Alpaca order history"), findsOneWidget);
    });
  });
}
