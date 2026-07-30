/// CR101-MOBILE — integration coverage for the Settings risk-limits editor
/// through the REAL `SettingsScreen`, not a stand-in harness.
///
/// Covers the two acceptance criteria that need the real save flow:
///   #2 — a value set in L2 round-trips: set, save, and the SERVER's
///        returned value is what renders (not the locally-typed one).
///   #3 — L1 preset selection writes the two CR101-BE1 caps coherently
///        (clears their overrides); an explicit L2 edit to either flips
///        the dial to Custom.
///
/// `MandateNotifier.patch` is overridden per-test to hand back a
/// caller-controlled "server" mandate, exactly the `_FixedSimNotifier`
/// pattern `portfolio_screen_test.dart` uses for its own notifiers — no
/// real network touched.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/mandate.dart';
import 'package:ami_trade/screens/settings/settings_screen.dart';
import 'package:ami_trade/services/api/api_client.dart';
import 'package:ami_trade/state/auth_providers.dart';
import 'package:ami_trade/state/league_providers.dart';
import 'package:ami_trade/state/mandate_providers.dart';
import 'package:ami_trade/state/onboarding_providers.dart';
import 'package:ami_trade/state/sim_providers.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

/// Never touches real Dio/network — `_save()` audits holdings immediately
/// after a successful patch, and an unmocked `apiClientProvider` leaves a
/// real HTTP request's Timer pending past the test's teardown.
class _FakeApiClient extends ApiClient {
  _FakeApiClient() : super(baseUrl: 'test://localhost');

  @override
  Future<HoldingsAuditResult> auditMandateHoldings(String userId) async {
    return const HoldingsAuditResult(
      passed: true,
      mandateVersion: 1,
      maxOpenPositionsBreach: false,
      maxOpenRiskPctBreach: false,
      violationTickers: [],
    );
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

/// Hands back whatever `onPatch` computes as the "server" response —
/// never a bare echo of what the client sent, so a test can prove the
/// screen renders the SERVER's value, not local state.
class _ScriptedMandateNotifier extends MandateNotifier {
  _ScriptedMandateNotifier(super.ref, UserMandate initial) {
    state = MandateState(mandate: initial);
  }

  UserMandate Function(UserMandate before, Map<String, dynamic> updates)? onPatch;

  @override
  Future<void> patch(Map<String, dynamic> updates) async {
    final before = state.mandate!;
    final next = onPatch?.call(before, updates) ?? before;
    state = state.copyWith(mandate: next, saving: false);
  }
}

UserMandate _mandate({
  int riskScore = 3,
  double? sectorCapPct,
  double? singleNameCapPct,
  double? postLossCooldownHours,
  int? maxOpenPositions,
  int? maxTradesPerDay,
  int? maxTradesPerWeek,
  double? maxOpenRiskPct,
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
    riskScore: riskScore,
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
    learningStyle: 'quick',
    compliance: const ComplianceFlags(),
    dailyBriefing: const DailyBriefing(),
    plan: 'trial_trader',
    creditBalance: 75,
  );
}

Future<_ScriptedMandateNotifier> _pump(
  WidgetTester tester,
  UserMandate initial, {
  UserMandate Function(UserMandate before, Map<String, dynamic> updates)? onPatch,
}) async {
  tester.view.physicalSize = const Size(390, 1600);
  tester.view.devicePixelRatio = 1.0;
  addTearDown(tester.view.reset);

  late _ScriptedMandateNotifier notifier;
  await tester.pumpWidget(
    ProviderScope(
      overrides: [
        mandateNotifierProvider.overrideWith((ref) {
          notifier = _ScriptedMandateNotifier(ref, initial);
          notifier.onPatch = onPatch;
          return notifier;
        }),
        simNotifierProvider.overrideWith((ref) => _NoopSimNotifier(ref)),
        authNotifierProvider.overrideWith((ref) => _FixedAuthNotifier(ref)),
        leagueMeProvider.overrideWith((ref) async => throw Exception('no network in test')),
        apiClientProvider.overrideWithValue(_FakeApiClient()),
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
  return notifier;
}

Future<void> _expandRiskLimits(WidgetTester tester) async {
  final l = await _l(tester);
  await tester.tap(find.text(l.settingsRiskLimitsExpand));
  await tester.pump();
}

Future<AppLocalizations> _l(WidgetTester tester) async {
  final ctx = tester.element(find.byType(SettingsScreen));
  return AppLocalizations.of(ctx);
}

void main() {
  testWidgets('acceptance 2: save renders the SERVER value, not the locally-typed one',
      (tester) async {
    final initial = _mandate(maxOpenPositions: null);
    await _pump(
      tester,
      initial,
      // The "server" deliberately returns a DIFFERENT number than whatever
      // was sent — proves the screen isn't just echoing local state.
      onPatch: (before, updates) => _mandate(maxOpenPositions: 7),
    );
    await _expandRiskLimits(tester);

    await tester.enterText(find.byKey(const Key('riskLimitField_max_open_positions')), '12');
    await tester.pump();

    final l = await _l(tester);
    await tester.tap(find.text(l.settingsSave));
    await tester.pump();
    await tester.pump();

    // The server's 7, not the locally-typed 12.
    final rendered = tester
        .widget<TextField>(find.byKey(const Key('riskLimitField_max_open_positions')))
        .controller!
        .text;
    expect(rendered, '7');
  });

  testWidgets(
      'acceptance 3: moving the risk-profile dial re-asserts "following profile" '
      'for the two BE1 caps', (tester) async {
    final initial = _mandate(riskScore: 3, sectorCapPct: 25.0, singleNameCapPct: 10.0);
    await _pump(tester, initial);
    final l = await _l(tester);

    // Starts Custom — both BE1 caps are explicitly set.
    expect(find.text(l.settingsRiskLimitsProfileCustom), findsOneWidget);

    // Drag the risk slider to a new value.
    final slider = find.byType(Slider).first;
    await tester.drag(slider, const Offset(200, 0));
    await tester.pump();

    // The dial is coherent again — no Custom badge — proving the two BE1
    // caps' overrides were cleared, not left dangling on the old profile.
    expect(find.text(l.settingsRiskLimitsProfileCustom), findsNothing);
    expect(find.text(l.settingsRiskLimitsProfileFollowing), findsWidgets);
  });

  testWidgets('acceptance 3: an explicit L2 edit to a BE1 cap flips the dial to Custom',
      (tester) async {
    final initial = _mandate(riskScore: 3);
    await _pump(tester, initial);
    await _expandRiskLimits(tester);
    final l = await _l(tester);

    expect(find.text(l.settingsRiskLimitsProfileFollowing), findsWidgets);

    await tester.enterText(
      find.byKey(const Key('riskLimitField_sector_cap_pct')),
      '22',
    );
    await tester.pump();

    expect(find.text(l.settingsRiskLimitsProfileCustom), findsOneWidget);
  });
}
