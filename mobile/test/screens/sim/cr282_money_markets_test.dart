/// CR282 lane F1 - money on migrated screens is formatted from the ticker's
/// market. A US ticker keeps its `$` (the pre-CR282 string, unchanged); a `.KL`
/// ticker prints `RM`; neither screen shows the other's symbol.
///
/// Three surfaces: the Portfolio Positions tab (holding card + value card),
/// the History row (`TradeRow`) and the resting-order sentence that is built
/// from an ARB string whose `$` moved into the argument.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/sim.dart';
import 'package:ami_trade/models/sim_resting_order.dart';
import 'package:ami_trade/features/sim/order_pricing.dart';
import 'package:ami_trade/screens/sim/portfolio_screen.dart';
import 'package:ami_trade/state/alpaca_providers.dart';
import 'package:ami_trade/state/journal_providers.dart';
import 'package:ami_trade/state/portfolio_health_providers.dart';
import 'package:ami_trade/state/sim_providers.dart';
import 'package:ami_trade/state/watchlist_providers.dart';
import 'package:ami_trade/widgets/sim/resting_orders_section.dart';
import 'package:ami_trade/widgets/trade_row.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import '../../support/portfolio_health_fixtures.dart';

class _FixedSimNotifier extends SimNotifier {
  _FixedSimNotifier(super.ref, SimState fixed) {
    state = fixed;
  }
}

class _FixedWatchlistNotifier extends WatchlistNotifier {
  _FixedWatchlistNotifier(super.ref, WatchlistState fixed) {
    state = fixed;
  }
}

class _FixedJournalNotifier extends JournalNotifier {
  _FixedJournalNotifier(super.ref, JournalState fixed) {
    state = fixed;
  }
}

SimHolding _holding(String ticker) => SimHolding(
      ticker: ticker,
      quantity: 100,
      avgCost: 12.5,
      mark: 13.75,
      value: 1375,
      unrealisedPnl: 125,
      openedAt: DateTime(2026, 11, 1),
      stop: 11.25,
    );

SimPortfolio _portfolio(String ticker, {String? currency}) => SimPortfolio(
      userId: 'u1',
      portfolioId: 'p1',
      startingCapital: 50000,
      currentCash: 48625,
      holdings: [_holding(ticker)],
      totalValue: 50000,
      drawdownPct: 0,
      priceSource: 'yahoo',
      currency: currency,
    );

Future<void> _pumpPortfolio(WidgetTester tester, SimPortfolio p) async {
  tester.view.physicalSize = const Size(390, 844);
  tester.view.devicePixelRatio = 1.0;
  addTearDown(tester.view.reset);
  await tester.pumpWidget(
    ProviderScope(
      overrides: [
        simNotifierProvider.overrideWith(
            (ref) => _FixedSimNotifier(ref, SimState(portfolio: p))),
        watchlistNotifierProvider.overrideWith(
            (ref) => _FixedWatchlistNotifier(ref, const WatchlistState())),
        journalNotifierProvider.overrideWith(
            (ref) => _FixedJournalNotifier(ref, const JournalState())),
        alpacaLinkedProvider.overrideWith((ref) async => false),
        portfolioHealthProvider.overrideWith((ref) async => healthFixture()),
        sectorAllocationProvider
            .overrideWith((ref) async => const SectorAllocation(
                  allocation: {},
                  totalValue: 0,
                  compliance: SectorCompliance(
                    maxSector: 0,
                    maxAllowed: 0.4,
                    compliant: true,
                  ),
                )),
        portfolioHistoryProvider.overrideWith((ref) async =>
            const SimPortfolioHistory(points: [], twrPct: 0)),
      ],
      child: MaterialApp(
        localizationsDelegates: AppLocalizations.localizationsDelegates,
        supportedLocales: AppLocalizations.supportedLocales,
        home: const PortfolioScreen(),
      ),
    ),
  );
  await tester.pump();
  await tester.pump();
}

Future<void> _scrollToEnd(WidgetTester tester) async {
  final scrollable = find.descendant(
    of: find.byKey(const PageStorageKey<String>('portfolioPositionsScroll')),
    matching: find.byType(Scrollable),
  );
  await tester.drag(scrollable, const Offset(0, -1000000));
  await tester.pump();
  await tester.pump(const Duration(milliseconds: 300));
}

