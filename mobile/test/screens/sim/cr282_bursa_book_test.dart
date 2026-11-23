/// CR282 lane F2 - the Bursa (MYR) book in the app: the Portfolio market switch,
/// the RM book, and the `.KL` trade ticket (board-lot stepper, itemised fees,
/// the server's own refusal sentences, no short/Alpaca surfaces).
///
/// Bursa is a compile-time flag (`kBursaEnabled`); the screens read it through
/// `bursaEnabledProvider`, which these tests flip. The first group is the half
/// that matters most to a user who will never see Bursa: with the flag off the
/// screen is the one that shipped before CR282.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/sim.dart';
import 'package:ami_trade/models/tickers.dart';
import 'package:ami_trade/screens/sim/portfolio_screen.dart';
import 'package:ami_trade/screens/sim/trade_ticket_sheet.dart';
import 'package:ami_trade/services/api/api_client.dart';
import 'package:ami_trade/services/device_user.dart';
import 'package:ami_trade/state/alpaca_providers.dart';
import 'package:ami_trade/state/bursa_providers.dart';
import 'package:ami_trade/state/journal_providers.dart';
import 'package:ami_trade/state/onboarding_providers.dart';
import 'package:ami_trade/state/portfolio_health_providers.dart';
import 'package:ami_trade/state/sim_providers.dart';
import 'package:ami_trade/state/watchlist_providers.dart';
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../../support/portfolio_health_fixtures.dart';

// ── fakes ───────────────────────────────────────────────────────────────

class _FixedSim extends SimNotifier {
  _FixedSim(super.ref, SimState fixed) {
    state = fixed;
  }
}

class _FixedBursa extends BursaSimNotifier {
  _FixedBursa(super.ref, SimState fixed) {
    state = fixed;
  }
}

class _FixedWatchlist extends WatchlistNotifier {
  _FixedWatchlist(super.ref, WatchlistState fixed) {
    state = fixed;
  }
}

class _FixedJournal extends JournalNotifier {
  _FixedJournal(super.ref, JournalState fixed) {
    state = fixed;
  }
}

DioException _refusal(String code, String message) => DioException(
      requestOptions: RequestOptions(path: '/v1/sim/x'),
      response: Response<dynamic>(
        requestOptions: RequestOptions(path: '/v1/sim/x'),
        statusCode: 422,
        data: {
          'detail': {'code': code, 'message': message, 'market': 'MY'},
        },
      ),
      type: DioExceptionType.badResponse,
    );

/// A server that knows Bursa: prices a `.KL` quote, previews with fees, and
/// can be told to refuse the preview or the submit with a market rule.
class _BursaApi extends ApiClient {
  _BursaApi() : super(baseUrl: 'test://localhost');

  DioException? previewError;
  DioException? submitError;
  final previews = <Map<String, Object?>>[];
  var submits = 0;

  @override
  Future<TickerValidation> validateTicker(String ticker) async =>
      TickerValidation(ticker: ticker, exists: true);

  @override
  Future<({double price, double changePct, String source, String marketState})>
      simQuoteDetail(String ticker) async => (
            price: 6.20,
            changePct: 0.0,
            source: 'yahoo',
            marketState: 'CLOSED',
          );

  @override
  Future<SimPreviewResult> simPreview({
    required String userId,
    required String ticker,
    required String side,
    required double quantity,
    String orderType = 'market',
    double? limitPrice,
    double? triggerPrice,
    double? stop,
    double? target,
    String? verdictRef,
    Map<String, dynamic>? account,
  }) async {
    previews.add({'ticker': ticker, 'side': side, 'quantity': quantity});
    if (previewError != null) throw previewError!;
    return SimPreviewResult.fromJson({
      'accepted': true,
      'compliance': {'violations': <String>[], 'blocked_by': null},
      'currency': 'MYR',
      'market': 'MY',
      'fees': {
        'brokerage': 8.0,
        'clearing': 1.86,
        'stamp_duty': 0.62,
        'total': 10.48,
        'currency': 'MYR',
      },
    });
  }

