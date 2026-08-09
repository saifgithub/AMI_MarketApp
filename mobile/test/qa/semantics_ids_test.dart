/// CR162 — guards the automation contract in `lib/qa/semantics_ids.dart`.
///
/// The black-box UAT harness (`qa/appium/`) navigates by
/// `Semantics(identifier:)`, which Flutter maps to `resource-id` on Android and
/// `accessibilityIdentifier` on iOS. Nothing in the app *renders* an
/// identifier, so dropping one during a refactor is invisible locally — it
/// surfaces days later as a confusing red device run on melehost, of exactly
/// the shape CR080 already burned two sessions on.
///
/// This test is the loud, local failure that prevents that: it asserts the
/// identifiers reach the real semantics tree, that the set is complete, and
/// that they are locale-independent (an identifier that changed with the
/// rendered label would re-couple navigation to translation, which is the
/// coupling CR162 exists to remove).
library;

import 'package:ami_trade/qa/semantics_ids.dart';
import 'package:ami_trade/widgets/hex/hex_bottom_nav.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

/// Deliberately *not* the English labels — the point of an identifier is that
/// it survives translation, so the fixture renders labels the harness has
/// never seen.
const _arabicishItems = <HexNavItem>[
  HexNavItem(icon: Icons.grid_view_rounded, label: 'القاعة', id: NavIds.floor),
  HexNavItem(
      icon: Icons.account_balance_wallet_outlined,
      label: 'المحفظة',
      id: NavIds.portfolio),
  HexNavItem(
      icon: Icons.menu_book_outlined, label: 'السجل', id: NavIds.journal),
  HexNavItem(icon: Icons.school_outlined, label: 'الدروس', id: NavIds.lessons),
  HexNavItem(
      icon: Icons.settings_outlined, label: 'الإعدادات', id: NavIds.settings),
];

Future<void> _pump(WidgetTester t, List<HexNavItem> items) {
  return t.pumpWidget(MaterialApp(
    home: Scaffold(
      bottomNavigationBar:
          HexBottomNav(currentIndex: 0, onTap: (_) {}, items: items),
    ),
  ));
}

void main() {
  testWidgets('every bottom-nav destination is addressable by identifier',
      (t) async {
    final semantics = t.ensureSemantics();
    await _pump(t, _arabicishItems);

    for (final id in NavIds.all) {
      expect(find.bySemanticsIdentifier(id), findsOneWidget,
          reason: 'CR162: $id is missing from the semantics tree. The UAT '
              'harness navigates by this identifier on both platforms — '
              'restore it in hex_bottom_nav.dart / home_shell.dart rather '
              'than teaching the harness to tap by text again.');
    }

    semantics.dispose();
  });

  testWidgets('identifiers are locale-independent', (t) async {
    final semantics = t.ensureSemantics();

    // Same IDs, completely different rendered labels.
    await _pump(t, _arabicishItems);
    expect(find.bySemanticsIdentifier(NavIds.floor), findsOneWidget);
    expect(find.text('القاعة'), findsOneWidget);

    await _pump(t, const [
      HexNavItem(
          icon: Icons.grid_view_rounded, label: 'FLOOR', id: NavIds.floor),
    ]);
    expect(find.bySemanticsIdentifier(NavIds.floor), findsOneWidget,
        reason: 'the identifier must not track the rendered label — that is '
            'the translation coupling CR162 removes');
    expect(find.text('FLOOR'), findsOneWidget);

    semantics.dispose();
  });

  test('NavIds.all covers every declared destination', () {
    // A new destination added to the class but forgotten in `all` would be
    // invisible to the harness's GO/NO-GO gate, which asserts against `all`.
    expect(NavIds.all, hasLength(5));
    expect(NavIds.all.toSet(), hasLength(5), reason: 'identifiers must be unique');
    for (final id in NavIds.all) {
      expect(id, startsWith('ami.nav.'),
          reason: 'convention is ami.<area>.<thing> — qa/appium matches on it');
    }
  });
}
