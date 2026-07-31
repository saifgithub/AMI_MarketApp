/// Drains OneSignal's tap + foreground-arrival streams for the whole app
/// (CR027). Mounted once, wrapping the home shell — mirrors
/// `BugResolutionToasts`'s "wrap child, react to a stream/provider" shape.
library;

import 'dart:async';

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/services/notifications/app_navigator_key.dart';
import 'package:ami_trade/services/notifications/deep_link_dispatcher.dart';
import 'package:ami_trade/services/notifications/notification_service.dart';
import 'package:ami_trade/state/notification_providers.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:ami_trade/widgets/hex/hex_toast.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

const _kSoftAskShownPrefsKey = 'ami_push_soft_ask_shown';

/// Delay before the soft-ask dialog, so it doesn't collide with the home
/// shell's own entrance animation — same reasoning as
/// `BugResolutionToasts._kSettleDelay`.
const _kSoftAskSettleDelay = Duration(milliseconds: 1200);

class PushNotificationListener extends ConsumerStatefulWidget {
  const PushNotificationListener({super.key, required this.child});

  final Widget child;

  @override
  ConsumerState<PushNotificationListener> createState() =>
      _PushNotificationListenerState();
}

class _PushNotificationListenerState
    extends ConsumerState<PushNotificationListener> {
  StreamSubscription<dynamic>? _openedSub;
  StreamSubscription<dynamic>? _foregroundSub;

  @override
  void initState() {
    super.initState();
    final service = ref.read(notificationServiceProvider);

    _openedSub = service.notificationOpened().listen((link) {
      final navigator = appNavigatorKey.currentState;
      if (navigator == null) return;
      DeepLinkDispatcher.dispatch(navigator, link);
    });

    // A push arriving while the app is already open — the native banner is
    // suppressed by the service impl; this is the in-app surfacing CR027
    // actually ships (no dedicated notification centre — that's CR135).
    _foregroundSub = service.foregroundNotificationTitle().listen((title) {
      final context = appNavigatorKey.currentContext;
      if (context == null) return;
      HexToast.show(
        context,
        title,
        accent: AmiColors.hexBlue,
        icon: Icons.notifications_outlined,
      );
    });

    WidgetsBinding.instance.addPostFrameCallback((_) => _maybeShowSoftAsk(service));
  }

  /// CR027 locked UX: a soft in-app ask BEFORE the OS permission prompt —
  /// declining an unexpected cold-launch system prompt is permanent
  /// without a Settings trip, so the app asks first, in its own words.
  /// Shown once per install (SharedPreferences flag); skipped entirely if
  /// permission is already granted.
  Future<void> _maybeShowSoftAsk(NotificationService service) async {
    if (!service.isConfigured || service.permissionGranted) return;
    final prefs = await SharedPreferences.getInstance();
    if (prefs.getBool(_kSoftAskShownPrefsKey) ?? false) return;
    await prefs.setBool(_kSoftAskShownPrefsKey, true);

    await Future<void>.delayed(_kSoftAskSettleDelay);
    if (!mounted) return;
    final l = AppLocalizations.of(context);
    final agreed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text(l.pushSoftAskTitle),
        content: Text(l.pushSoftAskBody),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx, false),
            child: Text(l.pushSoftAskDecline),
          ),
          TextButton(
            onPressed: () => Navigator.pop(ctx, true),
            child: Text(l.pushSoftAskAccept),
          ),
        ],
      ),
    );
    if (agreed == true) {
      await service.requestPermission();
    }
  }

  @override
  void dispose() {
    _openedSub?.cancel();
    _foregroundSub?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => widget.child;
}
