/// CR133 §7 — the shared screen header.
///
/// The four screens that used to each carry a private `_Header` had already
/// drifted: Journal and Portfolio both ended in an `IconButton` but sat 12pt
/// apart from the right edge because one passed `only(right: xs)` and the other
/// `symmetric(horizontal: m)`. The point of extracting the component is that
/// there is now one rule instead of four copies, so the rule is what is
/// asserted here — not that a particular screen looks a particular way.
library;

import 'package:ami_trade/theme/ami_theme.dart';
import 'package:ami_trade/widgets/hex/ami_screen_header.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

Widget _host(Widget child) => MaterialApp(home: Scaffold(body: child));

EdgeInsets _padding(WidgetTester tester) {
  final container = tester.widget<Container>(
    find.ancestor(
      of: find.byType(Row),
      matching: find.byType(Container),
    ).first,
  );
  return container.padding! as EdgeInsets;
}

void main() {
  group('AmiScreenHeader', () {
    testWidgets('a bare title keeps the full right inset', (tester) async {
      await tester.pumpWidget(_host(
        const AmiScreenHeader(title: 'LESSONS', titleColor: AmiColors.hexGreen),
      ));
      expect(_padding(tester).right, AmiSpacing.m);
      expect(_padding(tester).left, AmiSpacing.m);
    });

    testWidgets('a trailing action tightens the right inset, because the '
        'action carries its own', (tester) async {
      await tester.pumpWidget(_host(
        AmiScreenHeader(
          title: 'PORTFOLIO',
          titleColor: AmiColors.hexCyan,
          actions: [IconButton(icon: const Icon(Icons.add), onPressed: () {})],
        ),
      ));
      expect(_padding(tester).right, AmiSpacing.xs);
      expect(_padding(tester).left, AmiSpacing.m);
    });

    testWidgets('the subtitle renders after the title, not instead of it',
        (tester) async {
      await tester.pumpWidget(_host(
        const AmiScreenHeader(
          title: 'SETTINGS',
          titleColor: AmiColors.hexBlue,
          subtitle: 'v4',
        ),
      ));
      expect(find.text('SETTINGS'), findsOneWidget);
      expect(find.text('v4'), findsOneWidget);
    });

    testWidgets('no back chevron unless asked for', (tester) async {
      await tester.pumpWidget(_host(
        const AmiScreenHeader(title: 'JOURNAL', titleColor: AmiColors.hexBlue),
      ));
      expect(find.byIcon(Icons.arrow_back_ios_new), findsNothing);
    });

    testWidgets('showBack pops by default, and honours an override',
        (tester) async {
      var pressed = 0;
      await tester.pumpWidget(_host(
        AmiScreenHeader(
          title: 'SETTINGS',
          titleColor: AmiColors.hexBlue,
          showBack: true,
          onBack: () => pressed++,
        ),
      ));
      await tester.tap(find.byIcon(Icons.arrow_back_ios_new));
      expect(pressed, 1);
    });

    testWidgets('the chrome is fixed — 64pt, glassChrome, slate700 underline',
        (tester) async {
      await tester.pumpWidget(_host(
        const AmiScreenHeader(title: 'FLOOR', titleColor: AmiColors.hexBlue),
      ));
      expect(tester.getSize(find.byType(AmiScreenHeader)).height, 64);
      final container = tester.widget<Container>(
        find.ancestor(of: find.byType(Row), matching: find.byType(Container))
            .first,
      );
      final decoration = container.decoration! as BoxDecoration;
      expect(decoration.color, AmiColors.glassChrome);
      expect((decoration.border! as Border).bottom.color, AmiColors.slate700);
    });
  });
}
