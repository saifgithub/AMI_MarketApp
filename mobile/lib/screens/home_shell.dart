/// Post-onboarding home — bottom nav with Floor / Portfolio / Journal /
/// Lessons / Settings. Five tabs is the alpha home; v1.0 can collapse some
/// behind a drawer if it gets crowded.
library;

import 'package:ami_trade/features/tour/tour_providers.dart';
import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/screens/floor/floor_placeholder_screen.dart';
import 'package:ami_trade/screens/journal/journal_screen.dart';
import 'package:ami_trade/screens/lessons/lessons_screen.dart';
import 'package:ami_trade/screens/settings/settings_screen.dart';
import 'package:ami_trade/screens/sim/portfolio_screen.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:ami_trade/widgets/ticker_tape.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

class HomeShell extends ConsumerStatefulWidget {
  const HomeShell({super.key});

  @override
  ConsumerState<HomeShell> createState() => _HomeShellState();
}

class _HomeShellState extends ConsumerState<HomeShell> {
  int _tab = 0;

  static const _tabs = <Widget>[
    FloorPlaceholderScreen(),
    PortfolioScreen(),
    JournalScreen(),
    LessonsScreen(),
    SettingsScreen(),
  ];

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    return Scaffold(
      backgroundColor: AmiColors.slate900,
      body: IndexedStack(index: _tab, children: _tabs),
      bottomNavigationBar: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            decoration: const BoxDecoration(
              color: AmiColors.glassChrome,
              border: Border(top: BorderSide(color: AmiColors.slate700)),
            ),
            // Strip the bottom inset from MediaQuery so BottomNavigationBar
            // doesn't absorb it internally — TickerTape owns that space.
            child: MediaQuery.removePadding(
              context: context,
              removeBottom: true,
              child: BottomNavigationBar(
                currentIndex: _tab,
                onTap: (i) {
                  setState(() => _tab = i);
                  ref.read(activeTabIndexProvider.notifier).state = i;
                },
                backgroundColor: Colors.transparent,
                elevation: 0,
                type: BottomNavigationBarType.fixed,
                selectedItemColor: AmiColors.hexBlue,
                unselectedItemColor: AmiColors.textLow,
                selectedLabelStyle:
                    AmiTypography.labelMono.copyWith(fontSize: 9),
                unselectedLabelStyle:
                    AmiTypography.labelMono.copyWith(fontSize: 9),
                items: [
                  BottomNavigationBarItem(
                    icon: const Icon(Icons.grid_view_rounded),
                    label: l.floorTabUpper,
                  ),
                  BottomNavigationBarItem(
                    icon: const Icon(Icons.account_balance_wallet_outlined),
                    label: l.portfolioTabUpper,
                  ),
                  BottomNavigationBarItem(
                    icon: const Icon(Icons.menu_book_outlined),
                    label: l.journalTabUpper,
                  ),
                  BottomNavigationBarItem(
                    icon: const Icon(Icons.school_outlined),
                    label: l.lessonsTabUpper,
                  ),
                  BottomNavigationBarItem(
                    icon: const Icon(Icons.settings_outlined),
                    label: l.settingsTabUpper,
                  ),
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
