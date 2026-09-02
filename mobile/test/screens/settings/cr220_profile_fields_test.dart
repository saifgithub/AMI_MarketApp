/// CR220 — the identity/goal fields are editable, and the PATCH they produce
/// uses the backend's own field names.
///
/// The load-bearing test here is `patch keys match the backend field names`.
/// `MandateStore.patch` deep-merges by key and the API ignores keys it does
/// not recognise, so a typo'd key returns 200 and silently drops the change —
/// the DEF195 failure a user cannot see. Nothing in the type system connects
/// the Dart string `'primary_goal'` to the Python field, so this test is the
/// only thing that does.
///
/// Harness mirrors `settings_screen_risk_limits_test.dart` — the real
/// `SettingsScreen` with `MandateNotifier.patch` overridden, no network.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/mandate.dart';
import 'package:ami_trade/models/tickers.dart';
import 'package:ami_trade/screens/settings/profile_fields_section.dart';
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

class _FakeApiClient extends ApiClient {
  _FakeApiClient() : super(baseUrl: 'test://localhost');

  /// The symbols this stand-in resolves. Everything else comes back
  /// `exists: false`, which is what the refusal tests need.
  static const known = {'AAPL', 'TSLA'};
  final List<String> validated = [];

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

  @override
  Future<TickerValidation> validateTicker(String ticker) async {
    validated.add(ticker);
    final up = ticker.toUpperCase();
    return TickerValidation(ticker: up, exists: known.contains(up));
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

class _RecordingMandateNotifier extends MandateNotifier {
  _RecordingMandateNotifier(super.ref, UserMandate initial) {
    state = MandateState(mandate: initial);
  }

  final List<Map<String, dynamic>> patches = [];

  @override
  Future<void> patch(Map<String, dynamic> updates) async {
    patches.add(Map<String, dynamic>.from(updates));
    state = state.copyWith(saving: false);
  }
}

UserMandate _mandate({
  String primaryGoal = 'long_term_wealth',
  String horizon = 'long',
  String path = 'long_horizon',
  String learningStyle = 'quick',
  String displayName = 'Trader',
  String timezone = 'UTC',
  List<String> riskQuotes = const [],
  ComplianceFlags compliance = const ComplianceFlags(),
}) {
  return UserMandate(
    userId: 'u1',
    version: 1,
    displayName: displayName,
    locale: 'en',
    timezone: timezone,
    primaryGoal: primaryGoal,
    horizon: horizon,
    path: path,
    riskScore: 3,
    riskComponents: const RiskComponents(
      drawdownResponse: 3, regretAsymmetry: 0, concentrationTolerance: 3,
    ),
    riskQuotes: riskQuotes,
    maxDrawdownPct: 30,
    learningStyle: learningStyle,
    compliance: compliance,
    plan: 'trial_trader',
    creditBalance: 75,
  );
}

late _FakeApiClient _api;

Future<_RecordingMandateNotifier> _pump(
  WidgetTester tester,
  UserMandate initial,
) async {
  tester.view.physicalSize = const Size(390, 3200);
  tester.view.devicePixelRatio = 1.0;
  addTearDown(tester.view.reset);

  _api = _FakeApiClient();
  late _RecordingMandateNotifier notifier;
  await tester.pumpWidget(
    ProviderScope(
      overrides: [
        mandateNotifierProvider.overrideWith((ref) {
          notifier = _RecordingMandateNotifier(ref, initial);
          return notifier;
        }),
        simNotifierProvider.overrideWith((ref) => _NoopSimNotifier(ref)),
        authNotifierProvider.overrideWith((ref) => _FixedAuthNotifier(ref)),
        myHandleProvider.overrideWith((ref) async => throw Exception('no network')),
        apiClientProvider.overrideWithValue(_api),
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

Future<AppLocalizations> _l(WidgetTester tester) async =>
    AppLocalizations.of(tester.element(find.byType(SettingsScreen)));

Future<void> _tapChip(WidgetTester tester, String key) async {
  await tester.scrollUntilVisible(find.byKey(Key(key)), 200,
      scrollable: find.byType(Scrollable).first);
  await tester.tap(find.byKey(Key(key)));
  await tester.pump();
}

Future<void> _save(WidgetTester tester) async {
  final l = await _l(tester);
  await tester.scrollUntilVisible(find.text(l.settingsSave), 200,
      scrollable: find.byType(Scrollable).first);
  await tester.tap(find.text(l.settingsSave));
  await tester.pump();
  await tester.pump();
}

void main() {
  // ── The DEF195 guard ──────────────────────────────────────────────────────

  testWidgets('patch keys match the backend Mandate field names exactly',
      (tester) async {
    final n = await _pump(tester, _mandate());
    await _tapChip(tester, 'primaryGoal_income_now');
    await _tapChip(tester, 'horizon_short');
    await _tapChip(tester, 'path_active');
    await _tapChip(tester, 'learningStyle_visual');
    await _save(tester);

    expect(n.patches, hasLength(1));
    final sent = n.patches.single;
    // Exact snake_case names from backend/app/schemas/mandate.py. A rename
    // here would 200 and drop the change silently.
    expect(sent['primary_goal'], 'income_now');
    expect(sent['horizon'], 'short');
    expect(sent['path'], 'active');
    expect(sent['learning_style'], 'visual');
  });

  testWidgets('an untouched field is not sent', (tester) async {
    final n = await _pump(tester, _mandate());
    await _tapChip(tester, 'primaryGoal_income_now');
    await _save(tester);

    final sent = n.patches.single;
    expect(sent.containsKey('primary_goal'), isTrue);
    // Sparse PATCH: the store deep-merges, so sending an unchanged field is
    // harmless but sending EVERY field would make the journal diff noise.
    expect(sent.containsKey('horizon'), isFalse);
    expect(sent.containsKey('path'), isFalse);
    expect(sent.containsKey('learning_style'), isFalse);
  });

  testWidgets('selecting the value already stored sends nothing', (tester) async {
    final n = await _pump(tester, _mandate(primaryGoal: 'income_now'));
    await _tapChip(tester, 'primaryGoal_income_now');
    await _save(tester);
    expect(n.patches, isEmpty);
  });

  // ── display_name ──────────────────────────────────────────────────────────

  testWidgets('display name round-trips through the patch', (tester) async {
    final n = await _pump(tester, _mandate());
    await tester.scrollUntilVisible(find.byKey(const Key('displayNameField')), 200,
        scrollable: find.byType(Scrollable).first);
    await tester.enterText(find.byKey(const Key('displayNameField')), 'Ada');
    await tester.pump();
    await _save(tester);
    expect(n.patches.single['display_name'], 'Ada');
  });

  testWidgets('an emptied display name is never sent', (tester) async {
    // The server has no default to fall back to on PATCH (only onboarding
    // stamps "Trader"), so an empty name would leave the analysts with
    // nothing to call the user by.
    final n = await _pump(tester, _mandate());
    await tester.scrollUntilVisible(find.byKey(const Key('displayNameField')), 200,
        scrollable: find.byType(Scrollable).first);
    await tester.enterText(find.byKey(const Key('displayNameField')), '   ');
    await tester.pump();
    await _save(tester);
    expect(n.patches.isEmpty || !n.patches.single.containsKey('display_name'), isTrue);
  });

  // ── Path.BOTH is offered ──────────────────────────────────────────────────

  testWidgets('path picker offers BOTH', (tester) async {
    // Only legitimate because CR220 wired its three overlay_generator
    // branches — before that it silently rendered the LONG_HORIZON prompt.
    final n = await _pump(tester, _mandate());
    await _tapChip(tester, 'path_both');
    await _save(tester);
    expect(n.patches.single['path'], 'both');
  });

  // ── Ticker rules ──────────────────────────────────────────────────────────

  testWidgets('a validated ticker is added to the blocklist', (tester) async {
    final n = await _pump(tester, _mandate());
    await tester.scrollUntilVisible(find.byKey(const Key('blocklist_input')), 200,
        scrollable: find.byType(Scrollable).first);
    await tester.enterText(find.byKey(const Key('blocklist_input')), 'aapl');
    await tester.ensureVisible(find.byKey(const Key('blocklist_add')));
    await tester.pump();
    await tester.tap(find.byKey(const Key('blocklist_add')));
    await tester.pumpAndSettle();

    expect(_api.validated, contains('AAPL'));
    await _save(tester);
    final compliance = n.patches.single['compliance'] as Map<String, dynamic>;
    expect(compliance['ticker_blocklist'], ['AAPL']);
  });

  testWidgets('an unknown ticker is refused and never added', (tester) async {
    final n = await _pump(tester, _mandate());
    await tester.scrollUntilVisible(find.byKey(const Key('blocklist_input')), 200,
        scrollable: find.byType(Scrollable).first);
    await tester.enterText(find.byKey(const Key('blocklist_input')), 'NOTREAL');
    await tester.ensureVisible(find.byKey(const Key('blocklist_add')));
    await tester.pump();
    await tester.tap(find.byKey(const Key('blocklist_add')));
    await tester.pumpAndSettle();

    final l = await _l(tester);
    expect(find.text(l.settingsTickerUnknown), findsOneWidget);
    // The refusal is the whole point: no chip was created, so nothing can be
    // saved into an enforced list.
    expect(find.byKey(const Key('blocklist_chip_NOTREAL')), findsNothing);
    expect(n.patches, isEmpty);
  });

  testWidgets('a non-empty allowlist shows the standing warning', (tester) async {
    await _pump(
      tester,
      _mandate(compliance: const ComplianceFlags(tickerAllowlist: ['AAPL'])),
    );
    expect(find.byKey(const Key('allowlistWarning')), findsOneWidget);
  });

  testWidgets('clearing the last allowlist entry sends null, never []',
      (tester) async {
    // `[]` would mean "nothing is tradable" and the API refuses it; `null`
    // means "no allowlist". The two must never collapse together.
    final n = await _pump(
      tester,
      _mandate(compliance: const ComplianceFlags(tickerAllowlist: ['AAPL'])),
    );
    await tester.ensureVisible(find.byKey(const Key('allowlist_chip_AAPL')));
    await tester.pump();
    await tester.tap(find.descendant(
      of: find.byKey(const Key('allowlist_chip_AAPL')),
      matching: find.byIcon(Icons.close),
    ));
    await tester.pumpAndSettle();
    await _save(tester);

    final c = n.patches.single['compliance'] as Map<String, dynamic>;
    expect(c.containsKey('ticker_allowlist'), isTrue,
        reason: 'the key must be SENT as null, not omitted — an absent key '
            'deep-merges to "keep what was stored"');
    expect(c['ticker_allowlist'], isNull);
  });

  // ── Option tables ─────────────────────────────────────────────────────────

  testWidgets('every option value is a valid backend enum member',
      (tester) async {
    // Mirrors backend/app/schemas/mandate.py. A value the schema rejects
    // would 422 at save time, which is loud — but the user would have no way
    // to complete the edit, so catch it here instead.
    const backendGoals = {
      'retirement', 'long_term_wealth', 'income_now',
      'specific_goal', 'learning_to_trade', 'exploring',
    };
    const backendHorizons = {'short', 'medium', 'long', 'very_long'};
    const backendPaths = {'active', 'long_horizon', 'both'};
    const backendStyles = {'quick', 'story', 'visual', 'hands_on'};

    await _pump(tester, _mandate());
    final l = await _l(tester);
    Set<String> values(List<MandateOption> o) => o.map((x) => x.value).toSet();

    expect(values(primaryGoalOptions(l)), backendGoals);
    expect(values(horizonOptions(l)), backendHorizons);
    expect(values(pathOptions(l)), backendPaths);
    expect(values(learningStyleOptions(l)), backendStyles);
  });
}