SimTrade _trade(String ticker) => SimTrade(
      id: 't1',
      userId: 'u1',
      ticker: ticker,
      side: 'buy',
      quantity: 100,
      entryPrice: 1234.5,
      stop: 1100,
      target: 1500,
      openedAt: DateTime(2026, 11, 1),
      closedAt: DateTime(2026, 11, 5),
      closedPrice: 1400,
      status: 'won',
      realisedPnl: 165.5,
    );

SimRestingOrder _resting(String ticker) => SimRestingOrder(
      id: 'r1',
      ticker: ticker,
      side: 'buy',
      quantity: 100,
      orderType: SimOrderType.limit,
      state: RestingOrderState.working,
      tif: SimOrderTif.gtd30,
      limitPrice: 9.5,
    );

Future<void> _pumpWidget(WidgetTester tester, Widget child) async {
  await tester.pumpWidget(MaterialApp(
    localizationsDelegates: AppLocalizations.localizationsDelegates,
    supportedLocales: AppLocalizations.supportedLocales,
    home: Scaffold(body: SingleChildScrollView(child: child)),
  ));
  await tester.pump();
}

void main() {
  group('Portfolio Positions tab', () {
    testWidgets('US book: every amount is dollars, no RM', (tester) async {
      await _pumpPortfolio(tester, _portfolio('AAPL'));
      expect(find.textContaining(r'$50,000.00'), findsWidgets);
      expect(find.textContaining(r'$48,625.00'), findsWidgets);
      await _scrollToEnd(tester);
      expect(find.textContaining(r'100 sh · $12.50'), findsOneWidget);
      expect(find.textContaining('RM'), findsNothing);
    });

    testWidgets('MYR book with a .KL holding: RM throughout, no \$',
        (tester) async {
      await _pumpPortfolio(tester, _portfolio('1155.KL', currency: 'MYR'));
      expect(find.textContaining('RM50,000.00'), findsWidgets);
      expect(find.textContaining('RM48,625.00'), findsWidgets);
      await _scrollToEnd(tester);
      expect(find.textContaining('1155.KL'), findsWidgets);
      expect(find.textContaining('100 sh · RM12.50'), findsOneWidget);
      expect(find.textContaining(r'$'), findsNothing);
    });
  });

  group('TradeRow', () {
    testWidgets('US trade prints \$ with the legacy grouping', (tester) async {
      await _pumpWidget(tester, TradeRow(trade: _trade('AAPL')));
      expect(find.textContaining(r'BUY 100 AAPL @ $1,234.50'), findsOneWidget);
      expect(find.textContaining(r'stop $1,100.00'), findsOneWidget);
      expect(find.textContaining(r'target $1,500.00'), findsOneWidget);
      expect(find.textContaining(r'closed $1,400.00'), findsOneWidget);
      expect(find.text(r'+$165.50'), findsOneWidget);
    });

    testWidgets('.KL trade prints RM, never \$', (tester) async {
      await _pumpWidget(tester, TradeRow(trade: _trade('1155.KL')));
      expect(find.textContaining('BUY 100 1155.KL @ RM1,234.50'),
          findsOneWidget);
      expect(find.textContaining('stop RM1,100.00'), findsOneWidget);
      expect(find.text('+RM165.50'), findsOneWidget);
      expect(find.textContaining(r'$'), findsNothing);
    });
  });

  group('Resting-order sentence (ARB placeholder carries the money)', () {
    Future<String?> sentence(WidgetTester tester, String ticker) async {
      String? out;
      await tester.pumpWidget(MaterialApp(
        localizationsDelegates: AppLocalizations.localizationsDelegates,
        supportedLocales: AppLocalizations.supportedLocales,
        home: Builder(builder: (context) {
          out = restingOrderIntentLine(
              AppLocalizations.of(context), _resting(ticker));
          return const SizedBox.shrink();
        }),
      ));
      return out;
    }

    testWidgets('US', (tester) async {
      expect(await sentence(tester, 'AAPL'), r'waits for a fall to $9.50');
    });

    testWidgets('.KL', (tester) async {
      expect(await sentence(tester, '1155.KL'), 'waits for a fall to RM9.50');
    });
  });
}
