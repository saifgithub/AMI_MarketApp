/// CR101-MOBILE — coverage for `RiskLimitsSection` in isolation (no
/// Riverpod/SettingsScreen scaffolding needed — it's a plain StatelessWidget
/// driven entirely by constructor props).
///
/// Acceptance 1 (as amended by CR129): all seven fields visible/settable,
///   each in its own units; an unset limit renders "Following your risk
///   profile — {resolved}" when the server exposes the enforced value, the
///   no-number fallback when it does not (older backends), and never "OFF" —
///   post-CR129 every field falls back to a server-side preset.
/// Acceptance 4: a looser-than-current edit discloses its consequence
///   inline, at set-time — before any Save button exists in this tree.
/// Acceptance 5: the retro-tightening dialog states flag-and-block, never
///   a forced sell.
/// Acceptance 6/7: `classifyLimitEdit` is pure and reads only the field's
///   declared directionality — a behavioural guard that a hardcoded
///   substitute value cannot satisfy (see the two-mandate distinct-value
///   test), plus a source-literal guard as a second, independent net.
library;

import 'dart:io';

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/mandate.dart';
import 'package:ami_trade/screens/settings/risk_limits_section.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

UserMandate _mandate({
  double? sectorCapPct,
  double? singleNameCapPct,
  double? postLossCooldownHours,
  int? maxOpenPositions,
  int? maxTradesPerDay,
  int? maxTradesPerWeek,
  double? maxOpenRiskPct,
  ResolvedCaps? resolved,
}) {
  return UserMandate(
    userId: 'u1',
    version: 1,
    displayName: 'Trader',
    locale: 'en',
    timezone: 'UTC',
    primaryGoal: 'long_term_wealth',
    horizon: 'long',
    path: 'long_horizon',
    riskScore: 3,
    riskComponents: const RiskComponents(
      drawdownResponse: 3, regretAsymmetry: 0, concentrationTolerance: 3,
    ),
    maxDrawdownPct: 30,
    sectorCapPct: sectorCapPct,
    singleNameCapPct: singleNameCapPct,
    postLossCooldownHours: postLossCooldownHours,
    maxOpenPositions: maxOpenPositions,
    maxTradesPerDay: maxTradesPerDay,
    maxTradesPerWeek: maxTradesPerWeek,
    maxOpenRiskPct: maxOpenRiskPct,
    resolved: resolved,
    learningStyle: 'quick',
    compliance: const ComplianceFlags(),
    plan: 'trial_trader',
    creditBalance: 75,
  );
}

Future<void> _pumpSection(
  WidgetTester tester, {
  required UserMandate mandate,
  Map<String, dynamic> pending = const {},
  void Function(LimitFieldConfig, num?)? onFieldChanged,
}) async {
  tester.view.physicalSize = const Size(390, 2000);
  tester.view.devicePixelRatio = 1.0;
  addTearDown(tester.view.reset);
  await tester.pumpWidget(
    MaterialApp(
      localizationsDelegates: AppLocalizations.localizationsDelegates,
      supportedLocales: AppLocalizations.supportedLocales,
      home: Scaffold(
        body: SingleChildScrollView(
          child: RiskLimitsSection(
            mandate: mandate,
            pending: pending,
            onFieldChanged: onFieldChanged ?? (_, __) {},
            expanded: true,
            onToggleExpanded: () {},
          ),
        ),
      ),
    ),
  );
  await tester.pump();
}

