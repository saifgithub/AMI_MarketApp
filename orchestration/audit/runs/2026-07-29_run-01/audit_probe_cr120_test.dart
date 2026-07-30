/// AUDIT PROBE — CR120 round 1, auditor (track U). Scratch file in the audit
/// worktree only; never committed, never part of the submission. Fixtures
/// copied from the lane's own portfolio_screen_test.dart so the probe drives
/// the identical heavy profile.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/alpaca.dart';
import 'package:ami_trade/models/sim.dart';
import 'package:ami_trade/models/watchlist.dart';
import 'package:ami_trade/screens/sim/portfolio_screen.dart';
import 'package:ami_trade/state/alpaca_providers.dart';
import 'package:ami_trade/state/journal_providers.dart';
import 'package:ami_trade/state/sim_providers.dart';
import 'package:ami_trade/state/watchlist_providers.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

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

SimPortfolio _portfolio({required List<SimHolding> holdings}) => SimPortfolio(
      userId: 'u1',
      portfolioId: 'p1',
      startingCapital: 100000,
      currentCash: 31050,
      holdings: holdings,
      totalValue: 255614.88,
      drawdownPct: 4.2,
      priceSource: 'yahoo',
    );

SimHolding _holding(int i) => SimHolding(
      ticker: 'H${i.toString().padLeft(3, '0')}',
      quantity: (10 + i).toDouble(),
      avgCost: (50 + i).toDouble(),
      mark: (55 + i).toDouble(),
      value: (55 + i) * (10 + i).toDouble(),
      unrealisedPnl: 50.0 + i,
      openedAt: DateTime.now().subtract(Duration(days: i)),
    );

SimTrade _openTrade(int i) => SimTrade(
      id: 'open-$i',
      userId: 'u1',
      ticker: 'O${i.toString().padLeft(3, '0')}',
      side: 'buy',
      quantity: 10,
      entryPrice: 100,
      openedAt: DateTime.now().subtract(Duration(days: i)),
      status: 'open',
      realisedPnl: 0,
      stop: 90,
      target: 120,
    );

SimTrade _closedTrade(int i, {required DateTime closedAt}) => SimTrade(
      id: 'closed-$i',
      userId: 'u1',
      ticker: 'C${i.toString().padLeft(3, '0')}',
      side: i.isEven ? 'buy' : 'sell',
      quantity: 10,
      entryPrice: 100,
      openedAt: closedAt.subtract(const Duration(days: 3)),
      closedAt: closedAt,
      closedPrice: i.isEven ? 110 : 90,
      status: i.isEven ? 'won' : 'lost',
      realisedPnl: i.isEven ? 41.5 : -18.2,
    );

WatchlistEntry _watchlistEntry(int i) => WatchlistEntry(
      id: 'w-$i',
      userId: 'u1',
      ticker: 'W${i.toString().padLeft(3, '0')}',
      addedAt: DateTime.now().subtract(Duration(days: i)),
      price: 120.5 + i,
      dayChangePct: i.isEven ? 1.2 : -0.8,
    );

SimState _heavySimState() {
  final closed = List.generate(
    195,
    (i) => _closedTrade(i, closedAt: DateTime.now().subtract(Duration(days: i))),
  );
  return SimState(
    portfolio: _portfolio(holdings: List.generate(12, _holding)),
    trades: [...List.generate(5, _openTrade), ...closed],
  );
}

WatchlistState _heavyWatchlistState() =>
    WatchlistState(items: List.generate(40, _watchlistEntry));

Future<void> _pump(
  WidgetTester tester, {
  Locale? locale,
  ThemeData? theme,
}) async {
  tester.view.physicalSize = const Size(390, 844);
  tester.view.devicePixelRatio = 1.0;
  addTearDown(tester.view.reset);

  await tester.pumpWidget(
    ProviderScope(
      overrides: [
        simNotifierProvider
            .overrideWith((ref) => _FixedSimNotifier(ref, _heavySimState())),
        watchlistNotifierProvider.overrideWith(
            (ref) => _FixedWatchlistNotifier(ref, _heavyWatchlistState())),
        journalNotifierProvider.overrideWith(
            (ref) => _FixedJournalNotifier(ref, const JournalState())),
        alpacaStatusProvider
            .overrideWith((ref) async => const AlpacaStatus(linked: false)),
        sectorAllocationProvider.overrideWith((ref) async =>
            const SectorAllocation(
              allocation: {},
              totalValue: 0,
              compliance: SectorCompliance(
                maxSector: 0, maxAllowed: 0.4, compliant: true,
              ),
            )),
      ],
      child: MaterialApp(
        locale: locale,
        theme: theme,
        localizationsDelegates: AppLocalizations.localizationsDelegates,
        supportedLocales: AppLocalizations.supportedLocales,
        home: const PortfolioScreen(),
      ),
    ),
  );
  await tester.pump();
  await tester.pump();
}

