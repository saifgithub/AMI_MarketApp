/// DEF506 — reopening the app onto a Room that is still running.
///
/// AMI-DL-4 (real iPhone): reopen showed the Floor with no sign the run was
/// alive. Ruling (Saiful, 2026-11-20): open on the Floor with a rejoin banner;
/// REJOIN takes the user back into that Room; never auto-jump; never charge.
///
/// Covers the lookup (what counts as "in flight"), the banner, the tap, the
/// resume re-check, and a failing lookup.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/room.dart';
import 'package:ami_trade/models/sector_watch.dart';
import 'package:ami_trade/qa/semantics_ids.dart';
import 'package:ami_trade/screens/floor/floor_providers.dart';
import 'package:ami_trade/screens/floor/floor_screen.dart';
import 'package:ami_trade/screens/home_shell.dart';
import 'package:ami_trade/screens/room/room_screen.dart';
import 'package:ami_trade/services/api/api_client.dart';
import 'package:ami_trade/services/device_user.dart';
import 'package:ami_trade/state/active_room_provider.dart';
import 'package:ami_trade/state/onboarding_providers.dart';
import 'package:ami_trade/state/room_providers.dart';
import 'package:ami_trade/state/sim_providers.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

RoomRunSnapshot _run(
  String id,
  String ticker,
  String status, {
  DateTime? startedAt,
}) =>
    RoomRunSnapshot(
      id: id,
      userId: 'u',
      ticker: ticker,
      status: status,
      modelTier: 'mid',
      transcript: const [],
      startedAt: startedAt ?? DateTime.now().toUtc(),
    );

/// Answers `listUserRooms` from a script, one response per call (the last one
/// repeats). Counts calls. Anything that would convene or charge is recorded
/// on [streamedTickers] so a test can assert it never happened.
class _FakeApi extends ApiClient {
  _FakeApi(this.responses) : super(baseUrl: 'test://localhost');

  final List<Object> responses; // List<RoomRunSnapshot> or an Exception
  int listCalls = 0;
  final List<String> streamedTickers = [];

  @override
  Future<List<RoomRunSnapshot>> listUserRooms(String userId,
      {int limit = 50}) async {
    final i = listCalls < responses.length ? listCalls : responses.length - 1;
    listCalls++;
    final r = responses[i];
    if (r is Exception) throw r;
    return r as List<RoomRunSnapshot>;
  }

  @override
  Stream<Map<String, dynamic>> streamRoom({
    required String userId,
    required String ticker,
    String locale = 'en',
    Map<String, dynamic>? mandateOverride,
    Map<String, dynamic>? alpaca,
  }) {
    streamedTickers.add(ticker);
    return const Stream.empty();
  }
}

/// Stands in for the real notifier so opening the Room does not stream; records
/// that the attach path (`start`, the same call the Convene sheet ends in) ran.
class _RecordingRoom extends RoomNotifier {
  _RecordingRoom(super.ref, super.ticker, this.starts, RoomState initial) {
    state = initial;
  }

  final List<String> starts;

  @override
  Future<void> start() async {
    starts.add('start');
  }
}

class _FixedSim extends SimNotifier {
  _FixedSim(super.ref) {
    state = const SimState();
  }
}

Future<void> _pumpFloor(
  WidgetTester t,
  _FakeApi api, {
  List<String>? roomStarts,
  RoomState roomState =
      const RoomState(streaming: true, reattached: true, runId: 'r1'),
}) async {
  await t.binding.setSurfaceSize(const Size(390, 844));
  addTearDown(() => t.binding.setSurfaceSize(null));
  t.view.devicePixelRatio = 1.0;
  addTearDown(t.view.resetDevicePixelRatio);

  await t.pumpWidget(ProviderScope(
    overrides: [
      apiClientProvider.overrideWithValue(api),
      simNotifierProvider.overrideWith((ref) => _FixedSim(ref)),
      teamCallsProvider.overrideWith((ref) async => const []),
      sectorWatchProvider
          .overrideWith((ref) async => const SectorWatch(state: 'empty')),
      callPriceProvider.overrideWith((ref, ticker) async => null),
      roomNotifierProvider.overrideWith((ref, ticker) {
        final n = _RecordingRoom(ref, ticker, roomStarts ?? <String>[], roomState);
        Future.microtask(n.start); // same as the real provider factory
        return n;
      }),
    ],
    child: const MaterialApp(
      localizationsDelegates: AppLocalizations.localizationsDelegates,
      supportedLocales: AppLocalizations.supportedLocales,
      home: FloorScreen(),
    ),
  ));
  await _settle(t);
}

