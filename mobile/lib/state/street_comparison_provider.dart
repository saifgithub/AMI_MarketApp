/// CR260 / CR267 WP-21b — whether the verdict card shows "How the Street rates
/// it" under the Room's call.
///
/// §3a.3 of the Beta programme plan: the Street rating is "shown to Beta
/// testers after the verdict, with a source label, behind a setting". So the
/// default is ON (testers see it) and Settings can turn it off. A user who
/// turns it off stays off: the write happens only inside [setEnabled], never on
/// first render, so a later change of default still reaches installs that never
/// touched the switch (the [RoomViewModeNotifier] rule, CR106).
///
/// The setting only hides the card. The comparison itself is computed by the
/// backend after the verdict and is never an input to the Room.
library;

import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

const streetComparisonPrefsKey = 'ami_street_comparison_enabled';

class StreetComparisonSettingNotifier extends StateNotifier<bool> {
  StreetComparisonSettingNotifier() : super(true) {
    _hydrate();
  }

  @visibleForTesting
  StreetComparisonSettingNotifier.withoutHydration(super.initial);

  Future<void> _hydrate() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final stored = prefs.getBool(streetComparisonPrefsKey);
      if (stored != null) state = stored;
    } catch (_) {
      // Best-effort: an unreadable preference keeps the default.
    }
  }

  Future<void> setEnabled(bool enabled) async {
    state = enabled;
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setBool(streetComparisonPrefsKey, enabled);
    } catch (_) {}
  }
}

final streetComparisonEnabledProvider =
    StateNotifierProvider<StreetComparisonSettingNotifier, bool>((ref) {
  return StreetComparisonSettingNotifier();
});
