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
import 'package:ami_trade/screens/floor/floor_screen.dart';
import 'package:ami_trade/screens/home_shell.dart';
import 'package:ami_trade/screens/journal/journal_screen.dart';
import 'package:ami_trade/screens/sim/trade_ticket_sheet.dart';
import 'package:ami_trade/state/alpaca_providers.dart';
import 'package:ami_trade/state/journal_providers.dart';
import 'package:ami_trade/state/sim_providers.dart';
import 'package:ami_trade/state/watchlist_providers.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:ami_trade/widgets/ads/anchored_ad_banner.dart';
import 'package:ami_trade/widgets/ads/shell_banner_slot.dart';
import 'package:ami_trade/widgets/hex/hex_bottom_nav.dart';
import 'package:ami_trade/widgets/ticker_tape.dart';
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

/// CR232 — `_settle`'s 500ms budget isn't always enough for a route's own
/// pop/push transition (default `MaterialPageRoute` transition + Navigator
/// bookkeeping) to finish unmounting the old route's subtree, even though
/// the Navigator's own `canPop()` flips immediately. Measured: 500ms left
/// the popped route's `Text('PUSHED PAGE')` still in the tree; 1000ms does
/// not. Used only by the tests that assert on state *after* a pop, not a
/// blanket replacement for `_settle`.
Future<void> _settleAfterTransition(WidgetTester t) async {
  for (var i = 0; i < 20; i++) {
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

  // CR232 — persistent chrome across pushed pages. Saiful: "The bottom
  // menu, the ad, and the ticker tape should always be on every screen and
  // page." These five tests are the shell half of that ruling; the
  // structural Icons.close guard (`exit_affordance_structural_test.dart`)
  // is the other half.

  testWidgets(
      'CR232: a page pushed from inside a tab still shows the bottom nav '
      'and the ticker tape', (t) async {
    await _pumpHome(t);
    await _settle(t);

    // Push exactly the way every real call site does: `Navigator.of(context)`
    // from a widget living inside the active tab's pane (here, FloorScreen
    // itself — tab 0 is active by default). Post-CR232 that resolves to the
    // tab's own nested Navigator (`_TabNavigator`), not the root one, which
    // is the whole mechanism this CR relies on — see `home_shell.dart`'s
    // library comment.
    final floorContext = t.element(find.byType(FloorScreen));
    Navigator.of(floorContext).push(MaterialPageRoute<void>(
      builder: (_) => const Scaffold(
        backgroundColor: AmiColors.slate900,
        body: Center(child: Text('PUSHED PAGE')),
      ),
    ));
    await _settle(t);

    expect(find.text('PUSHED PAGE'), findsOneWidget,
        reason: 'the push must have landed — otherwise the rest of this '
            'test is vacuous');
    expect(find.byType(HexBottomNav), findsOneWidget,
        reason: 'CR232: the bottom nav must survive a page pushed from '
            "inside a tab — before this CR every push covered HomeShell's "
            'own Scaffold, which is what forced the Icons.close pattern');
    expect(find.byType(TickerTape), findsOneWidget,
        reason: 'CR232: the ticker tape is part of the same persistent '
            'chrome as the bottom nav');
  });

  testWidgets('CR232: re-tapping the active tab pops its stack to root',
      (t) async {
    await _pumpHome(t);
    await _settle(t);

    final floorContext = t.element(find.byType(FloorScreen));
    Navigator.of(floorContext).push(MaterialPageRoute<void>(
      builder: (_) => const Scaffold(
        backgroundColor: AmiColors.slate900,
        body: Center(child: Text('PUSHED PAGE')),
      ),
    ));
    await _settle(t);
    expect(find.text('PUSHED PAGE'), findsOneWidget);

    // Floor is tab 0 — already active. Tapping it again must pop the pushed
    // page back to Floor's own root, not switch tabs (there is nowhere else
    // to switch to; Floor is already showing).
    await t.tap(find.text('FLOOR'));
    await _settleAfterTransition(t);

    expect(find.text('PUSHED PAGE'), findsNothing,
        reason: 'CR232 rule 5: tapping the already-selected tab pops that '
            "tab's stack to its root");
    expect(find.byType(FloorScreen), findsOneWidget);
    expect(find.byType(HexBottomNav), findsOneWidget);
  });

  testWidgets('CR232: the software keyboard hides the persistent chrome',
      (t) async {
    await _pumpHome(t);
    await _settle(t);
    expect(find.byType(HexBottomNav), findsOneWidget);
    expect(find.byType(TickerTape), findsOneWidget);

    // Simulate the keyboard opening: a nonzero bottom `viewInsets`, exactly
    // what the OS reports while the software keyboard covers that much of
    // the screen. `home_shell.dart` reads this via
    // `MediaQuery.viewInsetsOf(context)`.
    t.view.viewInsets = const FakeViewPadding(bottom: 300);
    addTearDown(() => t.view.resetViewInsets());
    await _settle(t);

    expect(find.byType(HexBottomNav), findsNothing,
        reason: 'CR232 rule 2 exception (a): the keyboard hides the '
            'persistent chrome rather than fighting it for screen space');
    expect(find.byType(TickerTape), findsNothing);

    // And it comes back once the keyboard closes.
    t.view.resetViewInsets();
    await _settle(t);
    expect(find.byType(HexBottomNav), findsOneWidget);
    expect(find.byType(TickerTape), findsOneWidget);
  });

  // CR226 — the banner slot's place in the chrome order, and the keyboard
  // rule extended to it.

  testWidgets(
      'CR226: the ad slot sits between the bottom nav and the ticker tape',
      (t) async {
    await _pumpHome(t);
    await _settle(t);

    // ShellBannerSlot (which renders AnchoredAdBanner) must exist as a
    // sibling of HexBottomNav and TickerTape inside the SAME chrome Column
    // — CR226 §Scope 1's nav / ad slot / ticker tape order, not merely
    // "somewhere on screen".
    expect(find.byType(ShellBannerSlot), findsOneWidget,
        reason: 'CR232 reserved the slot; CR226 must still be filling it '
            'with AnchoredAdBanner, not leaving home_shell.dart pointed at '
            'a dangling reference');
    expect(find.byType(AnchoredAdBanner), findsOneWidget);

    final navY = t.getBottomLeft(find.byType(HexBottomNav)).dy;
    final slotY = t.getTopLeft(find.byType(ShellBannerSlot)).dy;
    final tapeY = t.getTopLeft(find.byType(TickerTape)).dy;
    expect(slotY, greaterThanOrEqualTo(navY),
        reason: 'CR226 §Scope 1: the ad slot is BELOW the nav');
    expect(tapeY, greaterThanOrEqualTo(slotY),
        reason: 'CR226 §Scope 1: the ticker tape is BELOW the ad slot — '
            'nav / ad slot / ticker tape, top to bottom');
  });

  testWidgets('CR226: the keyboard hides the ad slot along with the rest '
      'of the chrome', (t) async {
    await _pumpHome(t);
    await _settle(t);
    expect(find.byType(ShellBannerSlot), findsOneWidget);

    t.view.viewInsets = const FakeViewPadding(bottom: 300);
    addTearDown(() => t.view.resetViewInsets());
    await _settle(t);

    expect(find.byType(ShellBannerSlot), findsNothing,
        reason: 'CR226/CR232: the ad slot is part of the SAME persistent '
            'chrome Column as the nav and tape — it must disappear with '
            'them, not linger as a banner floating above the keyboard');

    t.view.resetViewInsets();
    await _settle(t);
    expect(find.byType(ShellBannerSlot), findsOneWidget);
  });

  testWidgets(
      'CR232: the trade ticket opens as a page with back + Cancel, no '
      'Icons.close', (t) async {
    await _pumpHome(t);
    await _settle(t);

    // Portfolio tab (index 1) carries a "NEW TRADE"-style CTA in production,
    // but the ticket is exercised directly here — same as the chrome-
    // persistence test above — because reaching it through Portfolio's own
    // UI is unrelated surface this test does not need to depend on.
    //
    // `verdictRef` is non-null so the "NO AI VERDICT" advisory (bug
    // d5717660) does not render — that card carries its OWN inline
    // `Icons.close` dismiss (CR232 rule 4's allowed exception, not the
    // page's exit), which would make the blanket `findsNothing` below fail
    // for a reason unrelated to what this test checks.
    final floorContext = t.element(find.byType(FloorScreen));
    TradeTicketSheet.show(floorContext, verdictRef: 'v1');
    await _settle(t);

    expect(find.byType(TradeTicketSheet), findsOneWidget,
        reason: 'the ticket must have opened — otherwise the rest of this '
            'test is vacuous');
    // CR232 rule 3/4 — a back chevron AND a text "Cancel", not a top-right X.
    expect(find.bySemanticsIdentifier(ExitIds.navBack), findsOneWidget,
        reason: 'CR232: the trade ticket is a pushed page, not a sheet — it '
            "carries AmiScreenHeader's back chevron");
    expect(find.bySemanticsIdentifier(ExitIds.tradeTicketCancel),
        findsOneWidget,
        reason: 'CR232 rule 3: the trade ticket carries a text "Cancel" '
            'action alongside the back chevron');
    expect(find.byIcon(Icons.close), findsNothing,
        reason: 'CR232: DEF415\'s close-button approach is superseded — the '
            'ticket must not carry a top-right Icons.close any more');
    // And the shell chrome underneath is still there.
    expect(find.byType(HexBottomNav), findsOneWidget);
    expect(find.byType(TickerTape), findsOneWidget);
  });

  // Saiful, from TestFlight build +108's screenshots: the sim trade ticket's
  // content rendered under the iOS status bar (clock/signal/battery
  // overlapping the TICKER field and BUY/SELL toggle). Root cause was
  // `Scaffold.appBar: PreferredSize(...)` — not covered by `SafeArea`, unlike
  // every other screen's `AmiScreenHeader`, which sits inside `body:
  // SafeArea(...)`. Fixed on both trade tickets; these two tests are the
  // regression net for the sim ticket (the games ticket shares the exact
  // same structure and fix — see games_trade_ticket_test.dart's own
  // coverage of the analogous screen).
  testWidgets(
      'CR232: the trade ticket header sits below the top safe-area inset',
      (t) async {
    // A generous inset — bigger than any real status bar (Dynamic Island
    // devices run ~59dp) — so the test fails loudly if the header is placed
    // with no regard for `padding.top` at all, not just marginally wrong.
    t.view.padding = const FakeViewPadding(top: 80);
    addTearDown(() => t.view.resetPadding());
    await _pumpHome(t);
    await _settle(t);

    final floorContext = t.element(find.byType(FloorScreen));
    TradeTicketSheet.show(floorContext, verdictRef: 'v1');
    await _settle(t);
    expect(find.byType(TradeTicketSheet), findsOneWidget);

    final headerTopLeft = t.getTopLeft(find.text('NEW TRADE').first);
    expect(headerTopLeft.dy, greaterThanOrEqualTo(80),
        reason: 'CR232: the header must render below MediaQuery.padding.top '
            "(80 here) — `Scaffold.appBar` is NOT SafeArea'd, which is "
            'exactly the defect Saiful caught on device: the header drew '
            'under the iOS status bar');
  });

  testWidgets(
      'CR232: tapping the trade ticket body dismisses the keyboard',
      (t) async {
    await _pumpHome(t);
    await _settle(t);

    final floorContext = t.element(find.byType(FloorScreen));
    TradeTicketSheet.show(floorContext, verdictRef: 'v1');
    await _settle(t);

    // Focus the QUANTITY field specifically (identified by its label —
    // several fields on this ticket share the same numeric keypad, so
    // matching on `keyboardType` alone is ambiguous). A numeric keypad on
    // iOS has no return key, so this is the field Saiful's screenshots
    // showed stuck open, covering the page. `showKeyboard` is flutter_test's
    // way of asserting focus without a real platform keyboard.
    await t.showKeyboard(find.byWidgetPredicate((w) =>
        w is TextField &&
        w.decoration?.labelText == 'QUANTITY'));
    expect(
        t.testTextInput.isVisible, isTrue,
        reason: 'the field must be focused — otherwise the rest of this '
            'test is vacuous');

    // Tap elsewhere on the page body (a point away from any field or
    // button — the ticket's own icon/heading area).
    await t.tapAt(const Offset(200, 20));
    await _settle(t);

    expect(t.testTextInput.isVisible, isFalse,
        reason: 'CR232: tapping the page body must dismiss the keyboard — '
            "an iOS numeric keypad has no return key, so without this "
            'affordance the keyboard has no way to close and covers the '
            "rest of the ticket (Saiful's +108 screenshots)");
  });
}