void main() {
  testWidgets(
      'acceptance 1 / CR129: all seven fields render; unset with NO resolved '
      'data (older backend) falls back to the quiet no-number label for all '
      'seven — never OFF, never a fabricated number', (tester) async {
    await _pumpSection(tester, mandate: _mandate());
    final ctx = tester.element(find.byType(RiskLimitsSection));
    final l = AppLocalizations.of(ctx);

    for (final label in [
      l.settingsRiskLimitsSectorCapLabel,
      l.settingsRiskLimitsSingleNameCapLabel,
      l.settingsRiskLimitsCooldownLabel,
      l.settingsRiskLimitsMaxOpenPositionsLabel,
      l.settingsRiskLimitsMaxTradesPerDayLabel,
      l.settingsRiskLimitsMaxTradesPerWeekLabel,
      l.settingsRiskLimitsMaxOpenRiskLabel,
    ]) {
      expect(find.text(label), findsOneWidget);
    }
    // Post-CR129 all seven follow the profile when unset — OFF never renders.
    expect(find.text(l.settingsRiskLimitsProfileFollowing), findsNWidgets(7));
    expect(find.text(l.settingsRiskLimitsOff), findsNothing);
    // Anti-fabrication: without server-resolved data, no "— {value}" variant
    // may appear anywhere (the widget must not compute a preset itself).
    final resolvedPrefix =
        l.settingsRiskLimitsFollowingResolved('').trim();
    expect(find.textContaining(resolvedPrefix), findsNothing);

    // No field is silently dropped.
    expect(find.byKey(const Key('riskLimitField_sector_cap_pct')), findsOneWidget);
    expect(find.byKey(const Key('riskLimitField_single_name_cap_pct')), findsOneWidget);
    expect(find.byKey(const Key('riskLimitField_post_loss_cooldown_hours')), findsOneWidget);
    expect(find.byKey(const Key('riskLimitField_max_open_positions')), findsOneWidget);
    expect(find.byKey(const Key('riskLimitField_max_trades_per_day')), findsOneWidget);
    expect(find.byKey(const Key('riskLimitField_max_trades_per_week')), findsOneWidget);
    expect(find.byKey(const Key('riskLimitField_max_open_risk_pct')), findsOneWidget);
  });

  testWidgets(
      'CR129 acceptance 1: every one of the seven unset rows renders the '
      'SERVER-resolved enforced value, with its unit, verbatim', (tester) async {
    const resolved = ResolvedCaps(
      sectorCapPct: 40.0,
      singleNameCapPct: 3.0,
      maxOpenPositions: 35,
      postLossCooldownHours: 1.0,
      maxTradesPerDay: 4,
      maxTradesPerWeek: 12,
      maxOpenRiskPct: 10.5,
    );
    await _pumpSection(tester, mandate: _mandate(resolved: resolved));
    final ctx = tester.element(find.byType(RiskLimitsSection));
    final l = AppLocalizations.of(ctx);

    for (final expected in [
      l.settingsRiskLimitsFollowingResolved('40%'),
      l.settingsRiskLimitsFollowingResolved('3%'),
      l.settingsRiskLimitsFollowingResolved('35'),
      l.settingsRiskLimitsFollowingResolved('1h'),
      l.settingsRiskLimitsFollowingResolved('4'),
      l.settingsRiskLimitsFollowingResolved('12'),
      l.settingsRiskLimitsFollowingResolved('10.5%'),
    ]) {
      expect(find.text(expected), findsOneWidget, reason: 'missing "$expected"');
    }
    // Every row got a number — the no-number fallback should be gone.
    expect(find.text(l.settingsRiskLimitsProfileFollowing), findsNothing);
    // No override anywhere — no provenance caption either.
    expect(find.text(l.settingsRiskLimitsSetByYou), findsNothing);
  });

  testWidgets(
      'CR129 acceptance 1: partial resolved (live-Alpha 2-field shape) shows '
      'numbers where the server gave them and the quiet fallback elsewhere',
      (tester) async {
    const resolved = ResolvedCaps(sectorCapPct: 40.0, singleNameCapPct: 3.0);
    await _pumpSection(tester, mandate: _mandate(resolved: resolved));
    final ctx = tester.element(find.byType(RiskLimitsSection));
    final l = AppLocalizations.of(ctx);

    expect(find.text(l.settingsRiskLimitsFollowingResolved('40%')), findsOneWidget);
    expect(find.text(l.settingsRiskLimitsFollowingResolved('3%')), findsOneWidget);
    expect(find.text(l.settingsRiskLimitsProfileFollowing), findsNWidgets(5));
  });

  testWidgets(
      'CR129: an explicit override shows the "Set by you" provenance caption '
      'and the override in the text field', (tester) async {
    // Override is 22 — while set, the server's resolved echoes it.
    final mandate = _mandate(
      maxOpenPositions: 22,
      resolved: const ResolvedCaps(
        sectorCapPct: 40.0,
        singleNameCapPct: 3.0,
        maxOpenPositions: 22,
        postLossCooldownHours: 1.0,
        maxTradesPerDay: 4,
        maxTradesPerWeek: 12,
        maxOpenRiskPct: 10.5,
      ),
    );
    await _pumpSection(tester, mandate: mandate);
    final ctx = tester.element(find.byType(RiskLimitsSection));
    final l = AppLocalizations.of(ctx);

    expect(
      find.byKey(const Key('riskLimitSetByYou_max_open_positions')),
      findsOneWidget,
    );
    expect(find.text(l.settingsRiskLimitsSetByYou), findsOneWidget);
    final rendered = tester
        .widget<TextField>(find.byKey(const Key('riskLimitField_max_open_positions')))
        .controller!
        .text;
    expect(rendered, '22');
    // The overridden row's clear-chip must NOT present the resolved echo of
    // the override as a profile default — the true preset is unknowable
    // client-side while an override is set, so it claims no number.
    expect(find.text(l.settingsRiskLimitsFollowingResolved('22')), findsNothing);
    expect(find.text(l.settingsRiskLimitsProfileFollowing), findsOneWidget);
  });

  testWidgets(
      'acceptance 1 / shown-equals-enforced: each field renders exactly the mandate\'s '
      'own value — two distinct fixtures render two distinct numbers, ruling out a '
      'hardcoded substitute (acceptance 6/7 behavioural guard)', (tester) async {
    final a = _mandate(
      sectorCapPct: 17.5, singleNameCapPct: 6.25, postLossCooldownHours: 13.0,
      maxOpenPositions: 9, maxTradesPerDay: 11, maxTradesPerWeek: 23, maxOpenRiskPct: 8.75,
    );
    final b = _mandate(
      sectorCapPct: 63.0, singleNameCapPct: 41.5, postLossCooldownHours: 2.5,
      maxOpenPositions: 2, maxTradesPerDay: 4, maxTradesPerWeek: 6, maxOpenRiskPct: 37.0,
    );

    // Matches `_LimitFieldRow._formatForEdit`'s own rule: an integral
    // double renders without a trailing ".0" (13.0 -> "13"), a fractional
    // one keeps its decimals (17.5 -> "17.5").
    String fmtDouble(double d) => d == d.roundToDouble() ? d.toInt().toString() : d.toString();

    for (final fixture in [a, b]) {
      await _pumpSection(tester, mandate: fixture);
      for (final cfg in kRiskLimitFields) {
        final rendered = tester
            .widget<TextField>(find.byKey(Key('riskLimitField_${cfg.key}')))
            .controller!
            .text;
        final expected = switch (cfg.key) {
          'sector_cap_pct' => fmtDouble(fixture.sectorCapPct!),
          'single_name_cap_pct' => fmtDouble(fixture.singleNameCapPct!),
          'post_loss_cooldown_hours' => fmtDouble(fixture.postLossCooldownHours!),
          'max_open_positions' => fixture.maxOpenPositions.toString(),
          'max_trades_per_day' => fixture.maxTradesPerDay.toString(),
          'max_trades_per_week' => fixture.maxTradesPerWeek.toString(),
          'max_open_risk_pct' => fmtDouble(fixture.maxOpenRiskPct!),
          _ => throw StateError('unhandled ${cfg.key}'),
        };
        expect(rendered, expected, reason: '${cfg.key} on fixture ${fixture.sectorCapPct}');
      }
    }
  });

  testWidgets('acceptance 4: raising an already-explicit count field discloses looser-than-current',
      (tester) async {
    final mandate = _mandate(maxTradesPerDay: 3);
    await _pumpSection(tester, mandate: mandate, pending: {'max_trades_per_day': 8});
    final ctx = tester.element(find.byType(RiskLimitsSection));
    final l = AppLocalizations.of(ctx);
    expect(find.text(l.settingsRiskLimitsDisclosureLooser), findsOneWidget);
  });

  testWidgets(
      'acceptance 4 / CR129: clearing an explicit limit discloses back-to-profile '
      '(mechanism only, no number — the preset is unknowable while an override '
      'is set), never "removes the limit"', (tester) async {
    final mandate = _mandate(
      maxOpenPositions: 5,
      // Server resolved echoes the still-persisted override.
      resolved: const ResolvedCaps(maxOpenPositions: 5),
    );
    await _pumpSection(tester, mandate: mandate, pending: {'max_open_positions': null});
    final ctx = tester.element(find.byType(RiskLimitsSection));
    final l = AppLocalizations.of(ctx);
    expect(find.text(l.settingsRiskLimitsDisclosureBackToProfile), findsOneWidget);
    expect(find.text(l.settingsRiskLimitsDisclosureOff), findsNothing);
    // The disclosure names the mechanism only — a number here would be a
    // client-side guess at a preset the API does not expose in this state.
    expect(l.settingsRiskLimitsDisclosureBackToProfile.contains(RegExp(r'\d')), isFalse);
    // And the chip must not present the stale resolved echo (5) as the
    // profile default the field is returning to.
    expect(find.text(l.settingsRiskLimitsFollowingResolved('5')), findsNothing);
  });

  testWidgets('acceptance 4 / CR040: setting a percent field to exactly 100 discloses '
      'even when nothing was set before', (tester) async {
    final mandate = _mandate();
    await _pumpSection(tester, mandate: mandate, pending: {'max_open_risk_pct': 100});
    final ctx = tester.element(find.byType(RiskLimitsSection));
    final l = AppLocalizations.of(ctx);
    expect(find.text(l.settingsRiskLimitsDisclosure100), findsOneWidget);
  });

  testWidgets('acceptance 4: a BE1 cap moving from unset (profile) to explicit discloses '
      'the mechanism honestly, direction unknown', (tester) async {
    final mandate = _mandate();
    await _pumpSection(tester, mandate: mandate, pending: {'sector_cap_pct': 30.0});
    final ctx = tester.element(find.byType(RiskLimitsSection));
    final l = AppLocalizations.of(ctx);
    expect(find.text(l.settingsRiskLimitsDisclosureFollowing), findsOneWidget);
  });

  testWidgets('acceptance 4 (negative): tightening an existing limit discloses nothing',
      (tester) async {
    final mandate = _mandate(maxTradesPerDay: 10);
    await _pumpSection(tester, mandate: mandate, pending: {'max_trades_per_day': 3});
    final ctx = tester.element(find.byType(RiskLimitsSection));
    final l = AppLocalizations.of(ctx);
    expect(find.text(l.settingsRiskLimitsDisclosureLooser), findsNothing);
    expect(find.text(l.settingsRiskLimitsDisclosureOff), findsNothing);
  });

  testWidgets('acceptance 5: retro-tightening dialog states flag-and-block, never a forced sell',
      (tester) async {
    await tester.pumpWidget(MaterialApp(
      localizationsDelegates: AppLocalizations.localizationsDelegates,
      supportedLocales: AppLocalizations.supportedLocales,
      home: Builder(builder: (context) {
        return ElevatedButton(
          onPressed: () => RetroTighteningDialog.show(context, ['AAPL', 'MSFT']),
          child: const Text('open'),
        );
      }),
    ));
    await tester.tap(find.text('open'));
    await tester.pumpAndSettle();

    final ctx = tester.element(find.byType(RetroTighteningDialog));
    final l = AppLocalizations.of(ctx);
    expect(find.text(l.settingsRiskLimitsRetroTitle), findsOneWidget);
    expect(find.text(l.settingsRiskLimitsRetroBody), findsOneWidget);
    expect(find.textContaining('AAPL'), findsOneWidget);
    // States flag-and-block, and explicitly rules out a forced sell — never
    // "liquidate"/"force-sold" language (assign §3's fixed behaviour).
    expect(l.settingsRiskLimitsRetroBody.toLowerCase(), contains('nothing is sold automatically'));
    expect(l.settingsRiskLimitsRetroBody.toLowerCase(), isNot(contains('liquidat')));
  });

  group('classifyLimitEdit — pure direction logic (acceptance 4/7)', () {
    const sector = LimitFieldConfig(
      key: 'sector_cap_pct', kind: LimitKind.percent, presetLinked: true, higherIsLooser: true,
    );
    // Deliberately declared presetLinked:false (a shape no shipped field has
    // post-CR129) to keep the pure function's non-preset branch covered.
    const cooldown = LimitFieldConfig(
      key: 'post_loss_cooldown_hours', kind: LimitKind.hours, presetLinked: false, higherIsLooser: false,
    );
    const positions = LimitFieldConfig(
      key: 'max_open_positions', kind: LimitKind.count, presetLinked: false, higherIsLooser: true,
    );

    test('unset BE2 field turning on is tightening — no disclosure', () {
      expect(
        classifyLimitEdit(positions, oldValue: null, newValue: 5),
        LimitDisclosure.none,
      );
    });

    test('unset BE1 field turning explicit — unknown direction', () {
      expect(
        classifyLimitEdit(sector, oldValue: null, newValue: 30),
        LimitDisclosure.unknownDirection,
      );
    });

    test('raising a count cap is looser', () {
      expect(
        classifyLimitEdit(positions, oldValue: 4, newValue: 9),
        LimitDisclosure.looser,
      );
    });

    test('lowering a count cap is tighter — no disclosure', () {
      expect(
        classifyLimitEdit(positions, oldValue: 9, newValue: 4),
        LimitDisclosure.none,
      );
    });

    test('shortening the cooldown is looser (inverted direction)', () {
      expect(
        classifyLimitEdit(cooldown, oldValue: 24, newValue: 6),
        LimitDisclosure.looser,
      );
    });

    test('lengthening the cooldown is tighter — no disclosure', () {
      expect(
        classifyLimitEdit(cooldown, oldValue: 6, newValue: 24),
        LimitDisclosure.none,
      );
    });

    test('clearing an explicit value on a non-preset field is a removal', () {
      expect(
        classifyLimitEdit(positions, oldValue: 5, newValue: null),
        LimitDisclosure.off,
      );
    });

    test('CR129: clearing an explicit value on a preset-linked field is '
        'back-to-profile, not removal — and every shipped field is preset-linked', () {
      expect(
        classifyLimitEdit(sector, oldValue: 40, newValue: null),
        LimitDisclosure.backToProfile,
      );
      for (final cfg in kRiskLimitFields) {
        expect(cfg.presetLinked, isTrue,
            reason: '${cfg.key} must be preset-linked post-CR129');
        expect(
          classifyLimitEdit(cfg, oldValue: 5, newValue: null),
          LimitDisclosure.backToProfile,
        );
      }
    });

    test('percent field set to exactly 100 always discloses, any prior value', () {
      expect(
        classifyLimitEdit(sector, oldValue: 40, newValue: 100),
        LimitDisclosure.hundredPercent,
      );
    });

    test('unchanged value discloses nothing', () {
      expect(
        classifyLimitEdit(positions, oldValue: 5, newValue: 5),
        LimitDisclosure.none,
      );
    });
  });

  group('CR129 Custom detection — hasExplicitRiskLimitOverride covers all seven', () {
    test('no override anywhere is not Custom', () {
      expect(hasExplicitRiskLimitOverride(_mandate(), const {}), isFalse);
    });

    test('a server-persisted override on ANY of the seven reads Custom', () {
      final fixtures = <UserMandate>[
        _mandate(sectorCapPct: 25.0),
        _mandate(singleNameCapPct: 10.0),
        _mandate(postLossCooldownHours: 8.0),
        _mandate(maxOpenPositions: 5),
        _mandate(maxTradesPerDay: 3),
        _mandate(maxTradesPerWeek: 11),
        _mandate(maxOpenRiskPct: 6.5),
      ];
      for (final m in fixtures) {
        expect(hasExplicitRiskLimitOverride(m, const {}), isTrue);
      }
    });

    test('a pending (unsaved) override on ANY of the seven reads Custom', () {
      for (final cfg in kRiskLimitFields) {
        expect(
          hasExplicitRiskLimitOverride(_mandate(), {cfg.key: 5}),
          isTrue,
          reason: 'pending ${cfg.key} must flip Custom',
        );
      }
    });

    test('pending nulls over server overrides (the L1 dial-clear) is NOT Custom', () {
      final m = _mandate(
        sectorCapPct: 25.0,
        singleNameCapPct: 10.0,
        postLossCooldownHours: 8.0,
        maxOpenPositions: 5,
        maxTradesPerDay: 3,
        maxTradesPerWeek: 11,
        maxOpenRiskPct: 6.5,
      );
      final pending = {for (final cfg in kRiskLimitFields) cfg.key: null};
      expect(hasExplicitRiskLimitOverride(m, pending), isFalse);
    });
  });

  test('acceptance 6: no known backend risk-cap preset literal appears in the '
      'risk-limits editing surface (source-level guard, belt to the behavioural '
      'guard above)', () {
    // The exact preset numbers CR101-BE1/BE2's bridges measured
    // (`risk_tier_cap`, `SINGLE_NAME_ABSOLUTE_CAP_PCT`, `_DEFAULT_SECTOR_CAP`)
    // — see backend/app/trading_math/sizing.py and
    // backend/app/services/sector_allocation.py — EXTENDED with CR129's
    // preset tables (backend/app/trading_math/risk_limits.py: positions
    // 65/65/35/30/30, cooldown 4/2/1/1/0.5h, trades 2-6/day 6-20/week,
    // open-risk 0.25-0.50 x max_drawdown, e.g. 7.5/9.0/10.5/13.5/15.0 at
    // DD 30). None of them may appear as a bare literal anywhere this screen
    // computes a DISPLAYED risk-limit value; every number must come from
    // `mandate.<field>`, `mandate.resolved.<field>`, or a value the user is
    // actively typing. Bare integers that collide with legitimate UI
    // constants in these files (20, 30, 15 — icon sizes, drawdown picker
    // options) are guarded via their float spellings instead, and `1.0` is
    // omitted because it substring-matches version strings in comments
    // ("0.1.0+94") — the cooldown table stays covered by 4.0/2.0/0.5. A
    // client-side copy of the preset TABLES (maps/lists of these values)
    // cannot avoid the covered tokens.
    final knownCapLiterals = RegExp(
        r'\b(0\.40|40\.0|50\.0|4\.5|1\.5|3\.0'
        r'|65|35|12'
        r'|65\.0|35\.0|30\.0|20\.0|15\.0'
        r'|4\.0|2\.0|0\.5|0\.25|0\.50'
        r'|7\.5|9\.0|10\.5|13\.5)\b');
    final files = [
      File('lib/screens/settings/risk_limits_section.dart'),
      File('lib/screens/settings/settings_screen.dart'),
    ];
    for (final f in files) {
      final text = f.readAsStringSync();
      final matches = knownCapLiterals.allMatches(text).map((m) => m.group(0)).toList();
      expect(matches, isEmpty, reason: '${f.path} contains a known backend cap literal: $matches');
    }
  });
}
