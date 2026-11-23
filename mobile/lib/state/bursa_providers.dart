/// CR282 lane F2 - Riverpod state for the Bursa switch: whether the build has
/// Bursa at all, and which book the Portfolio screen is showing.
///
/// [bursaEnabledProvider] wraps the compile-time `kBursaEnabled` so a widget
/// test can turn Bursa on without a `--dart-define`; production reads the const.
/// With it off nothing here reads storage or the network.
library;

import 'package:ami_trade/features/markets/bursa_flag.dart';
import 'package:ami_trade/features/markets/market.dart';
import 'package:ami_trade/services/device_user.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

final bursaEnabledProvider = Provider<bool>((ref) => kBursaEnabled);

/// The book the Portfolio screen shows. Starts US; with Bursa on, the last
/// choice is restored from local storage (per user, best-effort: a storage
/// failure leaves US, never breaks the screen).
class SelectedMarketNotifier extends StateNotifier<AppMarket> {
  SelectedMarketNotifier({required bool enabled})
      : _enabled = enabled,
        super(AppMarket.us) {
    if (enabled) _restore();
  }

  final bool _enabled;

  static String _key(String userId) => 'portfolio_market_$userId';

  Future<void> _restore() async {
    try {
      final userId = await DeviceUser.getOrCreate();
      final prefs = await SharedPreferences.getInstance();
      final saved = prefs.getString(_key(userId));
      if (!mounted || saved == null) return;
      if (saved == AppMarket.my.apiCode) state = AppMarket.my;
    } catch (e) {
      debugPrint('selected market restore failed: $e');
    }
  }

  Future<void> select(AppMarket market) async {
    if (!_enabled || state == market) return;
    state = market;
    try {
      final userId = await DeviceUser.getOrCreate();
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString(_key(userId), market.apiCode);
    } catch (e) {
      debugPrint('selected market persist failed: $e');
    }
  }
}

final selectedMarketProvider =
    StateNotifierProvider<SelectedMarketNotifier, AppMarket>((ref) {
  return SelectedMarketNotifier(enabled: ref.watch(bursaEnabledProvider));
});
