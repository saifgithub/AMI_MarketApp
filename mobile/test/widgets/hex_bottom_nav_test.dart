/// CR016 (E4/D8 / C2) — HexBottomNav renders all destinations and routes taps
/// to the right index (Material semantics preserved through the visual swap).
library;

import 'package:ami_trade/qa/semantics_ids.dart';
import 'package:ami_trade/widgets/hex/hex_bottom_nav.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

const _items = <HexNavItem>[
  HexNavItem(
      icon: Icons.grid_view_rounded, label: 'FLOOR', id: NavIds.floor),
  HexNavItem(
      icon: Icons.account_balance_wallet_outlined,
      label: 'PORTFOLIO',
      id: NavIds.portfolio),
  HexNavItem(
      icon: Icons.emoji_events_outlined, label: 'GAME', id: NavIds.game),
  HexNavItem(
      icon: Icons.school_outlined, label: 'LESSONS', id: NavIds.lessons),
  HexNavItem(
      icon: Icons.person_outline, label: 'YOU', id: NavIds.you),
];

Future<void> _pump(WidgetTester t, int index, void Function(int) onTap) {
  return t.pumpWidget(MaterialApp(
    home: Scaffold(
      bottomNavigationBar:
          HexBottomNav(currentIndex: index, onTap: onTap, items: _items),
    ),
  ));
}

void main() {
  testWidgets('renders all five destinations', (t) async {
    await _pump(t, 0, (_) {});
    for (final it in _items) {
      expect(find.text(it.label), findsOneWidget);
    }
    expect(t.takeException(), isNull);
  });

  testWidgets('tapping a destination routes its index', (t) async {
    int? tapped;
    await _pump(t, 0, (i) => tapped = i);
    await t.tap(find.text('GAME'));
    expect(tapped, 2);
    await t.tap(find.text('YOU'));
    expect(tapped, 4);
  });
}
