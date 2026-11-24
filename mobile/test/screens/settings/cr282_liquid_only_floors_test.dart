/// CR282 — the Settings > Compliance "Liquid-only" explanation states the
/// floors (US $500M market cap and $1M traded a day) instead of "sufficient
/// average daily volume", and adds the Bursa Malaysia floors (RM300M / RM250k)
/// only when the Bursa flag is on.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/auth.dart';
import 'package:ami_trade/models/mandate.dart';
import 'package:ami_trade/screens/settings/settings_screen.dart';
import 'package:ami_trade/services/alpaca/alpaca_credential_store.dart';
import 'package:ami_trade/services/api/api_client.dart';
import 'package:ami_trade/state/auth_providers.dart';
import 'package:ami_trade/state/bursa_providers.dart';
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

Future<void> _openLiquidOnlySheet(WidgetTester t, {required bool bursa}) async {
  const size = Size(390, 7000);
  t.view.physicalSize = size;
  t.view.devicePixelRatio = 1.0;
  addTearDown(t.view.reset);
  await t.pumpWidget(ProviderScope(
    overrides: [
      bursaEnabledProvider.overrideWithValue(bursa),
      mandateNotifierProvider.overrideWith((ref) => _FloorPassMandate(ref)),
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
  for (var i = 0; i < 8; i++) {
    await t.pump(const Duration(milliseconds: 80));
  }
  final l = await AppLocalizations.delegate.load(const Locale('en'));
  await t.tap(find.text(l.settingsComplianceLiquidOnly));
  for (var i = 0; i < 8; i++) {
    await t.pump(const Duration(milliseconds: 80));
  }
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  setUp(() {
    FlutterSecureStoragePlatform.instance =
        TestFlutterSecureStoragePlatform(<String, String>{});
    SharedPreferences.setMockInitialValues({});
    AlpacaCredentialStore.resetCacheForTest();
  });

  testWidgets('Liquid-only explainer states the US floors; no Bursa line',
      (t) async {
    await _openLiquidOnlySheet(t, bursa: false);
    final l = await AppLocalizations.delegate.load(const Locale('en'));
    expect(find.text(l.settingsComplianceLiquidOnlyExplainBody), findsOneWidget);
    expect(l.settingsComplianceLiquidOnlyExplainBody,
        allOf(contains(r'$500M market cap'), contains(r'$1M traded a day')));
    expect(find.text(l.settingsComplianceLiquidOnlyExplainBursa), findsNothing);
  });

  testWidgets('Liquid-only explainer adds the Bursa floors when Bursa is on',
      (t) async {
    await _openLiquidOnlySheet(t, bursa: true);
    final l = await AppLocalizations.delegate.load(const Locale('en'));
    expect(find.text(l.settingsComplianceLiquidOnlyExplainBody), findsOneWidget);
    expect(find.text(l.settingsComplianceLiquidOnlyExplainBursa), findsOneWidget);
    expect(l.settingsComplianceLiquidOnlyExplainBursa,
        allOf(contains('RM300M market cap'), contains('RM250k traded a day')));
  });
}
