/// Post-onboarding home — bottom nav with Floor / Portfolio / Journal /
/// Lessons / Settings. Five tabs is the alpha home; v1.0 can collapse some
/// behind a drawer if it gets crowded.
library;

import 'package:ami_trade/features/nav/ami_tab.dart';
import 'package:ami_trade/features/tour/tour_providers.dart';
import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/qa/semantics_ids.dart';
import 'package:ami_trade/screens/floor/floor_screen.dart';
import 'package:ami_trade/screens/journal/journal_screen.dart';
import 'package:ami_trade/screens/lessons/lessons_screen.dart';
import 'package:ami_trade/screens/settings/settings_screen.dart';
import 'package:ami_trade/screens/sim/portfolio_screen.dart';
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

  static const _tabs = <Widget>[
    FloorScreen(),
    PortfolioScreen(),
    JournalScreen(),
    LessonsScreen(),
    SettingsScreen(),
  ];

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    // DEF190 — `activeTabIndexProvider` used to be write-only from this
    // shell's own tap handler below; a screen buried inside a tab (Portfolio
    // History's "Review in Journal") had no way to actually switch tabs, so
    // it pushed a second, orphaned JournalScreen on top of the shell instead
    // — which covers the bottom nav, because the nav lives in THIS Scaffold,
    // below the pushed route. Listening here makes an external write to the
    // provider do what the tap handler already does: switch `_tab`. Guarded
    // on `next != _tab` so the tap handler's own write (which already set
    // `_tab` directly, synchronously, before this listener next fires) is a
    // no-op here, not a second rebuild.
    ref.listen<AmiTab>(activeTabProvider, (prev, next) {
      if (next != _tab) setState(() => _tab = next);
    });
    return Scaffold(
      backgroundColor: AmiColors.slate900,
      body: IndexedStack(index: _tab.index, children: _tabs),
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
                currentIndex: _tab.index,
                onTap: (i) {
                  // The bar hands back a position; AmiTab.values is the one
                  // place that position becomes a tab, so the mapping cannot
                  // drift from the child order below (asserted in the test).
                  final tab = AmiTab.values[i];
                  setState(() => _tab = tab);
                  ref.read(activeTabProvider.notifier).state = tab;
                },
                items: [
                  HexNavItem(
                      icon: Icons.grid_view_rounded,
                      label: l.floorTabUpper,
                      id: NavIds.floor),
                  HexNavItem(
                      icon: Icons.account_balance_wallet_outlined,
                      label: l.portfolioTabUpper,
                      id: NavIds.portfolio),
                  HexNavItem(
                      icon: Icons.menu_book_outlined,
                      label: l.journalTabUpper,
                      id: NavIds.journal),
                  HexNavItem(
                      icon: Icons.school_outlined,
                      label: l.lessonsTabUpper,
                      id: NavIds.lessons),
                  HexNavItem(
                      icon: Icons.settings_outlined,
                      label: l.settingsTabUpper,
                      id: NavIds.settings),
                ],
              ),
            ),
          ),
          const TickerTape(),
        ],
      ),
    );
  }
}