Future<void> _scrollToEnd(WidgetTester tester, String key) async {
  final scrollable = find.descendant(
    of: find.byKey(PageStorageKey<String>(key)),
    matching: find.byType(Scrollable),
  );
  await tester.drag(scrollable, const Offset(0, -1000000));
  await tester.pump();
  await tester.pump(const Duration(milliseconds: 300));
}

void main() {
  testWidgets('PROBE 1 — independent re-measure of Positions scroll extent',
      (tester) async {
    await _pump(tester);
    final scrollableFinder = find.descendant(
      of: find.byKey(const PageStorageKey<String>('portfolioPositionsScroll')),
      matching: find.byType(Scrollable),
    );
    final scrollState = tester.state<ScrollableState>(scrollableFinder);
    final screens = (844 + scrollState.position.maxScrollExtent) / 844;
    // ignore: avoid_print
    print('AUDIT-MEASURE screens=$screens');
    expect(tester.takeException(), isNull);
  });

  testWidgets('PROBE 2 — History SHOW ALL state survives segment round-trip',
      (tester) async {
    await _pump(tester);
    await tester.tap(find.textContaining('HISTORY 195'));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 300));
    await _scrollToEnd(tester, 'portfolioHistoryScroll');
    await tester.tap(find.textContaining('SHOW ALL 195'));
    await tester.pump();

    // Leave History for Positions, then come back.
    await tester.tap(find.textContaining('POSITIONS 12'));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 300));
    await tester.tap(find.textContaining('HISTORY 195'));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 300));

    // PageStorage restored the scrolled-down position — drag back to the
    // top before reading the header.
    final historyScrollable = find.descendant(
      of: find.byKey(const PageStorageKey<String>('portfolioHistoryScroll')),
      matching: find.byType(Scrollable),
    );
    await tester.drag(historyScrollable, const Offset(0, 1000000));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 300));
    expect(find.textContaining('LAST 25 CLOSED'), findsNothing,
        reason: 'cap header back after round-trip — _showAll State did NOT '
            'survive; IndexedStack claim fails');
    expect(find.text('195 CLOSED'), findsOneWidget);
    await _scrollToEnd(tester, 'portfolioHistoryScroll');
    expect(find.textContaining('SHOW ALL 195'), findsNothing,
        reason: 'SHOW ALL reappeared after segment round-trip — _showAll '
            'State did NOT survive; IndexedStack claim fails');
    expect(find.textContaining('C194'), findsWidgets,
        reason: 'oldest closed trade not built after round-trip — the '
            'expansion itself did not survive');
    expect(tester.takeException(), isNull);
  });

  testWidgets('PROBE 3 — real RTL (ar locale) render, no exceptions',
      (tester) async {
    await _pump(tester, locale: const Locale('ar'));
    await tester.pump(const Duration(milliseconds: 300));

    // Directionality really is RTL.
    final dir = tester.widget<Directionality>(
        find.byType(Directionality).first);
    expect(dir.textDirection, TextDirection.rtl,
        reason: 'ar locale did not produce RTL directionality');

    // Isolated numeric run present on the value card.
    final isolated = find.byWidgetPredicate((w) =>
        w is Text &&
        (w.data ?? '').contains('⁦') &&
        (w.data ?? '').contains('⁩'));
    expect(isolated, findsWidgets);

    // Exercise all three tabs under RTL — any RenderFlex reorder blowup
    // surfaces as an exception here.
    await tester.tap(find.textContaining('WATCHLIST 40'));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 300));
    await tester.tap(find.textContaining('HISTORY 195'));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 300));
    await _scrollToEnd(tester, 'portfolioHistoryScroll');
    expect(tester.takeException(), isNull);
  });
}
