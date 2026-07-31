/// DEF206 — `HexAvatar` renders a SOLID family fill with a white label.
///
/// This file used to pin the opposite (DEF142's canvas interior + a 4.0px
/// font floor that suppressed the label entirely below it). Saiful reverted
/// that treatment on sight of the shipped `0.1.0+62` build: the saturated hex
/// grid is the Floor's identity, the outline version read as washed out, and
/// the lock glyph collided with the low-contrast label.
///
/// The tests are inverted rather than deleted, deliberately — DEF142 was a
/// deliberate, argued change, so the thing that stops it being re-applied by
/// someone reading only its rationale is a red test, not a comment.
library;

import 'package:ami_trade/theme/ami_theme.dart';
import 'package:ami_trade/widgets/hex/hex_avatar.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

Future<void> _pump(WidgetTester t, Widget child) async {
  await t.pumpWidget(MaterialApp(home: Scaffold(body: Center(child: child))));
}

void main() {
  // Every distinct `size` actually passed at a real call site (the 20-site,
  // ten-size census), plus what it renders — `size * 0.16`.
  const census = {
    20: 3.2, // lesson_tile.dart:104
    28: 4.48, // room_screen.dart x3, lesson_reader_screen.dart:278
    32: 5.12, // league_screen.dart, room_transcript_rows.dart
    44: 7.04, // brief/brief-history/one-on-one
    48: 7.68, // agent_action_sheet.dart
    56: 8.96, // floor comb
    72: 11.52, // floor comb detail row
    96: 15.36, // default (unlock screen uses 160)
  };

  group('DEF206 — every census size keeps its label', () {
    for (final entry in census.entries) {
      final size = entry.key.toDouble();
      final expectedPx = entry.value;

      testWidgets('size $size renders its label at ${expectedPx}px', (t) async {
        await _pump(
          t,
          HexAvatar(label: 'FUND', color: AmiColors.hexCyan, size: size),
        );
        final finder = find.text('FUND');
        expect(finder, findsOneWidget,
            reason: 'DEF206 removed DEF142\'s font floor — no size suppresses '
                'the label any more, including the 20pt lesson_tile site');
        final text = t.widget<Text>(finder);
        expect(text.style!.fontSize, closeTo(expectedPx, 0.01));
      });
    }
  });

  group('DEF206 — solid family fill, white label', () {
    testWidgets('interior is the family colour and the label is white',
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
      expect(decoration.color, AmiColors.hexPurple,
          reason: 'the interior is a SOLID family fill — reverting to the '
              'canvas interior is the DEF142 regression this pins');
      expect(decoration.border!.top.color, AmiColors.hexPurple);

      final text = t.widget<Text>(find.text('FUND'));
      expect(text.style!.color, Colors.white,
          reason: 'white on the family fill, not the family colour on canvas');
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
