/// DEF190 — the bottom nav bar disappeared when Journal was opened via
/// "Review in Journal" from Portfolio's History tab.
///
/// `_JournalPointer` used to `Navigator.push` a second, orphaned
/// `JournalScreen` on top of `HomeShell`'s own `Scaffold` — the bottom nav
/// lives in that Scaffold, below whatever gets pushed on top of it, so it
/// was covered, not removed, until the user backed out. The fix routes
/// through `activeTabProvider` instead, which `HomeShell` now listens
/// to, so "review in Journal" switches the shell's own tab rather than
/// pushing a route.
///
/// This pumps the real `HomeShell` (all five tabs are eagerly built inside
/// its `IndexedStack`) with just enough state overridden that Portfolio's
/// History tab has a closed trade to show a "REVIEW IN JOURNAL" link for —
/// the same fixture shape `sector_legend_cap_test.dart` uses for
/// `PortfolioScreen` directly.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/sim.dart';
import 'package:ami_trade/screens/home_shell.dart';
import 'package:ami_trade/screens/journal/journal_screen.dart';
import 'package:ami_trade/state/alpaca_providers.dart';
import 'package:ami_trade/state/journal_providers.dart';
import 'package:ami_trade/state/sim_providers.dart';
import 'package:ami_trade/state/watchlist_providers.dart';
import 'package:ami_trade/widgets/hex/hex_bottom_nav.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ami_trade/features/games/games_gate.dart';
import 'package:ami_trade/features/nav/ami_tab.dart';
import 'package:ami_trade/features/tour/tour_providers.dart';
import 'package:ami_trade/qa/semantics_ids.dart';
import 'package:ami_trade/screens/you/you_providers.dart';
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

Future<void> _pumpHome(WidgetTester tester) async {
  tester.view.physicalSize = const Size(390, 844);
  tester.view.devicePixelRatio = 1.0;
  addTearDown(tester.view.reset);

  await tester.pumpWidget(
    ProviderScope(
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
        alpacaLinkedProvider
            .overrideWith((ref) async => false),
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
    ),
  );
  await tester.pump();
  await tester.pump();
}

/// Not `pumpAndSettle`: something on this shell (the ticker tape, or a
/// pulse loader on one of the five tabs) animates without ever settling —
/// the same reason `room_live_status_test.dart`'s acceptance #7 test uses
/// explicit frames instead. A fixed handful of frames is enough to let any
/// state change (a `setState`, a route push) actually land.
Future<void> _settle(WidgetTester t) async {
  for (var i = 0; i < 10; i++) {
    await t.pump(const Duration(milliseconds: 50));
  }
}

