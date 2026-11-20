/// DEF508 — the "Following your risk profile — {value}" chip in Settings >
/// Mandate > Risk limits lost its value on a real phone (AMI-DL-5, Android,
/// 360 dp, build 119) although DEF502 had already set maxLines: 2.
///
/// Root cause: Flutter's `_RenderChip` measures the label's height with a dry
/// layout at the chip's FULL max width, then lays the label out narrower (minus
/// the check mark, label padding and chip padding) with that one-line height as
/// `maxHeight`. A label that fits on one line at full width but wraps at the
/// real width gets clamped to one line's height, so the second line (the
/// value) is cut. These tests drive the chip across a range of widths and
/// text scales, so they bite on the mechanism, not on one font's metrics
/// (the test env has no IBM Plex Mono; the device does).
library;

import 'dart:ui' show Tristate;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/mandate.dart';
import 'package:ami_trade/screens/settings/risk_limits_section.dart';
import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter_test/flutter_test.dart';

UserMandate _mandate() => const UserMandate(
      userId: 'u1',
      version: 1,
      displayName: 'Trader',
      locale: 'en',
      timezone: 'UTC',
      primaryGoal: 'long_term_wealth',
      horizon: 'long',
      path: 'long_horizon',
      riskScore: 3,
      riskComponents: RiskComponents(
        drawdownResponse: 3,
        regretAsymmetry: 0,
        concentrationTolerance: 3,
      ),
      maxDrawdownPct: 30,
      resolved: ResolvedCaps(
        sectorCapPct: 40.0,
        singleNameCapPct: 3.0,
        maxOpenPositions: 35,
        postLossCooldownHours: 1.0,
        maxTradesPerDay: 4,
        maxTradesPerWeek: 12,
        maxOpenRiskPct: 10.5,
      ),
      learningStyle: 'quick',
      compliance: ComplianceFlags(),
      plan: 'trial_trader',
      creditBalance: 75,
    );

Future<void> _pump(
  WidgetTester tester, {
  required double dpWidth,
  required double dpr,
  required double textScale,
  Locale locale = const Locale('en'),
}) async {
  tester.view.physicalSize = Size(dpWidth * dpr, 4000 * dpr);
  tester.view.devicePixelRatio = dpr;
  addTearDown(tester.view.reset);
  await tester.pumpWidget(
    MaterialApp(
      locale: locale,
      localizationsDelegates: AppLocalizations.localizationsDelegates,
      supportedLocales: AppLocalizations.supportedLocales,
      builder: (context, child) => MediaQuery(
        data: MediaQuery.of(context).copyWith(
          textScaler: TextScaler.linear(textScale),
        ),
        child: child!,
      ),
      home: Scaffold(
        body: SingleChildScrollView(
          child: RiskLimitsSection(
            mandate: _mandate(),
            pending: const {},
            onFieldChanged: (_, __) {},
            expanded: true,
            onToggleExpanded: () {},
          ),
        ),
      ),
    ),
  );
  await tester.pumpAndSettle();
}

const _keys = [
  'sector_cap_pct',
  'single_name_cap_pct',
  'max_open_positions',
  'post_loss_cooldown_hours',
  'max_trades_per_day',
  'max_trades_per_week',
  'max_open_risk_pct',
];

/// Every line of [para] is inside the paragraph's own box and the chip's box.
void _expectFullyVisible(WidgetTester tester, String key, String reason,
    {bool checkMaxLines = true}) {
  final chip = find.byKey(Key('riskLimitOff_$key'));
  expect(chip, findsOneWidget, reason: reason);
  final label = find.descendant(of: chip, matching: find.byType(Text));
  expect(label, findsOneWidget, reason: reason);
  final para = tester.renderObject<RenderParagraph>(label);
  final boxes = para.getBoxesForSelection(
    TextSelection(
      baseOffset: 0,
      extentOffset: para.text.toPlainText().length,
    ),
  );
  expect(boxes, isNotEmpty, reason: reason);
  final textBottom = boxes.map((b) => b.bottom).reduce((a, b) => a > b ? a : b);
  expect(textBottom, lessThanOrEqualTo(para.size.height + 0.5),
      reason: '$reason: text runs past the bottom of its own box (clipped)');
  if (checkMaxLines) {
    expect(para.didExceedMaxLines, isFalse,
        reason: '$reason: ellipsis/maxLines');
  }
  final chipRect = tester.getRect(chip);
  final labelRect = tester.getRect(label);
  expect(labelRect.bottom, lessThanOrEqualTo(chipRect.bottom + 0.5),
      reason: '$reason: label outside chip');
  expect(labelRect.right, lessThanOrEqualTo(chipRect.right + 0.5),
      reason: '$reason: label outside chip');
}

