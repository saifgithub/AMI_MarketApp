/// Device-stable user_id (shared_preferences) + persisted bearer token
/// (flutter_secure_storage, CR125).
///
/// Pre-A7: only `device_user_id` was persisted, and the bearer token was
/// re-issued from scratch on every app launch. Adversarial audit (2026-05-18)
/// finding A2 closed the "device_user_id alone is proof of possession" hole,
/// so the bearer token must now ride alongside the device id and be replayed
/// to the backend on every bootstrap. Same property survives across launches.
///
/// CR125 (security review H8): the bearer token used to live in
/// SharedPreferences — cleartext, and riding Android Auto Backup / iOS
/// iCloud-iTunes backups, so anyone with a device backup read it and gained
/// permanent impersonation. It now lives in the Keychain
/// (`first_unlock_this_device` — decryptable only after the device's first
/// unlock post-boot, and excluded from backups by construction) / Android
/// Keystore (`encryptedSharedPreferences`, also backup-excluded via
/// `android:allowBackup="false"` in AndroidManifest.xml). `device_user_id`,
/// the install id, and the onboarding session id stay on SharedPreferences —
/// none of them is a credential.
library;

import 'dart:io' show Platform;

import 'package:device_info_plus/device_info_plus.dart';
import 'package:flutter/foundation.dart' show visibleForTesting;
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:package_info_plus/package_info_plus.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:uuid/uuid.dart';

/// BL1 (AT:R33): device + build context shipped to /v1/auth/anon. All three
/// values are best-effort — a read failure on any of them yields null,
/// never blocks the bootstrap call.
class DeviceContext {
  const DeviceContext({
    this.deviceModel,
    this.osVersion,
    this.appVersion,
    this.buildNumber,
  });
  final String? deviceModel;
  final String? osVersion;
  final String? appVersion;

  /// CR121 — the numeric build number alone (e.g. 26 out of "0.1.0+26"),
  /// parsed straight from `PackageInfo.buildNumber` rather than re-derived
  /// from [appVersion] by string-splitting it a second time. Null on the
  /// same best-effort basis as the other fields. This is what the version
  /// gate compares against the server's floor — a single integer, not a
  /// semver parse.
  final int? buildNumber;

  static Future<DeviceContext> read() async {
    String? deviceModel;
    String? osVersion;
    String? appVersion;
    int? buildNumber;
    try {
      final di = DeviceInfoPlugin();
      if (Platform.isIOS) {
        final i = await di.iosInfo;
        deviceModel = i.utsname.machine; // e.g. "iPhone15,2"
        osVersion = '${i.systemName} ${i.systemVersion}'; // "iOS 18.2"
      } else if (Platform.isAndroid) {
        final a = await di.androidInfo;
        deviceModel = '${a.manufacturer} ${a.model}';
        osVersion = 'Android ${a.version.release}';
      }
    } catch (_) {
      // device_info_plus can fail on simulators / unusual configs — fine.
    }
    try {
      final p = await PackageInfo.fromPlatform();
      appVersion = '${p.version}+${p.buildNumber}'; // e.g. "0.1.0+26"
      buildNumber = int.tryParse(p.buildNumber);
    } catch (_) {}
    return DeviceContext(
      deviceModel: deviceModel,
      osVersion: osVersion,
      appVersion: appVersion,
      buildNumber: buildNumber,
    );
  }
}

class DeviceUser {
  DeviceUser._();

  static const String _kIdKey = 'ami.device_user_id';
  static const String _kTokenKey = 'ami.bearer_token';
  // BL2 (AT:R33): per-install stable identifier — generated once on first
  // launch and NEVER overwritten (unlike _kIdKey, which gets replaced with
  // the adopted user_id on claim). Keys the user_devices table so two
  // phones on one Apple ID surface as two device rows under one user.
  static const String _kInstallIdKey = 'ami.device_install_id';
  // BL13 (AT:R32 backend, AT:R37 mobile wiring): session_id returned by
  // /v1/onboarding/start. Persisted so the eventual claim call can pass it
  // through to /v1/auth/*, letting the backend stamp `claimed_user_id` on
  // the OnboardingSession row. Cleared on successful claim (one-shot).
  static const String _kOnboardingSessionIdKey = 'ami.onboarding_session_id';
  static String? _cachedId;
  static String? _cachedToken;
  static String? _cachedInstallId;
  static String? _cachedOnboardingSessionId;

  /// CR125 — Keychain on iOS (`first_unlock_this_device`: decryptable only
  /// once the device has been unlocked at least once since boot, never
  /// synced via iCloud Keychain), Keystore-backed EncryptedSharedPreferences
  /// on Android. `resetOnError` recovers from a corrupted keystore (e.g. a
  /// restored-from-backup device with no matching key) by wiping the secure
  /// store rather than throwing — the caller sees "no token", which is
  /// exactly the re-auth path already in place for a first launch.
  static const FlutterSecureStorage _secureStorage = FlutterSecureStorage(
    iOptions: IOSOptions(
      accessibility: KeychainAccessibility.first_unlock_this_device,
    ),
    aOptions: AndroidOptions(
      encryptedSharedPreferences: true,
      resetOnError: true,
    ),
  );

  /// Return the persisted user_id, minting one on first launch.
  static Future<String> getOrCreate() async {
    if (_cachedId != null) return _cachedId!;
    final prefs = await SharedPreferences.getInstance();
    var id = prefs.getString(_kIdKey);
    if (id == null) {
      id = const Uuid().v4();
      await prefs.setString(_kIdKey, id);
    }
    _cachedId = id;
    return id;
  }

