/// DEF481 items 3 and 7 — Settings deep-scroll and MANAGE ACCOUNT.
///
/// (3) OPEN MY MANDATE on a refused trade opens Settings scrolled to the
///     section holding the rule that refused it, not at the top of a
///     thirteen-section list. The list is lazy, so the target has to be walked
///     to; these tests pin that it ends up on screen.
/// (7) A signed-in user's MANAGE ACCOUNT opens the subscription tier picker
///     (the paywall sheet); a guest still goes to sign-in.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/auth.dart';
import 'package:ami_trade/models/mandate.dart';
import 'package:ami_trade/screens/auth/sign_in_screen.dart';
import 'package:ami_trade/screens/settings/settings_screen.dart';
import 'package:ami_trade/services/api/api_client.dart';
import 'package:ami_trade/state/auth_providers.dart';
import 'package:ami_trade/state/mandate_providers.dart';
import 'package:ami_trade/state/me_providers.dart';
import 'package:ami_trade/state/onboarding_providers.dart';
import 'package:ami_trade/state/sim_providers.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

/// Short enough that every anchor target starts below the fold.
const double _kViewH = 320;

class _Api extends ApiClient {
  _Api() : super(baseUrl: 'test://localhost');

  @override
  Future<void> alpacaReportLinkState(bool linked) async {}
}

class _Auth extends AuthNotifier {
  _Auth(super.ref, {required bool claimed}) {
    state = AuthState(
      user: AuthUser(
        id: 'u1',
        email: claimed ? 'trader@example.com' : null,
        isAnonymous: !claimed,
        createdAt: DateTime.utc(2026, 1, 1),
      ),
      token: 'tok',
    );
  }

  @override
  Future<void> bootstrap() async {}
}

class _NoopSim extends SimNotifier {
  _NoopSim(super.ref);
  @override
  Future<void> refresh() async {}
}

class _Mandate extends MandateNotifier {
  _Mandate(super.ref) {
    state = MandateState(
      mandate: UserMandate.fromJson({
        'user_id': 'u1',
        'plan': 'trial_trader',
        'display_name': 'Trader',
      }),
    );
  }

  @override
  Future<void> refresh() async {}
}

Future<void> _pump(
  WidgetTester tester, {
  SettingsAnchor? anchor,
  bool claimed = true,
}) async {
  tester.view.physicalSize = const Size(390, _kViewH);
  tester.view.devicePixelRatio = 1.0;
  addTearDown(tester.view.reset);

  await tester.pumpWidget(
    ProviderScope(
      overrides: [
        mandateNotifierProvider.overrideWith((ref) => _Mandate(ref)),
        simNotifierProvider.overrideWith((ref) => _NoopSim(ref)),
        authNotifierProvider.overrideWith((ref) => _Auth(ref, claimed: claimed)),
        myHandleProvider.overrideWith((ref) async => 'HANDLE'),
        apiClientProvider.overrideWithValue(_Api()),
      ],
      child: MaterialApp(
        localizationsDelegates: AppLocalizations.localizationsDelegates,
        supportedLocales: AppLocalizations.supportedLocales,
        home: SettingsScreen(anchor: anchor),
      ),
    ),
  );
  await tester.pump();
  await tester.pump();
}

AppLocalizations _l(WidgetTester tester) =>
    AppLocalizations.of(tester.element(find.byType(SettingsScreen)));

/// True when the section's title is laid out inside the viewport.
bool _titleOnScreen(WidgetTester tester, String title) {
  final f = find.text(title);
  if (f.evaluate().isEmpty) return false;
  final r = tester.getRect(f.first);
  return r.top >= 0 && r.bottom <= _kViewH;
}

void main() {
  testWidgets('no anchor: Settings opens at the top, compliance is below the fold',
      (tester) async {
    await _pump(tester);
    expect(_titleOnScreen(tester, _l(tester).settingsSectionCompliance), isFalse);
  });

  for (final c in <(SettingsAnchor, String Function(AppLocalizations))>[
    (SettingsAnchor.compliance, (l) => l.settingsSectionCompliance),
    (SettingsAnchor.riskLimits, (l) => l.settingsSectionRiskLimits),
    (SettingsAnchor.tickerRules, (l) => l.settingsSectionTickerRules),
  ]) {
    testWidgets('anchor ${c.$1.name}: that section is on screen after open',
        (tester) async {
      await _pump(tester, anchor: c.$1);
      await tester.pumpAndSettle();
      expect(_titleOnScreen(tester, c.$2(_l(tester))), isTrue,
          reason: '${c.$1.name} must be scrolled into view');
    });
  }

  test('blocked_by slug picks the section that holds the rule', () {
    expect(settingsAnchorForBlockedBy('allowlist'), SettingsAnchor.tickerRules);
    expect(settingsAnchorForBlockedBy('blocklist'), SettingsAnchor.tickerRules);
    for (final s in [
      'concentration',
      'cooldown',
      'max_open_positions',
      'over_trading',
      'open_risk',
    ]) {
      expect(settingsAnchorForBlockedBy(s), SettingsAnchor.riskLimits, reason: s);
    }
    for (final s in ['compliance', 'long_only', 'locale', null]) {
      expect(settingsAnchorForBlockedBy(s), SettingsAnchor.compliance,
          reason: '$s');
    }
  });

  testWidgets('MANAGE ACCOUNT (signed in) opens the subscription tier picker',
      (tester) async {
    await _pump(tester);
    final l = _l(tester);
    final button = find.byKey(const Key('accountPrimaryButton'));
    await tester.scrollUntilVisible(button, 300,
        scrollable: find.byType(Scrollable).first);
    await tester.ensureVisible(button);
    await tester.pump();
    expect(find.descendant(of: button, matching: find.text(l.settingsManageAccount)),
        findsOneWidget);

    await tester.tap(button);
    await tester.pumpAndSettle();

    expect(find.text(l.upgradeSheetTitle), findsOneWidget);
    expect(find.byType(SignInScreen), findsNothing);
  });

  testWidgets('guest keeps SIGN IN -> the sign-in screen', (tester) async {
    await _pump(tester, claimed: false);
    final l = _l(tester);
    final button = find.byKey(const Key('accountPrimaryButton'));
    await tester.scrollUntilVisible(button, 300,
        scrollable: find.byType(Scrollable).first);
    await tester.ensureVisible(button);
    await tester.pump();
    expect(find.descendant(of: button, matching: find.text(l.settingsSignIn)),
        findsOneWidget);

    await tester.tap(button);
    await tester.pumpAndSettle();

    expect(find.byType(SignInScreen), findsOneWidget);
    expect(find.text(l.upgradeSheetTitle), findsNothing);
  });
}
