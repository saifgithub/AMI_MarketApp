/// Post-onboarding home — the bottom nav (CR133 §2).
///
/// `FLOOR · PORTFOLIO · GAME · LESSONS · YOU`, or the same four without GAME
/// when the compile-time `AMI_GAMES` gate is off. Journal and Settings left the
/// bar in CR133 and live inside `YOU` as segments.
///
/// **Nothing here counts.** Every index is an index into [AmiTab.visible], and
/// the panes below are built by the same const-folded condition that filters
/// it, so the bar, the `IndexedStack` and the tab enum cannot drift apart —
/// asserted in `home_shell_test.dart` rather than maintained by hand. CR133 §3
/// measured what the alternative costs: three of the five old integer literals
/// kept working through the reorder, so a smoke test would have passed while
/// "Review in Journal" opened the game.
library;

import 'package:ami_trade/features/games/games_gate.dart';
import 'package:ami_trade/features/nav/ami_tab.dart';
import 'package:ami_trade/features/tour/nav_change_sheet.dart';
import 'package:ami_trade/features/tour/tour_providers.dart';
import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/qa/semantics_ids.dart';
import 'package:ami_trade/screens/floor/floor_screen.dart';
import 'package:ami_trade/screens/games/games_home_screen.dart';
import 'package:ami_trade/screens/lessons/lessons_screen.dart';
import 'package:ami_trade/screens/sim/portfolio_screen.dart';
import 'package:ami_trade/screens/you/you_screen.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:ami_trade/widgets/hex/hex_bottom_nav.dart';
import 'package:ami_trade/widgets/ticker_tape.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

class HomeShell extends ConsumerStatefulWidget {
  const HomeShell({super.key});

  @override
  ConsumerState<HomeShell> createState() => _HomeShellState();
}

class _HomeShellState extends ConsumerState<HomeShell> {
  AmiTab _tab = AmiTab.floor;

  /// One pane per entry of [AmiTab.visible], in the same order.
  ///
  /// The `if (kGamesEnabled)` is a **const** condition, so in a gated-off build
  /// the compiler removes the entry and nothing references `GamesHomeScreen` —
  /// the games screens tree-shake out, which is the store-binary guarantee
  /// CR109's dark launch rests on. A `switch` returning the screen would have
  /// been a live reference and would have quietly shipped the whole feature
  /// into every binary.
  static const _panes = <Widget>[
    FloorScreen(),
    PortfolioScreen(),
    if (kGamesEnabled) GamesHomeScreen(),
    LessonsScreen(),
    YouScreen(),
  ];

  @override
  void initState() {
    super.initState();
    // CR180 — tell the people who learned the OLD bar that it moved.
    //
    // Every section tour is gated on a `tour_*_seen` flag, so the walkthrough
    // system is silent for exactly the population whose mental model CR133
    // just invalidated: they already took every tour. `shouldShowNavChange`
    // returns false for a brand-new user, so this cannot land on top of the
    // Floor tour it would otherwise be competing with.
    WidgetsBinding.instance.addPostFrameCallback((_) async {
      final service = ref.read(tourServiceProvider);
      if (!await service.shouldShowNavChange()) return;
      await service.markNavChangeSeen();
      if (!mounted) return;
      await NavChangeSheet.show(context);
    });
  }

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final tabs = AmiTab.visible;
    // DEF190 — `activeTabProvider` used to be write-only from this shell's own
    // tap handler below; a screen buried inside a tab (Portfolio History's
    // "Review in Journal") had no way to actually switch tabs, so it pushed a
    // second, orphaned screen on top of the shell instead — which covers the
    // bottom nav, because the nav lives in THIS Scaffold, below the pushed
    // route. Listening here makes an external write to the provider do what the
    // tap handler already does: switch `_tab`. Guarded on `next != _tab` so the
    // tap handler's own write (which already set `_tab` directly, synchronously,
    // before this listener next fires) is a no-op here, not a second rebuild.
    ref.listen<AmiTab>(activeTabProvider, (prev, next) {
      // A tab this binary does not render cannot be shown. Nothing writes
      // `game` in a gated-off build, so this is a guard against a future caller
      // rather than a live path — and it drops the write rather than
      // substituting a different tab, because landing the user somewhere they
      // did not ask for is the failure this whole CR is about.
      if (!tabs.contains(next)) {
        assert(false, 'activeTabProvider was set to $next, which this build '
            'does not render (AMI_GAMES=$kGamesEnabled)');
        return;
      }
      if (next != _tab) setState(() => _tab = next);
    });
    return Scaffold(
      backgroundColor: AmiColors.slate900,
      body: IndexedStack(index: tabs.indexOf(_tab), children: _panes),
      bottomNavigationBar: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            decoration: const BoxDecoration(
              color: AmiColors.glassChrome,
              border: Border(top: BorderSide(color: AmiColors.slate700)),
            ),
            // Strip the bottom inset from MediaQuery so the nav doesn't absorb
            // it internally — TickerTape owns that space.
            child: MediaQuery.removePadding(
              context: context,
              removeBottom: true,
              child: HexBottomNav(
                currentIndex: tabs.indexOf(_tab),
                onTap: (i) {
                  // The bar hands back a position; `AmiTab.visible` is the one
                  // place that position becomes a tab, so the mapping cannot
                  // drift from the pane order above.
                  final tab = tabs[i];
                  setState(() => _tab = tab);
                  ref.read(activeTabProvider.notifier).state = tab;
                },
                items: [for (final tab in tabs) _itemFor(tab, l)],
              ),
            ),
          ),
          const TickerTape(),
        ],
      ),
    );
  }

  /// One arm per [AmiTab]. A `switch` on the enum with no `default`, so adding
  /// a destination is a compile error here rather than a tab that renders with
  /// someone else's icon.
  HexNavItem _itemFor(AmiTab tab, AppLocalizations l) {
    return switch (tab) {
      AmiTab.floor => HexNavItem(
          icon: Icons.grid_view_rounded,
          label: l.floorTabUpper,
          id: NavIds.floor),
      AmiTab.portfolio => HexNavItem(
          icon: Icons.account_balance_wallet_outlined,
          label: l.portfolioTabUpper,
          id: NavIds.portfolio),
      AmiTab.game => HexNavItem(
          icon: Icons.emoji_events_outlined,
          label: l.gameTabUpper,
          id: NavIds.game),
      AmiTab.lessons => HexNavItem(
          icon: Icons.school_outlined,
          label: l.lessonsTabUpper,
          id: NavIds.lessons),
      AmiTab.you => HexNavItem(
          icon: Icons.person_outline, label: l.youTabUpper, id: NavIds.you),
    };
  }
}
