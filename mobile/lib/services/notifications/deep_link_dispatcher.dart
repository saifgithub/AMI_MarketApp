/// Deep-link dispatcher (CR027; CR232 round 2 routes it through the
/// owning tab's nested Navigator).
///
/// One route table, not one `if` per feature — matches CR027's lock. The
/// same table serves both entry points into deep-linked navigation: a
/// tapped OS push ([PushNotificationListener]) today, and — since CR135 —
/// a tap on a row in [NotificationCentreScreen], reusing this exact
/// dispatcher rather than a second mapping.
///
/// **CR232 round 2 (MAJOR-1).** Before this, `dispatch` took a raw
/// `NavigatorState` and the caller decided which one — `PushNotificationListener`
/// passed the ROOT navigator (`appNavigatorKey`, the only one reachable from a
/// push-tap callback, which has no `BuildContext`), so a notification-opened
/// page landed ABOVE `HomeShell`'s Scaffold and covered the persistent chrome
/// CR232 exists to guarantee. Every other push site in the app resolves
/// through `Navigator.of(context)` inside a tab's own nested Navigator
/// (`home_shell.dart`'s `_TabNavigator`) and never had this problem; this was
/// the one entry point with no `BuildContext` to resolve through.
///
/// The fix: each route now declares the [AmiTab] it belongs on. `dispatch`
/// takes a `WidgetRef` instead of a `NavigatorState`, switches `activeTabProvider`
/// to that tab (the same mechanism DEF190 already uses for an external tab
/// switch — see `home_shell.dart`), then looks up that tab's own
/// `GlobalKey<NavigatorState>` via `homeShellNavKeysProvider` and pushes
/// there. If the shell hasn't published its keys yet (`null` — the cold-start
/// case where the app is launched BY the notification tap, so
/// `PushNotificationListener` is listening before `HomeShell` has rendered
/// its first frame), `dispatch` returns a `DeepLinkDispatchResult.deferred`
/// instead of silently dropping the link or falling back to the root
/// navigator — CR040 degrade-loudly: the caller queues and retries rather
/// than the link vanishing.
library;

import 'package:ami_trade/features/nav/ami_tab.dart';
import 'package:ami_trade/features/nav/home_shell_navigation.dart';
import 'package:ami_trade/features/tour/tour_providers.dart';
import 'package:ami_trade/screens/sim/ticker_detail_screen.dart';
import 'package:ami_trade/services/notifications/notification_models.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

typedef DeepLinkPush = void Function(
  NavigatorState navigator,
  Map<String, dynamic> params,
);

/// A route table entry: which tab owns the pushed page, and how to push it
/// once that tab's Navigator is in hand.
class DeepLinkRoute {
  const DeepLinkRoute(this.tab, this.push);

  final AmiTab tab;
  final DeepLinkPush push;
}

enum DeepLinkDispatchResult {
  /// The route was found, the shell's nav keys were available, and the push
  /// (or stub no-op) ran.
  handled,

  /// `link.route` isn't in the table. CR040: logged in debug, not silently
  /// swallowed — matches the pre-CR232 behaviour for an unknown route.
  unknownRoute,

  /// The route is known, but `HomeShell` hasn't published its nav keys yet
  /// (`homeShellNavKeysProvider` reads null) — most plausibly a cold start
  /// where the notification tap itself launched the app, and
  /// `PushNotificationListener` is listening before `HomeShell` has rendered
  /// its first frame. The caller must queue the link and retry, not drop it
  /// and not fall back to the root navigator.
  deferred,
}

abstract final class DeepLinkDispatcher {
  static final Map<String, DeepLinkRoute> _routes = {
    'open_holding_detail': DeepLinkRoute(AmiTab.portfolio, _openHoldingDetail),
    // Reserved for future consumers not built in CR027 (CR095/CR109/BL11/
    // Room-verdict) — entries exist so their route string isn't silently
    // "unknown" the moment those CRs start calling notify() with them. The
    // owning tab is CR232's best call for where each will land; the CR that
    // fills in the real push should confirm it still holds rather than
    // assume it.
    'open_journal_entry': DeepLinkRoute(AmiTab.you, _stub),
    'open_room_verdict': DeepLinkRoute(AmiTab.floor, _stub),
    'open_lesson': DeepLinkRoute(AmiTab.lessons, _stub),
    'open_game_close': DeepLinkRoute(AmiTab.game, _stub),
  };

  static DeepLinkDispatchResult dispatch(WidgetRef ref, DeepLink link) {
    final entry = _routes[link.route];
    if (entry == null) {
      // CR040: visible, not silently swallowed.
      if (kDebugMode) {
        debugPrint('DeepLinkDispatcher: unknown route "${link.route}"');
      }
      return DeepLinkDispatchResult.unknownRoute;
    }

    final navKeys = ref.read(homeShellNavKeysProvider);
    if (navKeys == null) {
      if (kDebugMode) {
        debugPrint(
            'DeepLinkDispatcher: shell not mounted yet, deferring "${link.route}"');
      }
      return DeepLinkDispatchResult.deferred;
    }

    // Not every tab exists in a gated-off build (AmiTab.game with AMI_GAMES
    // off) — the map is still keyed on every AmiTab.values entry
    // (home_shell.dart's `_navKeys` comment), so the key always exists, but
    // switching to a tab this binary doesn't render would be the same
    // "landed somewhere the user didn't ask for" failure DEF190 already
    // guards against in HomeShell. Fail loudly rather than switch.
    if (!AmiTab.visible.contains(entry.tab)) {
      if (kDebugMode) {
        debugPrint('DeepLinkDispatcher: route "${link.route}" targets '
            '${entry.tab}, which this build does not render');
      }
      return DeepLinkDispatchResult.unknownRoute;
    }

    if (ref.read(activeTabProvider) != entry.tab) {
      ref.read(activeTabProvider.notifier).state = entry.tab;
    }
    final navigator = navKeys[entry.tab]!.currentState;
    if (navigator == null) {
      // The key exists but the tab's Navigator isn't attached to the tree
      // yet (e.g. HomeShell published keys but this frame hasn't built the
      // IndexedStack children). Defer rather than push through a null.
      if (kDebugMode) {
        debugPrint(
            'DeepLinkDispatcher: ${entry.tab} navigator not attached yet, '
            'deferring "${link.route}"');
      }
      return DeepLinkDispatchResult.deferred;
    }
    entry.push(navigator, link.params);
    return DeepLinkDispatchResult.handled;
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
