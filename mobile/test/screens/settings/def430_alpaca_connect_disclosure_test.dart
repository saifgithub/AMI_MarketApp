/// DEF430 (Saiful, 2026-09-25: "publish + link-screen notice") — a plain
/// disclosure must render on the Alpaca connect screen, above BOTH tabs,
/// BEFORE the user links anything, so consent happens at the point of
/// collection rather than only in the Privacy Policy.
///
/// Two things pinned here:
///   1. The disclosure text renders on first paint (no interaction needed)
///      and survives switching between the API KEY and OAUTH tabs — it is
///      shared chrome above the `TabBarView`, not per-tab copy that could
///      drift or go missing on one tab.
///   2. It does not overflow at a small phone width (320dp, DEF435's own
///      floor) or at 1.3x text scale — same size/scale convention
///      `settings_overflow_test.dart` uses for this class of regression.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/screens/settings/alpaca_connect_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

Future<void> _pump(
  WidgetTester tester, {
  Size size = const Size(390, 844),
  double textScale = 1.0,
}) async {
  tester.view.physicalSize = size;
  tester.view.devicePixelRatio = 1.0;
  addTearDown(tester.view.reset);

  await tester.pumpWidget(
    ProviderScope(
      child: MediaQuery(
        data: MediaQueryData(
          size: size,
          textScaler: TextScaler.linear(textScale),
        ),
        child: const MaterialApp(
          localizationsDelegates: AppLocalizations.localizationsDelegates,
          supportedLocales: AppLocalizations.supportedLocales,
          home: AlpacaConnectScreen(),
        ),
      ),
    ),
  );
  for (var i = 0; i < 6; i++) {
    await tester.pump(const Duration(milliseconds: 50));
  }
}

void main() {
  group('DEF430 — Alpaca link-screen disclosure', () {
    testWidgets('renders before linking, on the API KEY tab (the default)',
        (tester) async {
      await _pump(tester);

      expect(
        find.textContaining('Your Alpaca keys stay on this phone'),
        findsOneWidget,
      );
      expect(find.textContaining('AMI sends your account summary'),
          findsOneWidget);
      expect(
        find.textContaining('A live account is shown on this phone only'),
        findsOneWidget,
      );
      expect(tester.takeException(), isNull);
    });

    testWidgets('survives switching to the OAUTH tab', (tester) async {
      await _pump(tester);

      await tester.tap(find.text('OAUTH'));
      await tester.pump(const Duration(milliseconds: 200));

      expect(
        find.textContaining('Your Alpaca keys stay on this phone'),
        findsOneWidget,
        reason: 'the disclosure is shared chrome above the TabBarView, not '
            'per-tab copy',
      );
      expect(tester.takeException(), isNull);
    });

    testWidgets('no overflow at 320dp width, default text scale',
        (tester) async {
      await _pump(tester, size: const Size(320, 690));
      expect(tester.takeException(), isNull);
    });

    testWidgets('no overflow at 320dp width and 1.3x text scale',
        (tester) async {
      await _pump(tester, size: const Size(320, 690), textScale: 1.3);
      expect(tester.takeException(), isNull);
      expect(
        find.textContaining('Your Alpaca keys stay on this phone'),
        findsOneWidget,
      );
    });

    testWidgets('no overflow at 1.3x text scale on a baseline phone width',
        (tester) async {
      await _pump(tester, size: const Size(375, 812), textScale: 1.3);
      expect(tester.takeException(), isNull);
    });
  });
}
