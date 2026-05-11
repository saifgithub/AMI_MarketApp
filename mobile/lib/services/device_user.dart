/// Device-stable user_id, persisted via shared_preferences.
///
/// Pre-auth, the iPhone has no real user_id — but Coach Your Agent needs a
/// stable key so the user's overlay versions survive across app launches and
/// across 1-on-1 sessions. We mint a UUID once on first launch and reuse it
/// forever (until auth, when we'll migrate to the real user_id).
library;

import 'package:shared_preferences/shared_preferences.dart';
import 'package:uuid/uuid.dart';

class DeviceUser {
  DeviceUser._();

  static const String _kPrefKey = 'ami.device_user_id';
  static String? _cached;

  static Future<String> getOrCreate() async {
    if (_cached != null) return _cached!;
    final prefs = await SharedPreferences.getInstance();
    var id = prefs.getString(_kPrefKey);
    if (id == null) {
      id = const Uuid().v4();
      await prefs.setString(_kPrefKey, id);
    }
    _cached = id;
    return id;
  }
}
