/// DEF479 — Alpaca Disconnect, Regenerate handle, Sign out and Relink were all
/// one-tap and irreversible (Disconnect wipes the stored credential, Regenerate
/// is a one-shot API, Relink wipes before the connect screen so backing out
/// leaves the user unlinked). Saiful's ruling (2026-10-20): confirm on all four.
///
/// Each action is driven through the real `SettingsScreen`: tapping it must
/// open a dialog and do NOTHING until the dialog is confirmed; CANCEL leaves
/// the world exactly as it was.
library;

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

class _RecordingApi extends ApiClient {
  _RecordingApi() : super(baseUrl: 'test://localhost');

  int regenerateCalls = 0;

  @override
  Future<String> regenerateHandle() async {
    regenerateCalls++;
    return 'NEWHANDLE';
  }

  @override
  Future<void> alpacaReportLinkState(bool linked) async {}
}

class _ClaimedAuthNotifier extends AuthNotifier {
  _ClaimedAuthNotifier(super.ref, this.log) {
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

  final List<String> log;

  @override
  Future<void> bootstrap() async {}

  @override
  Future<void> signOut() async {
    log.add('signOut');
  }
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

Future<void> _pump(WidgetTester tester, _RecordingApi api, List<String> log) async {
  const size = Size(390, 900);
  tester.view.physicalSize = size;
  tester.view.devicePixelRatio = 1.0;
  addTearDown(tester.view.reset);

  await tester.pumpWidget(
    ProviderScope(
      overrides: [
        mandateNotifierProvider.overrideWith((ref) => _FixedMandateNotifier(ref)),
        simNotifierProvider.overrideWith((ref) => _NoopSimNotifier(ref)),
        authNotifierProvider
            .overrideWith((ref) => _ClaimedAuthNotifier(ref, log)),
        myHandleProvider.overrideWith((ref) async => 'OLDHANDLE'),
        apiClientProvider.overrideWithValue(api),
      ],
      child: const MediaQuery(
        data: MediaQueryData(size: size),
        child: MaterialApp(
          localizationsDelegates: AppLocalizations.localizationsDelegates,
          supportedLocales: AppLocalizations.supportedLocales,
          home: SettingsScreen(),
        ),
      ),
    ),
  );
  for (var i = 0; i < 6; i++) {
    await tester.pump(const Duration(milliseconds: 50));
  }
}

Future<void> _scrollTo(WidgetTester tester, Finder target) async {
  await tester.scrollUntilVisible(target, 300,
      scrollable: find.byType(Scrollable).first);
  await tester.pump(const Duration(milliseconds: 50));
}

Future<void> _settle(WidgetTester tester) async {
  for (var i = 0; i < 6; i++) {
    await tester.pump(const Duration(milliseconds: 50));
  }
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  late _RecordingApi api;
  late List<String> log;

  setUp(() {
    FlutterSecureStoragePlatform.instance =
        TestFlutterSecureStoragePlatform(<String, String>{});
    SharedPreferences.setMockInitialValues({});
    AlpacaCredentialStore.resetCacheForTest();
    api = _RecordingApi();
    log = [];
  });

  testWidgets('REGENERATE HANDLE asks first; CANCEL sends nothing',
      (tester) async {
    await _pump(tester, api, log);
    await _scrollTo(tester, find.text('REGENERATE HANDLE'));

    await tester.tap(find.text('REGENERATE HANDLE'));
    await _settle(tester);
    expect(find.text('REGENERATE HANDLE?'), findsOneWidget);
    expect(api.regenerateCalls, 0, reason: 'the one-shot call must wait');

    await tester.tap(find.text('CANCEL'));
    await _settle(tester);
    expect(api.regenerateCalls, 0);
  });

  testWidgets('REGENERATE HANDLE calls the API only once confirmed',
      (tester) async {
    await _pump(tester, api, log);
    await _scrollTo(tester, find.text('REGENERATE HANDLE'));

    await tester.tap(find.text('REGENERATE HANDLE'));
    await _settle(tester);
    await tester.tap(find.text('REGENERATE'));
    await _settle(tester);

    expect(api.regenerateCalls, 1);
  });

  testWidgets('Sign out asks first; CANCEL keeps the session', (tester) async {
    await _pump(tester, api, log);
    await _scrollTo(tester, find.text('Sign out'));

    await tester.tap(find.text('Sign out'));
    await _settle(tester);
    expect(find.text('SIGN OUT?'), findsOneWidget);
    expect(log, isEmpty);

    await tester.tap(find.text('CANCEL'));
    await _settle(tester);
    expect(log, isEmpty);
  });

  testWidgets('Sign out signs out once confirmed', (tester) async {
    await _pump(tester, api, log);
    await _scrollTo(tester, find.text('Sign out'));

    await tester.tap(find.text('Sign out'));
    await _settle(tester);
    await tester.tap(find.text('SIGN OUT'));
    await _settle(tester);

    expect(log, ['signOut']);
  });

  testWidgets('Alpaca Disconnect asks first; CANCEL keeps the credential',
      (tester) async {
    await AlpacaCredentialStore.save('PKKEY', 'secret',
        baseUrl: kDefaultAlpacaBaseUrl);
    await _pump(tester, api, log);
    await _scrollTo(tester, find.text('Disconnect'));

    await tester.tap(find.text('Disconnect'));
    await _settle(tester);
    expect(find.text('DISCONNECT ALPACA PAPER?'), findsOneWidget);
    expect(await AlpacaCredentialStore.isLinked(), isTrue,
        reason: 'nothing is wiped while the dialog is open');

    await tester.tap(find.text('CANCEL'));
    await _settle(tester);
    expect(await AlpacaCredentialStore.isLinked(), isTrue);
  });

  testWidgets('Alpaca Disconnect wipes the credential once confirmed',
      (tester) async {
    await AlpacaCredentialStore.save('PKKEY', 'secret',
        baseUrl: kDefaultAlpacaBaseUrl);
    await _pump(tester, api, log);
    await _scrollTo(tester, find.text('Disconnect'));

    await tester.tap(find.text('Disconnect'));
    await _settle(tester);
    await tester.tap(find.text('DISCONNECT'));
    await _settle(tester);

    expect(await AlpacaCredentialStore.isLinked(), isFalse);
  });

  testWidgets('Relink asks before the credential wipe; CANCEL keeps it stored',
      (tester) async {
    await AlpacaCredentialStore.save('AKKEY', 'secret',
        baseUrl: 'https://api.alpaca.markets');
    await _pump(tester, api, log);
    await _scrollTo(tester, find.text('Relink'));

    await tester.tap(find.text('Relink'));
    await _settle(tester);
    expect(find.text('RELINK ALPACA PAPER?'), findsOneWidget);
    expect(find.text('Connect Alpaca Paper'), findsNothing);

    await tester.tap(find.text('CANCEL'));
    await _settle(tester);

    expect(await AlpacaCredentialStore.read(), isNotNull,
        reason: 'backing out of the dialog must not have wiped the credential');
    expect(find.text('Relink'), findsOneWidget);
  });
}
