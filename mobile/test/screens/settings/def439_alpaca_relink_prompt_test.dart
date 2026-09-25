/// DEF439 — a credential stored before this fix, resolving to a non-paper
/// (live) host, must render as NOT linked, with a relink prompt — not
/// silently as though it were an ordinary paper link, and not silently as
/// though nothing were stored at all.
///
/// Harness mirrors `cr236_credits_row_test.dart`: the real `SettingsScreen`
/// with the heavy notifiers (`mandate`, `sim`, `auth`) fixed to a no-network
/// state. `alpacaLinkedProvider`/`alpacaStoredNonPaperProvider` are NOT
/// overridden — both are pure local reads (`AlpacaCredentialStore` +
/// `isAlpacaPaperHost`, no network) — so the real `flutter_secure_storage`
/// test double drives them exactly as it would on-device.
///
/// The Connected Accounts section is well down `SettingsScreen`'s `ListView`
/// (a real, lazily-built sliver list, not a plain `Column` — elements past
/// the initial viewport are not built until scrolled into range), so every
/// test scrolls to it via `scrollUntilVisible` before asserting, the same
/// pattern `cr236_credits_row_test.dart`/`cr220_profile_fields_test.dart` use.
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

class _FakeApiClient extends ApiClient {
  _FakeApiClient() : super(baseUrl: 'test://localhost');
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

Future<void> _pumpSettings(WidgetTester tester) async {
  const size = Size(390, 900);
  tester.view.physicalSize = size;
  tester.view.devicePixelRatio = 1.0;
  addTearDown(tester.view.reset);

  await tester.pumpWidget(
    ProviderScope(
      overrides: [
        mandateNotifierProvider.overrideWith((ref) => _FixedMandateNotifier(ref)),
        simNotifierProvider.overrideWith((ref) => _NoopSimNotifier(ref)),
        authNotifierProvider.overrideWith((ref) => _ClaimedAuthNotifier(ref)),
        myHandleProvider.overrideWith((ref) async => throw Exception('no network')),
        apiClientProvider.overrideWithValue(_FakeApiClient()),
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

/// Scrolls the settings `ListView` until "CONNECTED ACCOUNTS" is built and
/// on-screen — see the file docstring for why this is necessary.
Future<void> _scrollToAlpacaSection(WidgetTester tester) async {
  await tester.scrollUntilVisible(
    find.text('CONNECTED ACCOUNTS'),
    300,
    scrollable: find.byType(Scrollable).first,
  );
  await tester.pump(const Duration(milliseconds: 50));
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  setUp(() {
    FlutterSecureStoragePlatform.instance =
        TestFlutterSecureStoragePlatform(<String, String>{});
    SharedPreferences.setMockInitialValues({});
    AlpacaCredentialStore.resetCacheForTest();
  });

  group('DEF439 — Settings Connected Accounts row', () {
    testWidgets('unlinked (nothing stored) shows plain "Not connected"',
        (tester) async {
      await _pumpSettings(tester);
      await _scrollToAlpacaSection(tester);

      expect(find.text('Not connected'), findsOneWidget);
      expect(find.text('Connect'), findsOneWidget);
      expect(find.textContaining('relink'), findsNothing);
    });

    testWidgets('a stored PAPER credential shows "Connected"', (tester) async {
      await AlpacaCredentialStore.save('PKKEY', 'secret',
          baseUrl: kDefaultAlpacaBaseUrl);
      await _pumpSettings(tester);
      await _scrollToAlpacaSection(tester);

      expect(find.text('Connected'), findsOneWidget);
      expect(find.text('Disconnect'), findsOneWidget);
    });

    testWidgets(
        'a stored LIVE (non-paper) credential renders as NOT linked, with '
        'a relink prompt — the DEF439 regression guard', (tester) async {
      await AlpacaCredentialStore.save('AKKEY', 'secret',
          baseUrl: 'https://api.alpaca.markets');
      await _pumpSettings(tester);
      await _scrollToAlpacaSection(tester);

      expect(find.text('Connected'), findsNothing,
          reason: 'a live account must never read as "Connected" the way a '
              'paper one does — that is DEF439\'s own root complaint');
      expect(
        find.textContaining('AMI now links Alpaca paper accounts only'),
        findsOneWidget,
        reason: 'must say WHY a relink is needed, not just "Not connected"',
      );
      expect(find.text('Relink'), findsOneWidget);
      expect(find.text('Disconnect'), findsNothing,
          reason: 'not linked, so there is nothing to disconnect — only '
              'relink');
    });

    testWidgets('tapping Relink clears the stale credential before opening '
        'the connect screen', (tester) async {
      await AlpacaCredentialStore.save('AKKEY', 'secret',
          baseUrl: 'https://api.alpaca.markets');
      await _pumpSettings(tester);
      await _scrollToAlpacaSection(tester);

      await tester.tap(find.text('Relink'));
      for (var i = 0; i < 4; i++) {
        await tester.pump(const Duration(milliseconds: 50));
      }

      expect(await AlpacaCredentialStore.isLinked(), isFalse,
          reason: 'the stale live credential must be cleared, not carried '
              'into the fresh link attempt');
      expect(find.text('Connect Alpaca Paper'), findsOneWidget,
          reason: 'the connect screen should now be open');
    });
  });
}
