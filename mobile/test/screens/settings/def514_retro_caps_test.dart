/// DEF514 — saving a tightened single-name (or sector) cap that current
/// holdings already breach must show the "Some holdings now breach this limit"
/// disclosure, with the offender and its weight. The dialog used to fire only
/// for `max_open_positions` / `max_open_risk_pct`, on the false premise that
/// those were the only limits with a portfolio-state dimension; the trade
/// ticket refuses on the single-name cap against the same holdings.
///
/// Same harness as `settings_screen_retro_audit_test.dart` (scripted
/// `MandateNotifier` + fake `ApiClient`); the fake client returns an audit.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/mandate.dart';
import 'package:ami_trade/screens/settings/risk_limits_section.dart';
import 'package:ami_trade/screens/settings/settings_screen.dart';
import 'package:ami_trade/services/api/api_client.dart';
import 'package:ami_trade/state/auth_providers.dart';
import 'package:ami_trade/state/me_providers.dart';
import 'package:ami_trade/state/mandate_providers.dart';
import 'package:ami_trade/state/onboarding_providers.dart';
import 'package:ami_trade/state/sim_providers.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

class _AuditApiClient extends ApiClient {
  _AuditApiClient(this.result) : super(baseUrl: 'test://localhost');

  final HoldingsAuditResult result;
  int audits = 0;

  @override
  Future<HoldingsAuditResult> auditMandateHoldings(String userId) async {
    audits++;
    return result;
  }
}

class _FixedAuthNotifier extends AuthNotifier {
  _FixedAuthNotifier(super.ref);

  @override
  Future<void> bootstrap() async {}
}

class _NoopSimNotifier extends SimNotifier {
  _NoopSimNotifier(super.ref);

  @override
  Future<void> refresh() async {}
}

class _ScriptedMandateNotifier extends MandateNotifier {
  _ScriptedMandateNotifier(super.ref, UserMandate initial) {
    state = MandateState(mandate: initial);
  }

  @override
  Future<void> patch(Map<String, dynamic> updates) async {
    final b = state.mandate!;
    final next = UserMandate(
      userId: b.userId,
      version: b.version + 1,
      displayName: b.displayName,
      locale: b.locale,
      timezone: b.timezone,
      primaryGoal: b.primaryGoal,
      horizon: b.horizon,
      path: b.path,
      riskScore: b.riskScore,
      riskComponents: b.riskComponents,
      maxDrawdownPct: b.maxDrawdownPct,
      sectorCapPct:
          (updates['sector_cap_pct'] as num?)?.toDouble() ?? b.sectorCapPct,
      singleNameCapPct: (updates['single_name_cap_pct'] as num?)?.toDouble() ??
          b.singleNameCapPct,
      postLossCooldownHours: b.postLossCooldownHours,
      maxOpenPositions: b.maxOpenPositions,
      maxTradesPerDay: b.maxTradesPerDay,
      maxTradesPerWeek: b.maxTradesPerWeek,
      maxOpenRiskPct: b.maxOpenRiskPct,
      learningStyle: b.learningStyle,
      compliance: b.compliance,
      plan: b.plan,
      creditBalance: b.creditBalance,
    );
    state = state.copyWith(mandate: next, saving: false);
  }
}

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
      maxOpenPositions: null,
      learningStyle: 'quick',
      compliance: ComplianceFlags(),
      plan: 'trial_trader',
      creditBalance: 75,
    );

const _nflxBreach = HoldingsAuditResult(
  passed: false,
  mandateVersion: 2,
  maxOpenPositionsBreach: false,
  maxOpenRiskPctBreach: false,
  violationTickers: ['NFLX'],
  singleNameCapBreach: true,
  singleNameCapPct: 3,
  singleNameBreaches: [ConcentrationBreach(name: 'NFLX', weightPct: 46.5)],
);

const _clean = HoldingsAuditResult(
  passed: true,
  mandateVersion: 2,
  maxOpenPositionsBreach: false,
  maxOpenRiskPctBreach: false,
  violationTickers: [],
);

Future<void> _pump(WidgetTester tester, _AuditApiClient api) async {
  tester.view.physicalSize = const Size(390, 1600);
  tester.view.devicePixelRatio = 1.0;
  addTearDown(tester.view.reset);
  await tester.pumpWidget(
    ProviderScope(
      overrides: [
        mandateNotifierProvider
            .overrideWith((ref) => _ScriptedMandateNotifier(ref, _mandate())),
        simNotifierProvider.overrideWith((ref) => _NoopSimNotifier(ref)),
        authNotifierProvider.overrideWith((ref) => _FixedAuthNotifier(ref)),
        myHandleProvider.overrideWith(
            (ref) async => throw Exception('no network in test')),
        apiClientProvider.overrideWithValue(api),
      ],
      child: MaterialApp(
        localizationsDelegates: AppLocalizations.localizationsDelegates,
        supportedLocales: AppLocalizations.supportedLocales,
        home: const SettingsScreen(),
      ),
    ),
  );
  await tester.pump();
  await tester.pump();
}

