/// Drains OneSignal's tap + foreground-arrival streams for the whole app
/// (CR027). Mounted once, wrapping the home shell — mirrors
/// `BugResolutionToasts`'s "wrap child, react to a stream/provider" shape.
library;

import 'dart:async';

import 'package:ami_trade/features/nav/ami_tab.dart';
import 'package:ami_trade/features/nav/home_shell_navigation.dart';
import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/services/notifications/app_navigator_key.dart';
import 'package:ami_trade/services/notifications/deep_link_dispatcher.dart';
import 'package:ami_trade/services/notifications/notification_models.dart';
import 'package:ami_trade/services/notifications/notification_service.dart';
import 'package:ami_trade/state/notification_providers.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:ami_trade/widgets/hex/hex_toast.dart';
import 'package:flutter/foundation.dart';
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

  /// Listens for `HomeShell` publishing its nav keys, to flush
  /// [_pendingLinks]. Created lazily (only once something is actually
  /// queued) and cancelled in [dispose] like the stream subs above.
  ProviderSubscription<Map<AmiTab, GlobalKey<NavigatorState>>?>? _navKeysSub;

  /// CR232 round 2 (MAJOR-1) — a notification tap that arrives before
  /// `HomeShell` has published `homeShellNavKeysProvider` (most plausibly a
  /// cold start where the tap itself launched the app: OneSignal's click
  /// listener is registered in `main()` before `runApp`, and this widget's
  /// `_openedSub` can start receiving before `HomeShell` renders its first
  /// frame). CR040 — degrade loudly, don't drop the link: queue it here and
  /// flush once the shell is mounted, instead of falling back to the root
  /// navigator (which is the exact defect this fixes) or silently losing
  /// the tap.
  final List<DeepLink> _pendingLinks = [];

  @override
  void initState() {
    super.initState();
    final service = ref.read(notificationServiceProvider);

    _openedSub = service.notificationOpened().listen(_handleOpenedLink);

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

  void _handleOpenedLink(DeepLink link) {
    final result = DeepLinkDispatcher.dispatch(ref, link);
    if (result != DeepLinkDispatchResult.deferred) return;
    _pendingLinks.add(link);
    if (kDebugMode) {
      debugPrint('PushNotificationListener: queued "${link.route}" — shell '
          'not mounted yet (${_pendingLinks.length} pending)');
    }
    // Flush the moment the shell publishes its nav keys, rather than polling
    // — `ref.listenManual` survives past this callback because it's stored
    // and cancelled in dispose(), same as the stream subs above.
    _navKeysSub ??= ref.listenManual(homeShellNavKeysProvider, (prev, next) {
      if (next == null || _pendingLinks.isEmpty) return;
      final queued = List<DeepLink>.of(_pendingLinks);
      _pendingLinks.clear();
      // Re-dispatch through the same path (not a direct push) — a deferred
      // link can defer again (e.g. the shell published keys but this
      // particular tab's Navigator hasn't attached to the tree on this exact
      // frame), and re-entering `_handleOpenedLink` re-queues it correctly
      // instead of duplicating the queue/flush logic here.
      for (final pending in queued) {
        _handleOpenedLink(pending);
      }
    });
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
    _navKeysSub?.close();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => widget.child;
}
