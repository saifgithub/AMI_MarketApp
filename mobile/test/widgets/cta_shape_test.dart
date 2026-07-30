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
import 'package:ami_trade/theme/hex_clipper.dart';
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

    // DEF167(a) — CR113's "all three shapes covered" claim was false: the
    // octagon (chip) and the regular hexagon (avatar, track button) were
    // both represented above, but `FlatTopHexagonBarClipper` — the shape
    // whose entire reason to exist is arbitrary aspect ratio (the
    // BOARD|TRANSCRIPT toggle, the Portfolio journal-pointer bar) — had no
    // case at all. A square-ish size would prove nothing about that; this
    // uses a 300x44 bar (ratio ~6.8:1), nowhere near the regular hexagon's
    // fixed 2:√3 (~1.1547:1).
    testWidgets(
        'FlatTopHexagonBarClipper is a true hexagon at a wide, non-2:√3 '
        'aspect ratio', (tester) async {
      const size = Size(300, 44);
      const endInset = 10.0;
      final path = const FlatTopHexagonBarClipper(endInset: endInset)
          .getClip(size);

      // The defining difference from the octagon: the octagon chamfers each
      // corner with its OWN diagonal, leaving a vertical edge down the
      // right/left sides between the two corner cuts. The hex-bar's two
      // corner diagonals on each end converge to a single point at the
      // vertical middle — there is no vertical edge at all. So just inside
      // the right edge, near the top or bottom, must be OUTSIDE the hex-bar
      // even though the equivalent point is inside an octagon of the same
      // envelope and corner size.
      expect(
        path.contains(Offset(size.width - 0.1, 15)),
        isFalse,
        reason: 'no vertical right edge — the ends taper to a point, unlike '
            'the octagon',
      );
      expect(
        path.contains(Offset(size.width - 0.1, 29)),
        isFalse,
        reason: 'symmetric check below the vertical middle',
      );
      // The point itself — dead centre of the right end — IS the vertex.
      expect(
        path.contains(Offset(size.width - 0.05, size.height / 2)),
        isTrue,
        reason: 'the tip of the point sits at the vertical middle',
      );
      // Flat top/bottom (not angled, unlike the octagon's chamfered top
      // corners): just inside the inset, at y=0, is on the boundary of the
      // filled region — a point one pixel further in, at (endInset + 1, 1),
      // must be INSIDE, proving the top edge is flat between the insets.
      expect(
        path.contains(const Offset(endInset + 1, 1)),
        isTrue,
        reason: 'flat top edge between the two end insets',
      );

      final octagon =
          const CutCornerOctagonClipper(cornerCut: endInset).getClip(size);
      expect(
        octagon.contains(Offset(size.width - 0.1, 15)),
        isTrue,
        reason: 'the octagon DOES keep a vertical right edge at the same '
            'envelope — this is the mechanical difference DEF167(a) proves',
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
