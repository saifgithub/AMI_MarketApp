/// DEF439 (Saiful, 2026-09-25: "add key validation. Check out alpaca key
/// format") — only an Alpaca **paper** account can ever be linked.
///
/// Alpaca's own convention names paper key IDs "PK..." and live key IDs
/// "AK...", but does not document it, so an unrecognised prefix is never
/// hard-refused on that basis alone (see `alpaca_connect_screen.dart`'s file
/// docstring). The real, structural boundary is the endpoint: a paper key
/// pair gets a 401 from the live endpoint and vice versa. This file pins:
///
///   1. an "AK..." key ID is refused before any network call;
///   2. a non-paper host is refused by the endpoint field's own validator;
///   3. a "PK..." key on the (default) paper host reaches `validate()`;
///   4. an unknown-prefix key ID is NOT refused outright — it reaches the
///      endpoint check / `validate()` rather than being hard-blocked;
///   5. a 401 from `validate()` shows copy naming the live-key possibility.
///
/// Uses a fake `AlpacaClient` (matching `def419_per_account_test.dart`'s
/// `_FixedAlpacaClient` convention) injected via `alpacaClientProvider`, so
/// no real network call is made and `validate()` calls are recorded/counted.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/screens/settings/alpaca_connect_screen.dart';
import 'package:ami_trade/services/alpaca/alpaca_client.dart';
import 'package:ami_trade/services/alpaca/alpaca_credential_store.dart';
import 'package:ami_trade/state/alpaca_providers.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_secure_storage/test/test_flutter_secure_storage_platform.dart';
import 'package:flutter_secure_storage_platform_interface/flutter_secure_storage_platform_interface.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

class _RecordingAlpacaClient extends AlpacaClient {
  _RecordingAlpacaClient({this.throwsAuthFailure = false});

  final bool throwsAuthFailure;
  int validateCalls = 0;
  String? lastKeyId;
  String? lastBaseUrl;

  @override
  Future<void> validate(String keyId, String secret,
      {String baseUrl = kDefaultAlpacaBaseUrl}) async {
    validateCalls++;
    lastKeyId = keyId;
    lastBaseUrl = baseUrl;
    if (throwsAuthFailure) {
      throw const AlpacaException(401, 'unauthorized');
    }
  }
}

Future<void> _pump(WidgetTester tester, AlpacaClient client) async {
  await tester.pumpWidget(
    ProviderScope(
      overrides: [alpacaClientProvider.overrideWithValue(client)],
      child: const MaterialApp(
        localizationsDelegates: AppLocalizations.localizationsDelegates,
        supportedLocales: AppLocalizations.supportedLocales,
        home: AlpacaConnectScreen(),
      ),
    ),
  );
  for (var i = 0; i < 4; i++) {
    await tester.pump(const Duration(milliseconds: 50));
  }
}

const _testSecret =
    'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'; // 40 chars, matches the field's hint

// `_ApiKeyTab` lays out API KEY ID / SECRET KEY / API ENDPOINT as three
// `TextFormField`s directly inside ONE outer form `Column` (the labels are
// plain sibling `Text` widgets, not each wrapped in their own `Column`), so
// `find.ancestor(of: find.text(label), matching: find.byType(Column))`
// always resolves to that SAME outer column for every label — ordinal
// position within `find.byType(TextFormField)` is the only reliable way to
// target one field over another.
const _keyFieldIndex = 0;
const _secretFieldIndex = 1;
const _endpointFieldIndex = 2;