  @override
  Future<SimSubmitResult> simSubmit({
    required String userId,
    required String ticker,
    required String side,
    required double quantity,
    String orderType = 'market',
    double? limitPrice,
    double? triggerPrice,
    String? tif,
    double? stop,
    double? target,
    int? horizonDays,
    String? verdictRef,
  }) async {
    submits++;
    if (submitError != null) throw submitError!;
    throw StateError('this test never lets a submit succeed');
  }

  @override
  Future<void> simEvaluate(String userId) async {}

  @override
  Future<SimPortfolio> simPortfolio(String userId) async => _usBook();

  @override
  Future<List<SimTrade>> simListTrades(String userId,
          {String? statusFilter}) async =>
      const [];

  @override
  Future<SimPortfolio> simMarketPortfolio(String userId, market) async =>
      _myBook();

  @override
  Future<List<SimTrade>> simMarketTrades(String userId, market) async =>
      const [];
}

SimPortfolio _usBook() => SimPortfolio(
      userId: 'u',
      portfolioId: 'p-us',
      startingCapital: 10000,
      currentCash: 10000,
      holdings: const [],
      totalValue: 10000,
      drawdownPct: 0,
    );

SimHolding _myHolding({double qty = 100}) => SimHolding(
      ticker: '1155.KL',
      quantity: qty,
      avgCost: 9.80,
      mark: 10.20,
      value: qty * 10.20,
      unrealisedPnl: qty * 0.40,
      openedAt: DateTime(2026, 11, 20),
    );

SimPortfolio _myBook({
  List<SimHolding> holdings = const [],
  double cash = 50000,
}) =>
    SimPortfolio(
      userId: 'u',
      portfolioId: 'p-my',
      startingCapital: 50000,
      currentCash: cash,
      holdings: holdings,
      totalValue: cash + holdings.fold<double>(0, (a, h) => a + h.value),
      drawdownPct: 0,
      priceSource: 'yahoo',
      currency: 'MYR',
    );

SimTrade _myWon() => SimTrade(
      id: 't-my',
      userId: 'u',
      ticker: '1155.KL',
      side: 'buy',
      quantity: 100,
      entryPrice: 9.80,
      openedAt: DateTime(2026, 11, 1),
      closedAt: DateTime(2026, 11, 5),
      closedPrice: 11.45,
      status: 'won',
      realisedPnl: 165,
    );

// ── Portfolio screen harness ────────────────────────────────────────────

class _Created {
  var bursaProviderBuilt = false;
}

Future<void> _pumpPortfolio(
  WidgetTester t, {
  required bool bursaOn,
  SimState? bursaState,
  _Created? created,
}) async {
  t.view.physicalSize = const Size(390, 844);
  t.view.devicePixelRatio = 1.0;
  addTearDown(t.view.reset);
  await t.pumpWidget(ProviderScope(
    overrides: [
      bursaEnabledProvider.overrideWithValue(bursaOn),
      simNotifierProvider.overrideWith(
          (ref) => _FixedSim(ref, SimState(portfolio: _usBook()))),
      bursaSimProvider.overrideWith((ref) {
        created?.bursaProviderBuilt = true;
        return _FixedBursa(
            ref, bursaState ?? SimState(portfolio: _myBook()));
      }),
      watchlistNotifierProvider
          .overrideWith((ref) => _FixedWatchlist(ref, const WatchlistState())),
      journalNotifierProvider
          .overrideWith((ref) => _FixedJournal(ref, const JournalState())),
      alpacaLinkedProvider.overrideWith((ref) async => false),
      portfolioHealthProvider.overrideWith((ref) async => healthFixture()),
      sectorAllocationProvider.overrideWith((ref) async => const SectorAllocation(
            allocation: {},
            totalValue: 0,
            compliance:
                SectorCompliance(maxSector: 0, maxAllowed: 0.4, compliant: true),
          )),
      portfolioHistoryProvider.overrideWith(
          (ref) async => const SimPortfolioHistory(points: [], twrPct: 0)),
    ],
    child: MaterialApp(
      localizationsDelegates: AppLocalizations.localizationsDelegates,
      supportedLocales: AppLocalizations.supportedLocales,
      home: const PortfolioScreen(),
    ),
  ));
  await t.pump();
  await t.pump();
  // The value card's count-up animation owns a ticker; let it finish.
  await t.pump(const Duration(milliseconds: 500));
}

