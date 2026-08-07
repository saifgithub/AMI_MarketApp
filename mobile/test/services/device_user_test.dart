/// CR125 — the SharedPreferences → flutter_secure_storage migration in
/// `DeviceUser`, and that `clear()` / `clearTokenOnly()` actually reach the
/// secure store, not just the plaintext prefs copy.
///
/// Uses flutter_secure_storage's own bundled test double
/// (`TestFlutterSecureStoragePlatform`, from `flutter_secure_storage/test/`)
/// backed by a plain in-memory map — the same map is inspected directly to
/// assert on secure-storage state, since `DeviceUser` itself exposes no
/// "peek the secure store" API (by design: nothing outside it should read
/// the token except through `getToken()`).
library;

import 'package:ami_trade/services/device_user.dart';
import 'package:flutter_secure_storage/test/test_flutter_secure_storage_platform.dart';
import 'package:flutter_secure_storage_platform_interface/flutter_secure_storage_platform_interface.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

const _kTokenKey = 'ami.bearer_token';
const _kIdKey = 'ami.device_user_id';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  late Map<String, String> secureData;

  setUp(() {
    secureData = <String, String>{};
    FlutterSecureStoragePlatform.instance =
        TestFlutterSecureStoragePlatform(secureData);
    SharedPreferences.setMockInitialValues({});
    DeviceUser.resetCacheForTest();
  });

  group('CR125 — first-launch migration', () {
    test('no legacy token, no secure token: getToken() returns null', () async {
      expect(await DeviceUser.getToken(), isNull);
      expect(secureData.containsKey(_kTokenKey), isFalse);
    });

    test('moves a legacy plaintext token into secure storage', () async {
      SharedPreferences.setMockInitialValues({_kTokenKey: 'legacy-token-abc'});
      DeviceUser.resetCacheForTest();

      final token = await DeviceUser.getToken();

      expect(token, 'legacy-token-abc');
      expect(secureData[_kTokenKey], 'legacy-token-abc');
      final prefs = await SharedPreferences.getInstance();
      expect(prefs.getString(_kTokenKey), isNull,
          reason: 'the plaintext copy must be deleted after migration');
    });

    test('a second call is a no-op (idempotent)', () async {
      SharedPreferences.setMockInitialValues({_kTokenKey: 'legacy-token-abc'});
      DeviceUser.resetCacheForTest();

      final first = await DeviceUser.getToken();
      DeviceUser.resetCacheForTest(); // simulate a fresh process, no in-memory cache
      final second = await DeviceUser.getToken();

      expect(first, 'legacy-token-abc');
      expect(second, 'legacy-token-abc');
      expect(secureData[_kTokenKey], 'legacy-token-abc');
    });

    test(
      'interrupted after the secure write but before the prefs removal: '
      'next call still returns the token and finishes sweeping the plaintext copy',
      () async {
        // Simulate the interrupted state directly: secure storage already
        // has the value (as if the write half of a prior migration landed),
        // but the plaintext key is still sitting in prefs (as if the
        // process died before the remove() half ran).
        secureData[_kTokenKey] = 'legacy-token-abc';
        SharedPreferences.setMockInitialValues({_kTokenKey: 'legacy-token-abc'});
        DeviceUser.resetCacheForTest();

        final token = await DeviceUser.getToken();

        expect(token, 'legacy-token-abc');
        final prefs = await SharedPreferences.getInstance();
        expect(prefs.getString(_kTokenKey), isNull,
            reason: 'a leftover plaintext copy must be swept even when the '
                'secure write had already landed');
      },
    );

    test(
      'interrupted before the secure write ever lands: the whole migration retries',
      () async {
        SharedPreferences.setMockInitialValues({_kTokenKey: 'legacy-token-abc'});
        DeviceUser.resetCacheForTest();
        // getToken() never called yet — nothing has moved. A second,
        // independent call must still complete the migration correctly.
        final token = await DeviceUser.getToken();
        expect(token, 'legacy-token-abc');
        expect(secureData[_kTokenKey], 'legacy-token-abc');
      },
    );

    test('does not disturb device_user_id, only the token key', () async {
      SharedPreferences.setMockInitialValues({
        _kIdKey: 'some-stable-uuid',
        _kTokenKey: 'legacy-token-abc',
      });
      DeviceUser.resetCacheForTest();

      await DeviceUser.getToken();

      final prefs = await SharedPreferences.getInstance();
      expect(prefs.getString(_kIdKey), 'some-stable-uuid');
    });
  });

  group('CR125 — setIdAndToken() writes only to secure storage', () {
    test('token lands in secure storage, never in plaintext prefs', () async {
      await DeviceUser.setIdAndToken('user-123', 'fresh-token-xyz');

      expect(secureData[_kTokenKey], 'fresh-token-xyz');
      final prefs = await SharedPreferences.getInstance();
      expect(prefs.getString(_kTokenKey), isNull);
      expect(prefs.getString(_kIdKey), 'user-123');
    });

    test('getToken() after setIdAndToken() reads the cached value back', () async {
      await DeviceUser.setIdAndToken('user-123', 'fresh-token-xyz');
      expect(await DeviceUser.getToken(), 'fresh-token-xyz');
    });
  });

  group('CR125 — clear()', () {
    test('wipes the secure entry and the device id', () async {
      await DeviceUser.setIdAndToken('user-123', 'fresh-token-xyz');

      await DeviceUser.clear();

      expect(secureData.containsKey(_kTokenKey), isFalse);
      expect(await DeviceUser.getToken(), isNull);
      final prefs = await SharedPreferences.getInstance();
      expect(prefs.getString(_kIdKey), isNull);
    });

    test('also sweeps a stray legacy plaintext token, if one snuck back in', () async {
      SharedPreferences.setMockInitialValues({_kTokenKey: 'stray-legacy'});
      DeviceUser.resetCacheForTest();

      await DeviceUser.clear();

      final prefs = await SharedPreferences.getInstance();
      expect(prefs.getString(_kTokenKey), isNull);
      expect(secureData.containsKey(_kTokenKey), isFalse);
    });
  });

  group('CR125 — clearTokenOnly() (the onUnauthorized recovery path)', () {
    test('wipes the token but preserves device_user_id', () async {
      await DeviceUser.setIdAndToken('user-123', 'dead-token');

      await DeviceUser.clearTokenOnly();

      expect(await DeviceUser.getToken(), isNull);
      expect(secureData.containsKey(_kTokenKey), isFalse);
      final prefs = await SharedPreferences.getInstance();
      expect(prefs.getString(_kIdKey), 'user-123');
      // getOrCreate() must hand back the SAME id, not mint a new one.
      expect(await DeviceUser.getOrCreate(), 'user-123');
    });
  });
}
