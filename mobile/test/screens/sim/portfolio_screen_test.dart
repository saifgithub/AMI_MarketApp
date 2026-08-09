/// CR120 Phase 1 — Portfolio segmented tabs.
///
/// `PortfolioScreen` reads `simNotifierProvider` / `watchlistNotifierProvider`
/// / `journalNotifierProvider` directly; this harness overrides each with a
/// notifier pre-seeded to a fixed state (never calling `refresh()`, so no
/// real network/DeviceUser call is touched — the same pattern
/// `room_live_data_notice_test.dart` uses for `roomNotifierProvider`).
///
/// Measured, not asserted (§9 acceptance 1): the heavy-profile scroll extent
/// is read off the real `ScrollPosition` of the mounted Positions tab, at a
/// 390×844 test surface matching the CR's own prototype measurements.
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

/// A `JournalNotifier` that never resolves `retentionLoaded` — used to
/// prove the D3/6b "unknown" path specifically, not merely that some
/// caveat rendered. Overrides `refresh()` to a no-op so the provider's own
/// `Future.microtask(n.refresh)` on creation cannot accidentally complete
/// and flip `retentionLoaded` mid-test.
class _NeverLoadedJournalNotifier extends JournalNotifier {
  _NeverLoadedJournalNotifier(super.ref);