void main() {
  /// CR133 §3 — the enum's declaration order IS the bar's left-to-right order,
  /// and `HomeShell`'s `IndexedStack` indexes its children by `AmiTab.index`.
  /// Those are one fact held in two places, so it gets asserted rather than
  /// maintained by hand: a tab added to the enum without a matching child (or
  /// the reverse) is how a reorder silently points a tab at the wrong screen.
  test('AmiTab declares the bar in order, GAME at slot 3', () {
    expect(AmiTab.values,
        [AmiTab.floor, AmiTab.portfolio, AmiTab.game, AmiTab.lessons, AmiTab.you]);
    expect(AmiTab.values.map((t) => t.index).toList(), [0, 1, 2, 3, 4]);
  });

  test('a gated-off build drops GAME and leaves no hole', () {
    // Tests run without --dart-define=AMI_GAMES, i.e. the store-binary shape.
    expect(kGamesEnabled, isFalse,
        reason: 'this test suite asserts the DEFAULT build; if AMI_GAMES is on '
            'here, the assertions below are describing a different binary');
    expect(AmiTab.visible,
        [AmiTab.floor, AmiTab.portfolio, AmiTab.lessons, AmiTab.you]);
    expect(AmiTab.visible.contains(AmiTab.game), isFalse);
  });

  testWidgets('the bar, the panes and AmiTab.visible are one fact', (t) async {
    // CR133 §3 — three lists that must stay the same length and the same
    // order. Held in two places (the enum, and `HomeShell._panes`), so it is
    // asserted rather than maintained by hand: a tab added without a matching
    // pane is how a reorder silently points a tab at the wrong screen, and
    // three of the five old integer literals kept working through exactly
    // that reorder.
    await _pumpHome(t);
    await _settle(t);
    final nav = t.widget<HexBottomNav>(find.byType(HexBottomNav));
    expect(nav.items.length, AmiTab.visible.length);
    expect(nav.items.map((i) => i.id).toList(), NavIds.all);

    final stack = t.widget<IndexedStack>(find.descendant(
      of: find.byType(HomeShell),
      matching: find.byType(IndexedStack),
    ).first);
    expect(stack.children.length, AmiTab.visible.length,
        reason: 'a pane per visible tab — any other count means the '
            'IndexedStack index is addressing the wrong screen');
  });

  testWidgets('SETTINGS and JOURNAL are no longer bottom-nav destinations',
      (t) async {
    // They moved inside YOU (CR133 §4). Asserted because the failure mode of
    // getting this wrong is not a crash: it is two ways to reach the same
    // screen, one of which is the one users learned.
    await _pumpHome(t);
    await _settle(t);
    final nav = t.widget<HexBottomNav>(find.byType(HexBottomNav));
    final labels = nav.items.map((i) => i.label).toList();
    expect(labels, ['FLOOR', 'PORTFOLIO', 'LESSONS', 'YOU']);
  });

  testWidgets(
      'DEF190: the bottom nav survives "Review in Journal" from '
      "Portfolio's History tab", (t) async {
    await _pumpHome(t);

    // Land on Portfolio (tab 1).
    await t.tap(find.text('PORTFOLIO'));
    await _settle(t);
    expect(find.byType(HexBottomNav), findsOneWidget);

    // Switch to the History segment inside Portfolio.
    await t.tap(find.textContaining('HISTORY'));
    await _settle(t);

    // "Review in Journal" must be visible now that there is a closed trade.
    final reviewLink = find.text('REVIEW IN JOURNAL');
    expect(reviewLink, findsOneWidget);

    await t.tap(reviewLink);
    await _settle(t);

    // `find.byType` searches the whole tree regardless of paint order, so a
    // route pushed on TOP of the nav bar still "finds" it — that check alone
    // would pass even on the buggy build (the nav bar is covered, not
    // removed). The two checks that actually distinguish "switched tabs"
    // from "pushed a route on top": no route is pushable-back-from (nothing
    // was pushed), and there is still exactly ONE `JournalScreen` — the one
    // `IndexedStack` always keeps alive — not a second, orphaned one.
    final homeShellContext = t.element(find.byType(HomeShell));
    expect(Navigator.of(homeShellContext).canPop(), isFalse,
        reason: 'DEF190: "Review in Journal" must switch tabs, not push a '
            'route the user has to back out of');
    expect(find.byType(JournalScreen), findsOneWidget,
        reason: 'a pushed route would create a second, orphaned '
            'JournalScreen alongside the one already living in the '
            'IndexedStack');
    expect(find.byType(HexBottomNav), findsOneWidget,
        reason: 'DEF190: the bottom nav bar must survive "Review in '
            'Journal" from Portfolio > History');
    // CR133 §3 — the Journal is a segment of YOU now, so "landed on the
    // Journal" means the YOU tab is active AND its JOURNAL segment is
    // selected. Asserting only the tab would pass while the user stared at
    // Settings with the entry they asked for one invisible tap away.
    final container = ProviderScope.containerOf(t.element(find.byType(HomeShell)));
    expect(container.read(activeTabProvider), AmiTab.you);
    expect(container.read(youSegmentProvider), YouSegment.journal);
    expect(container.read(journalVisibleProvider), isTrue);
    expect(t.takeException(), isNull);
  });
}
