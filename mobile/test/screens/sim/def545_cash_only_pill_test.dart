/// DEF545 - TOTAL VALUE's LIVE/MOCK pill flipped to MOCK after a full sell. The
/// server now labels a book with nothing priced `cash`; the pill makes no claim
/// for it, and still says MOCK for a held position priced from the mock walk.
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

SimPortfolio _book(String source, {List<SimHolding> holdings = const []}) =>
    SimPortfolio(
      userId: 'u1',
      portfolioId: 'p1',
      startingCapital: 100000,
      currentCash: 100000,
      holdings: holdings,
      totalValue: 100000,
      drawdownPct: 0,
      priceSource: source,
    );

Future<void> _pump(WidgetTester tester, SimPortfolio p) async {
  tester.view.physicalSize = const Size(390, 844);
  tester.view.devicePixelRatio = 1.0;
  addTearDown(tester.view.reset);
  await tester.pumpWidget(
    ProviderScope(
      overrides: [
        simNotifierProvider
            .overrideWith((ref) => _Sim(ref, SimState(portfolio: p))),
        watchlistNotifierProvider.overrideWith((ref) => _Watch(ref)),
        journalNotifierProvider.overrideWith((ref) => _Journal(ref)),
        alpacaLinkedProvider.overrideWith((ref) async => false),
        portfolioHealthProvider.overrideWith((ref) async => healthFixture()),
        sectorAllocationProvider.overrideWith((ref) async =>
            const SectorAllocation(
              allocation: {},
              totalValue: 0,
              compliance: SectorCompliance(
                  maxSector: 0, maxAllowed: 0.4, compliant: true),
            )),
        portfolioHistoryProvider.overrideWith(
            (ref) async => const SimPortfolioHistory(points: [], twrPct: 0)),
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

void main() {
  test('cash is not a mock price and not a live claim', () {
    final cash = _book('cash');
    expect(cash.isCashOnly, isTrue);
    expect(_book('mock_walk').isCashOnly, isFalse);
    expect(_book('yahoo').isCashOnly, isFalse);
  });

  testWidgets('a cash-only book shows neither LIVE nor MOCK', (tester) async {
    await _pump(tester, _book('cash'));
    expect(find.text('MOCK'), findsNothing);
    expect(find.text('LIVE'), findsNothing);
  });

  testWidgets('a mock-priced book still says MOCK', (tester) async {
    await _pump(
      tester,
      _book('mock_walk', holdings: [
        SimHolding(
          ticker: 'F',
          quantity: 1,
          avgCost: 10,
          mark: 10,
          value: 10,
          unrealisedPnl: 0,
          openedAt: DateTime(2026, 11, 24),
        ),
      ]),
    );
    expect(find.text('MOCK'), findsOneWidget);
  });
}
