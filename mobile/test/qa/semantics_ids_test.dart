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

import 'package:ami_trade/features/nav/ami_tab.dart';
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
      icon: Icons.emoji_events_outlined, label: 'المسابقة', id: NavIds.game),
  HexNavItem(icon: Icons.school_outlined, label: 'الدروس', id: NavIds.lessons),
  HexNavItem(icon: Icons.person_outline, label: 'أنت', id: NavIds.you),
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

  testWidgets('a destination is announced once, not twice', (t) async {
    // DEF249: `Semantics(label: x, child: Text(x))` concatenates — iOS reported
    // label="FLOOR\nFLOOR", so VoiceOver said every tab twice and an exact-text
    // locator could never match. Invisible on Android, where the Text keeps its
    // own node, and invisible to a tap test. Only a label assertion catches it.
    final semantics = t.ensureSemantics();
    await _pump(t, const [
      HexNavItem(
          icon: Icons.grid_view_rounded, label: 'FLOOR', id: NavIds.floor),
    ]);

    final node = t.getSemantics(find.bySemanticsIdentifier(NavIds.floor));
    expect(node.label, 'FLOOR',
        reason: 'DEF249: a duplicated label means the Semantics wrapper is '
            'setting `label:` as well as wrapping a Text that already '
            'provides one');

    semantics.dispose();
  });

  test('NavIds.all covers every destination this build renders', () {
    // A new destination added to the class but forgotten in `all` would be
    // invisible to the harness's GO/NO-GO gate, which asserts against `all`.
    //
    // CR133 — the length is `AmiTab.visible`, not a literal: GAME is behind
    // the compile-time AMI_GAMES gate, and the harness runs against store
    // builds, so a hard 5 would demand it find a tab a `--no-games` binary
    // correctly does not have.
    expect(NavIds.all, hasLength(AmiTab.visible.length));
    expect(NavIds.all.toSet(), hasLength(AmiTab.visible.length),
        reason: 'identifiers must be unique');
    for (final id in NavIds.all) {
      expect(id, startsWith('ami.nav.'),
          reason: 'convention is ami.<area>.<thing> — qa/appium matches on it');
    }
  });
}
