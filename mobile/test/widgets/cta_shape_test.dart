/// CR113 — large CTAs stop being hex-cut, and the boundary of that change is
/// the thing worth guarding.
///
/// Saiful, on the account-claim CTA: *"the larger buttons should all be normal
/// rounded edge buttons. there are several of these so let's fix them all."*
/// "All of them" turned out to be **one widget**: `HexButton` applied its clip
/// unconditionally, with no size variant, so all six user-facing call sites
/// changed together.
///
/// The CR judged a guard "likely not worth it — this is a judgement about size,
/// not a mechanical invariant." Half of that is right. *Which* buttons count as
/// large is a judgement no test can hold. But **the boundary is mechanical**,
/// and the boundary is the part that breaks: CR113 explicitly rejected three
/// wider sweeps because hex geometry also lives in the chips, the avatars, the
/// honeycomb and the segmented toggles, and taking those too *"would delete the
/// app's identity."* A future tidy-up reading only "AMI moved off hex clipping"
/// is exactly the plausible next edit. So this file pins both directions: the
/// CTA has no clip, and the marks still do.
library;

import 'package:ami_trade/theme/ami_theme.dart';
import 'package:ami_trade/widgets/hex/hex_avatar.dart';
import 'package:ami_trade/widgets/hex/hex_button.dart';
import 'package:ami_trade/widgets/hex/hex_chip.dart';
import 'package:ami_trade/widgets/hex/track_hex_button.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

Widget _host(Widget child) => MaterialApp(
      home: Scaffold(body: Center(child: child)),
    );

/// The `BoxDecoration` of the button's own animated container.
BoxDecoration _buttonDecoration(WidgetTester tester) {
  final container = tester.widget<AnimatedContainer>(
    find.descendant(
      of: find.byType(HexButton),
      matching: find.byType(AnimatedContainer),
    ),
  );
  return container.decoration! as BoxDecoration;
}

void main() {
  group('CR113 — the large CTA is a rounded rect', () {
    testWidgets('HexButton renders no ClipPath at all', (tester) async {
      await tester.pumpWidget(
        _host(HexButton(label: 'SAVE MY TEAM', onPressed: () {})),
      );

      expect(
        find.descendant(
          of: find.byType(HexButton),
          matching: find.byType(ClipPath),
        ),
        findsNothing,
        reason: 'a full-width CTA with all four corners cut reads as a chevron '
            'banner, not a hexagonal mark — that is the report',
      );
    });

    testWidgets('…and carries the app surface radius instead', (tester) async {
      await tester.pumpWidget(
        _host(HexButton(label: 'CONVENE', onPressed: () {})),
      );

      expect(
        _buttonDecoration(tester).borderRadius,
        BorderRadius.circular(AmiRadii.card),
        reason: 'AmiRadii.card is what every content surface already uses; a '
            'large CTA is a surface wearing a control\'s clothes',
      );
    });

    testWidgets('a disabled button is still rounded', (tester) async {
      // The enabled/disabled branch picks colours, and an early version of this
      // widget picked its *shape* on a variant too. Prove shape is unconditional
      // now — that unconditionality is the whole reason "fix them all" was one
      // edit rather than six.
      await tester.pumpWidget(
        _host(const HexButton(label: 'SUBMIT', onPressed: null)),
      );
      expect(
        _buttonDecoration(tester).borderRadius,
        BorderRadius.circular(AmiRadii.card),
      );
      expect(
        find.descendant(
          of: find.byType(HexButton),
          matching: find.byType(ClipPath),
        ),
        findsNothing,
      );
    });

    testWidgets('the glow halo matches the button radius, not a square',
        (tester) async {
      // The halo sits on a container BEHIND the button. It used to be cropped
      // by the ClipPath; with the clip gone it is cropped by nothing, so if it
      // does not carry the same radius the result is a square shadow behind a
      // rounded button — visible only on the glow variant, and only as a
      // slightly wrong silhouette, which is how it would survive review.
      await tester.pumpWidget(
        _host(HexButton(
          label: 'CONVENE THE ROOM',
          onPressed: () {},
          variant: HexButtonVariant.glow,
        )),
      );

      final halo = tester
          .widgetList<DecoratedBox>(find.descendant(
            of: find.byType(HexButton),
            matching: find.byType(DecoratedBox),
          ))
          .map((d) => d.decoration as BoxDecoration)
          .firstWhere((d) => (d.boxShadow?.isNotEmpty ?? false));

      expect(halo.borderRadius, _buttonDecoration(tester).borderRadius,
          reason: 'halo and button must share a silhouette');
    });
  });

  group('CR113 — the boundary: marks and controls KEEP their geometry', () {
    // Each of these was named in the CR as deliberately out of scope. Three
    // shapes are represented: the octagon (chip), the regular hexagon (avatar,
    // track button). If a later sweep generalises "AMI moved off hex clipping",
    // it trips here.

    testWidgets('HexChip still clips', (tester) async {
      await tester.pumpWidget(_host(const HexChip(label: 'BULLISH')));
      expect(
        find.descendant(
          of: find.byType(HexChip),
          matching: find.byType(ClipPath),
        ),
        findsWidgets,
        reason: 'a chip is a mark, not a surface — CR113 kept it on purpose',
      );
    });

    testWidgets('HexAvatar still clips', (tester) async {
      await tester.pumpWidget(_host(const HexAvatar(
        label: 'BULL',
        color: AmiColors.hexBlue,
      )));
      expect(
        find.descendant(
          of: find.byType(HexAvatar),
          matching: find.byType(ClipPath),
        ),
        findsWidgets,
        reason: 'the 12 agent avatars ARE the honeycomb — this is the identity '
            'the CR refused to sweep',
      );
    });

    testWidgets('TrackHexButton still clips', (tester) async {
      await tester.pumpWidget(_host(TrackHexButton(
        label: 'ISLAMIC FINANCE',
        color: AmiColors.hexBlue,
        completed: 3,
        total: 8,
        onTap: () {},
      )));
      expect(
        find.descendant(
          of: find.byType(TrackHexButton),
          matching: find.byType(ClipPath),
        ),
        findsWidgets,
        reason: 'CR108 edits this widget for an opposite reason — the two must '
            'not be conflated in one pass',
      );
    });
  });
}
