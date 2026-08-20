/// CR135 — rows and preferences for the in-app notification centre.
///
/// [AppNotification] mirrors `app/schemas/notifications.py::NotificationOut`;
/// [NotificationPreference] mirrors `NotificationPreferenceOut`. The `type`
/// wire string stays on the model verbatim (DEF210 class): a value this
/// client has never heard of must render as a plain row, never throw and
/// never impersonate a known type — the backend ships by rsync days ahead
/// of the store build. [NotificationType] is the typed mirror of the
/// backend's `NOTIFICATION_TYPES` vocabulary; parity is enforced by
/// `backend/tests/unit/test_cr135_notification_type_parity.py`, which
/// parses this file, so adding a member here or a type there fails pytest,
/// not the user.
library;

import 'package:ami_trade/services/notifications/notification_models.dart';

enum NotificationType {
  priceAlert,
  dailyReminder,
  gameEntriesClosing,
  gameFinalStretch,
  gameSettled,
  gameRankMove,
  restingOrderFilled,
  restingOrderTriggered,
  restingOrderRejected,
}

extension NotificationTypeJson on NotificationType {
  String get wire {
    switch (this) {
      case NotificationType.priceAlert:
        return 'price_alert';
      case NotificationType.dailyReminder:
        return 'daily_reminder';
      case NotificationType.gameEntriesClosing:
        return 'game_entries_closing';
      case NotificationType.gameFinalStretch:
        return 'game_final_stretch';
      case NotificationType.gameSettled:
        return 'game_settled';
      case NotificationType.gameRankMove:
        return 'game_rank_move';
      case NotificationType.restingOrderFilled:
        return 'resting_order_filled';
      case NotificationType.restingOrderTriggered:
        return 'resting_order_triggered';
      case NotificationType.restingOrderRejected:
        return 'resting_order_rejected';
    }
  }

  static NotificationType? fromWire(String? s) {
    switch (s) {
      case 'price_alert':
        return NotificationType.priceAlert;
      case 'daily_reminder':
        return NotificationType.dailyReminder;
      case 'game_entries_closing':
        return NotificationType.gameEntriesClosing;
      case 'game_final_stretch':
        return NotificationType.gameFinalStretch;
      case 'game_settled':
        return NotificationType.gameSettled;
      case 'game_rank_move':
        return NotificationType.gameRankMove;
      case 'resting_order_filled':
        return NotificationType.restingOrderFilled;
      case 'resting_order_triggered':
        return NotificationType.restingOrderTriggered;
      case 'resting_order_rejected':
        return NotificationType.restingOrderRejected;
      default:
        return null;
    }
  }
}

class AppNotification {
  const AppNotification({
    required this.id,
    required this.type,
    required this.title,
    required this.body,
    required this.deepLink,
    required this.createdAt,
    this.sourceRef,
    this.readAt,
  });

  final String id;

  /// The wire value, kept verbatim. Use [knownType] for typed branching —
  /// null means "a type this build predates", which renders generically.
  final String type;

  final String title;
  final String body;
  final DeepLink deepLink;
  final String? sourceRef;
  final DateTime? readAt;
  final DateTime createdAt;

  NotificationType? get knownType => NotificationTypeJson.fromWire(type);

  bool get isUnread => readAt == null;

  factory AppNotification.fromJson(Map<String, dynamic> j) {
    return AppNotification(
      id: j['id'] as String,
      type: j['type'] as String? ?? '',
      title: j['title'] as String? ?? '',
      body: j['body'] as String? ?? '',
      deepLink: DeepLink.fromJson(
          (j['deep_link'] as Map?)?.cast<String, dynamic>() ?? const {}),
      sourceRef: j['source_ref'] as String?,
      readAt: j['read_at'] != null
          ? DateTime.tryParse(j['read_at'] as String)
          : null,
      createdAt: DateTime.tryParse(j['created_at'] as String? ?? '') ??
          DateTime.fromMillisecondsSinceEpoch(0, isUtc: true),
    );
  }
}

/// One page of `GET /v1/notifications/{user_id}` — `total` counts the whole
/// history so the client can page without a second endpoint.
class NotificationPage {
  const NotificationPage({required this.items, required this.total});

  final List<AppNotification> items;
  final int total;

  factory NotificationPage.fromJson(Map<String, dynamic> j) {
    return NotificationPage(
      items: ((j['items'] as List?) ?? const [])
          .map((e) => AppNotification.fromJson(e as Map<String, dynamic>))
          .toList(),
      total: ((j['total'] as num?) ?? 0).toInt(),
    );
  }
}

/// A per-type push toggle. `updatedAt == null` means never toggled — the
/// server's enabled-by-default, not a stored row.
class NotificationPreference {
  const NotificationPreference({
    required this.type,
    required this.enabled,
    this.updatedAt,
  });

  final String type;
  final bool enabled;
  final DateTime? updatedAt;

  NotificationType? get knownType => NotificationTypeJson.fromWire(type);

  factory NotificationPreference.fromJson(Map<String, dynamic> j) {
    return NotificationPreference(
      type: j['type'] as String,
      enabled: j['enabled'] as bool? ?? true,
      updatedAt: j['updated_at'] != null
          ? DateTime.tryParse(j['updated_at'] as String)
          : null,
    );
  }
}