Future<void> _openBursa(WidgetTester t) async {
  await t.tap(find.text('BURSA'));
  await t.pump();
  await t.pump(const Duration(milliseconds: 700));
}

// ── Ticket harness ──────────────────────────────────────────────────────

Future<void> _pumpTicket(
  WidgetTester t,
  _BursaApi api, {
  String? ticker = '1155.KL',
  bool alpacaLinked = false,
  SimPortfolio? myBook,
}) async {
  await t.binding.setSurfaceSize(const Size(390, 1800));
  addTearDown(() => t.binding.setSurfaceSize(null));
  await t.pumpWidget(ProviderScope(
    overrides: [
      bursaEnabledProvider.overrideWithValue(true),
      apiClientProvider.overrideWithValue(api),
      alpacaLinkedProvider.overrideWith((ref) async => alpacaLinked),
      simNotifierProvider.overrideWith((ref) => _FixedSim(
          ref, SimState(portfolio: _usBook(), restingOrdersSupported: true))),
      bursaSimProvider.overrideWith((ref) =>
          _FixedBursa(ref, SimState(portfolio: myBook ?? _myBook()))),
    ],
    child: MaterialApp(
      localizationsDelegates: AppLocalizations.localizationsDelegates,
      supportedLocales: AppLocalizations.supportedLocales,
      home: TradeTicketSheet(tickerPrefill: ticker),
    ),
  ));
  // Past the validator's debounce, then the quote lands.
  for (var i = 0; i < 8; i++) {
    await t.pump(const Duration(milliseconds: 120));
  }
}

Finder _field(String label) => find.byWidgetPredicate((w) =>
    w is TextField &&
    w.decoration?.labelText != null &&
    w.decoration!.labelText!.toUpperCase() == label);

String _qty(WidgetTester t) =>
    t.widget<TextField>(_field('QUANTITY')).controller!.text;

Future<void> _settle(WidgetTester t) async {
  // The preview is debounced (400 ms) then awaited.
  for (var i = 0; i < 6; i++) {
    await t.pump(const Duration(milliseconds: 150));
  }
}

