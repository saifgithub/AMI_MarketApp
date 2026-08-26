/// CR129 items 2-3 — the Day Trader picker entry and its disclosure gate,
/// through the REAL `SettingsScreen`.
///
/// Every fixture preset value is DELIBERATELY unlike production
/// (91.0 / 92.0 / 0.25 / 424242… vs the backend's 100.0 / 0.0 / 999999), so
/// no test here can go green via a client-side constant: the only way the
/// staged PATCH can match the assertion is by round-tripping the values the
/// fake server served (acceptance 2). The fixture disclosure text carries
/// "Compliance" and "halal" so the acceptance-4 what-is-NOT-removed
/// assertion is meaningful, not vacuous.
///
/// Covers:
///   (i)   null `day_trader_preset` (older backend) → the entry does not
///         exist — hidden, never approximated.
///   (ii)  tapping the entry shows the dialog BEFORE any patch is sent, body
///         verbatim from the server.
///   (iii) cancel stages nothing — no Save button, nothing dirty.
///   (iv)  confirm + Save PATCHes the served overrides verbatim.
///   (v)   post-save the caption is the Day Trader state; one field edit →
///         Custom; slider move → Following (acceptance 3, both directions).
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

/// Values a production backend would never serve — see the library docstring.
const Map<String, num> kFixtureOverrides = {
  'sector_cap_pct': 91.0,
  'single_name_cap_pct': 92.0,
  'post_loss_cooldown_hours': 0.25,
  'max_open_positions': 424242,
  'max_trades_per_day': 424243,
  'max_trades_per_week': 424244,
  'max_open_risk_pct': 93.0,
};

const String kFixtureDisclosure =
    'FIXTURE DISCLOSURE — removes the limits you control. '
    'Compliance, locale, and halal/allow-blocklist rules still apply — '
    'this preset cannot touch them.';

const DayTraderPresetInfo kFixturePreset = DayTraderPresetInfo(
  overrides: kFixtureOverrides,
  disclosure: kFixtureDisclosure,
);

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

/// Records every PATCH payload — (ii)'s "nothing sent before confirm" and
/// (iv)'s verbatim-round-trip assertions read `patches` directly — and hands
/// back whatever `onPatch` computes as the "server" response, never a bare
/// echo of local state.
class _RecordingMandateNotifier extends MandateNotifier {
  _RecordingMandateNotifier(super.ref, UserMandate initial) {
    state = MandateState(mandate: initial);
  }

  final List<Map<String, dynamic>> patches = [];
  UserMandate Function(UserMandate before, Map<String, dynamic> updates)? onPatch;

  @override
  Future<void> patch(Map<String, dynamic> updates) async {
    patches.add(Map<String, dynamic>.from(updates));
    final before = state.mandate!;
    final next = onPatch?.call(before, updates) ?? before;
    state = state.copyWith(mandate: next, saving: false);
  }
}

UserMandate _mandate({
  int riskScore = 3,
  DayTraderPresetInfo? dayTraderPreset,
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
    dayTraderPreset: dayTraderPreset,
    learningStyle: 'quick',
    compliance: const ComplianceFlags(),
    plan: 'trial_trader',
    creditBalance: 75,
  );
}

/// The fixture mandate a "server" that has APPLIED the preset would return:
/// every override stored verbatim, preset still stamped on the response.
UserMandate _mandateWithPresetApplied() {
  return _mandate(
    dayTraderPreset: kFixturePreset,
    sectorCapPct: (kFixtureOverrides['sector_cap_pct']!).toDouble(),
    singleNameCapPct: (kFixtureOverrides['single_name_cap_pct']!).toDouble(),
    postLossCooldownHours:
        (kFixtureOverrides['post_loss_cooldown_hours']!).toDouble(),
    maxOpenPositions: (kFixtureOverrides['max_open_positions']!).toInt(),
    maxTradesPerDay: (kFixtureOverrides['max_trades_per_day']!).toInt(),
    maxTradesPerWeek: (kFixtureOverrides['max_trades_per_week']!).toInt(),
    maxOpenRiskPct: (kFixtureOverrides['max_open_risk_pct']!).toDouble(),
  );
}

