/// CR015 (E4/D7 / C4) — HexToast.show inserts an overlay toast that displays
/// the message, then auto-dismisses (no pending timer / no leaked entry).
library;

import 'package:ami_trade/theme/ami_theme.dart';
import 'package:ami_trade/widgets/hex/hex_toast.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets('HexToast.show shows the message then auto-dismisses',
      (t) async {
    late BuildContext ctx;
    await t.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: Builder(builder: (c) {
            ctx = c;
            return const SizedBox.expand();
          }),
        ),
      ),
    );

    HexToast.show(
      ctx,
      'PROPOSAL SAVED',
      accent: AmiColors.hexGreen,
      icon: Icons.check_circle_outline,
      duration: const Duration(seconds: 2),
    );

    await t.pump(); // insert overlay
    await t.pump(const Duration(milliseconds: 300)); // slide-in
    expect(find.text('PROPOSAL SAVED'), findsOneWidget);
    expect(t.takeException(), isNull);

    // Advance past the hold + slide-out so the entry removes itself and no
    // timer stays pending at teardown.
    await t.pump(const Duration(seconds: 2));
    await t.pump(const Duration(milliseconds: 400));
    await t.pumpAndSettle();
    expect(find.text('PROPOSAL SAVED'), findsNothing);
  });
}
