/// Device-stable user_id + persisted bearer token, via shared_preferences.
///
/// Pre-A7: only `device_user_id` was persisted, and the bearer token was
/// re-issued from scratch on every app launch. Adversarial audit (2026-05-18)
/// finding A2 closed the "device_user_id alone is proof of possession" hole,
/// so the bearer token must now ride alongside the device id and be replayed
/// to the backend on every bootstrap. Same property survives across launches.
library;

import 'dart:io' show Platform;

import 'package:device_info_plus/device_info_plus.dart';
import 'package:package_info_plus/package_info_plus.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:uuid/uuid.dart';

/// BL1 (AT:R33): device + build context shipped to /v1/auth/anon. All three
/// values are best-effort — a read failure on any of them yields null,
/// never blocks the bootstrap call.
class DeviceContext {
  const DeviceContext({this.deviceModel, this.osVersion, this.appVersion});
  final String? deviceModel;
  final String? osVersion;
  final String? appVersion;

  static Future<DeviceContext> read() async {
    String? deviceModel;
    String? osVersion;
    String? appVersion;
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
    } catch (_) {}
    return DeviceContext(
      deviceModel: deviceModel,
      osVersion: osVersion,
      appVersion: appVersion,
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
  static Future<String?> getToken() async {
    if (_cachedToken != null) return _cachedToken;
    final prefs = await SharedPreferences.getInstance();
    _cachedToken = prefs.getString(_kTokenKey);
    return _cachedToken;
  }

  /// Persist the backend-issued (user_id, token) pair. Call this after every
  /// successful bootstrap or claim — the returned user_id may differ from the
  /// one we sent (when the backend mints fresh per A2).
  static Future<void> setIdAndToken(String userId, String token) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_kIdKey, userId);
    await prefs.setString(_kTokenKey, token);
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
    await prefs.remove(_kTokenKey);
    _cachedId = null;
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
}