void _backgroundAndReturn(WidgetTester t) {
  for (final st in [
    AppLifecycleState.inactive,
    AppLifecycleState.hidden,
    AppLifecycleState.paused,
    AppLifecycleState.hidden,
    AppLifecycleState.inactive,
    AppLifecycleState.resumed,
  ]) {
    t.binding.handleAppLifecycleStateChanged(st);
  }
}

Future<void> _settle(WidgetTester t) async {
  for (var i = 0; i < 10; i++) {
    await t.pump(const Duration(milliseconds: 50));
  }
}


void main() {
  setUp(() {
    SharedPreferences.setMockInitialValues({'tour_floor_seen': true});
    DeviceUser.resetCacheForTest();
  });

  Finder banner() => find.bySemanticsIdentifier(FloorIds.rejoinBanner);
  Finder cta() => find.bySemanticsIdentifier(FloorIds.rejoinCta);

  group('activeRoomRunFrom — what counts as in flight', () {
    final now = DateTime.utc(2026, 11, 20, 12);

    test('newest run running and inside the attach window', () {
      final a = activeRoomRunFrom([
        _run('r2', 'MSFT', 'running',
            startedAt: now.subtract(const Duration(minutes: 3))),
        _run('r1', 'AAPL', 'completed'),
      ], now: now);
      expect(a, const ActiveRoomRun(runId: 'r2', ticker: 'MSFT'));
    });

    test('finished, failed, queued, or empty is not in flight', () {
      for (final s in ['completed', 'failed', 'cancelled', 'queued']) {
        expect(activeRoomRunFrom([_run('r', 'MSFT', s, startedAt: now)],
            now: now), isNull, reason: s);
      }
      expect(activeRoomRunFrom(const [], now: now), isNull);
    });

    test('a running row past the 30 min attach window is stranded, not live',
        () {
      expect(
          activeRoomRunFrom([
            _run('r', 'MSFT', 'running',
                startedAt: now.subtract(const Duration(minutes: 31))),
          ], now: now),
          isNull,
          reason: 'REJOIN on it would convene a new run and charge');
    });

    test('only the newest row counts: an older running row is ignored', () {
      expect(
          activeRoomRunFrom([
            _run('r2', 'MSFT', 'completed', startedAt: now),
            _run('r1', 'AAPL', 'running', startedAt: now),
          ], now: now),
          isNull);
    });

    test('an offset-less server timestamp is read as UTC', () {
      final r = RoomRunSnapshot.fromJson({
        'id': 'r',
        'user_id': 'u',
        'ticker': 'MSFT',
        'status': 'running',
        'started_at': '2026-11-20T11:58:00',
      });
      expect(r.startedAt, DateTime.utc(2026, 11, 20, 11, 58));
    });
  });

  testWidgets('an in-flight run shows the banner naming the ticker',
      (t) async {
    final api = _FakeApi([
      [_run('r1', 'MSFT', 'running')],
    ]);
    await _pumpFloor(t, api);

    expect(banner(), findsOneWidget);
    expect(cta(), findsOneWidget);
    final l = AppLocalizations.of(t.element(find.byType(FloorScreen)));
    expect(find.text(l.floorRejoinBanner('MSFT')), findsOneWidget);
    expect(find.text(l.floorRejoinCta), findsOneWidget);
    expect(find.byType(RoomScreen), findsNothing,
        reason: 'the ruling: Floor first, never an auto-jump into the Room');
    expect(api.streamedTickers, isEmpty);
  });

  testWidgets('no run, or a finished run, shows no banner', (t) async {
    await _pumpFloor(t, _FakeApi([<RoomRunSnapshot>[]]));
    expect(banner(), findsNothing);
  });

  testWidgets('a finished run shows no banner', (t) async {
    await _pumpFloor(
        t, _FakeApi([[_run('r1', 'MSFT', 'completed')]]));
    expect(banner(), findsNothing);
  });

  testWidgets('REJOIN opens the Room for that ticker through the attach path, '
      'with no convene call of its own', (t) async {
    final starts = <String>[];
    final api = _FakeApi([
      [_run('r1', 'MSFT', 'running')],
    ]);
    await _pumpFloor(t, api, roomStarts: starts);

    await t.tap(cta());
    await _settle(t);

    final room = find.byType(RoomScreen);
    expect(room, findsOneWidget);
    expect(t.widget<RoomScreen>(room).ticker, 'MSFT');
    expect(starts, ['start'],
        reason: 'RoomNotifier.start is the one attach call the Convene sheet '
            'also ends in; the server dedups it onto the running run');
    expect(api.streamedTickers, isEmpty,
        reason: 'no second stream request issued by the banner itself');
    expect(api.listCalls, 2, reason: 'launch lookup + re-check at tap');
  });

  testWidgets('REJOIN on a run that ended since the banner was drawn opens '
      'nothing and clears the banner', (t) async {
    final starts = <String>[];
    final api = _FakeApi([
      [_run('r1', 'MSFT', 'running')],
      [_run('r1', 'MSFT', 'completed')],
    ]);
    await _pumpFloor(t, api, roomStarts: starts);
    expect(banner(), findsOneWidget);

    await t.tap(cta());
    await _settle(t);

    expect(find.byType(RoomScreen), findsNothing);
    expect(starts, isEmpty,
        reason: 'attaching now would convene a fresh run and charge');
    expect(banner(), findsNothing);
  });

  testWidgets('the banner is gone once the user has rejoined', (t) async {
    final api = _FakeApi([
      [_run('r1', 'MSFT', 'running')],
      [_run('r1', 'MSFT', 'running')],
      [_run('r1', 'MSFT', 'completed')],
    ]);
    // `done` so the Room's leave-confirmation does not hold the pop.
    await _pumpFloor(t, api,
        roomState: const RoomState(reattached: true, done: true, runId: 'r1'));

    await t.tap(cta());
    await _settle(t);
    expect(find.byType(RoomScreen), findsOneWidget);
    expect(banner(), findsNothing, reason: 'cleared on rejoin');

    final nav = Navigator.of(t.element(find.byType(RoomScreen)));
    final popped = await nav.maybePop();
    expect(popped, isTrue);
    await t.pump(const Duration(seconds: 2));
    await _settle(t);

    expect(find.byType(RoomScreen), findsNothing);
    expect(banner(), findsNothing, reason: 'the run finished while in the Room');
  });

  testWidgets('a lookup error shows no banner and does not crash', (t) async {
    await _pumpFloor(t, _FakeApi([Exception('network down')]));
    expect(t.takeException(), isNull);
    expect(banner(), findsNothing);
    expect(find.byType(FloorScreen), findsOneWidget);
  });

  testWidgets('resume re-checks: a run started while away shows the banner; '
      'one that ended while away clears it', (t) async {
    final api = _FakeApi([
      <RoomRunSnapshot>[],
      [_run('r1', 'NVDA', 'running')],
      <RoomRunSnapshot>[],
    ]);
    await t.binding.setSurfaceSize(const Size(390, 844));
    addTearDown(() => t.binding.setSurfaceSize(null));
    await t.pumpWidget(ProviderScope(
      overrides: [
        apiClientProvider.overrideWithValue(api),
        simNotifierProvider.overrideWith((ref) => _FixedSim(ref)),
        teamCallsProvider.overrideWith((ref) async => const []),
        sectorWatchProvider
            .overrideWith((ref) async => const SectorWatch(state: 'empty')),
        callPriceProvider.overrideWith((ref, ticker) async => null),
      ],
      child: const MaterialApp(
        localizationsDelegates: AppLocalizations.localizationsDelegates,
        supportedLocales: AppLocalizations.supportedLocales,
        home: HomeShell(),
      ),
    ));
    await _settle(t);
    expect(banner(), findsNothing);
    expect(api.listCalls, 1, reason: 'launch lookup');

    _backgroundAndReturn(t);
    await _settle(t);
    expect(api.listCalls, 2, reason: 'resume lookup');
    expect(banner(), findsOneWidget);

    _backgroundAndReturn(t);
    await _settle(t);
    expect(banner(), findsNothing);
  });
}
