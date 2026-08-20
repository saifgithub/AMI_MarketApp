/// DEF341 — a ticker symbol never wraps mid-symbol.
///
/// Field screenshot (0.1.0+68, iOS): "GOOGL" rendered as "GOOG"/"L" in the
/// Portfolio watchlist row, because the symbol Text sat in a fixed 72pt box
/// with no fit constraint and statMid/24px "GOOGL" is wider than that. The
/// contract pinned here: a 5-char ticker renders on ONE line at the 390pt
/// test surface, scaled down to fit rather than broken — in both render
/// paths, the Portfolio watchlist row and the watchlist quick-action sheet.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/alpaca.dart';
import 'package:ami_trade/models/journal.dart';
import 'package:ami_trade/models/sim.dart';
import 'package:ami_trade/models/watchlist.dart';
import 'package:ami_trade/screens/sim/portfolio_screen.dart';
import 'package:ami_trade/state/alpaca_providers.dart';
import 'package:ami_trade/state/journal_providers.dart';
import 'package:ami_trade/state/portfolio_health_providers.dart';
import 'package:ami_trade/state/sim_providers.dart';
import 'package:ami_trade/state/watchlist_providers.dart';
import 'package:ami_trade/widgets/watchlist_sheet.dart';
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

SimState _simState() => SimState(
      portfolio: SimPortfolio(
        userId: 'u1',
        portfolioId: 'p1',
        startingCapital: 100000,
        currentCash: 100000,
        holdings: const [],
        totalValue: 100000,
        drawdownPct: 0,
        priceSource: 'yahoo',
      ),
      // One settled trade: the empty History branch returns before the
      // watchlist slivers are spliced in, so an empty book would never
      // mount the row under test.
      trades: [
        SimTrade(
          id: 'closed-1',
          userId: 'u1',
          ticker: 'AAPL',
          side: 'buy',
          quantity: 10,
          entryPrice: 100,
          openedAt: DateTime(2026, 7, 1),
          closedAt: DateTime(2026, 7, 4),
          closedPrice: 110,
          status: 'won',
          realisedPnl: 100,
        ),
      ],
    );

WatchlistState _watchlist() => WatchlistState(items: [
      WatchlistEntry(
        id: 'w-googl',
        userId: 'u1',
        ticker: 'GOOGL',
        addedAt: DateTime(2026, 8, 1),
        price: 187.33,
        dayChangePct: 1.2,
      ),
    ]);

Future<void> _pumpPortfolio(WidgetTester tester) async {
  tester.view.physicalSize = const Size(390, 844);
  tester.view.devicePixelRatio = 1.0;
  addTearDown(tester.view.reset);

  await tester.pumpWidget(
    ProviderScope(
      overrides: [
        simNotifierProvider
            .overrideWith((ref) => _FixedSimNotifier(ref, _simState())),
        watchlistNotifierProvider
            .overrideWith((ref) => _FixedWatchlistNotifier(ref, _watchlist())),
        journalNotifierProvider.overrideWith(
            (ref) => _FixedJournalNotifier(ref, const JournalState())),
        alpacaStatusProvider
            .overrideWith((ref) async => const AlpacaStatus(linked: false)),
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
  testWidgets('watchlist row: a 5-char ticker renders one line at 390pt',
      (tester) async {
    await _pumpPortfolio(tester);

    // The watchlist is a section of the History tab (CR188 slice 3).
    await tester.tap(find.textContaining('HISTORY'));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 300));
    final scrollable = find.descendant(
      of: find.byKey(const PageStorageKey<String>('portfolioHistoryScroll')),
      matching: find.byType(Scrollable),
    );
    await tester.scrollUntilVisible(find.text('GOOGL'), 300,
        scrollable: scrollable);
    await tester.pump();

    final ticker = find.text('GOOGL');
    expect(ticker, findsOneWidget);
    final rect = tester.getRect(ticker);
    // One displayed line: at the test font "GOOGL"/statMid is wider than the
    // row's 72pt symbol box, so the unfixed layout wraps it to two lines
    // (~48pt tall). Scaled-to-fit it stays a single ~24pt line inside the box.
    expect(rect.height, lessThan(30),
        reason: 'ticker wrapped to a second line — a symbol never breaks '
            'mid-symbol (measured ${rect.height.toStringAsFixed(1)}pt tall)');
    expect(rect.width, lessThanOrEqualTo(72.5),
        reason: 'ticker must fit its 72pt column, scaled down, not overflow');
    expect(tester.takeException(), isNull);
  });

  testWidgets('watchlist sheet: the ticker headline never wraps or overflows',
      (tester) async {
    tester.view.physicalSize = const Size(390, 844);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.reset);

    await tester.pumpWidget(
      ProviderScope(
        child: MaterialApp(
          localizationsDelegates: AppLocalizations.localizationsDelegates,
          supportedLocales: AppLocalizations.supportedLocales,
          home: Consumer(
            builder: (context, ref, _) => Scaffold(
              body: Center(
                child: ElevatedButton(
                  onPressed: () => showWatchlistSheet(
                    context,
                    ref,
                    ticker: 'GOOGL',
                    price: 187.33,
                  ),
                  child: const Text('open'),
                ),
              ),
            ),
          ),
        ),
      ),
    );
    await tester.tap(find.text('open'));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 300));

    final ticker = find.text('GOOGL');
    expect(ticker, findsOneWidget);
    expect(tester.getRect(ticker).height, lessThan(30),
        reason: 'sheet headline ticker must stay a single line');
    expect(tester.takeException(), isNull);
  });
}
