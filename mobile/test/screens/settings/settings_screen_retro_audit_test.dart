/// DEF194 — a failed retro-tightening breach check used to be a bare
/// `catch (_)`, so "nothing is in breach" and "we could not check" were the
/// same silence. CR040: if a failure fires silently, what does the user end
/// up believing? Here, that they are compliant when the app never checked.
///
/// The fix keeps the swallow (a failed audit read must never make a
/// genuinely-succeeded mandate save look failed) but adds a disclosure: a
/// quiet snackbar naming the third state. This reuses
/// `settings_screen_risk_limits_test.dart`'s exact harness (a scripted
/// `MandateNotifier` + a fake `ApiClient`) with one difference — the fake
/// client's `auditMandateHoldings` throws, the live shape when the audit GET
/// itself fails right after a successful PATCH.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/mandate.dart';
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

/// The live shape: the PATCH already succeeded, and the immediately-following
/// audit GET throws (connection blip, timeout, whatever).
class _ThrowingAuditApiClient extends ApiClient {
  _ThrowingAuditApiClient() : super(baseUrl: 'test://localhost');

  @override
  Future<HoldingsAuditResult> auditMandateHoldings(String userId) async {
    throw Exception('simulated network failure on the audit read');
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
    final before = state.mandate!;
    // Echo the patched value back — the "server" honestly saved it; this
    // test is about the AUDIT read failing, not the save itself.
    final next = UserMandate(
      userId: before.userId,
      version: before.version + 1,
      displayName: before.displayName,
      locale: before.locale,
      timezone: before.timezone,
      primaryGoal: before.primaryGoal,
      horizon: before.horizon,
      path: before.path,
      riskScore: before.riskScore,
      riskComponents: before.riskComponents,
      maxDrawdownPct: before.maxDrawdownPct,
      sectorCapPct: before.sectorCapPct,
      singleNameCapPct: before.singleNameCapPct,
      postLossCooldownHours: before.postLossCooldownHours,
      maxOpenPositions:
          (updates['max_open_positions'] as num?)?.toInt() ?? before.maxOpenPositions,
      maxTradesPerDay: before.maxTradesPerDay,
      maxTradesPerWeek: before.maxTradesPerWeek,
      maxOpenRiskPct: before.maxOpenRiskPct,
      learningStyle: before.learningStyle,
      compliance: before.compliance,
      plan: before.plan,
      creditBalance: before.creditBalance,
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

Future<void> _pump(WidgetTester tester, UserMandate initial) async {
  tester.view.physicalSize = const Size(390, 1600);
  tester.view.devicePixelRatio = 1.0;
  addTearDown(tester.view.reset);

  await tester.pumpWidget(
    ProviderScope(
      overrides: [
        mandateNotifierProvider
            .overrideWith((ref) => _ScriptedMandateNotifier(ref, initial)),
        simNotifierProvider.overrideWith((ref) => _NoopSimNotifier(ref)),
        authNotifierProvider.overrideWith((ref) => _FixedAuthNotifier(ref)),
        myHandleProvider.overrideWith(
            (ref) async => throw Exception('no network in test')),
        apiClientProvider.overrideWithValue(_ThrowingAuditApiClient()),
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

void main() {
  testWidgets(
      'DEF194: a failed retro-audit read discloses "could not check", not '
      'silence', (tester) async {
    await _pump(tester, _mandate());
    final l = AppLocalizations.of(tester.element(find.byType(SettingsScreen)));

    await tester.tap(find.text(l.settingsRiskLimitsExpand));
    await tester.pump();

    // A retro-audited field (CR101-MOBILE assign §3: only these two carry a
    // portfolio-state dimension) — touching it is what makes `_save()` fire
    // the post-patch audit read at all.
    await tester.enterText(
      find.byKey(const Key('riskLimitField_max_open_positions')),
      '5',
    );
    await tester.pump();

    await tester.tap(find.text(l.settingsSave));
    // Let the save's own async work land, then confirm it succeeded — a
    // SnackBar shows here, and Flutter queues a SECOND one behind it rather
    // than showing both at once, so the audit-failure disclosure below
    // won't appear until this one's default ~4s duration elapses.
    for (var i = 0; i < 10; i++) {
      await tester.pump(const Duration(milliseconds: 50));
    }
    expect(find.text(l.settingsMandateUpdated), findsOneWidget,
        reason: 'the PATCH really did succeed; only the follow-up AUDIT '
            'read failed');

    // Pump past the first SnackBar's default duration so the queued
    // disclosure actually surfaces.
    for (var i = 0; i < 90; i++) {
      await tester.pump(const Duration(milliseconds: 50));
    }

    // The third state — "we could not check" — must be visible, not just
    // logged. This is the exact gap DEF194 reports: before the fix, a
    // caught-and-swallowed exception left the user with nothing here.
    expect(find.text(l.settingsRetroAuditFailed), findsOneWidget,
        reason: 'DEF194: a failed audit read must be disclosed, not silently '
            'indistinguishable from "nothing is in breach"');
    expect(tester.takeException(), isNull);
  });
}
