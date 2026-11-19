// CR278 (CR267 WP-36) - a Beta build is English only: the locale is pinned to
// `en` and Settings shows no language switch. Default builds are unchanged.
//
// `kBetaBuild` is a compile-time define, so the tests drive the same seams the
// app reads: `LocaleNotifier(englishOnly:)` and `betaEnglishOnlyProvider`.

import 'package:ami_trade/features/beta/beta_build.dart';
import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/i18n/locale_provider.dart';
import 'package:ami_trade/models/auth.dart';
import 'package:ami_trade/models/mandate.dart';
import 'package:ami_trade/screens/settings/settings_screen.dart';
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

class _FixedMandateNotifier extends MandateNotifier {
  _FixedMandateNotifier(super.ref) {
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

Future<void> _settle(WidgetTester t) async {
  for (var i = 0; i < 6; i++) {
    await t.pump(const Duration(milliseconds: 80));
  }
}

Future<void> _pumpSettings(WidgetTester t, {required bool beta}) async {
  const size = Size(390, 900);
  t.view.physicalSize = size;
  t.view.devicePixelRatio = 1.0;
  addTearDown(t.view.reset);
  await t.pumpWidget(ProviderScope(
    overrides: [
      betaEnglishOnlyProvider.overrideWithValue(beta),
      mandateNotifierProvider.overrideWith((ref) => _FixedMandateNotifier(ref)),
      simNotifierProvider.overrideWith((ref) => _NoopSimNotifier(ref)),
      authNotifierProvider.overrideWith((ref) => _ClaimedAuthNotifier(ref)),
      myHandleProvider.overrideWith((ref) async => null),
      apiClientProvider.overrideWithValue(_Api()),
    ],
    child: MediaQuery(
      data: const MediaQueryData(size: size),
      child: MaterialApp(
        locale: const Locale('en'),
        localizationsDelegates: AppLocalizations.localizationsDelegates,
        supportedLocales: AppLocalizations.supportedLocales,
        home: const SettingsScreen(),
      ),
    ),
  ));
  await _settle(t);
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  setUp(() {
    FlutterSecureStoragePlatform.instance =
        TestFlutterSecureStoragePlatform(<String, String>{});
    SharedPreferences.setMockInitialValues({});
  });

  test('a default build is not a Beta build', () {
    expect(kBetaBuild, isFalse);
    final c = ProviderContainer();
    addTearDown(c.dispose);
    expect(c.read(betaEnglishOnlyProvider), isFalse);
    expect(c.read(localeNotifierProvider), isNull,
        reason: 'default builds still follow the system locale');
  });

  test('English-only pins the locale from the first frame', () {
    final n = LocaleNotifier(englishOnly: true);
    expect(n.state, const Locale('en'));
  });

  test('English-only ignores setLocale and never writes a preference',
      () async {
    final n = LocaleNotifier(englishOnly: true);
    await n.setLocale(const Locale('ar'));
    expect(n.state, const Locale('en'));
    await n.setLocale(null);
    expect(n.state, const Locale('en'));
    final prefs = await SharedPreferences.getInstance();
    expect(prefs.getString('ami_locale_override'), isNull);
  });

  test('English-only ignores an Arabic override stored by an earlier build',
      () async {
    SharedPreferences.setMockInitialValues({'ami_locale_override': 'ar'});
    final n = LocaleNotifier(englishOnly: true);
    await Future<void>.delayed(const Duration(milliseconds: 20));
    expect(n.state, const Locale('en'));
  });

  test('default notifier still switches language (nothing changed)', () async {
    final n = LocaleNotifier();
    await n.setLocale(const Locale('ms'));
    expect(n.state, const Locale('ms'));
  });

  testWidgets('Settings shows the language switch in a default build',
      (t) async {
    await _pumpSettings(t, beta: false);
    final l = await AppLocalizations.delegate.load(const Locale('en'));
    await t.scrollUntilVisible(
      find.text(l.settingsSectionLanguageUpper),
      300,
      scrollable: find.byType(Scrollable).first,
    );
    expect(find.text(l.settingsSectionLanguageUpper), findsOneWidget);
    expect(find.text('Bahasa Melayu'), findsWidgets);
  });

  testWidgets('Settings has no language switch in a Beta build', (t) async {
    await _pumpSettings(t, beta: true);
    final l = await AppLocalizations.delegate.load(const Locale('en'));
    // Walk the whole page: the section must not exist anywhere.
    final scrollable = find.byType(Scrollable).first;
    await t.scrollUntilVisible(find.text(l.settingsSectionHelp), 300,
        scrollable: scrollable);
    await _settle(t);
    expect(find.text(l.settingsSectionLanguageUpper), findsNothing);
    expect(find.text('Bahasa Melayu'), findsNothing);
    expect(find.text('العربية'), findsNothing);
  });
}
