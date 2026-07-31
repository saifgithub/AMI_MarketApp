/// Deep-link dispatcher (CR027).
///
/// One route table, not one `if` per feature — matches CR027's lock. The
/// same table serves both entry points into deep-linked navigation: a
/// tapped OS push ([PushNotificationListener]) today, and — once CR135
/// builds an in-app notification list — a tap on a row there, reusing this
/// exact dispatcher rather than a second mapping.
library;

import 'package:ami_trade/screens/sim/ticker_detail_screen.dart';
import 'package:ami_trade/services/notifications/notification_models.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';

typedef DeepLinkRoute = void Function(
  NavigatorState navigator,
  Map<String, dynamic> params,
);

abstract final class DeepLinkDispatcher {
  static final Map<String, DeepLinkRoute> _routes = {
    'open_holding_detail': _openHoldingDetail,
    // Reserved for future consumers not built in CR027 (CR095/CR109/BL11/
    // Room-verdict) — entries exist so their route string isn't silently
    // "unknown" the moment those CRs start calling notify() with them.
    'open_journal_entry': _stub,
    'open_room_verdict': _stub,
    'open_lesson': _stub,
    'open_game_close': _stub,
  };

  static void dispatch(NavigatorState navigator, DeepLink link) {
    final route = _routes[link.route];
    if (route == null) {
      // CR040: visible, not silently swallowed.
      if (kDebugMode) {
        debugPrint('DeepLinkDispatcher: unknown route "${link.route}"');
      }
      return;
    }
    route(navigator, link.params);
  }

  static void _openHoldingDetail(
    NavigatorState navigator,
    Map<String, dynamic> params,
  ) {
    final ticker = params['ticker'] as String?;
    if (ticker == null || ticker.isEmpty) return;
    navigator.push(
      MaterialPageRoute<void>(builder: (_) => TickerDetailScreen(ticker: ticker)),
    );
  }

  static void _stub(NavigatorState navigator, Map<String, dynamic> params) {}
}
