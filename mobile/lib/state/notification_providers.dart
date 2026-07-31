/// Riverpod wiring for the CR027 notification service.
///
/// Just one provider today — there's no list/badge state to hold (that's
/// CR135's job once it exists). [notificationServiceProvider] is a plain
/// (non-autoDispose) [Provider] so the same [OneSignalNotificationService]
/// instance — and its event streams — persists for the app's lifetime,
/// matching `purchaseServiceProvider`'s shape.
library;

import 'package:ami_trade/services/notifications/notification_service.dart';
import 'package:ami_trade/services/notifications/onesignal_notification_service.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

final notificationServiceProvider = Provider<NotificationService>((ref) {
  return OneSignalNotificationService();
});
