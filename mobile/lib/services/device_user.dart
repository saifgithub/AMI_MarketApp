/// Device-stable user_id + persisted bearer token, via shared_preferences.
///
/// Pre-A7: only `device_user_id` was persisted, and the bearer token was
/// re-issued from scratch on every app launch. Adversarial audit (2026-05-18)
/// finding A2 closed the "device_user_id alone is proof of possession" hole,
/// so the bearer token must now ride alongside the device id and be replayed
/// to the backend on every bootstrap. Same property survives across launches.
library;

import 'package:shared_preferences/shared_preferences.dart';
import 'package:uuid/uuid.dart';

class DeviceUser {
  DeviceUser._();

  static const String _kIdKey = 'ami.device_user_id';
  static const String _kTokenKey = 'ami.bearer_token';
  static String? _cachedId;
  static String? _cachedToken;

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

  /// Wipe both — used by sign-out (Phase 4).
  static Future<void> clear() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(_kIdKey);
    await prefs.remove(_kTokenKey);
    _cachedId = null;
    _cachedToken = null;
  }
}
