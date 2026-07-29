/// DEF142 — `HexAvatar` legibility: canvas-interior treatment + font floor.
///
/// `room_board_test.dart` pins the contrast math (the comb already shares it,
/// non-vacuously); this file pins the two things that are `HexAvatar`-shaped
/// specifically — the census-derived font floor and the render-no-label
/// branch below it — by iterating every real call-site size rather than
/// asserting on one.
library;

import 'package:ami_trade/theme/ami_theme.dart';
import 'package:ami_trade/widgets/hex/hex_avatar.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

Future<void> _pump(WidgetTester t, Widget child) async {
  await t.pumpWidget(MaterialApp(home: Scaffold(body: Center(child: child))));
}

void main() {
  // Every distinct `size` actually passed at a real call site (DEF142's
  // 20-site, ten-size census), plus what it renders — `size * 0.16`.
  const census = {
    20: 3.2, // lesson_tile.dart:104 — below the floor
    28: 4.48, // room_screen.dart x3, lesson_reader_screen.dart:278
    32: 5.12, // league_screen.dart, room_transcript_rows.dart
    44: 7.04, // brief/brief-history/one-on-one
    48: 7.68, // agent_action_sheet.dart
    56: 8.96, // floor comb
    72: 11.52, // floor comb detail row
    96: 15.36, // default (unlock screen uses 160)
  };

  group('DEF142 — font-size floor, derived from the census', () {
    for (final entry in census.entries) {
      final size = entry.key.toDouble();
      final expectedPx = entry.value;

      testWidgets('size $size renders at ${expectedPx}px', (t) async {
        await _pump(
          t,
          HexAvatar(label: 'FUND', color: AmiColors.hexCyan, size: size),
        );
        final belowFloor = expectedPx < 4.0;
        final finder = find.text('FUND');
        if (belowFloor) {
          expect(finder, findsNothing,
              reason: 'a $expectedPx label is a smudge, not a label — '
                  'DEF142 A3 says render none');
        } else {
          expect(finder, findsOneWidget);
          final text = t.widget<Text>(finder);
          expect(text.style!.fontSize, closeTo(expectedPx, 0.01));
        }
      });
    }

    testWidgets('the census names a real site below the floor', (t) async {
      // lesson_tile.dart:104 — size 20, 3.2px. Pinned by name per acceptance
      // #4: "a test names a real site that hits this branch."
      await _pump(
        t,
        HexAvatar(label: 'FUND', color: AmiColors.hexCyan, size: 20),
      );
      expect(find.text('FUND'), findsNothing);
    });

    testWidgets('an empty label never renders a Text either', (t) async {
      await _pump(
        t,
        HexAvatar(label: '', color: AmiColors.hexCyan, size: 96),
      );
      expect(find.byType(Text), findsNothing);
    });
  });

  group('DEF142 — canvas-interior treatment', () {
    testWidgets('interior is the canvas, border and label are the family colour',
        (t) async {
      await _pump(
        t,
        HexAvatar(label: 'FUND', color: AmiColors.hexPurple, size: 96),
      );
      final container = t.widget<Container>(find.descendant(
        of: find.byType(HexAvatar),
        matching: find.byType(Container),
      ));
      final decoration = container.decoration! as BoxDecoration;
      expect(decoration.color, AmiColors.slate900,
          reason: 'the interior must be the canvas, never a solid family fill');
      expect(decoration.border!.top.color, AmiColors.hexPurple);

      final text = t.widget<Text>(find.text('FUND'));
      expect(text.style!.color, AmiColors.hexPurple);
    });

    testWidgets('locked state keeps its own muted treatment', (t) async {
      await _pump(
        t,
        HexAvatar(
          label: 'FUND',
          color: AmiColors.hexPurple,
          size: 96,
          status: HexAvatarStatus.locked,
        ),
      );
      final container = t.widget<Container>(find.descendant(
        of: find.byType(HexAvatar),
        matching: find.byType(Container),
      ));
      final decoration = container.decoration! as BoxDecoration;
      expect(decoration.color, AmiColors.slate800);
      expect(decoration.border!.top.color, AmiColors.slate600);

      final text = t.widget<Text>(find.text('FUND'));
      expect(text.style!.color, AmiColors.textLow);
    });
  });
}
