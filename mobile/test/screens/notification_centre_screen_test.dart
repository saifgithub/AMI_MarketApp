/// CR135 — the notification centre's contract: error ≠ empty (CR040), a
/// tapped unread row is stamped read server-side, READ ALL fires the bulk
/// stamp, and the notifications-off banner appears exactly when OS
/// permission is the thing standing between AMI and the lock screen.
library;

import 'dart:async';

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/app_notification.dart';
import 'package:ami_trade/screens/notifications/notification_centre_screen.dart';
import 'package:ami_trade/services/api/api_client.dart';
import 'package:ami_trade/services/device_user.dart';
import 'package:ami_trade/services/notifications/notification_models.dart';
import 'package:ami_trade/services/notifications/notification_service.dart';
import 'package:ami_trade/state/notification_centre_providers.dart';
import 'package:ami_trade/state/notification_providers.dart';
import 'package:ami_trade/state/onboarding_providers.dart';
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

class _FakeApi extends ApiClient {
  _FakeApi({this.failMarkAll = false}) : super(baseUrl: 'test://localhost');

  final bool failMarkAll;
  final readCalls = <String>[];
  int markAllCalls = 0;
  int unreadCountCalls = 0;

  @override
  Future<void> markNotificationRead(
      String userId, String notificationId) async {
    readCalls.add(notificationId);
  }

  @override
  Future<int> markAllNotificationsRead(String userId) async {
    markAllCalls++;
    if (failMarkAll) {
      throw DioException(
        requestOptions:
            RequestOptions(path: '/v1/notifications/$userId/read_all'),
        type: DioExceptionType.connectionError,
      );
    }
    return 2;
  }

  @override
  Future<int> notificationUnreadCount(String userId) async {
    unreadCountCalls++;
    return 0;
  }

  @override
  Future<NotificationPage> notifications(String userId,
      {int limit = 50, int offset = 0}) async {
    return const NotificationPage(items: [], total: 0);
  }
}

class _FakeNotificationService implements NotificationService {
  _FakeNotificationService({this.granted = true});

  bool granted;
  int permissionRequests = 0;

  @override
  bool get isConfigured => true;

  @override
  bool get permissionGranted => granted;

  @override
  Future<void> initialize() async {}

  @override
  Future<bool> requestPermission() async {
    permissionRequests++;
    return granted;
  }

  @override
  Future<void> login(String userId) async {}

  @override
  Future<void> logout() async {}

  @override
  Stream<DeepLink> notificationOpened() => const Stream.empty();

  @override
  Stream<String> foregroundNotificationTitle() => const Stream.empty();
}

AppNotification _row(String id, {bool unread = true, String? title}) {
  return AppNotification(
    id: id,
    type: 'price_alert',
    title: title ?? 'AAPL crossed 240',
    body: 'Above your 240.00 threshold.',
    // A route the dispatcher doesn't know: dispatch no-ops, so the tap
    // test isolates the read-stamp without dragging TickerDetail's own
    // providers into this widget tree.
    deepLink: const DeepLink(route: 'not_a_route'),
    readAt: unread ? null : DateTime.utc(2026, 8, 20, 11),
    createdAt: DateTime.utc(2026, 8, 20, 10),
  );
}

Future<_FakeApi> _pump(
  WidgetTester tester, {
  AsyncValue<NotificationPage>? page,
  bool permissionGranted = true,
  bool failMarkAll = false,
  _FakeNotificationService? service,
}) async {
  tester.view.physicalSize = const Size(390, 844);
  tester.view.devicePixelRatio = 1.0;
  addTearDown(tester.view.reset);
  SharedPreferences.setMockInitialValues({});
  DeviceUser.resetCacheForTest();

  final api = _FakeApi(failMarkAll: failMarkAll);
  await tester.pumpWidget(ProviderScope(
    overrides: [
      apiClientProvider.overrideWithValue(api),
      notificationServiceProvider.overrideWithValue(
          service ?? _FakeNotificationService(granted: permissionGranted)),
      if (page != null)
        notificationPageProvider.overrideWith(
          (ref) => page.when(
            data: (d) => Future.value(d),
            error: (e, st) => Future<NotificationPage>.error(e, st),
            loading: () =>
                Completer<NotificationPage>().future, // never settles
          ),
        ),
    ],
    child: const MaterialApp(
      localizationsDelegates: AppLocalizations.localizationsDelegates,
      supportedLocales: AppLocalizations.supportedLocales,
      home: NotificationCentreScreen(),
    ),
  ));
  await tester.pump();
  await tester.pump(const Duration(milliseconds: 300));
  return api;
}

