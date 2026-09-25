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
  bool rejectCancelAsLiveHost = false;
  int openFetchCount = 0;
  int closedFetchCount = 0;

  @override
  Future<List<AlpacaOrder>> orders({
    String status = 'open',
    int? limit,
    bool nested = true,
  }) async {
    if (status == 'open') {
      openFetchCount++;
      return openOrders;
    }
    closedFetchCount++;
    return closedOrders;
  }

  @override
  Future<void> cancelOrder(String orderId) async {
    if (rejectCancelAsLiveHost) {
      throw const AlpacaOrderRejected(
          'refusing to cancel an order against a non-paper Alpaca host');
    }
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

/// Pumps `AlpacaOpenOrdersSection` alongside `AlpacaHistorySection` in one
/// tree, the way `_OrdersTab`/`_HistoryTab` both keep an Alpaca provider
/// alive in the real app (History is a separate tab, but the two providers
/// are independent and CR234's cancel path invalidates both regardless of
/// which tab is on screen). Needed to observe `alpacaClosedOrdersProvider`
/// actually refetch: it is `autoDispose`, so with nothing watching it,
/// `ref.invalidate` has nothing to refresh.
Future<void> _pumpOpenOrdersAndHistory(
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
      home: Scaffold(
        body: ListView(
          children: const [AlpacaOpenOrdersSection(), AlpacaHistorySection()],
        ),
      ),
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

    testWidgets(
        'a failed cancel still refreshes both the open and closed providers',
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
      await _pumpOpenOrdersAndHistory(t, alpacaClient: client, apiClient: api);

      // Both providers resolve once on initial build.
      expect(client.openFetchCount, 1);
      expect(client.closedFetchCount, 1);

      await t.tap(find.text('CANCEL ORDER'));
      await t.pump(const Duration(milliseconds: 60));
      await t.tap(find.text('CANCEL ORDER').last);
      for (var i = 0; i < 4; i++) {
        await t.pump(const Duration(milliseconds: 60));
      }

      // A lost race (already filled) still means the order is no longer
      // open — the catch block must refresh both providers regardless of
      // whether the cancel itself "succeeded", so a stale cancel button
      // doesn't linger for an order that's already gone.
      expect(client.openFetchCount, greaterThan(1),
          reason: 'open-orders provider must be refreshed after a failed '
              'cancel, not just a successful one');
      expect(client.closedFetchCount, greaterThan(1),
          reason: 'closed-orders provider must be refreshed after a failed '
              'cancel, not just a successful one');
    });

    testWidgets(
        'a refused cancel on a live-linked account shows a clear message, '
        'not a silent failure', (t) async {
      final client = _FixedOrdersAlpacaClient(openOrders: [
        const AlpacaOrder(
          id: 'ord_1',
          symbol: 'ASML',
          side: 'buy',
          qty: 10,
          status: 'new',
        ),
      ])..rejectCancelAsLiveHost = true;
      final api = _RecordingApiClient();
      await _pumpOpenOrders(t, alpacaClient: client, apiClient: api);

      await t.tap(find.text('CANCEL ORDER'));
      await t.pump(const Duration(milliseconds: 60));
      await t.tap(find.text('CANCEL ORDER').last);
      for (var i = 0; i < 4; i++) {
        await t.pump(const Duration(milliseconds: 60));
      }

      // MINOR-2 (CR234 round 1): AlpacaOrderRejected is a different type
      // from AlpacaException, so a naive catch-only-AlpacaException handler
      // lets this escape as an unhandled async error — no snackbar, no
      // audit row, and the button just does nothing when tapped.
      expect(find.textContaining("Couldn't cancel"), findsOneWidget,
          reason: 'a structural refusal must surface a clear message, not '
              'fail silently');
      // CR234 round-2 MINOR-4 (DEF439 closes the reachability, but the copy
      // itself is fixed regardless as a backstop): this used to interpolate
      // `AlpacaOrderRejected.message` directly — the raw developer string
      // `cancelOrder()` throws ("refusing to cancel an order against a
      // non-paper Alpaca host: <url>") — straight into user-facing copy.
      expect(find.textContaining('non-paper Alpaca host'), findsNothing,
          reason: 'the raw developer-facing exception string must never '
              'reach the snackbar verbatim');
      expect(find.textContaining('not a paper account'), findsOneWidget,
          reason: 'user-actionable copy in its place');
      // DEF439 round 2 (auditor u66 MINOR-3) — round 1's "user-actionable
      // copy in its place" was itself a hard-coded English literal in
      // alpaca_orders_section.dart, unreachable for AR/MS translation
      // (`retranslate:[ar,ms]` never applies to a string ARB never sees).
      // Pin that the snackbar now renders exactly
      // AppLocalizations.alpacaOrderCancelNonPaperDetail's value, so this
      // string lives in ONE place (the ARB) rather than two independently
      // driftable ones. Mutation: hard-coding a different literal back into
      // alpaca_orders_section.dart, or changing only the ARB value, must
      // fail this assertion.
      final l = AppLocalizations.of(t.element(find.byType(AlpacaOpenOrdersSection)));
      expect(
        find.textContaining(l.alpacaOrderCancelNonPaperDetail),
        findsOneWidget,
        reason: 'the snackbar detail must come from the ARB key, not a '
            'second, independently-hand-written English copy of it',
      );
      // Nothing was sent to Alpaca, so nothing to audit-log.
      expect(api.calls, isEmpty);
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
