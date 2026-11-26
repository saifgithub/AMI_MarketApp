/// CR285 — the debt-maturity horizon and minimum debt coverage rows in Settings > risk limits.
///
/// Pins: the rows appear only while the server says the check is active (shown = enforced), the
/// horizon renders in months and the coverage in "x" units, an unset value shows the SERVER-resolved
/// number (the horizon's chip says it follows the horizon, not the risk profile), an edit PATCHes
/// under the exact backend key (months as a whole number), each info icon opens its own explain
/// sheet, and neither row is in the Day Trader preset's field list.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/mandate.dart';
import 'package:ami_trade/screens/settings/risk_limits_section.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

const _active = ResolvedCaps(
  debtHorizonMonths: 24,
  debtHorizonMonthsSource: 'default',
  minDebtCoverage: 1.25,
  minDebtCoverageSource: 'default',
  debtCheckActive: true,
);

UserMandate _mandate({
  int? debtHorizonMonths,
  double? minDebtCoverage,
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
    debtHorizonMonths: debtHorizonMonths,
    minDebtCoverage: minDebtCoverage,
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
  tester.view.physicalSize = const Size(390, 3200);
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
  testWidgets('neither row shows while the check is not active', (tester) async {
    for (final resolved in [null, const ResolvedCaps(), const ResolvedCaps(debtCheckActive: false)]) {
      await _pump(tester, mandate: _mandate(resolved: resolved));
      expect(find.byKey(const Key('riskLimitField_debt_horizon_months')), findsNothing);
      expect(find.byKey(const Key('riskLimitField_min_debt_coverage')), findsNothing);
    }
  });

  testWidgets('both rows render with their labels and units when active', (tester) async {
    await _pump(tester, mandate: _mandate(resolved: _active));
    final l = AppLocalizations.of(tester.element(find.byType(RiskLimitsSection)));
    expect(find.text(l.settingsDebtHorizonLabel), findsOneWidget);
    expect(find.text(l.settingsDebtCoverageLabel), findsOneWidget);
    expect(find.byKey(const Key('riskLimitField_debt_horizon_months')), findsOneWidget);
    expect(find.byKey(const Key('riskLimitField_min_debt_coverage')), findsOneWidget);
    expect(find.text(' mo'), findsOneWidget);
    expect(find.text('×'), findsOneWidget);
  });

  testWidgets('an unset value shows the server-resolved number; the horizon follows the horizon',
      (tester) async {
    await _pump(tester, mandate: _mandate(resolved: _active));
    final l = AppLocalizations.of(tester.element(find.byType(RiskLimitsSection)));
    expect(find.text(l.settingsDebtHorizonFromHorizonResolved('24 mo')), findsOneWidget);
    expect(find.text(l.settingsRiskLimitsFromProfileResolved('1.25×')), findsOneWidget);
    final box = tester.widget<TextField>(find.byKey(const Key('riskLimitField_debt_horizon_months')));
    expect(box.decoration!.hintText, '24');
  });

  testWidgets('a user value reads back verbatim, says so, and offers the way back', (tester) async {
    await _pump(tester, mandate: _mandate(debtHorizonMonths: 36, minDebtCoverage: 2.0, resolved: _active));
    final l = AppLocalizations.of(tester.element(find.byType(RiskLimitsSection)));
    expect(
      tester.widget<TextField>(find.byKey(const Key('riskLimitField_debt_horizon_months'))).controller!.text,
      '36',
    );
    expect(
      tester.widget<TextField>(find.byKey(const Key('riskLimitField_min_debt_coverage'))).controller!.text,
      '2',
    );
    expect(find.byKey(const Key('riskLimitSetByYou_debt_horizon_months')), findsOneWidget);
    expect(find.byKey(const Key('riskLimitSetByYou_min_debt_coverage')), findsOneWidget);
    expect(find.text(l.settingsDebtHorizonUseHorizon), findsOneWidget);
  });

  testWidgets('typing PATCHes under the exact backend keys; months are whole numbers', (tester) async {
    final got = <String, num?>{};
    await _pump(
      tester,
      mandate: _mandate(resolved: _active),
      onFieldChanged: (cfg, v) => got[cfg.key] = v,
    );
    await tester.enterText(find.byKey(const Key('riskLimitField_debt_horizon_months')), '36');
    await tester.enterText(find.byKey(const Key('riskLimitField_min_debt_coverage')), '1.8');
    expect(got['debt_horizon_months'], 36);
    expect(got['min_debt_coverage'], 1.8);

    await tester.enterText(find.byKey(const Key('riskLimitField_debt_horizon_months')), '3.5');
    expect(got['debt_horizon_months'], 35, reason: 'the "." is filtered out: the server field is an int');
  });

  testWidgets('a smaller number discloses as looser; clearing returns to the default', (tester) async {
    await _pump(
      tester,
      mandate: _mandate(debtHorizonMonths: 36, resolved: _active),
      pending: const {'debt_horizon_months': 12},
    );
    final l = AppLocalizations.of(tester.element(find.byType(RiskLimitsSection)));
    expect(find.text(l.settingsRiskLimitsDisclosureLooser), findsOneWidget);

    await _pump(
      tester,
      mandate: _mandate(debtHorizonMonths: 36, resolved: _active),
      pending: const {'debt_horizon_months': null},
    );
    expect(find.text(l.settingsRiskLimitsDisclosureBackToProfile), findsOneWidget);
  });

  testWidgets('each info icon opens its own explain sheet', (tester) async {
    await _pump(tester, mandate: _mandate(resolved: _active));
    final l = AppLocalizations.of(tester.element(find.byType(RiskLimitsSection)));

    await tester.tap(find.byKey(const Key('riskLimitExplainSheet_debt_horizon_months')));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('explainSheet_debt_horizon_months')), findsOneWidget);
    expect(find.text(l.settingsDebtHorizonSheetBody), findsOneWidget);
    await tester.tapAt(const Offset(10, 10));
    await tester.pumpAndSettle();

    await tester.tap(find.byKey(const Key('riskLimitExplainSheet_min_debt_coverage')));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('explainSheet_min_debt_coverage')), findsOneWidget);
    expect(find.text(l.settingsDebtCoverageSheetBody), findsOneWidget);
  });

  test('ResolvedCaps and UserMandate decode the new fields; absent is null', () {
    final m = UserMandate.fromJson({
      'user_id': 'u1',
      'debt_horizon_months': 36,
      'min_debt_coverage': 2.0,
      'resolved': {
        'debt_horizon_months': 24, 'debt_horizon_months_source': 'default',
        'min_debt_coverage': 1.25, 'min_debt_coverage_source': 'user',
        'debt_check_active': true,
      },
    });
    expect(m.debtHorizonMonths, 36);
    expect(m.minDebtCoverage, 2.0);
    expect(m.resolved!.debtHorizonMonths, 24);
    expect(m.resolved!.debtHorizonMonthsSource, 'default');
    expect(m.resolved!.minDebtCoverageSource, 'user');
    expect(m.resolved!.debtCheckActive, isTrue);
    expect(m.resolved!.valueFor('debt_horizon_months'), 24);
    expect(m.resolved!.valueFor('min_debt_coverage'), 1.25);

    final old = UserMandate.fromJson({'user_id': 'u1', 'resolved': {}});
    expect(old.debtHorizonMonths, isNull);
    expect(old.resolved!.debtCheckActive, isNull);
  });

  test('the rows are not in the Day Trader preset field list; larger is the tighter number', () {
    final keys = kRiskLimitFields.map((c) => c.key);
    expect(keys, isNot(contains('debt_horizon_months')));
    expect(keys, isNot(contains('min_debt_coverage')));
    expect(kDebtCheckFields.map((c) => c.key), ['debt_horizon_months', 'min_debt_coverage']);
    expect(kDebtCheckFields.every((c) => !c.higherIsLooser), isTrue);
  });
}
