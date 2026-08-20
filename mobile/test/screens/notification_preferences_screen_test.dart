/// CR135 — the push-preferences screen: one toggle per server-vocabulary
/// type, PATCHes go over the wire (server-enforced, not a client-side
/// hide), a failed save flips back and says so (CR040), and a type this
/// build predates renders by its raw wire name instead of vanishing
/// (DEF210 class).
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/app_notification.dart';
import 'package:ami_trade/screens/notifications/notification_preferences_screen.dart';
import 'package:ami_trade/services/api/api_client.dart';
import 'package:ami_trade/services/device_user.dart';
import 'package:ami_trade/state/onboarding_providers.dart';
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

const _allTypes = [
  'price_alert',
  'daily_reminder',
  'game_entries_closing',
  'game_final_stretch',
  'game_settled',
  'game_rank_move',
  'resting_order_filled',
  'resting_order_triggered',
  'resting_order_rejected',
];

class _FakeApi extends ApiClient {
  _FakeApi({
    this.failLoad = false,
    this.failPatch = false,
    List<String>? serverTypes,
  })  : serverTypes = serverTypes ?? _allTypes,
        super(baseUrl: 'test://localhost');

  final bool failLoad;
  final bool failPatch;
  final List<String> serverTypes;
  final patches = <Map<String, bool>>[];
  final _disabled = <String>{};

  List<NotificationPreference> _items() => [
        for (final t in serverTypes)
          NotificationPreference(type: t, enabled: !_disabled.contains(t)),
      ];

  @override
  Future<List<NotificationPreference>> notificationPreferences(
      String userId) async {
    if (failLoad) {
      throw DioException(
        requestOptions:
            RequestOptions(path: '/v1/notifications/$userId/preferences'),
        type: DioExceptionType.connectionError,
      );
    }
    return _items();
  }

  @override
  Future<List<NotificationPreference>> patchNotificationPreferences(
      String userId, Map<String, bool> updates) async {
    if (failPatch) {
      throw DioException(
        requestOptions:
            RequestOptions(path: '/v1/notifications/$userId/preferences'),
        type: DioExceptionType.connectionError,
      );
    }
    patches.add(updates);
    updates.forEach((t, enabled) {
      enabled ? _disabled.remove(t) : _disabled.add(t);
    });
    return _items();
  }
}

Future<_FakeApi> _pump(WidgetTester tester, {_FakeApi? api}) async {
  tester.view.physicalSize = const Size(390, 1600);
  tester.view.devicePixelRatio = 1.0;
  addTearDown(tester.view.reset);
  SharedPreferences.setMockInitialValues({});
  DeviceUser.resetCacheForTest();

  final fake = api ?? _FakeApi();
  await tester.pumpWidget(ProviderScope(
    overrides: [apiClientProvider.overrideWithValue(fake)],
    child: const MaterialApp(
      localizationsDelegates: AppLocalizations.localizationsDelegates,
      supportedLocales: AppLocalizations.supportedLocales,
      home: NotificationPreferencesScreen(),
    ),
  ));
  await tester.pump();
  await tester.pump(const Duration(milliseconds: 300));
  return fake;
}

void main() {
  testWidgets('renders one labelled toggle per server type', (tester) async {
    await _pump(tester);
    expect(find.byType(Switch), findsNWidgets(_allTypes.length));
    expect(find.text('Price alerts'), findsOneWidget);
    expect(find.text('Daily reminders'), findsOneWidget);
    expect(find.text('Order filled'), findsOneWidget);
  });

  testWidgets('a toggle PATCHes exactly that type', (tester) async {
    final api = await _pump(tester);
    // The first row is price_alert — the server's ordering is the UI's.
    await tester.tap(find.byType(Switch).first);
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 300));
    expect(api.patches, [
      {'price_alert': false},
    ]);
    // The thumb reflects the server's refreshed answer.
    expect(tester.widget<Switch>(find.byType(Switch).first).value, isFalse);
  });

  testWidgets('a failed save flips back and says so (CR040)', (tester) async {
    final api = await _pump(tester, api: _FakeApi(failPatch: true));
    await tester.tap(find.byType(Switch).first);
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 300));
    expect(api.patches, isEmpty);
    expect(tester.widget<Switch>(find.byType(Switch).first).value, isTrue);
    expect(find.byType(SnackBar), findsOneWidget);
  });

  testWidgets('load failure is a distinct error state with retry (CR040)',
      (tester) async {
    await _pump(tester, api: _FakeApi(failLoad: true));
    expect(find.text("Couldn't load your notification settings."),
        findsOneWidget);
    expect(find.text('TRY AGAIN'), findsOneWidget);
    expect(find.byType(Switch), findsNothing);
  });

  testWidgets('a type this build predates renders by its wire name (DEF210)',
      (tester) async {
    await _pump(tester,
        api: _FakeApi(serverTypes: [..._allTypes, 'brand_new_type']));
    expect(find.text('brand_new_type'), findsOneWidget);
    expect(find.byType(Switch), findsNWidgets(_allTypes.length + 1));
  });

  test('every known type resolves to a localised label, unknown falls back',
      () async {
    final l = await AppLocalizations.delegate.load(const Locale('en'));
    final seen = <String>{};
    for (final t in NotificationType.values) {
      final label = notificationTypeLabel(l, t.wire);
      expect(label, isNot(t.wire),
          reason: '${t.wire} must have a real localised label');
      expect(seen.add(label), isTrue,
          reason: 'label "$label" reused by two types');
    }
    expect(notificationTypeLabel(l, 'brand_new_type'), 'brand_new_type');
  });
}
