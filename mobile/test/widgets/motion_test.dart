/// CR014 (E3/D2+D3) — the motion widgets build and animate without throwing:
/// HexPulseLoader, HexAvatar signal/attention pulse, HexChip pulse-dot, and the
/// repaired HexButton.glow variant. Repeating animations never settle, so we
/// advance with `pump(Duration)` (never `pumpAndSettle`).
library;

import 'package:ami_trade/theme/ami_theme.dart';
import 'package:ami_trade/widgets/hex/hex_avatar.dart';
import 'package:ami_trade/widgets/hex/hex_button.dart';
import 'package:ami_trade/widgets/hex/hex_chip.dart';
import 'package:ami_trade/widgets/hex/hex_pulse_loader.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

Future<void> _host(WidgetTester t, Widget child) async {
  await t.pumpWidget(
    MaterialApp(home: Scaffold(body: Center(child: child))),
  );
  await t.pump(const Duration(milliseconds: 600));
  await t.pump(const Duration(milliseconds: 600));
}

void main() {
  testWidgets('HexPulseLoader breathes without throwing', (t) async {
    await _host(t, const HexPulseLoader());
    expect(t.takeException(), isNull);
    expect(find.byType(HexPulseLoader), findsOneWidget);
  });

  testWidgets('HexAvatar signal pulse builds without throwing', (t) async {
    await _host(t, const HexAvatar(
      label: 'FA',
      color: AmiColors.hexCyan,
      status: HexAvatarStatus.signal,
    ));
    expect(t.takeException(), isNull);
    expect(find.text('FA'), findsOneWidget);
  });

  testWidgets('HexAvatar attention pulse shows the badge', (t) async {
    await _host(t, const HexAvatar(
      label: 'PM',
      color: AmiColors.hexPurple,
      status: HexAvatarStatus.attention,
    ));
    expect(t.takeException(), isNull);
    expect(find.text('!'), findsOneWidget);
  });

  testWidgets('HexAvatar can switch status without leaking a controller',
      (t) async {
    await t.pumpWidget(const MaterialApp(
      home: Scaffold(
        body: Center(
          child: HexAvatar(
            label: 'X',
            color: AmiColors.hexGreen,
            status: HexAvatarStatus.idle,
          ),
        ),
      ),
    ));
    await t.pump();
    await t.pumpWidget(const MaterialApp(
      home: Scaffold(
        body: Center(
          child: HexAvatar(
            label: 'X',
            color: AmiColors.hexGreen,
            status: HexAvatarStatus.signal,
          ),
        ),
      ),
    ));
    await t.pump(const Duration(milliseconds: 300));
    expect(t.takeException(), isNull);
  });

  testWidgets('HexChip pulse-dot builds without throwing', (t) async {
    await _host(t, const HexChip(
      label: 'LIVE',
      color: AmiColors.hexGreen,
      variant: HexChipVariant.tinted,
      showDot: true,
    ));
    expect(t.takeException(), isNull);
    expect(find.text('LIVE'), findsOneWidget);
  });

  testWidgets('HexButton.glow renders a shadow halo when enabled', (t) async {
    await _host(t, HexButton(
      label: 'CONVENE',
      variant: HexButtonVariant.glow,
      onPressed: () {},
    ));
    expect(t.takeException(), isNull);
    expect(find.text('CONVENE'), findsOneWidget);
    // The glow halo is a DecoratedBox carrying a boxShadow behind the clip.
    final hasGlow = _hasBoxShadow(t);
    expect(hasGlow, isTrue);
  });
}

/// True if any DecoratedBox in the tree carries a non-empty boxShadow.
bool _hasBoxShadow(WidgetTester t) {
  final boxes = t.widgetList<DecoratedBox>(find.byType(DecoratedBox));
  for (final b in boxes) {
    final d = b.decoration;
    if (d is BoxDecoration && (d.boxShadow?.isNotEmpty ?? false)) return true;
  }
  return false;
}