Future<_RecordingMandateNotifier> _pump(
  WidgetTester tester,
  UserMandate initial, {
  UserMandate Function(UserMandate before, Map<String, dynamic> updates)? onPatch,
}) async {
  tester.view.physicalSize = const Size(390, 1600);
  tester.view.devicePixelRatio = 1.0;
  addTearDown(tester.view.reset);

  late _RecordingMandateNotifier notifier;
  await tester.pumpWidget(
    ProviderScope(
      overrides: [
        mandateNotifierProvider.overrideWith((ref) {
          notifier = _RecordingMandateNotifier(ref, initial);
          notifier.onPatch = onPatch;
          return notifier;
        }),
        simNotifierProvider.overrideWith((ref) => _NoopSimNotifier(ref)),
        authNotifierProvider.overrideWith((ref) => _FixedAuthNotifier(ref)),
        myHandleProvider.overrideWith((ref) async => throw Exception('no network in test')),
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

Future<AppLocalizations> _l(WidgetTester tester) async {
  final ctx = tester.element(find.byType(SettingsScreen));
  return AppLocalizations.of(ctx);
}

const _chipKey = Key('riskPresetDayTrader');
const _bodyKey = Key('dayTraderDisclosureBody');

void main() {
  testWidgets('(i) no day_trader_preset from the server → no Day Trader entry',
      (tester) async {
    await _pump(tester, _mandate(dayTraderPreset: null));
    expect(find.byKey(_chipKey), findsNothing);
  });

  testWidgets(
      '(ii) tapping Day Trader shows the disclosure BEFORE any patch, body '
      'verbatim from the server', (tester) async {
    final notifier = await _pump(tester, _mandate(dayTraderPreset: kFixturePreset));

    await tester.tap(find.byKey(_chipKey));
    await tester.pumpAndSettle();

    expect(find.byKey(_bodyKey), findsOneWidget);
    final body = tester.widget<Text>(find.byKey(_bodyKey));
    expect(body.data, kFixtureDisclosure);
    expect(notifier.patches, isEmpty,
        reason: 'the disclosure must precede ANY network write');
  });

  testWidgets('(iii) cancel stages nothing — no Save button, caption unchanged',
      (tester) async {
    final notifier = await _pump(tester, _mandate(dayTraderPreset: kFixturePreset));
    final l = await _l(tester);

    await tester.tap(find.byKey(_chipKey));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('dayTraderCancel')));
    await tester.pumpAndSettle();

    expect(find.byKey(_bodyKey), findsNothing);
    expect(find.text(l.settingsSave), findsNothing,
        reason: 'nothing staged → nothing to save');
    expect(find.text(l.settingsRiskPresetDayTraderActive), findsNothing);
    expect(tester.widget<ChoiceChip>(find.byKey(_chipKey)).selected, isFalse);
    expect(notifier.patches, isEmpty);
  });

  testWidgets(
      '(iv) confirm + Save PATCHes the SERVER-served overrides verbatim, and '
      'the disclosure named what is NOT removed', (tester) async {
    final notifier = await _pump(
      tester,
      _mandate(dayTraderPreset: kFixturePreset),
      onPatch: (before, updates) => _mandateWithPresetApplied(),
    );
    final l = await _l(tester);

    await tester.tap(find.byKey(_chipKey));
    await tester.pumpAndSettle();

    // Acceptance 4, second half: the text on screen names what survives.
    final body = tester.widget<Text>(find.byKey(_bodyKey)).data!;
    expect(body, contains('Compliance'));
    expect(body, contains('halal'));

    await tester.tap(find.byKey(const Key('dayTraderConfirm')));
    await tester.pumpAndSettle();

    expect(notifier.patches, isEmpty,
        reason: 'confirm STAGES; only the user\'s Save sends');
    expect(tester.widget<ChoiceChip>(find.byKey(_chipKey)).selected, isTrue);

    await tester.tap(find.text(l.settingsSave));
    await tester.pump();
    await tester.pump();

    expect(notifier.patches, hasLength(1));
    final sent = notifier.patches.single;
    for (final entry in kFixtureOverrides.entries) {
      expect(sent[entry.key], entry.value,
          reason: '${entry.key} must round-trip the served value verbatim');
    }
  });

  testWidgets(
      '(v) post-save caption is Day Trader; one field edit → Custom; slider '
      'move → Following', (tester) async {
    await _pump(
      tester,
      _mandate(dayTraderPreset: kFixturePreset),
      onPatch: (before, updates) => _mandateWithPresetApplied(),
    );
    final l = await _l(tester);

    await tester.tap(find.byKey(_chipKey));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('dayTraderConfirm')));
    await tester.pumpAndSettle();
    await tester.tap(find.text(l.settingsSave));
    await tester.pump();
    await tester.pump();

    // The selected state holds against the SERVER's stored values — the
    // pending map was cleared on save.
    expect(find.text(l.settingsRiskPresetDayTraderActive), findsOneWidget);
    expect(tester.widget<ChoiceChip>(find.byKey(_chipKey)).selected, isTrue);

    // Editing any single field breaks verbatim equality → Custom.
    await tester.tap(find.text(l.settingsRiskLimitsExpand));
    await tester.pump();
    await tester.enterText(
      find.byKey(const Key('riskLimitField_sector_cap_pct')),
      '55',
    );
    await tester.pump();
    expect(find.text(l.settingsRiskPresetDayTraderActive), findsNothing);
    expect(find.text(l.settingsRiskLimitsProfileCustom), findsOneWidget);

    // Moving the profile dial clears all seven overrides → Following.
    await tester.drag(find.byType(Slider).first, const Offset(200, 0));
    await tester.pump();
    expect(find.text(l.settingsRiskPresetDayTraderActive), findsNothing);
    expect(find.text(l.settingsRiskLimitsProfileCustom), findsNothing);
    expect(find.text(l.settingsRiskLimitsProfileFollowing), findsWidgets);
    expect(tester.widget<ChoiceChip>(find.byKey(_chipKey)).selected, isFalse);
  });
}
