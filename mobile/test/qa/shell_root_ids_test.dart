/// CR264 Phase C — the live HomeShell semantics tree exposes the tab-host and
/// segment-pane root ids the exhaustive crawl keys on.
///
/// Pumps the real `HomeShell` and asserts, via `find.bySemanticsIdentifier`,
/// that the Floor root is in the tree, and that switching Portfolio / YOU
/// segments keeps the host id AND exposes the active pane's own id.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/sim.dart';
import 'package:ami_trade/screens/home_shell.dart';
import 'package:ami_trade/state/alpaca_providers.dart';
import 'package:ami_trade/state/journal_providers.dart';
import 'package:ami_trade/state/sim_providers.dart';
import 'package:ami_trade/state/watchlist_providers.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ami_trade/qa/semantics_ids.dart';
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

SimTrade _closedTrade() => SimTrade(
      id: 't1',
      userId: 'u1',
      ticker: 'AAPL',
      side: 'buy',
      quantity: 10,
      entryPrice: 100,
      openedAt: DateTime(2026, 1, 1),
      closedAt: DateTime(2026, 1, 5),
      closedPrice: 110,
      status: 'won',
      realisedPnl: 100,
    );

Future<void> _settle(WidgetTester t) async {
  for (var i = 0; i < 10; i++) {
    await t.pump(const Duration(milliseconds: 50));
  }
}

void main() {
  testWidgets('Floor, Portfolio and YOU hosts and their panes carry root ids',
      (t) async {
    final sem = t.ensureSemantics();
    t.view.physicalSize = const Size(390, 844);
    t.view.devicePixelRatio = 1.0;
    addTearDown(t.view.reset);
    await t.pumpWidget(ProviderScope(
      overrides: [
        simNotifierProvider.overrideWith((ref) => _FixedSimNotifier(
              ref,
              SimState(
                portfolio: SimPortfolio(
                  userId: 'u1',
                  portfolioId: 'p1',
                  startingCapital: 100000,
                  currentCash: 100000,
                  holdings: const [],
                  totalValue: 100000,
                  drawdownPct: 0.0,
                  priceSource: 'yahoo',
                ),
                trades: [_closedTrade()],
              ),
            )),
        watchlistNotifierProvider.overrideWith(
            (ref) => _FixedWatchlistNotifier(ref, const WatchlistState())),
        journalNotifierProvider.overrideWith(
            (ref) => _FixedJournalNotifier(ref, const JournalState())),
        alpacaLinkedProvider.overrideWith((ref) async => false),
        sectorAllocationProvider.overrideWith((ref) async => SectorAllocation(
              allocation: const {'Cash': 1.0},
              totalValue: 100000,
              compliance: const SectorCompliance(
                maxSector: 0.1,
                maxSectorName: 'Cash',
                maxAllowed: 0.4,
                compliant: true,
              ),
            )),
      ],
      child: const MaterialApp(
        localizationsDelegates: AppLocalizations.localizationsDelegates,
        supportedLocales: AppLocalizations.supportedLocales,
        home: HomeShell(),
      ),
    ));
    await _settle(t);

    expect(find.bySemanticsIdentifier(ScreenIds.floorScreen), findsOneWidget,
        reason: 'Floor root id missing from the live HomeShell tree');

    await t.tap(find.text('PORTFOLIO'));
    await _settle(t);
    expect(
        find.bySemanticsIdentifier(ScreenIds.portfolioScreen), findsOneWidget);

    await t.tap(find.textContaining('ORDERS'));
    await _settle(t);
    expect(
        find.bySemanticsIdentifier(ScreenIds.portfolioScreen), findsOneWidget,
        reason: 'host id must survive a segment switch');
    expect(find.bySemanticsIdentifier(ScreenIds.portfolioOrdersPane),
        findsOneWidget);
    expect(find.bySemanticsIdentifier(ScreenIds.portfolioPositionsPane),
        findsNothing);

    await t.tap(find.text('YOU'));
    await _settle(t);
    expect(find.bySemanticsIdentifier(ScreenIds.youScreen), findsOneWidget);
    expect(
        find.bySemanticsIdentifier(ScreenIds.youSettingsPane), findsOneWidget);

    await t.tap(find.text('JOURNAL'));
    await _settle(t);
    expect(find.bySemanticsIdentifier(ScreenIds.youScreen), findsOneWidget);
    expect(
        find.bySemanticsIdentifier(ScreenIds.youJournalPane), findsOneWidget);
    expect(find.bySemanticsIdentifier(ScreenIds.youSettingsPane), findsNothing);

    sem.dispose();
  });
}
