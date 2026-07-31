/// OneSignal implementation of [NotificationService] (CR027).
///
/// The ONLY file that touches `package:onesignal_flutter`. Foreground
/// pushes suppress OneSignal's own native banner (`preventDefault()`) —
/// the app shows its own `HexToast` instead, matching CR027's in-app
/// facility (a toast, not a system alert).
library;

import 'dart:async';

import 'package:ami_trade/services/notifications/notification_models.dart';
import 'package:ami_trade/services/notifications/notification_service.dart';
import 'package:ami_trade/services/notifications/onesignal_config.dart';
import 'package:onesignal_flutter/onesignal_flutter.dart';

class OneSignalNotificationService implements NotificationService {
  bool _initialized = false;
  final _openedController = StreamController<DeepLink>.broadcast();
  final _foregroundController = StreamController<String>.broadcast();

  @override
  bool get isConfigured => OneSignalConfig.isConfigured;

  @override
  Future<void> initialize() async {
    if (_initialized || !isConfigured) return;
    _initialized = true;

    await OneSignal.initialize(OneSignalConfig.appId);

    OneSignal.Notifications.addClickListener((event) {
      final data = event.notification.additionalData ?? const <String, dynamic>{};
      _openedController.add(DeepLink.fromJson(data));
    });

    OneSignal.Notifications.addForegroundWillDisplayListener((event) {
      event.preventDefault();
      final title = event.notification.title;
      if (title != null && title.isNotEmpty) {
        _foregroundController.add(title);
      }
    });
  }

  @override
  bool get permissionGranted => OneSignal.Notifications.permission;

  @override
  Future<bool> requestPermission() =>
      OneSignal.Notifications.requestPermission(true);

  @override
  Future<void> login(String userId) => OneSignal.login(userId);

  @override
  Future<void> logout() => OneSignal.logout();

  @override
  Stream<DeepLink> notificationOpened() => _openedController.stream;

  @override
  Stream<String> foregroundNotificationTitle() => _foregroundController.stream;
}
