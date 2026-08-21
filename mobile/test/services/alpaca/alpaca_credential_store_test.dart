/// CR202 — the Alpaca key pair lives in the Keychain / Keystore and nowhere
/// else.
///
/// This is the whole point of the change, so it is asserted rather than
/// assumed: before CR202 the key was POSTed to the AMI backend and stored in
/// Postgres, which cost us DEF044, DEF181, DEF182 and DEF185. The most
/// important test here is the one proving nothing lands in SharedPreferences —
/// that is cleartext and rides device backups, which is exactly how CR125's
/// bearer-token leak worked.
///
/// Uses flutter_secure_storage's own bundled test double, backed by a plain
/// in-memory map, the same way device_user_test.dart does.
library;

import 'package:ami_trade/services/alpaca/alpaca_credential_store.dart';
import 'package:flutter_secure_storage/test/test_flutter_secure_storage_platform.dart';
import 'package:flutter_secure_storage_platform_interface/flutter_secure_storage_platform_interface.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

const _kKeyIdKey = 'ami.alpaca_key_id';
const _kSecretKey = 'ami.alpaca_secret';
const _kModeKey = 'ami.alpaca_auth_mode';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  late Map<String, String> secureData;

  setUp(() {
    secureData = <String, String>{};
    FlutterSecureStoragePlatform.instance =
        TestFlutterSecureStoragePlatform(secureData);
    SharedPreferences.setMockInitialValues({});
    AlpacaCredentialStore.resetCacheForTest();
  });

  group('storage location', () {
    test('unlinked by default', () async {
      expect(await AlpacaCredentialStore.read(), isNull);
      expect(await AlpacaCredentialStore.isLinked(), isFalse);
    });

    test('a saved pair round-trips through secure storage', () async {
      await AlpacaCredentialStore.save('PKTEST123', 'secret-abc');
      AlpacaCredentialStore.resetCacheForTest();

      final creds = await AlpacaCredentialStore.read();
      expect(creds, isNotNull);
      expect(creds!.keyId, 'PKTEST123');
      expect(creds.secret, 'secret-abc');
      expect(creds.mode, AlpacaAuthMode.apiKey);
      expect(secureData[_kKeyIdKey], 'PKTEST123');
      expect(secureData[_kSecretKey], 'secret-abc');
    });

    test('nothing is written to SharedPreferences', () async {
      await AlpacaCredentialStore.save('PKTEST123', 'secret-abc');
      final prefs = await SharedPreferences.getInstance();
      expect(prefs.getKeys(), isEmpty,
          reason: 'SharedPreferences is cleartext and rides device backups — '
              'a credential must never land there (CR125/CR202)');
    });

    test('clear() wipes every key, not just the id', () async {
      await AlpacaCredentialStore.save('PKTEST123', 'secret-abc');
      await AlpacaCredentialStore.clear();

      expect(await AlpacaCredentialStore.read(), isNull);
      expect(secureData.containsKey(_kKeyIdKey), isFalse);
      expect(secureData.containsKey(_kSecretKey), isFalse);
      expect(secureData.containsKey(_kModeKey), isFalse);
    });
  });

  group('half-written pairs', () {
    test('a key with no secret reads as unlinked, not as an empty credential',
        () async {
      secureData[_kKeyIdKey] = 'PKTEST123';
      AlpacaCredentialStore.resetCacheForTest();

      expect(await AlpacaCredentialStore.read(), isNull,
          reason: 'an empty secret would be sent to Alpaca and come back 401, '
              'which reads to the user as "Alpaca is broken" rather than '
              '"you are not linked"');
    });

    test('an empty string is not a credential', () async {
      secureData[_kKeyIdKey] = 'PKTEST123';
      secureData[_kSecretKey] = '';
      AlpacaCredentialStore.resetCacheForTest();

      expect(await AlpacaCredentialStore.read(), isNull);
    });
  });

  group('auth mode', () {
    test('oauth mode round-trips', () async {
      await AlpacaCredentialStore.save('tok', 'refresh',
          mode: AlpacaAuthMode.oauth);
      AlpacaCredentialStore.resetCacheForTest();

      expect((await AlpacaCredentialStore.read())!.mode, AlpacaAuthMode.oauth);
    });

    test('an absent mode marker defaults to apiKey', () async {
      secureData[_kKeyIdKey] = 'PKTEST123';
      secureData[_kSecretKey] = 'secret-abc';
      AlpacaCredentialStore.resetCacheForTest();

      expect((await AlpacaCredentialStore.read())!.mode, AlpacaAuthMode.apiKey);
    });
  });
}
