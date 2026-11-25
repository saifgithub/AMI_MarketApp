/// DEF544 - the Portfolio panels that read their own endpoints (Health card,
/// equity curve, sector donut) were never re-read after a fill, so the Health
/// card kept "NO HOLDINGS TO MEASURE" from before the first buy while POSITIONS
/// (read from `SimState`) said 1. Pins that a change to the book re-fetches all
/// three, and that a price tick alone does not.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/sim.dart';
import 'package:ami_trade/screens/sim/portfolio_screen.dart';
import 'package:ami_trade/state/alpaca_providers.dart';
import 'package:ami_trade/state/journal_providers.dart';
import 'package:ami_trade/state/portfolio_health_providers.dart';
import 'package:ami_trade/state/sim_providers.dart';
import 'package:ami_trade/state/watchlist_providers.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import '../../support/portfolio_health_fixtures.dart';

class _Sim extends SimNotifier {
  _Sim(super.ref, SimState s) {
    state = s;
  }

  void put(SimState s) => state = s;
}

class _Watch extends WatchlistNotifier {
  _Watch(super.ref) {
    state = const WatchlistState();
  }
}

class _Journal extends JournalNotifier {
  _Journal(super.ref) {
    state = const JournalState();
  }
}

SimHolding _held(double qty, {double mark = 10}) => SimHolding(
      ticker: 'F',
      quantity: qty,
      avgCost: 10,
      mark: mark,
      value: qty * mark,
      unrealisedPnl: 0,
      openedAt: DateTime(2026, 11, 24),
    );

SimState _book(List<SimHolding> holdings,
        {double cash = 100000, double mark = 10}) =>
    SimState(
      portfolio: SimPortfolio(
        userId: 'u1',
        portfolioId: 'p1',
        startingCapital: 100000,
        currentCash: cash,
        holdings: holdings,
        totalValue: cash + holdings.fold(0.0, (a, h) => a + h.quantity * mark),
        drawdownPct: 0,
        priceSource: 'yahoo',
      ),
    );

void main() {
  test('book signature moves on a fill and not on a price tick', () {
    final empty = portfolioBookSignature(_book(const []));
    final held = portfolioBookSignature(_book([_held(1)], cash: 99990));
    expect(held, isNot(empty));
    expect(
      portfolioBookSignature(
          _book([_held(1, mark: 12)], cash: 99990, mark: 12)),
      held,
    );
    expect(portfolioBookSignature(const SimState()), '');
  });

  testWidgets('a fill re-reads Health, equity curve and sector feeds',
      (tester) async {
    tester.view.physicalSize = const Size(390, 844);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.reset);

    var health = 0, history = 0, sector = 0;
    late _Sim sim;
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          simNotifierProvider.overrideWith((ref) {
            sim = _Sim(ref, _book(const []));
            return sim;
          }),
          watchlistNotifierProvider.overrideWith((ref) => _Watch(ref)),
          journalNotifierProvider.overrideWith((ref) => _Journal(ref)),
          alpacaLinkedProvider.overrideWith((ref) async => false),
          portfolioHealthProvider.overrideWith((ref) async {
            health++;
            return healthFixture();
          }),
          sectorAllocationProvider.overrideWith((ref) async {
            sector++;
            return const SectorAllocation(
              allocation: {},
              totalValue: 0,
              compliance: SectorCompliance(
                  maxSector: 0, maxAllowed: 0.4, compliant: true),
            );
          }),
          portfolioHistoryProvider.overrideWith((ref) async {
            history++;
            return const SimPortfolioHistory(points: [], twrPct: 0);
          }),
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
    expect([health, history, sector], [1, 1, 1]);

    // A price tick: same positions, same cash, same ledger - no re-read.
    sim.put(_book(const [], cash: 100000, mark: 11));
    await tester.pump();
    await tester.pump();
    expect([health, history, sector], [1, 1, 1]);

    // The first buy lands.
    sim.put(_book([_held(1)], cash: 99990));
    await tester.pump();
    await tester.pump();
    expect([health, history, sector], [2, 2, 2]);

    // And the full sell.
    sim.put(_book(const [], cash: 100000));
    await tester.pump();
    await tester.pump();
    expect([health, history, sector], [3, 3, 3]);
  });
}
