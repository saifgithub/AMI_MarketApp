/// CR102 — the Floor header's inbox bell: the badge derives its count from
/// the inbox payload, shows only when unread > 0, and is silently absent on
/// error (the badge may be absent; only the inbox screen may say "failed").
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/inbox_message.dart';
import 'package:ami_trade/models/sector_watch.dart';
import 'package:ami_trade/screens/floor/floor_providers.dart';
import 'package:ami_trade/screens/floor/floor_screen.dart';
import 'package:ami_trade/state/inbox_providers.dart';
import 'package:ami_trade/state/sim_providers.dart';
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

class _FixedSim extends SimNotifier {
  _FixedSim(super.ref) {
    state = const SimState();
  }
}

InboxMessage _unread(String id) => InboxMessage(
      id: id,
      direction: 'out',
      title: 'Broadcast $id',
      body: 'body',
      priority: 'normal',
      createdAt: DateTime.utc(2026, 8, 18, 10),
    );

Future<void> _pumpFloor(
  WidgetTester t, {
  List<InboxMessage>? inbox,
  Object? inboxError,
}) async {
  await t.binding.setSurfaceSize(const Size(390, 720));
  addTearDown(() => t.binding.setSurfaceSize(null));
  t.view.devicePixelRatio = 1.0;
  addTearDown(t.view.resetDevicePixelRatio);

  await t.pumpWidget(ProviderScope(
    overrides: [
      simNotifierProvider.overrideWith((ref) => _FixedSim(ref)),
      teamCallsProvider.overrideWith((ref) async => const []),
      sectorWatchProvider
          .overrideWith((ref) async => const SectorWatch(state: 'empty')),
      callPriceProvider.overrideWith((ref, ticker) async => null),
      conveneCloseProvider.overrideWith((ref, k) async => null),
      inboxProvider.overrideWith((ref) {
        if (inboxError != null) throw inboxError;
        return inbox ?? const <InboxMessage>[];
      }),
    ],
    child: MaterialApp(
      localizationsDelegates: AppLocalizations.localizationsDelegates,
      supportedLocales: AppLocalizations.supportedLocales,
      home: const FloorScreen(),
      routes: {
        '/inbox': (_) => const Scaffold(body: Text('INBOX-ROUTE')),
      },
    ),
  ));
  // The Floor's league + daily-challenge providers each fire a Dio request
  // on creation; the futures never resolve against no server, but their
  // timers are pending until the fake clock has moved (same idiom as
  // floor_v02_test.dart).
  for (var i = 0; i < 10; i++) {
    await t.pump(const Duration(milliseconds: 50));
  }
}

void main() {
  setUp(() => SharedPreferences.setMockInitialValues({'tour_floor_seen': true}));

  testWidgets('the bell renders with no badge when nothing is unread',
      (t) async {
    await _pumpFloor(t, inbox: [
      // A read broadcast and a reply — neither counts as unread.
      InboxMessage(
        id: 'm1',
        direction: 'out',
        title: 'Read one',
        body: 'b',
        priority: 'normal',
        createdAt: DateTime.utc(2026, 8, 18, 10),
        readAt: DateTime.utc(2026, 8, 18, 11),
      ),
      InboxMessage(
        id: 'r1',
        direction: 'in',
        body: 'my reply',
        replyToId: 'm1',
        createdAt: DateTime.utc(2026, 8, 18, 12),
      ),
    ]);

    expect(find.byIcon(Icons.notifications_outlined), findsOneWidget);
    expect(find.text('1'), findsNothing);
    expect(find.text('2'), findsNothing);
  });

  testWidgets('the badge shows the unread count derived from the list',
      (t) async {
    await _pumpFloor(t, inbox: [_unread('m1'), _unread('m2'), _unread('m3')]);
    expect(find.text('3'), findsOneWidget);
  });

  testWidgets('the badge caps at 9+', (t) async {
    await _pumpFloor(t,
        inbox: [for (var i = 0; i < 12; i++) _unread('m$i')]);
    expect(find.text('9+'), findsOneWidget);
  });

  testWidgets('on a failed fetch the bell is bare — no badge, no crash',
      (t) async {
    await _pumpFloor(
      t,
      inboxError: DioException(
        requestOptions: RequestOptions(path: '/v1/messages'),
        type: DioExceptionType.connectionError,
      ),
    );
    expect(find.byIcon(Icons.notifications_outlined), findsOneWidget);
    expect(t.takeException(), isNull);
  });

  testWidgets('tapping the bell pushes /inbox', (t) async {
    await _pumpFloor(t, inbox: [_unread('m1')]);
    await t.tap(find.byIcon(Icons.notifications_outlined));
    await t.pumpAndSettle();
    expect(find.text('INBOX-ROUTE'), findsOneWidget);
  });
}