Future<void> _fillAndSubmit(
  WidgetTester tester, {
  required String keyId,
  String secret = _testSecret,
  String? baseUrl,
}) async {
  final fields = find.byType(TextFormField);
  await tester.enterText(fields.at(_keyFieldIndex), keyId);
  await tester.enterText(fields.at(_secretFieldIndex), secret);
  if (baseUrl != null) {
    await tester.enterText(fields.at(_endpointFieldIndex), baseUrl);
  }

  await tester.pump(const Duration(milliseconds: 50));
  // The CONNECT button can sit below the fold once the endpoint field and
  // its helper text are filled/visible — scroll the tab's own
  // SingleChildScrollView so it is hit-testable before tapping, rather than
  // assuming a tall-enough default test surface.
  await tester.dragUntilVisible(
    find.text('CONNECT'),
    find.byType(SingleChildScrollView).first,
    const Offset(0, -80),
  );
  await tester.pump(const Duration(milliseconds: 50));
  await tester.tap(find.text('CONNECT'));
  for (var i = 0; i < 6; i++) {
    await tester.pump(const Duration(milliseconds: 50));
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

  group('DEF439 — API key ID prefix', () {
    testWidgets('an "AK..." key ID is refused with no network call',
        (tester) async {
      final client = _RecordingAlpacaClient();
      await _pump(tester, client);

      await _fillAndSubmit(tester, keyId: 'AKTESTLIVEKEY123456789');

      expect(client.validateCalls, 0,
          reason: 'a recognisably-live key must never reach the network — '
              'refused before any call to validate()');
      expect(find.textContaining("That's a live-account key"), findsOneWidget);
      expect(find.textContaining('paper keys start with PK'), findsOneWidget);
    });

    testWidgets('the check is case-insensitive', (tester) async {
      final client = _RecordingAlpacaClient();
      await _pump(tester, client);

      await _fillAndSubmit(tester, keyId: 'aktestlivekey123456789');

      expect(client.validateCalls, 0);
      expect(find.textContaining("That's a live-account key"), findsOneWidget);
    });

    testWidgets(
        'a "PK..." key ID on the default paper host reaches validate()',
        (tester) async {
      final client = _RecordingAlpacaClient();
      await _pump(tester, client);

      await _fillAndSubmit(tester, keyId: 'PKTESTPAPERKEY123456789');

      expect(client.validateCalls, 1,
          reason: 'a paper-shaped key ID must pass through to the endpoint '
              'check');
      expect(client.lastKeyId, 'PKTESTPAPERKEY123456789');
      expect(client.lastBaseUrl, kDefaultAlpacaBaseUrl);
    });

    testWidgets(
        'a real-shaped 26-char PK key ID with a 44-char secret is accepted '
        '— no length rule, only the prefix/host checks', (tester) async {
      // Architect data point (2026-09-25): a real Alpaca paper key ID
      // measured 26 characters, its secret 44 — and lengths vary between
      // key generations, so nothing in this screen may assume a fixed
      // length for either field. This pins that directly, at exactly those
      // measured lengths, so a future length check would fail here first.
      const keyId26 = 'PK1234567890ABCDEFGHIJKLMN'; // 26 chars
      const secret44 =
          'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnop12'; // 44 chars
      expect(keyId26.length, 26);
      expect(secret44.length, 44);

      final client = _RecordingAlpacaClient();
      await _pump(tester, client);

      await _fillAndSubmit(tester, keyId: keyId26, secret: secret44);

      expect(client.validateCalls, 1);
      expect(client.lastKeyId, keyId26);
      expect(find.textContaining("That's a live-account key"), findsNothing);
      expect(find.textContaining('Required'), findsNothing);
    });

    testWidgets(
        'an unknown-prefix key ID is not refused outright — it reaches '
        'the endpoint check rather than being hard-blocked', (tester) async {
      final client = _RecordingAlpacaClient();
      await _pump(tester, client);

      await _fillAndSubmit(tester, keyId: 'ZZSOMENEWPREFIX123456');

      expect(find.textContaining("That's a live-account key"), findsNothing,
          reason: 'Alpaca does not document the PK/AK convention, so an '
              'unrecognised prefix must not be hard-refused on that basis '
              'alone');
      expect(client.validateCalls, 1,
          reason: 'an unrecognised prefix goes on to the real, structural '
              'check: the endpoint');
    });
  });

  group('DEF439 — API endpoint host', () {
    testWidgets('a non-paper (live) host is refused by the form validator',
        (tester) async {
      final client = _RecordingAlpacaClient();
      await _pump(tester, client);

      await _fillAndSubmit(
        tester,
        keyId: 'PKTESTPAPERKEY123456789',
        baseUrl: 'https://api.alpaca.markets',
      );

      expect(client.validateCalls, 0,
          reason: 'a live host must be refused by the field validator '
              'before the form can submit at all');
      expect(find.textContaining('Alpaca paper-trading host'), findsOneWidget);
    });

    testWidgets('a CR224 paper region/account variant host still validates',
        (tester) async {
      final client = _RecordingAlpacaClient();
      await _pump(tester, client);

      await _fillAndSubmit(
        tester,
        keyId: 'PKTESTPAPERKEY123456789',
        baseUrl: 'https://paper-api-xyz.alpaca.markets',
      );

      expect(client.validateCalls, 1,
          reason: 'CR224 exists for exactly this — a paper account Alpaca '
              'resolved to a different (still paper) host');
      expect(client.lastBaseUrl, 'https://paper-api-xyz.alpaca.markets');
    });
  });

  group('DEF439 — 401 from validate() shows the live-key hint', () {
    testWidgets('an auth failure names the live-key possibility',
        (tester) async {
      final client = _RecordingAlpacaClient(throwsAuthFailure: true);
      await _pump(tester, client);

      await _fillAndSubmit(tester, keyId: 'PKTESTPAPERKEY123456789');

      expect(client.validateCalls, 1);
      expect(find.textContaining('live-account key'), findsOneWidget,
          reason: 'a 401 may mean an unrecognised-prefix live key slipped '
              'past the AK check, so the copy must name that possibility, '
              'not only suggest a typo');
    });
  });

  group('DEF439 — no overflow at 320dp / 1.3x text scale', () {
    testWidgets('the AK-refusal error banner fits at 320dp width',
        (tester) async {
      tester.view.physicalSize = const Size(320, 900);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(tester.view.reset);

      final client = _RecordingAlpacaClient();
      await tester.pumpWidget(
        ProviderScope(
          overrides: [alpacaClientProvider.overrideWithValue(client)],
          child: const MediaQuery(
            data: MediaQueryData(size: Size(320, 900)),
            child: MaterialApp(
              localizationsDelegates: AppLocalizations.localizationsDelegates,
              supportedLocales: AppLocalizations.supportedLocales,
              home: AlpacaConnectScreen(),
            ),
          ),
        ),
      );
      for (var i = 0; i < 4; i++) {
        await tester.pump(const Duration(milliseconds: 50));
      }

      await _fillAndSubmit(tester, keyId: 'AKTESTLIVEKEY123456789');

      expect(tester.takeException(), isNull);
      expect(find.textContaining("That's a live-account key"), findsOneWidget);
    });

    testWidgets('the endpoint helper copy fits at 1.3x text scale on a '
        'baseline phone width', (tester) async {
      const size = Size(375, 900);
      tester.view.physicalSize = size;
      tester.view.devicePixelRatio = 1.0;
      addTearDown(tester.view.reset);

      final client = _RecordingAlpacaClient();
      await tester.pumpWidget(
        ProviderScope(
          overrides: [alpacaClientProvider.overrideWithValue(client)],
          child: const MediaQuery(
            data: MediaQueryData(size: size, textScaler: TextScaler.linear(1.3)),
            child: MaterialApp(
              localizationsDelegates: AppLocalizations.localizationsDelegates,
              supportedLocales: AppLocalizations.supportedLocales,
              home: AlpacaConnectScreen(),
            ),
          ),
        ),
      );
      for (var i = 0; i < 4; i++) {
        await tester.pump(const Duration(milliseconds: 50));
      }

      expect(tester.takeException(), isNull);
      // Two widgets carry this phrase today (the DEF430 disclosure banner
      // and the endpoint field's own helper text) — assert the endpoint
      // helper specifically rather than a substring both happen to share.
      expect(
        find.textContaining(
            'this cannot be a live-account endpoint'),
        findsOneWidget,
      );
    });
  });
}
