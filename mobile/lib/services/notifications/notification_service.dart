/// Notification service abstraction (CR027).
///
/// The seam between the app and the OneSignal SDK — mirrors
/// `services/billing/purchase_service.dart`'s split. [OneSignalNotificationService]
/// is the only file that touches `package:onesignal_flutter`.
library;

import 'package:ami_trade/services/notifications/notification_models.dart';

abstract class NotificationService {
  /// True when an App ID is present (always true today — it's provisioned
  /// and safe to embed, unlike RevenueCat's per-platform secret keys).
  bool get isConfigured;

  /// Initializes the SDK. Call once, before `runApp()`. Does NOT request
  /// push permission (CR027 locked UX) — only the soft-ask flow does that.
  Future<void> initialize();

  /// Current OS-level push permission state.
  bool get permissionGranted;

  /// Requests OS push permission. Only call after the user agrees via the
  /// in-app soft-ask — never at cold start.
  Future<bool> requestPermission();

  /// Binds this device to [userId] (OneSignal `external_user_id`). Call on
  /// every login (anonymous bootstrap or a claimed sign-in).
  Future<void> login(String userId);

  /// Clears the `external_user_id` binding. Call BEFORE re-bootstrapping a
  /// fresh anonymous identity on sign-out, so a shared device never
  /// receives the previous user's push in the gap.
  Future<void> logout();

  /// Fires when the user taps a push — foregrounded, resumed from
  /// background, or cold-started by the tap.
  Stream<DeepLink> notificationOpened();

  /// Fires when a push arrives while the app is foregrounded — the
  /// notification's title, for a toast (native display is suppressed;
  /// see the implementation).
  Stream<String> foregroundNotificationTitle();
}