  /// BL2: return the stable per-install id, minting once. NEVER overwritten
  /// by setIdAndToken or claim — survives across user-id rebinds.
  static Future<String> getOrCreateInstallId() async {
    if (_cachedInstallId != null) return _cachedInstallId!;
    final prefs = await SharedPreferences.getInstance();
    var id = prefs.getString(_kInstallIdKey);
    if (id == null) {
      id = const Uuid().v4();
      await prefs.setString(_kInstallIdKey, id);
    }
    _cachedInstallId = id;
    return id;
  }

  /// Return the persisted bearer token, or null on first launch (or after
  /// a `clear()` call). Caller is responsible for re-bootstrapping when null.
  ///
  /// CR125 first-launch migration: an install that predates the secure-
  /// storage move still has its token sitting in plaintext SharedPreferences.
  /// The first read here moves it across and deletes the plaintext copy.
  /// Idempotent and interruption-safe:
  ///   - normal case: secure storage has the value on every call after the
  ///     first — the legacy branch never runs again.
  ///   - interrupted after the secure write but before the prefs removal
  ///     (app killed mid-migration): the secure value already reads back
  ///     fine, and the leftover plaintext key is swept on this same call
  ///     rather than being left to linger indefinitely.
  ///   - interrupted before the secure write ever lands: secure storage is
  ///     still empty, so the next call just retries the whole migration.
  static Future<String?> getToken() async {
    if (_cachedToken != null) return _cachedToken;
    final secure = await _secureStorage.read(key: _kTokenKey);
    final prefs = await SharedPreferences.getInstance();
    if (secure != null) {
      _cachedToken = secure;
      if (prefs.containsKey(_kTokenKey)) {
        await prefs.remove(_kTokenKey);
      }
      return secure;
    }
    final legacy = prefs.getString(_kTokenKey);
    if (legacy != null) {
      await _secureStorage.write(key: _kTokenKey, value: legacy);
      await prefs.remove(_kTokenKey);
      _cachedToken = legacy;
      return legacy;
    }
    return null;
  }

  /// Persist the backend-issued (user_id, token) pair. Call this after every
  /// successful bootstrap or claim — the returned user_id may differ from the
  /// one we sent (when the backend mints fresh per A2). `user_id` isn't a
  /// credential, so it stays on SharedPreferences; the token goes to secure
  /// storage only (CR125).
  static Future<void> setIdAndToken(String userId, String token) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_kIdKey, userId);
    await _secureStorage.write(key: _kTokenKey, value: token);
    // Defensive sweep: strip a lingering plaintext copy in case a
    // first-launch migration was interrupted between its own write+remove.
    if (prefs.containsKey(_kTokenKey)) {
      await prefs.remove(_kTokenKey);
    }
    _cachedId = userId;
    _cachedToken = token;
  }

  /// Wipe both — used by sign-out (Phase 4). Install id + any pending
  /// onboarding session id survive (the install id is per-physical-device
  /// forever; a pending onboarding session id is one-shot and clears on
  /// successful claim).
  static Future<void> clear() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(_kIdKey);
    await prefs.remove(_kTokenKey); // sweep a stray legacy plaintext copy
    await _secureStorage.delete(key: _kTokenKey);
    _cachedId = null;
    _cachedToken = null;
  }

  /// CR125 — wipe only the dead credential, keeping `device_user_id`. Used
  /// by the [ApiClient.onUnauthorized] recovery path (an expired or revoked
  /// token), as opposed to [clear], which an explicit user-initiated
  /// sign-out uses to also drop the device id so the next bootstrap can't
  /// be mistaken for the signed-out identity.
  static Future<void> clearTokenOnly() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(_kTokenKey); // sweep a stray legacy plaintext copy
    await _secureStorage.delete(key: _kTokenKey);
    _cachedToken = null;
  }

  /// BL13: persist the OnboardingSession id returned by /v1/onboarding/start.
  /// Called from OnboardingNotifier.start() so a backgrounded app can still
  /// stamp claimed_user_id when the user comes back and signs in.
  static Future<void> setOnboardingSessionId(String sessionId) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_kOnboardingSessionIdKey, sessionId);
    _cachedOnboardingSessionId = sessionId;
  }

  /// Read the pending OnboardingSession id (null if none).
  static Future<String?> getOnboardingSessionId() async {
    if (_cachedOnboardingSessionId != null) return _cachedOnboardingSessionId;
    final prefs = await SharedPreferences.getInstance();
    _cachedOnboardingSessionId = prefs.getString(_kOnboardingSessionIdKey);
    return _cachedOnboardingSessionId;
  }

  /// Drop the pending OnboardingSession id — call after a successful claim
  /// so a fresh onboarding can never double-stamp the same session row.
  static Future<void> clearOnboardingSessionId() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(_kOnboardingSessionIdKey);
    _cachedOnboardingSessionId = null;
  }

  /// CR125 — drop the in-memory caches between test cases, so a fake
  /// SharedPreferences/secure-storage backend swapped in by one test can't
  /// leak a cached value into the next. Production code never calls this;
  /// the real app process only ever cold-starts once.
  @visibleForTesting
  static void resetCacheForTest() {
    _cachedId = null;
    _cachedToken = null;
    _cachedInstallId = null;
    _cachedOnboardingSessionId = null;
  }
}
