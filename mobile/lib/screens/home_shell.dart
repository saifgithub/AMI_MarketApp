/// Post-onboarding home — bottom nav with Floor / Journal / Lessons.
library;

import 'package:ami_trade/screens/floor/floor_placeholder_screen.dart';
import 'package:ami_trade/screens/journal/journal_screen.dart';
import 'package:ami_trade/screens/lessons/lessons_screen.dart';
import 'package:ami_trade/theme/ami_theme.dart';
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
    JournalScreen(),
    LessonsScreen(),
  ];

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AmiColors.slate900,
      body: IndexedStack(index: _tab, children: _tabs),
      bottomNavigationBar: Container(
        decoration: const BoxDecoration(
          color: AmiColors.glassChrome,
          border: Border(top: BorderSide(color: AmiColors.slate700)),
        ),
        child: SafeArea(
          top: false,
          child: BottomNavigationBar(
            currentIndex: _tab,
            onTap: (i) => setState(() => _tab = i),
            backgroundColor: Colors.transparent,
            elevation: 0,
            type: BottomNavigationBarType.fixed,
            selectedItemColor: AmiColors.hexBlue,
            unselectedItemColor: AmiColors.textLow,
            selectedLabelStyle: AmiTypography.labelMono.copyWith(fontSize: 10),
            unselectedLabelStyle: AmiTypography.labelMono.copyWith(fontSize: 10),
            items: const [
              BottomNavigationBarItem(
                icon: Icon(Icons.grid_view_rounded),
                label: 'FLOOR',
              ),
              BottomNavigationBarItem(
                icon: Icon(Icons.menu_book_outlined),
                label: 'JOURNAL',
              ),
              BottomNavigationBarItem(
                icon: Icon(Icons.school_outlined),
                label: 'LESSONS',
              ),
            ],
          ),
        ),
      ),
    );
  }
}