Future<void> _saveField(
    WidgetTester tester, String key, String value, AppLocalizations l) async {
  await tester.tap(find.text(l.settingsRiskLimitsExpand));
  await tester.pump();
  await tester.enterText(find.byKey(Key('riskLimitField_$key')), value);
  await tester.pump();
  await tester.tap(find.text(l.settingsSave));
  for (var i = 0; i < 10; i++) {
    await tester.pump(const Duration(milliseconds: 50));
  }
}

void main() {
  testWidgets(
      'DEF514: tightening single_name_cap_pct below a held name shows the '
      'disclosure with the ticker, weight and cap', (tester) async {
    final api = _AuditApiClient(_nflxBreach);
    await _pump(tester, api);
    final l = AppLocalizations.of(tester.element(find.byType(SettingsScreen)));

    await _saveField(tester, 'single_name_cap_pct', '3', l);

    expect(api.audits, 1);
    expect(find.byType(RetroTighteningDialog), findsOneWidget);
    expect(find.text(l.settingsRiskLimitsRetroTitle), findsOneWidget);
    expect(find.text(l.settingsRiskLimitsRetroBody), findsOneWidget);
    expect(find.byKey(const Key('retroSingleNameLine')), findsOneWidget);
    expect(find.textContaining('NFLX 46.5%'), findsOneWidget);
    expect(find.textContaining('3%'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets(
      'DEF514: a sector cap that holdings breach names the sector and its '
      'tickers', (tester) async {
    final api = _AuditApiClient(const HoldingsAuditResult(
      passed: false,
      mandateVersion: 2,
      maxOpenPositionsBreach: false,
      maxOpenRiskPctBreach: false,
      violationTickers: [],
      sectorCapBreach: true,
      sectorCapPct: 40,
      sectorBreaches: [
        ConcentrationBreach(
            name: 'Communication Services',
            weightPct: 45,
            tickers: ['GOOGL', 'NFLX']),
      ],
    ));
    await _pump(tester, api);
    final l = AppLocalizations.of(tester.element(find.byType(SettingsScreen)));

    await _saveField(tester, 'sector_cap_pct', '40', l);

    expect(find.byType(RetroTighteningDialog), findsOneWidget);
    expect(find.byKey(const Key('retroSectorLine')), findsOneWidget);
    expect(find.textContaining('Communication Services 45.0% (GOOGL, NFLX)'),
        findsOneWidget);
  });

  testWidgets('DEF514: a tightened cap that no holding breaches shows nothing',
      (tester) async {
    final api = _AuditApiClient(_clean);
    await _pump(tester, api);
    final l = AppLocalizations.of(tester.element(find.byType(SettingsScreen)));

    await _saveField(tester, 'single_name_cap_pct', '60', l);

    expect(api.audits, 1, reason: 'the audit still runs for this limit');
    expect(find.byType(RetroTighteningDialog), findsNothing);
  });

  testWidgets(
      'DEF514: an untouched cap does not audit or disclose, even when the '
      'portfolio already breaches one', (tester) async {
    final api = _AuditApiClient(_nflxBreach);
    await _pump(tester, api);
    final l = AppLocalizations.of(tester.element(find.byType(SettingsScreen)));

    // trade-pace limit: no holdings-side reading, so no audit at all.
    await _saveField(tester, 'max_trades_per_day', '3', l);

    expect(api.audits, 0);
    expect(find.byType(RetroTighteningDialog), findsNothing);
  });

  test('DEF514: an older server (no new fields) reads as no concentration breach',
      () {
    final r = HoldingsAuditResult.fromJson({
      'passed': true,
      'mandate_version': 3,
      'violations': <dynamic>[],
    });
    expect(r.singleNameCapBreach, isFalse);
    expect(r.sectorCapBreach, isFalse);
    expect(r.anyRetroBreach, isFalse);
  });

  test('DEF514: the new audit fields parse and trip anyRetroBreach', () {
    final r = HoldingsAuditResult.fromJson({
      'passed': false,
      'mandate_version': 3,
      'single_name_cap_breach': true,
      'single_name_cap_pct': 3.0,
      'single_name_breaches': [
        {'name': 'NFLX', 'weight_pct': 46.5, 'tickers': ['NFLX']},
      ],
      'sector_cap_breach': false,
      'violations': <dynamic>[],
    });
    expect(r.anyRetroBreach, isTrue);
    expect(r.singleNameCapPct, 3.0);
    expect(r.singleNameBreaches.single.name, 'NFLX');
    expect(r.singleNameBreaches.single.weightPct, 46.5);
  });
}
