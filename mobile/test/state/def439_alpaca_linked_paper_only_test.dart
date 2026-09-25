/// DEF439 (Saiful, 2026-09-25: "add key validation. Check out alpaca key
/// format") — `alpacaLinkedProvider` means "linked to a confirmed PAPER
/// account", not merely "some credential is stored on this device."
///
/// Before this fix, every "linked" gate downstream (the Portfolio Alpaca
/// section, the trade ticket's destination picker, the Settings row) read
/// `AlpacaCredentialStore.isLinked()` directly — true for ANY stored
/// credential, live or paper — which is how a live-linked account ended up
/// labelled "ALPACA PAPER" and offered as a trade destination (DEF439's own
/// root complaint, and DEF430 round-1 MINOR-1). This file pins the provider
/// semantics directly (no widget tree needed — `alpacaLinkedProvider` and
/// `alpacaStoredNonPaperProvider` are plain `FutureProvider`s over
/// `AlpacaClient`/`AlpacaCredentialStore`), plus the specific regression a
/// mutation of either check would reintroduce.
library;

import 'package:ami_trade/services/alpaca/alpaca_credential_store.dart';
import 'package:ami_trade/state/alpaca_providers.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_secure_storage/test/test_flutter_secure_storage_platform.dart';
import 'package:flutter_secure_storage_platform_interface/flutter_secure_storage_platform_interface.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  setUp(() {
    FlutterSecureStoragePlatform.instance =
        TestFlutterSecureStoragePlatform(<String, String>{});
    SharedPreferences.setMockInitialValues({});
    AlpacaCredentialStore.resetCacheForTest();
  });

  group('alpacaLinkedProvider — DEF439 paper-only semantics', () {
    test('false when nothing is stored', () async {
      final container = ProviderContainer();
      addTearDown(container.dispose);
      expect(await container.read(alpacaLinkedProvider.future), isFalse);
    });

    test('true for a stored paper-host credential', () async {
      await AlpacaCredentialStore.save('PKKEY', 'secret',
          baseUrl: kDefaultAlpacaBaseUrl);
      final container = ProviderContainer();
      addTearDown(container.dispose);
      expect(await container.read(alpacaLinkedProvider.future), isTrue);
    });

    test(
        'false for a stored LIVE-host credential — this is the DEF439 '
        'regression guard: before this fix, this read true because the old '
        'provider only checked `isLinked()`, not the host', () async {
      await AlpacaCredentialStore.save('AKKEY', 'secret',
          baseUrl: 'https://api.alpaca.markets');
      final container = ProviderContainer();
      addTearDown(container.dispose);
      expect(
        await container.read(alpacaLinkedProvider.future),
        isFalse,
        reason: 'a live-linked account must never read as "linked" — every '
            'downstream gate (destination picker, portfolio section, '
            'settings row) depends on this being false',
      );
    });
  });

  group('alpacaStoredNonPaperProvider — DEF439 relink signal', () {
    test('false when nothing is stored', () async {
      final container = ProviderContainer();
      addTearDown(container.dispose);
      expect(
          await container.read(alpacaStoredNonPaperProvider.future), isFalse);
    });

    test('false for a stored paper-host credential', () async {
      await AlpacaCredentialStore.save('PKKEY', 'secret',
          baseUrl: kDefaultAlpacaBaseUrl);
      final container = ProviderContainer();
      addTearDown(container.dispose);
      expect(
          await container.read(alpacaStoredNonPaperProvider.future), isFalse);
    });

    test(
        'true for a stored non-paper (live) credential — the case only '
        'reachable from before DEF439', () async {
      await AlpacaCredentialStore.save('AKKEY', 'secret',
          baseUrl: 'https://api.alpaca.markets');
      final container = ProviderContainer();
      addTearDown(container.dispose);
      expect(
        await container.read(alpacaStoredNonPaperProvider.future),
        isTrue,
        reason: 'this is exactly the signal the Settings row / Portfolio '
            'section use to show "relink" instead of silently rendering '
            'nothing or rendering the live account as paper',
      );
    });

    test(
        'alpacaLinkedProvider and alpacaStoredNonPaperProvider are never '
        'both true — mutation guard for the relink-prompt gating logic',
        () async {
      for (final baseUrl in [
        kDefaultAlpacaBaseUrl,
        'https://api.alpaca.markets',
        'https://paper-api-xyz.alpaca.markets',
      ]) {
        AlpacaCredentialStore.resetCacheForTest();
        await AlpacaCredentialStore.save('KEY', 'secret', baseUrl: baseUrl);
        final container = ProviderContainer();
        addTearDown(container.dispose);
        final linked = await container.read(alpacaLinkedProvider.future);
        final storedNonPaper =
            await container.read(alpacaStoredNonPaperProvider.future);
        expect(linked && storedNonPaper, isFalse,
            reason: 'for baseUrl=$baseUrl — a caller that shows the relink '
                'prompt whenever `!linked` (see portfolio_screen.dart, '
                'settings_screen.dart) must never ALSO show the normal '
                'linked UI for the same state');
      }
    });
  });
}