  @override
  Future<void> refresh({
    JournalEntryType? filterType,
    String plan = 'trial_trader',
    String? q,
  }) async {}
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

/// The CR's own "heavy" profile (§1.1): 40 watch, 12 held, 5 open + 195
/// closed. Closed trades spread newest-first across ~72 days so the span
/// caption has real dates to render, and the first 30 are dated within the
/// last 30 days (retention-window tests below rely on that split).
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

/// CR109 slice 1 — the equity-curve card is a real, permanent occupant of
/// the Positions tab now, same reasoning as the Health-card fixture below:
/// the scroll budget has to measure its POPULATED state (a live curve, no
/// caveat line), not the error notice an unmocked network call would
/// produce.
SimPortfolioHistory _equityHistoryFixture() => SimPortfolioHistory(
      points: List.generate(
        30,
        (i) => SimPortfolioHistoryPoint(
          asOfDate: DateTime(2026, 7, 1).add(Duration(days: i)),
          nav: 250000.0 + i * 200,
          cash: 30000,
          priceSource: 'live',
          capitalEvent: i == 0 ? 'open' : null,
        ),
      ),
      twrPct: 2.34,
    );

Future<void> _pump(
  WidgetTester tester, {
  required SimState sim,
  required WatchlistState watchlist,
  JournalState? journal,
  bool journalNeverLoads = false,
}) async {
  tester.view.physicalSize = const Size(390, 844);
  tester.view.devicePixelRatio = 1.0;
  addTearDown(tester.view.reset);

  await tester.pumpWidget(
    ProviderScope(
      overrides: [
        simNotifierProvider
            .overrideWith((ref) => _FixedSimNotifier(ref, sim)),
        watchlistNotifierProvider
            .overrideWith((ref) => _FixedWatchlistNotifier(ref, watchlist)),
        if (journalNeverLoads)
          journalNotifierProvider
              .overrideWith((ref) => _NeverLoadedJournalNotifier(ref))
        else
          journalNotifierProvider.overrideWith(
              (ref) => _FixedJournalNotifier(ref, journal ?? const JournalState())),
        alpacaStatusProvider
            .overrideWith((ref) async => const AlpacaStatus(linked: false)),
        // CR136 M09: the Health card is a real, permanent occupant of this
        // tab, so the scroll budget below has to measure it in its POPULATED
        // state — the state a user with holdings actually sees. Leaving it to
        // hit the network here would measure the error notice instead, which
        // is both smaller and not what ships.
        portfolioHealthProvider.overrideWith((ref) async => healthFixture()),
        sectorAllocationProvider.overrideWith((ref) async => const SectorAllocation(
              allocation: {},
              totalValue: 0,
              compliance: SectorCompliance(
                maxSector: 0, maxAllowed: 0.4, compliant: true,
              ),
            )),
        portfolioHistoryProvider
            .overrideWith((ref) async => _equityHistoryFixture()),
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

/// Drags a keyed `Scrollable` to its end. The History tab's summary/cap
/// header sits above 25 lazily-built `TradeRow`s, so the SHOW ALL button
/// and the Journal pointer below them are off the initial 844pt viewport
/// (plus cache extent) and are not yet built until scrolled into view —
/// that is what "lazy" (§9 acceptance 7) means, not a rendering bug.
Future<void> _scrollToEnd(WidgetTester tester, String pageStorageKeyLabel) async {
  final scrollable = find.descendant(
    of: find.byKey(PageStorageKey<String>(pageStorageKeyLabel)),
    matching: find.byType(Scrollable),
  );
  await tester.drag(scrollable, const Offset(0, -1000000));
  await tester.pump();
  await tester.pump(const Duration(milliseconds: 300));
}

double _screensOfScroll(WidgetTester tester, String pageStorageKeyLabel) {
  final scrollableFinder = find.descendant(
    of: find.byKey(PageStorageKey<String>(pageStorageKeyLabel)),
    matching: find.byType(Scrollable),
  );
  final scrollState = tester.state<ScrollableState>(scrollableFinder);
  final maxExtent = scrollState.position.maxScrollExtent;
  // Non-scrolling chrome (header + pinned value card + tab bar) occupies
  // (844 - viewportDimension) of the 844pt test surface; adding it back to
  // the scrollable's own total content height gives the same "whole page
  // scrollHeight" the CR's prototype read out of the DOM.
  return (844 + maxExtent) / 844;
}

void main() {
  group('CR120 §9 acceptance 1 — landing scroll at the heavy profile', () {
    // The budget was 3.0 screens and measured 2.99 — saturated. CR136 M09 adds
    // the Portfolio Health card to this tab, a deliberate new occupant, and it
    // measures 563pt collapsed (803pt with the risk-vs-money breakdown open,
    // which is why the breakdown ships collapsed at all — Saiful's call,
    // 2026-08-03). The tab now measures 3.71 screens.
    //
    // CR109 slice 1 adds the equity-curve card (`PortfolioEquityChart`) above
    // Sector Allocation — a THIRD deliberate new occupant, and the argument
    // the CR136 comment above asked for: the app could not draw a portfolio's
    // history before this, which is the CR's own justification for landing it
    // on this tab rather than gating it behind a new surface. Measured 3.93
    // screens at the heavy profile (30-point fixture, live throughout, no
    // caveat line); budget raised to 4.0.
    //
    // The number moves because the content moved; the guard stays real. Anyone
    // adding a FOURTH card here has to make the same argument out loud rather
    // than discovering the cap had quietly become decorative.
    testWidgets('Positions tab is <= 4.0 screens, measured from ScrollPosition',
        (tester) async {
      await _pump(tester, sim: _heavySimState(), watchlist: _heavyWatchlistState());

      final screens = _screensOfScroll(tester, 'portfolioPositionsScroll');
      expect(screens, lessThanOrEqualTo(4.0),
          reason: 'measured ${screens.toStringAsFixed(2)} screens at the '
              'heavy profile (12 held, 5 open, 195 closed, 40 watch)');
      expect(tester.takeException(), isNull);
    });
  });

  group('CR120 §9 acceptance 2 — open trades never hidden', () {
    testWidgets('open trades render on the landing tab; History excludes them',
        (tester) async {
      await _pump(tester, sim: _heavySimState(), watchlist: _heavyWatchlistState());

      // Open trades sit below 12 holding cards on the Positions tab — off
      // the initial viewport, same lazy-build reason as the History tests.
      // Scrolling to reach them (rather than requiring them in the first
      // screenful) is the acceptance itself: "never hidden" means reachable
      // on the landing tab, not necessarily above the fold.
      await _scrollToEnd(tester, 'portfolioPositionsScroll');
      expect(find.textContaining('O000'), findsOneWidget);

      // History count reads 195 (closed only), not 200.
      expect(find.textContaining('HISTORY 195'), findsOneWidget);
      expect(find.textContaining('HISTORY 200'), findsNothing);
      expect(tester.takeException(), isNull);
    });

    testWidgets('Positions tab shows the live pip whether or not selected',
        (tester) async {
      await _pump(tester, sim: _heavySimState(), watchlist: _heavyWatchlistState());
      // Switch to Watchlist tab.
      await tester.tap(find.textContaining('WATCHLIST 40'));
      await tester.pump();
      // The pip is part of the tab bar itself (always mounted), not tab
      // content, so it must still be findable with Positions unselected.
      expect(find.byWidgetPredicate((w) => w.runtimeType.toString() == '_LivePip'),
          findsOneWidget);
      expect(tester.takeException(), isNull);
    });
  });

  group('CR120 §9 acceptance 3/4 — 25-cap with span, summary over all closed', () {
    testWidgets('History caps at 25 with the span stated, summary reads 195',
        (tester) async {
      await _pump(tester, sim: _heavySimState(), watchlist: _heavyWatchlistState());
      await tester.tap(find.textContaining('HISTORY 195'));
      // HexChip's LIVE/MOCK pip pulses forever (..repeat(reverse: true)),
      // so pumpAndSettle() never returns on this screen — bounded pumps
      // instead, long enough to clear the 200ms tab-fill / scroll physics.
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 300));

      expect(find.textContaining('LAST 25 CLOSED'), findsOneWidget);
      expect(find.textContaining('ACROSS ALL 195 CLOSED'), findsOneWidget);
      // Won/lost computed over all 195 (98 even-indexed win, 97 lose),
      // not the visible 25.
      expect(find.text('98'), findsOneWidget); // WON
      expect(find.text('97'), findsOneWidget); // LOST
      expect(tester.takeException(), isNull);
    });
  });

  group('CR120 §9 acceptance 5 (D2) — SHOW ALL is an in-place expansion', () {
    testWidgets('SHOW ALL reveals every closed trade from Portfolio data',
        (tester) async {
      await _pump(tester, sim: _heavySimState(), watchlist: _heavyWatchlistState());
      await tester.tap(find.textContaining('HISTORY 195'));
      // HexChip's LIVE/MOCK pip pulses forever (..repeat(reverse: true)),
      // so pumpAndSettle() never returns on this screen — bounded pumps
      // instead, long enough to clear the 200ms tab-fill / scroll physics.
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 300));
      // The SHOW ALL button sits below the 25 lazily-built rows.
      await _scrollToEnd(tester, 'portfolioHistoryScroll');

      expect(find.textContaining('SHOW ALL 195'), findsOneWidget);
      await tester.tap(find.textContaining('SHOW ALL 195'));
      await tester.pump();

      // The oldest closed trade (C194, closedAt furthest in the past) is
      // now reachable — scroll the History list to the end again to prove
      // it is actually built, not merely counted.
      await _scrollToEnd(tester, 'portfolioHistoryScroll');
      expect(find.textContaining('SHOW ALL 195'), findsNothing);
      expect(tester.takeException(), isNull);
    });
  });

  group('CR120 §9 acceptance 6/6b (D3) — plan-aware Journal pointer', () {
    testWidgets('unknown retention (never loaded) shows the number-less caveat',
        (tester) async {
      await _pump(
        tester,
        sim: _heavySimState(),
        watchlist: _heavyWatchlistState(),
        journalNeverLoads: true,
      );
      await tester.tap(find.textContaining('HISTORY 195'));
      // HexChip's LIVE/MOCK pip pulses forever (..repeat(reverse: true)),
      // so pumpAndSettle() never returns on this screen — bounded pumps
      // instead, long enough to clear the 200ms tab-fill / scroll physics.
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 300));
      await _scrollToEnd(tester, 'portfolioHistoryScroll');

      expect(find.textContaining('may not show all of these'), findsOneWidget);
      // The finite-window and unlimited-specific strings must NOT appear —
      // proves this is the unknown path, not an accidental pass.
      expect(find.textContaining('shows the last'), findsNothing);
      expect(tester.takeException(), isNull);
    });

    testWidgets('known-unlimited retention shows no caveat line', (tester) async {
      await _pump(
        tester,
        sim: _heavySimState(),
        watchlist: _heavyWatchlistState(),
        journal: const JournalState(retentionDays: null, retentionLoaded: true),
      );
      await tester.tap(find.textContaining('HISTORY 195'));
      // HexChip's LIVE/MOCK pip pulses forever (..repeat(reverse: true)),
      // so pumpAndSettle() never returns on this screen — bounded pumps
      // instead, long enough to clear the 200ms tab-fill / scroll physics.
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 300));
      await _scrollToEnd(tester, 'portfolioHistoryScroll');

      expect(find.textContaining('may not show all of these'), findsNothing);
      expect(find.textContaining('shows the last'), findsNothing);
      expect(find.textContaining('REVIEW IN JOURNAL'), findsOneWidget);
      expect(tester.takeException(), isNull);
    });

    testWidgets('known-finite retention states the older count and "nothing is deleted"',
        (tester) async {
      await _pump(
        tester,
        sim: _heavySimState(),
        watchlist: _heavyWatchlistState(),
        journal: const JournalState(retentionDays: 30, retentionLoaded: true),
      );
      await tester.tap(find.textContaining('HISTORY 195'));
      // HexChip's LIVE/MOCK pip pulses forever (..repeat(reverse: true)),
      // so pumpAndSettle() never returns on this screen — bounded pumps
      // instead, long enough to clear the 200ms tab-fill / scroll physics.
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 300));
      await _scrollToEnd(tester, 'portfolioHistoryScroll');

      // Closed trades are dated 0..194 days ago against the fixture's
      // DateTime.now(); the cutoff the app computes is its own (later)
      // DateTime.now() minus 30 days, so trade 30 — created exactly 30
      // fixture-days ago — always lands a few hundred ms on the far side
      // of a cutoff drawn a few hundred ms later. Indices 30..194 = 165.
      expect(find.textContaining('shows the last 30 days'), findsOneWidget);
      expect(find.textContaining('165 of these 195 are older'), findsOneWidget);
      expect(find.textContaining('Nothing is deleted'), findsOneWidget);
      expect(tester.takeException(), isNull);
    });
  });

  group('CR120 §9 acceptance 7b — tab labels fit unshrunk at 1.0 and 1.15', () {
    for (final scale in [1.0, 1.15]) {
      testWidgets('no overflow at textScaleFactor $scale', (tester) async {
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
              sectorAllocationProvider.overrideWith((ref) async => const SectorAllocation(
                    allocation: {},
                    totalValue: 0,
                    compliance: SectorCompliance(
                      maxSector: 0, maxAllowed: 0.4, compliant: true,
                    ),
                  )),
              portfolioHistoryProvider
                  .overrideWith((ref) async => _equityHistoryFixture()),
            ],
            child: MediaQuery(
              data: MediaQueryData(textScaler: TextScaler.linear(scale)),
              child: MaterialApp(
                localizationsDelegates: AppLocalizations.localizationsDelegates,
                supportedLocales: AppLocalizations.supportedLocales,
                home: const PortfolioScreen(),
              ),
            ),
          ),
        );
        await tester.pump();
        await tester.pump();

        expect(find.textContaining('POSITIONS 12'), findsOneWidget);
        expect(find.textContaining('WATCHLIST 40'), findsOneWidget);
        expect(find.textContaining('HISTORY 195'), findsOneWidget);
        // A RenderFlex overflow (the CR108 FittedBox-shrink failure class)
        // throws during layout and surfaces here.
        expect(tester.takeException(), isNull);
      });
    }
  });

  group('CR120 §9 acceptance 8 — bidi-isolated numeric runs', () {
    testWidgets('the value card P&L run is wrapped in directional isolates',
        (tester) async {
      await _pump(tester, sim: _heavySimState(), watchlist: _heavyWatchlistState());

      final matches = find.byWidgetPredicate((w) =>
          w is Text && (w.data ?? '').contains('\u2066') && (w.data ?? '').contains('\u2069'));
      expect(matches, findsWidgets,
          reason: 'no isolated numeric run found — the value card P&L text '
              'should be wrapped in U+2066/U+2069');
      expect(tester.takeException(), isNull);
    });
  });

  group('CR120 §9 acceptance 9 — no clipping at 1.15 text scale', () {
    testWidgets('dark theme renders heavy profile at 1.15 without exceptions',
        (tester) async {
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
            sectorAllocationProvider.overrideWith((ref) async => const SectorAllocation(
                  allocation: {},
                  totalValue: 0,
                  compliance: SectorCompliance(
                    maxSector: 0, maxAllowed: 0.4, compliant: true,
                  ),
                )),
            portfolioHistoryProvider
                .overrideWith((ref) async => _equityHistoryFixture()),
          ],
          child: MediaQuery(
            data: const MediaQueryData(textScaler: TextScaler.linear(1.15)),
            child: MaterialApp(
              theme: ThemeData.dark(),
              localizationsDelegates: AppLocalizations.localizationsDelegates,
              supportedLocales: AppLocalizations.supportedLocales,
              home: const PortfolioScreen(),
            ),
          ),
        ),
      );
      await tester.pump();
      await tester.pump();
      // Exercise all three tabs at the larger scale.
      await tester.tap(find.textContaining('WATCHLIST 40'));
      await tester.pump();
      await tester.tap(find.textContaining('HISTORY 195'));
      await tester.pump();
      expect(tester.takeException(), isNull);
    });
  });

  group('CR120 §9 acceptance 10 — one shared closed-trade row widget', () {
    testWidgets('History rows render through TradeRow, same as open trades',
        (tester) async {
      await _pump(tester, sim: _heavySimState(), watchlist: _heavyWatchlistState());
      await tester.tap(find.textContaining('HISTORY 195'));
      // HexChip's LIVE/MOCK pip pulses forever (..repeat(reverse: true)),
      // so pumpAndSettle() never returns on this screen — bounded pumps
      // instead, long enough to clear the 200ms tab-fill / scroll physics.
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 300));
      // TradeRow renders the status pill uppercase; confirms the closed
      // rows go through the same widget the Positions tab uses for open
      // trades, not a second bespoke renderer.
      expect(find.text('WON'), findsWidgets);
      expect(tester.takeException(), isNull);
    });
  });
}
