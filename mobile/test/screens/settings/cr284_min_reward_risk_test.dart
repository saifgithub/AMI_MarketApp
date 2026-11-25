/// CR284 — the minimum reward-to-risk row in Settings > risk limits.
///
/// Pins: the row renders in ratio units (":1") next to the seven preset-backed
/// limits, an unset floor shows the SERVER-resolved number and not a client
/// guess, an edit PATCHes under the exact backend key, the info icon opens the
/// explain sheet, and the row stays out of the Day Trader preset's field list
/// (so the server's preset keeps matching).
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/mandate.dart';
import 'package:ami_trade/screens/settings/risk_limits_section.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

UserMandate _mandate({double? minRewardRisk, ResolvedCaps? resolved}) {
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
    minRewardRisk: minRewardRisk,
    resolved: resolved,
    learningStyle: 'quick',
    compliance: const ComplianceFlags(),
    plan: 'trial_trader',
    creditBalance: 75,
  );
}

Future<void> _pump(
  WidgetTester tester, {
  required UserMandate mandate,
  Map<String, dynamic> pending = const {},
  void Function(LimitFieldConfig, num?)? onFieldChanged,
}) async {
  tester.view.physicalSize = const Size(390, 2400);
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
  testWidgets('the row renders with a ":1" unit and its label', (tester) async {
    await _pump(tester, mandate: _mandate());
    final l = AppLocalizations.of(tester.element(find.byType(RiskLimitsSection)));
    expect(find.text(l.settingsRiskLimitsMinRewardRiskLabel), findsOneWidget);
    expect(find.byKey(const Key('riskLimitField_min_reward_risk')), findsOneWidget);
    expect(find.text(':1'), findsOneWidget);
  });

  testWidgets('an unset floor shows the server-resolved number, not a guess',
      (tester) async {
    await _pump(
      tester,
      mandate: _mandate(
        resolved: const ResolvedCaps(
          minRewardRisk: 1.5,
          minRewardRiskSource: 'default',
        ),
      ),
    );
    final l = AppLocalizations.of(tester.element(find.byType(RiskLimitsSection)));
    expect(
      find.text(l.settingsRiskLimitsFromProfileResolved('1.5:1')),
      findsOneWidget,
    );
  });

  testWidgets('with no resolved data the row falls back to the no-number label',
      (tester) async {
    await _pump(tester, mandate: _mandate());
    final l = AppLocalizations.of(tester.element(find.byType(RiskLimitsSection)));
    // Eight preset-backed rows now follow the profile; none shows a number.
    expect(find.text(l.settingsRiskLimitsFromProfile), findsNWidgets(8));
    expect(find.textContaining(l.settingsRiskLimitsFromProfileResolved('').trim()),
        findsNothing);
  });

  testWidgets('a user value shows as set by the user and reads back verbatim',
      (tester) async {
    await _pump(tester, mandate: _mandate(minRewardRisk: 2.5));
    final l = AppLocalizations.of(tester.element(find.byType(RiskLimitsSection)));
    final field = tester.widget<TextField>(
      find.byKey(const Key('riskLimitField_min_reward_risk')),
    );
    expect(field.controller!.text, '2.5');
    expect(find.byKey(const Key('riskLimitSetByYou_min_reward_risk')), findsOneWidget);
    expect(find.text(l.settingsRiskLimitsUseProfile), findsWidgets);
  });

  testWidgets('typing a value PATCHes under the exact backend key',
      (tester) async {
    LimitFieldConfig? gotCfg;
    num? gotValue;
    await _pump(
      tester,
      mandate: _mandate(),
      onFieldChanged: (cfg, v) {
        gotCfg = cfg;
        gotValue = v;
      },
    );
    await tester.enterText(
      find.byKey(const Key('riskLimitField_min_reward_risk')),
      '1.8',
    );
    expect(gotCfg?.key, 'min_reward_risk');
    expect(gotValue, 1.8);
  });

  testWidgets('a lower floor discloses as looser; clearing returns to profile',
      (tester) async {
    await _pump(
      tester,
      mandate: _mandate(minRewardRisk: 2.0),
      pending: const {'min_reward_risk': 1.0},
    );
    final l = AppLocalizations.of(tester.element(find.byType(RiskLimitsSection)));
    expect(find.text(l.settingsRiskLimitsDisclosureLooser), findsOneWidget);

    await _pump(
      tester,
      mandate: _mandate(minRewardRisk: 2.0),
      pending: const {'min_reward_risk': null},
    );
    expect(find.text(l.settingsRiskLimitsDisclosureBackToProfile), findsOneWidget);
  });

  testWidgets('the info icon opens the explain sheet', (tester) async {
    await _pump(tester, mandate: _mandate());
    final l = AppLocalizations.of(tester.element(find.byType(RiskLimitsSection)));
    await tester.tap(find.byKey(const Key('riskLimitExplainSheet_min_reward_risk')));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('rewardRiskSheet')), findsOneWidget);
    expect(find.text(l.settingsRiskLimitsMinRewardRiskSheetBody), findsOneWidget);
  });

  test('ResolvedCaps and UserMandate decode the new fields; absent is null', () {
    final m = UserMandate.fromJson({
      'user_id': 'u1',
      'min_reward_risk': 2.0,
      'resolved': {'min_reward_risk': 1.5, 'min_reward_risk_source': 'default'},
    });
    expect(m.minRewardRisk, 2.0);
    expect(m.resolved!.minRewardRisk, 1.5);
    expect(m.resolved!.minRewardRiskSource, 'default');
    expect(m.resolved!.valueFor('min_reward_risk'), 1.5);

    final old = UserMandate.fromJson({'user_id': 'u1', 'resolved': {}});
    expect(old.minRewardRisk, isNull);
    expect(old.resolved!.minRewardRisk, isNull);
  });

  test('the row is not in the Day Trader preset field list', () {
    expect(kRiskLimitFields.map((c) => c.key), isNot(contains('min_reward_risk')));
    expect(kRewardRiskField.single.key, 'min_reward_risk');
    expect(kRewardRiskField.single.higherIsLooser, isFalse);
  });
}