bool _submitEnabled(WidgetTester t) =>
    t.widget<ElevatedButton>(find.byType(ElevatedButton).last).onPressed !=
    null;

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  setUp(() {
    SharedPreferences.setMockInitialValues({});
    DeviceUser.resetCacheForTest();
  });

  group('flag off: the app is the one that shipped before Bursa', () {
    testWidgets('no market switch, and the Bursa book is never built',
        (t) async {
      final created = _Created();
      await _pumpPortfolio(t, bursaOn: false, created: created);

      expect(find.text('BURSA'), findsNothing);
      expect(created.bursaProviderBuilt, isFalse);
      expect(find.textContaining('RM'), findsNothing);
    });

    testWidgets('the ticket for a .KL ticker is not a Bursa ticket (no stepper)',
        (t) async {
      final api = _BursaApi();
      await t.binding.setSurfaceSize(const Size(390, 1800));
      addTearDown(() => t.binding.setSurfaceSize(null));
      await t.pumpWidget(ProviderScope(
        overrides: [
          bursaEnabledProvider.overrideWithValue(false),
          apiClientProvider.overrideWithValue(api),
          alpacaLinkedProvider.overrideWith((ref) async => false),
          simNotifierProvider.overrideWith((ref) => _FixedSim(
              ref, SimState(portfolio: _usBook(), restingOrdersSupported: true))),
        ],
        child: MaterialApp(
          localizationsDelegates: AppLocalizations.localizationsDelegates,
          supportedLocales: AppLocalizations.supportedLocales,
          home: const TradeTicketSheet(tickerPrefill: '1155.KL'),
        ),
      ));
      for (var i = 0; i < 8; i++) {
        await t.pump(const Duration(milliseconds: 120));
      }

      expect(find.byIcon(Icons.add_circle_outline), findsNothing);
      expect(_qty(t), '1');
      expect(api.previews, isEmpty);
    });
  });

  group('Portfolio market switch (flag on)', () {
    testWidgets('shows US | BURSA, US first', (t) async {
      await _pumpPortfolio(t, bursaOn: true);

      expect(find.text('US'), findsOneWidget);
      expect(find.text('BURSA'), findsOneWidget);
      // US book on screen: its $ value, no ringgit.
      expect(find.textContaining(r'$10,000.00'), findsWidgets);
    });

    testWidgets('a Bursa book nothing has touched shows the designed empty state',
        (t) async {
      await _pumpPortfolio(t, bursaOn: true);
      await _openBursa(t);

      expect(
          find.text('Your Bursa book starts with RM50,000 when you place your '
              'first Bursa trade.'),
          findsOneWidget);
      expect(find.text('NEW BURSA TRADE'), findsOneWidget);
      // An empty state, not an error and not a RM50,000.00 value card.
      expect(find.text('TRY AGAIN'), findsNothing);
      expect(find.text('RM50,000.00'), findsNothing);
    });

    testWidgets('a Bursa book with a holding renders every amount in RM',
        (t) async {
      await _pumpPortfolio(t,
          bursaOn: true,
          bursaState: SimState(
              portfolio: _myBook(holdings: [_myHolding()], cash: 49020)));
      await _openBursa(t);

      expect(find.textContaining('RM'), findsWidgets);
      // 100 x RM10.20 = RM1,020.00 holding, RM50,040.00 total.
      expect(find.textContaining('RM50,040.00'), findsWidgets);
      expect(find.textContaining('RM9.80'), findsWidgets);
      expect(find.textContaining(r'$'), findsNothing,
          reason: 'a US symbol under a ringgit book is the lie this CR removes');
      // The US-only blocks are not drawn under the MYR book.
      expect(find.textContaining('S&P'), findsNothing);
    });

    testWidgets('the closed-trade summary takes the book market (RM)',
        (t) async {
      await _pumpPortfolio(t,
          bursaOn: true,
          bursaState: SimState(
              portfolio: _myBook(cash: 50165),
              trades: [_myWon()]));
      await _openBursa(t);
      await t.tap(find.textContaining('HISTORY'));
      await t.pump();
      await t.pump(const Duration(milliseconds: 300));

      expect(find.textContaining('+RM165.00'), findsWidgets);
      expect(find.textContaining(r'$165'), findsNothing);
    });

    testWidgets('a remembered Bursa choice is restored on the next open',
        (t) async {
      SharedPreferences.setMockInitialValues({
        'ami.device_user_id': 'u-restore',
        'portfolio_market_u-restore': 'MY',
      });
      await _pumpPortfolio(t, bursaOn: true);
      await t.runAsync(
          () => Future<void>.delayed(const Duration(milliseconds: 50)));
      await t.pump(const Duration(milliseconds: 700));

      expect(find.textContaining('Your Bursa book starts with RM50,000'),
          findsOneWidget);
    });

    testWidgets('the last choice is remembered per user', (t) async {
      await _pumpPortfolio(t, bursaOn: true);
      await _openBursa(t);
      // The write lands asynchronously after the tap.
      await t.runAsync(() => Future<void>.delayed(const Duration(milliseconds: 50)));

      final prefs = await SharedPreferences.getInstance();
      final saved = prefs
          .getKeys()
          .where((k) => k.startsWith('portfolio_market_'))
          .map(prefs.getString)
          .toList();
      expect(saved, ['MY']);
    });
  });

  group('Bursa trade ticket', () {
    testWidgets('opens on one board lot and steps by 100, never below 100',
        (t) async {
      final api = _BursaApi();
      await _pumpTicket(t, api);

      expect(_qty(t), '100');
      await t.tap(find.byIcon(Icons.add_circle_outline));
      await t.pump();
      expect(_qty(t), '200');
      await t.tap(find.byIcon(Icons.add_circle_outline));
      await t.pump();
      expect(_qty(t), '300');
      await t.tap(find.byIcon(Icons.remove_circle_outline));
      await t.pump();
      expect(_qty(t), '200');
      await t.tap(find.byIcon(Icons.remove_circle_outline));
      await t.tap(find.byIcon(Icons.remove_circle_outline));
      await t.pump();
      expect(_qty(t), '100', reason: 'the stepper stops at one lot');
    });

    testWidgets('150 is refused with the board-lot hint and cannot submit',
        (t) async {
      final api = _BursaApi();
      await _pumpTicket(t, api);

      await t.enterText(_field('QUANTITY'), '150');
      await _settle(t);

      expect(find.text('Bursa trades in board lots of 100. Enter a multiple of 100.'),
          findsOneWidget);
      expect(_submitEnabled(t), isFalse);
      expect(api.previews.where((p) => p['quantity'] == 150.0), isEmpty,
          reason: 'no point asking the server about a quantity the market '
              'cannot take');

      await t.enterText(_field('QUANTITY'), '200');
      await _settle(t);
      expect(find.textContaining('board lots of 100'), findsNothing);
      expect(_submitEnabled(t), isTrue);
    });

    testWidgets('fractional input is not possible for a Bursa quantity',
        (t) async {
      final api = _BursaApi();
      await _pumpTicket(t, api);

      await t.enterText(_field('QUANTITY'), '100.5');
      await t.pump();

      expect(_qty(t), '1005', reason: 'digits only - no decimal point');
    });

    testWidgets('the itemised fees from the preview show before confirm',
        (t) async {
      final api = _BursaApi();
      await _pumpTicket(t, api);
      await _settle(t);

      expect(find.byKey(const Key('bursaFees')), findsOneWidget);
      expect(find.text('ESTIMATED FEES'), findsOneWidget);
      expect(find.text('Brokerage'), findsOneWidget);
      expect(find.text('RM8.00'), findsOneWidget);
      expect(find.text('Clearing'), findsOneWidget);
      expect(find.text('RM1.86'), findsOneWidget);
      expect(find.text('Stamp duty'), findsOneWidget);
      expect(find.text('RM0.62'), findsOneWidget);
      expect(find.text('RM10.48'), findsOneWidget);
      expect(api.previews.single['quantity'], 100.0);
    });

    testWidgets('a 422 market-rule refusal from the preview shows the server '
        'message verbatim', (t) async {
      const msg = 'limit price RM6.203 is not on Bursa\'s tick grid (RM0.01 '
          'ticks at this price). Nearest valid prices: RM6.2 or RM6.21.';
      final api = _BursaApi()..previewError = _refusal('tick_size', msg);
      await _pumpTicket(t, api);
      await _settle(t);

      expect(find.byKey(const Key('marketRefusal')), findsOneWidget);
      expect(find.text(msg), findsOneWidget);
      expect(find.byKey(const Key('bursaFees')), findsNothing);
    });

    testWidgets('a 422 refusal from submit is shown inline, not as a generic '
        'failure', (t) async {
      const msg = 'Bursa does not allow short selling in this app yet.';
      final api = _BursaApi()..submitError = _refusal('shorts_unsupported', msg);
      await _pumpTicket(t, api);
      await _settle(t);

      await t.tap(find.byType(ElevatedButton).last);
      for (var i = 0; i < 6; i++) {
        await t.pump(const Duration(milliseconds: 150));
      }

      expect(api.submits, 1);
      expect(find.text(msg), findsOneWidget);
      expect(find.textContaining('couldn'), findsNothing);
    });

    testWidgets('no short, no Alpaca mirror: a .KL sell with nothing held',
        (t) async {
      final api = _BursaApi();
      await _pumpTicket(t, api, alpacaLinked: true);

      await t.tap(find.text('SELL'));
      await _settle(t);

      expect(find.textContaining('opens a short'), findsNothing);
      expect(find.textContaining('You hold no'), findsNothing);
      expect(find.text('OPEN SHORT'), findsNothing);
      // The destination selector (AMI SIM / ALPACA PAPER / BOTH) is hidden.
      expect(find.textContaining('ALPACA'), findsNothing);
    });

    testWidgets('control: the same linked-Alpaca user still gets the selector '
        'on a US ticker', (t) async {
      final api = _BursaApi();
      await _pumpTicket(t, api, ticker: 'AAPL', alpacaLinked: true);

      expect(find.textContaining('ALPACA'), findsWidgets);
    });

    testWidgets('a .KL sell is judged against the MYR holding, not the US book',
        (t) async {
      final api = _BursaApi();
      await _pumpTicket(t, api,
          myBook: _myBook(holdings: [_myHolding(qty: 300)], cash: 47000));

      await t.tap(find.text('SELL'));
      await _settle(t);

      expect(find.textContaining('You hold 300 1155.KL'), findsOneWidget);
    });
  });
}
