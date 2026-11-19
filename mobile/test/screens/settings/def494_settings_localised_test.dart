/// DEF494 — Settings (and the Room's Street-rating card) were partly English in
/// Arabic and Malay (UAT-MAND-038, device run AMI-DL-1).
///
/// Two causes, both guarded here:
///   1. hard-coded English in the widgets ("Terms of Service", "Privacy
///      Policy", the language picker's second name, four compliance
///      explanations, the raw plan id `floor_pass` as a value);
///   2. ARB keys present in ar/ms but still holding the English copy, which
///      `l10n_key_parity_test` cannot see because the key exists.
///
/// The ARB guard scans the source of the Settings surfaces for the keys they
/// use and fails if any of them reads the same as English in ar or ms, bar a
/// short reasoned allowlist (brand names, strings with no letters).
library;

import 'dart:convert';
import 'dart:io';

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/auth.dart';
import 'package:ami_trade/models/mandate.dart';
import 'package:ami_trade/screens/settings/settings_screen.dart';
import 'package:ami_trade/services/alpaca/alpaca_credential_store.dart';
import 'package:ami_trade/services/api/api_client.dart';
import 'package:ami_trade/state/auth_providers.dart';
import 'package:ami_trade/state/mandate_providers.dart';
import 'package:ami_trade/state/me_providers.dart';
import 'package:ami_trade/state/onboarding_providers.dart';
import 'package:ami_trade/state/sim_providers.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_secure_storage/test/test_flutter_secure_storage_platform.dart';
import 'package:flutter_secure_storage_platform_interface/flutter_secure_storage_platform_interface.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

/// Identical to English on purpose: product tier names and the like. A key goes
/// here only with a reason; a new "translation" that is really the English copy
/// must not.
const _identicalOnPurpose = <String, String>{
  'settingsComplianceEsgLite': 'ESG-lite is the label the product uses in every language',
  'settingsRiskPresetDayTrader': 'Day Trader is a named preset (CR129)',
  'settingsRiskPresetDayTraderActive': 'leads with the preset name',
  'settingsDayTraderConfirm': 'names the preset (ms)',
  'planNameFloorPass': 'product tier name',
  'upgradePlanTrader': 'product tier name',
  'upgradePlanFloorManager': 'product tier name',
  'settingsProfileCreditsUnknown': 'a dash',
  'settingsLearningVisual': 'Visual is the Malay word as well',
  // content/i18n/sensitive_keys.json holds these to English until a human
  // translation arrives ('unscreened' must never become 'haram'); DEF144 pins it.
  'settingsComplianceHalal': 'Sharia-sensitive, held to English by sensitive_keys.json',
  'settingsComplianceHalalSubtitle': 'Sharia-sensitive, held to English by sensitive_keys.json',
  'settingsComplianceHalalExplainTitle': 'Sharia-sensitive, held to English by sensitive_keys.json',
  'settingsComplianceHalalExplainBody': 'Sharia-sensitive, held to English by sensitive_keys.json',
};

const _surfaces = [
  'lib/screens/settings/settings_screen.dart',
  'lib/screens/settings/profile_fields_section.dart',
  'lib/screens/settings/risk_limits_section.dart',
  'lib/screens/settings/ticker_rules_section.dart',
  'lib/screens/settings/street_comparison_setting.dart',
  'lib/screens/settings/day_trader_disclosure_dialog.dart',
  'lib/widgets/room/room_street_card.dart',
  'lib/i18n/plan_names.dart',
];

Map<String, dynamic> _arb(String locale) => jsonDecode(
        File('lib/l10n/app_$locale.arb').readAsStringSync())
    as Map<String, dynamic>;

class _Api extends ApiClient {
  _Api() : super(baseUrl: 'test://localhost');
}

class _ClaimedAuthNotifier extends AuthNotifier {
  _ClaimedAuthNotifier(super.ref) {
    state = AuthState(
      user: AuthUser(
        id: 'u1',
        email: 'trader@example.com',
        isAnonymous: false,
        createdAt: DateTime.utc(2026, 1, 1),
      ),
      token: 'tok',
    );
  }

  @override
  Future<void> bootstrap() async {}
}

class _NoopSimNotifier extends SimNotifier {
  _NoopSimNotifier(super.ref);
  @override
  Future<void> refresh() async {}
}