void main() {
  testWidgets(
      'DEF508: at the device width (360 dp, DPR 2) and 1.0 / 1.3 text scale '
      'every limit chip shows its whole label, value included', (tester) async {
    for (final scale in [1.0, 1.3]) {
      await _pump(tester, dpWidth: 360, dpr: 2, textScale: scale);
      final l =
          AppLocalizations.of(tester.element(find.byType(RiskLimitsSection)));
      for (final k in _keys) {
        _expectFullyVisible(tester, k, '360dp x$scale $k');
      }
      expect(find.text(l.settingsRiskLimitsFromProfileResolved('40%')),
          findsOneWidget);
      expect(find.text(l.settingsRiskLimitsFromProfileResolved('10.5%')),
          findsOneWidget);
    }
  });

  testWidgets(
      'DEF508: no width between a narrow and a wide phone clips the value '
      '(sweep — the clip needs a one-line-at-full-width label that wraps once '
      'the check and padding are subtracted)', (tester) async {
    for (var w = 300.0; w <= 600.0; w += 12) {
      for (final scale in [1.0, 1.3]) {
        await _pump(tester, dpWidth: w, dpr: 1, textScale: scale);
        for (final k in _keys) {
          _expectFullyVisible(tester, k, '${w}dp x$scale $k');
        }
      }
    }
  });

  testWidgets(
      'DEF508: the clip itself — a label that wraps to a second line is never '
      'cut to one line\'s height (fine sweep, line-clamp check only)',
      (tester) async {
    for (var w = 330.0; w <= 560.0; w += 4) {
      await _pump(tester, dpWidth: w, dpr: 1, textScale: 1.0);
      for (final k in _keys) {
        _expectFullyVisible(tester, k, '${w}dp $k', checkMaxLines: false);
      }
    }
  });

  testWidgets(
      'DEF508: Arabic and Malay labels (longer / right-to-left) also show the '
      'whole label at the device width and 1.3x', (tester) async {
    for (final code in ['ar', 'ms']) {
      await _pump(
        tester,
        dpWidth: 360,
        dpr: 2,
        textScale: 1.3,
        locale: Locale(code),
      );
      for (final k in _keys) {
        _expectFullyVisible(tester, k, '$code $k');
      }
    }
  });

  testWidgets(
      'DEF508: the chip is still a labelled, selected button that clears the '
      'limit on tap', (tester) async {
    num? changed = -1;
    tester.view.physicalSize = const Size(720, 8000);
    tester.view.devicePixelRatio = 2;
    addTearDown(tester.view.reset);
    final handle = tester.ensureSemantics();
    await tester.pumpWidget(
      MaterialApp(
        localizationsDelegates: AppLocalizations.localizationsDelegates,
        supportedLocales: AppLocalizations.supportedLocales,
        home: Scaffold(
          body: SingleChildScrollView(
            child: RiskLimitsSection(
              mandate: _mandate(),
              pending: const {},
              onFieldChanged: (_, v) => changed = v,
              expanded: true,
              onToggleExpanded: () {},
            ),
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();
    final chip = find.byKey(const Key('riskLimitOff_sector_cap_pct'));
    final l =
        AppLocalizations.of(tester.element(find.byType(RiskLimitsSection)));
    final data = tester.getSemantics(chip);
    expect(data.label, contains(l.settingsRiskLimitsFromProfileResolved('40%')));
    expect(data.flagsCollection.isSelected, Tristate.isTrue);
    expect(data.flagsCollection.isButton, isTrue);
    await tester.tap(chip);
    await tester.pump();
    expect(changed, isNull);
    handle.dispose();
  });
}
