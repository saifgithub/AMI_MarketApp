/// CR135 — Riverpod state for the in-app notification centre.
///
/// Deliberately NOT error-swallowing (CR040): the centre screen renders a
/// distinct error + retry state — "couldn't load" must never look like
/// "no notifications". Only the bell badge collapses error to absence,
/// because a badge has nothing honest to claim when the count is unknown
/// (same split as `unreadInboxCountProvider`).
///
/// The unread badge reads the server's `unread_count` — the same
/// `notifications` table the OS icon badge is driven from (CR135
/// badge-count parity: no second counter to drift).
library;

import 'package:ami_trade/models/app_notification.dart';
import 'package:ami_trade/services/api/friendly_error.dart';
import 'package:ami_trade/services/device_user.dart';
import 'package:ami_trade/state/auth_providers.dart';
import 'package:ami_trade/state/onboarding_providers.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

/// First page (50 rows), newest-first as the server orders them. At alpha
/// cadence the 90-day retention window never fills a page (CR135 doc §2);
/// paging beyond it is deliberately not built until a real user hits 50.
final notificationPageProvider =
    FutureProvider.autoDispose<NotificationPage>((ref) async {
  final token = ref.watch(authNotifierProvider).token;
  if (token == null) return const NotificationPage(items: [], total: 0);
  final userId = await DeviceUser.getOrCreate();
  return ref.watch(apiClientProvider).notifications(userId);
});

/// Server-side unread count for the YOU-header bell. NOT autoDispose — the
/// badge must survive navigation (inboxProvider's rationale).
final notificationUnreadCountProvider = FutureProvider<int>((ref) async {
  final token = ref.watch(authNotifierProvider).token;
  if (token == null) return 0;
  final userId = await DeviceUser.getOrCreate();
  return ref.watch(apiClientProvider).notificationUnreadCount(userId);
});

/// The badge's view of the count: absent (0) while loading and on error —
/// a badge can only assert a number it actually has.
final notificationBadgeCountProvider = Provider<int>((ref) {
  return ref.watch(notificationUnreadCountProvider).valueOrNull ?? 0;
});

/// Per-type push toggles, owned by a controller because a toggle is a
/// write: the state must reflect the server's answer, not the thumb's
/// position (server-enforced preferences, CR135 acceptance).
final notificationPrefsProvider = StateNotifierProvider.autoDispose<
    NotificationPrefsController,
    AsyncValue<List<NotificationPreference>>>((ref) {
  return NotificationPrefsController(ref)..load();
});

class NotificationPrefsController
    extends StateNotifier<AsyncValue<List<NotificationPreference>>> {
  NotificationPrefsController(this._ref) : super(const AsyncValue.loading());

  final Ref _ref;

  Future<void> load() async {
    state = const AsyncValue.loading();
    try {
      final userId = await DeviceUser.getOrCreate();
      final items =
          await _ref.read(apiClientProvider).notificationPreferences(userId);
      if (!mounted) return;
      state = AsyncValue.data(items);
    } catch (e, st) {
      if (!mounted) return;
      state = AsyncValue.error(e, st);
    }
  }

  /// Optimistic flip, reverted on failure. Returns null on success, a
  /// user-facing error sentence on failure — the screen surfaces it
  /// (CR040: a toggle that silently didn't take is a dark feature).
  Future<String?> toggle(String type, bool enabled) async {
    final before = state.valueOrNull;
    if (before == null) return null;
    state = AsyncValue.data([
      for (final p in before)
        if (p.type == type)
          NotificationPreference(
              type: p.type, enabled: enabled, updatedAt: p.updatedAt)
        else
          p,
    ]);
    try {
      final userId = await DeviceUser.getOrCreate();
      final items = await _ref
          .read(apiClientProvider)
          .patchNotificationPreferences(userId, {type: enabled});
      if (mounted) state = AsyncValue.data(items);
      return null;
    } catch (e) {
      if (mounted) state = AsyncValue.data(before);
      return friendlyError(e, action: 'save that notification setting');
    }
  }
}

/// Row-tap and mark-all-read writes for the centre screen.
class NotificationReadActions {
  NotificationReadActions(this._ref);

  final Ref _ref;

  /// Fire the server stamp for one row, then re-sync list + badge from the
  /// server either way. A failure leaves the row honestly unread — the
  /// re-fetch shows the true state rather than a client-side pretence.
  Future<void> markRead(String notificationId) async {
    try {
      final userId = await DeviceUser.getOrCreate();
      await _ref
          .read(apiClientProvider)
          .markNotificationRead(userId, notificationId);
    } catch (e) {
      if (kDebugMode) debugPrint('markNotificationRead failed: $e');
    } finally {
      _ref.invalidate(notificationPageProvider);
      _ref.invalidate(notificationUnreadCountProvider);
    }
  }

  /// Returns null on success, a user-facing error sentence on failure.
  Future<String?> markAllRead() async {
    try {
      final userId = await DeviceUser.getOrCreate();
      await _ref.read(apiClientProvider).markAllNotificationsRead(userId);
      return null;
    } catch (e) {
      return friendlyError(e, action: 'mark your notifications read');
    } finally {
      _ref.invalidate(notificationPageProvider);
      _ref.invalidate(notificationUnreadCountProvider);
    }
  }
}

final notificationReadActionsProvider =
    Provider<NotificationReadActions>((ref) => NotificationReadActions(ref));
