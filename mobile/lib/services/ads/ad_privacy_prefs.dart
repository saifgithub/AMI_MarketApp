/// CCPA "Do Not Sell" preference (CR122-COMPLIANCE, `ads.md:108`).
///
/// Persisted through the same [AdCapStore] seam MOBILE-B built (string KV on
/// SharedPreferences), read per programmatic request so a flip in Settings
/// applies to the very next ad without a restart, and it survives one — the
/// CR122 on-device test #5.
///
/// Failure direction (CR040): an UNREADABLE store restricts — `doNotSell()`
/// answers true, so AdMob gets `rdp=1` and never personalises on a pref we
/// could not read. The caps layer blocks ads on an unreadable store for the
/// same reason; a privacy setting must fail toward privacy, loudly.
library;

import 'package:ami_trade/services/ads/ad_frequency_caps.dart';
import 'package:flutter/foundation.dart';

class AdPrivacyPrefs {
  AdPrivacyPrefs(this._store);

  final AdCapStore _store;

  @visibleForTesting
  static const doNotSellKey = 'ads.ccpa_do_not_sell';

  /// Current CCPA choice; defaults to false (no opt-out recorded), true on
  /// an unreadable store (fail toward privacy).
  Future<bool> doNotSell() async {
    try {
      return await _store.read(doNotSellKey) == 'true';
    } catch (e) {
      debugPrint('CR122 CCPA pref unreadable — treating as Do-Not-Sell '
          '(restricted data processing) until it can be read: $e');
      return true;
    }
  }

  /// Persists the toggle. A failed write surfaces to the caller so Settings
  /// can tell the user the choice did not stick (never silently drop a
  /// privacy election).
  Future<void> setDoNotSell(bool value) =>
      _store.write(doNotSellKey, value ? 'true' : 'false');
}