void main() {
  testWidgets('rows render newest-first with the unread row distinct',
      (tester) async {
    await _pump(tester,
        page: AsyncValue.data(NotificationPage(items: [
          _row('n-1', unread: true, title: 'Unread row'),
          _row('n-2', unread: false, title: 'Read row'),
        ], total: 2)));

    expect(find.text('Unread row'), findsOneWidget);
    expect(find.text('Read row'), findsOneWidget);
    // The mark-all action only exists while something is unread.
    expect(find.byIcon(Icons.done_all), findsOneWidget);
  });

  testWidgets('empty state never shows a retry button (CR040)',
      (tester) async {
    await _pump(tester,
        page: const AsyncValue.data(NotificationPage(items: [], total: 0)));
    expect(find.text('No notifications yet.'), findsOneWidget);
    expect(find.text('TRY AGAIN'), findsNothing);
    expect(find.byIcon(Icons.done_all), findsNothing);
  });

  testWidgets('error state names the failure and offers retry (CR040)',
      (tester) async {
    // A separate test, not a re-pump: ProviderScope overrides are fixed at
    // creation, so swapping them on a live tree keeps the old container.
    await _pump(tester,
        page: AsyncValue.error(Exception('boom'), StackTrace.current));
    expect(find.text("Couldn't load your notifications."), findsOneWidget);
    expect(find.text('TRY AGAIN'), findsOneWidget);
    expect(find.text('No notifications yet.'), findsNothing);
  });

  testWidgets('tapping an unread row stamps it read server-side',
      (tester) async {
    final api = await _pump(tester,
        page: AsyncValue.data(NotificationPage(items: [
          _row('n-1', unread: true),
        ], total: 1)));

    await tester.tap(find.text('AAPL crossed 240'));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 300));
    expect(api.readCalls, ['n-1']);
  });

  testWidgets('tapping a read row does not re-stamp it', (tester) async {
    final api = await _pump(tester,
        page: AsyncValue.data(NotificationPage(items: [
          _row('n-2', unread: false),
        ], total: 1)));

    await tester.tap(find.text('AAPL crossed 240'));
    await tester.pump();
    expect(api.readCalls, isEmpty);
  });

  testWidgets('READ ALL fires the bulk stamp', (tester) async {
    final api = await _pump(tester,
        page: AsyncValue.data(NotificationPage(items: [
          _row('n-1', unread: true),
        ], total: 1)));

    await tester.tap(find.byIcon(Icons.done_all));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 300));
    expect(api.markAllCalls, 1);
  });

  testWidgets('a failed READ ALL says so instead of pretending (CR040)',
      (tester) async {
    await _pump(tester,
        failMarkAll: true,
        page: AsyncValue.data(NotificationPage(items: [
          _row('n-1', unread: true),
        ], total: 1)));

    await tester.tap(find.byIcon(Icons.done_all));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 300));
    expect(find.byType(SnackBar), findsOneWidget);
  });

  testWidgets('notifications-off banner shows only while permission is denied',
      (tester) async {
    await _pump(tester,
        permissionGranted: false,
        page: const AsyncValue.data(NotificationPage(items: [], total: 0)));
    expect(find.text('PUSH NOTIFICATIONS OFF'), findsOneWidget);

    await _pump(tester,
        permissionGranted: true,
        page: const AsyncValue.data(NotificationPage(items: [], total: 0)));
    expect(find.text('PUSH NOTIFICATIONS OFF'), findsNothing);
  });

  testWidgets('tapping the banner routes through requestPermission',
      (tester) async {
    final service = _FakeNotificationService(granted: false);
    await _pump(tester,
        service: service,
        page: const AsyncValue.data(NotificationPage(items: [], total: 0)));

    await tester.tap(find.text('PUSH NOTIFICATIONS OFF'));
    await tester.pump();
    expect(service.permissionRequests, 1);
  });
}