class _FloorPassMandate extends MandateNotifier {
  _FloorPassMandate(super.ref) {
    state = MandateState(
      mandate: UserMandate.fromJson({
        'user_id': 'u1',
        'plan': 'floor_pass',
        'display_name': 'Trader',
      }),
    );
  }

  @override
  Future<void> refresh() async {}
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  setUp(() {
    FlutterSecureStoragePlatform.instance =
        TestFlutterSecureStoragePlatform(<String, String>{});
    SharedPreferences.setMockInitialValues({});
    AlpacaCredentialStore.resetCacheForTest();
  });

  test('no key a Settings surface uses is the English copy in ar or ms', () {
    final en = _arb('en');
    final ar = _arb('ar');
    final ms = _arb('ms');
    final used = <String>{};
    final ref = RegExp(r'\bl\.(\w+)|AppLocalizations\.of\(\w+\)\.(\w+)');
    for (final f in _surfaces) {
      for (final m in ref.allMatches(File(f).readAsStringSync())) {
        used.add(m.group(1) ?? m.group(2)!);
      }
    }
    final offenders = <String>[];
    for (final k in used) {
      final e = en[k];
      if (e is! String || _identicalOnPurpose.containsKey(k)) continue;
      final letters = e.replaceAll(RegExp(r'\{[^}]*\}'), '');
      if (!RegExp(r'[A-Za-z]').hasMatch(letters)) continue;
      if (ar[k] == e) offenders.add('ar:$k');
      if (ms[k] == e) offenders.add('ms:$k');
    }
    expect(offenders, isEmpty,
        reason: 'English copy sitting in a translated ARB — translate it');
  });

  test('Settings source carries no hard-coded user-facing English', () {
    final src = File('lib/screens/settings/settings_screen.dart')
        .readAsStringSync();
    for (final english in [
      "'Terms of Service'",
      "'Privacy Policy'",
      "'Follow system'",
      '_complianceExplanations',
    ]) {
      expect(src.contains(english), isFalse,
          reason: '$english is hard-coded in the Settings screen');
    }
    expect(src.contains('value: m.plan)'), isFalse,
        reason: 'the raw plan id must go through planDisplayName');
    expect(src.contains('value: mandate.plan)'), isFalse);
  });

  for (final code in ['ar', 'ms']) {
    testWidgets('Settings renders its headings and plan in $code',
        (t) async {
      const size = Size(390, 7000);
      t.view.physicalSize = size;
      t.view.devicePixelRatio = 1.0;
      addTearDown(t.view.reset);
      await t.pumpWidget(ProviderScope(
        overrides: [
          mandateNotifierProvider.overrideWith((ref) => _FloorPassMandate(ref)),
          simNotifierProvider.overrideWith((ref) => _NoopSimNotifier(ref)),
          authNotifierProvider.overrideWith((ref) => _ClaimedAuthNotifier(ref)),
          myHandleProvider.overrideWith((ref) async => null),
          apiClientProvider.overrideWithValue(_Api()),
        ],
        child: MediaQuery(
          data: const MediaQueryData(size: size),
          child: MaterialApp(
            locale: Locale(code),
            localizationsDelegates: AppLocalizations.localizationsDelegates,
            supportedLocales: AppLocalizations.supportedLocales,
            home: const SettingsScreen(),
          ),
        ),
      ));
      for (var i = 0; i < 8; i++) {
        await t.pump(const Duration(milliseconds: 80));
      }
      final l = await AppLocalizations.delegate.load(Locale(code));

      for (final english in [
        'Terms of Service',
        'Privacy Policy',
        'Report a problem',
        'STREET RATING',
        'IDENTITY',
        'MEMBERSHIP',
        'floor_pass',
        'Follow system',
        'System',
      ]) {
        expect(find.text(english), findsNothing,
            reason: '"$english" is English in $code');
      }
      expect(find.text(l.settingsTermsOfService), findsOneWidget);
      expect(find.text(l.settingsPrivacyPolicy), findsOneWidget);
      expect(find.text(l.settingsSectionStreetRating), findsOneWidget);
      expect(find.text(l.settingsLanguageSystem), findsOneWidget);
      expect(find.text(l.planNameFloorPass), findsWidgets);
    });
  }
}
