/// Riverpod state for the active backend mode (Alpha / Beta / Prod).
///
/// Hydrates from `SharedPreferences` on construction, **unless** the
/// build was compiled without `ALLOW_BACKEND_SWITCH` — in that case
/// the notifier forces `BackendMode.prod` and wipes any stored
/// override so a tester upgrading from TestFlight to App Store can't
/// accidentally keep pointing at the alpha box.
///
/// See `docs/08_tech/backend_modes.md`.
library;

import 'package:ami_trade/services/api/backend_modes.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

const _prefsKey = 'ami_backend_mode';


class BackendModeNotifier extends StateNotifier<BackendMode> {
  BackendModeNotifier() : super(BackendUrls.defaultMode) {
    _hydrate();
  }

  Future<void> _hydrate() async {
    if (!kAllowBackendSwitch) {
      // Locked build (prod / App Store). Force prod and clear any
      // stored dev-flavor leftover. The clear is best-effort.
      state = BackendUrls.lockedMode;
      try {
        final prefs = await SharedPreferences.getInstance();
        await prefs.remove(_prefsKey);
      } catch (_) {/* best-effort */}
      return;
    }

    try {
      final prefs = await SharedPreferences.getInstance();
      final stored = backendModeFromString(prefs.getString(_prefsKey));
      if (stored != null && BackendUrls.availableModes.contains(stored)) {
        state = stored;
      }
    } catch (_) {
      // Fall back to the compile-time default (set in the super-call).
    }
  }

  /// Set the active mode. No-op on locked builds (the developer
  /// section that calls this is compiled out anyway, but be defensive).
  Future<void> setMode(BackendMode mode) async {
    if (!kAllowBackendSwitch) return;
    if (!BackendUrls.availableModes.contains(mode)) return;
    state = mode;
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString(_prefsKey, backendModeToString(mode));
    } catch (_) {/* best-effort persistence */}
  }
}


final backendModeProvider =
    StateNotifierProvider<BackendModeNotifier, BackendMode>((ref) {
  return BackendModeNotifier();
});


/// Convenience — the current active URL as a string. Returns null only
/// in the (impossible-by-design) case where the active mode has no URL
/// in this build. Callers should treat null as a programmer error;
/// `BackendUrls.availableModes` filtering should prevent it.
final activeBackendUrlProvider = Provider<String?>((ref) {
  final mode = ref.watch(backendModeProvider);
  return BackendUrls.urlFor(mode);
});
