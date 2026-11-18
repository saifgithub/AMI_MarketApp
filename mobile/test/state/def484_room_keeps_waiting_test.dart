/// DEF484 — the Room screen must not give up on a run that is still going.
///
/// UAT-ROOM-016 (2026-10-20): 2 of 2 real runs ended on "Reconnect timed out"
/// after 6-10 minutes while the server kept deliberating and later completed.
/// `_recoverViaPolling` used a fixed 90 s budget. Now it waits until the run
/// reaches a terminal state; a stream that ends cleanly without `done` also
/// resumes the wait; and a genuine give-up is a visible, honest state with a
/// way to keep waiting - never a silent timeout.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/journal.dart';
import 'package:ami_trade/models/room.dart';
import 'package:ami_trade/screens/room/room_screen.dart';
import 'package:ami_trade/services/api/api_client.dart';
import 'package:ami_trade/state/journal_providers.dart';
import 'package:ami_trade/state/lessons_providers.dart';
import 'package:ami_trade/state/onboarding_providers.dart';
import 'package:ami_trade/state/room_providers.dart';
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

const _fast = RoomRecoveryConfig(
  pollInterval: Duration(milliseconds: 1),
  maxWait: Duration(seconds: 20),
  maxUnreachable: Duration(milliseconds: 60),
);

class _NoopJournal extends JournalNotifier {
  _NoopJournal(super.ref);
  @override
  Future<void> refresh({
    JournalEntryType? filterType,
    String plan = 'trial_trader',
    String? q,
  }) async {}
}

class _NoopLessons extends LessonsNotifier {
  _NoopLessons(super.ref);
  @override
  Future<void> refresh() async {}
}

RoomRunSnapshot _snap(String status, {int agents = 0}) => RoomRunSnapshot(
      id: 'run-1',
      userId: 'u1',
      ticker: 'AAPL',
      status: status,
      modelTier: 'mid',
      transcript: [
        for (var i = 0; i < agents; i++)
          RoomTranscriptLine(agentId: 'agent_$i', content: 'turn $i'),
      ],
      verdict: status == 'completed'
          ? RoomVerdict.fromJson({
              'action': 'PASS',
              'reason': 'No edge.',
            })
          : null,
    );

/// Starts, then loses the stream (or ends it cleanly) with the run still
/// active; `getRoom` is scripted per call.
class _Api extends ApiClient {
  _Api({required this.onGetRoom, this.breakStream = true})
      : super(baseUrl: 'test://localhost');

  final Future<RoomRunSnapshot> Function(int call) onGetRoom;
  final bool breakStream;
  int getRoomCalls = 0;

  @override
  Stream<Map<String, dynamic>> streamRoom({
    required String userId,
    required String ticker,
    String locale = 'en',
    Map<String, dynamic>? mandateOverride,
    Map<String, dynamic>? alpaca,
  }) async* {
    yield {'kind': 'started', 'run_id': 'run-1'};
    await Future<void>.delayed(Duration.zero);
    if (breakStream) throw Exception('connection closed');
  }

  @override
  Future<RoomRunSnapshot> getRoom(String runId) {
    getRoomCalls++;
    return onGetRoom(getRoomCalls);
  }
}

ProviderContainer _container(_Api api) {
  final c = ProviderContainer(overrides: [
    apiClientProvider.overrideWithValue(api),
    roomRecoveryConfigProvider.overrideWithValue(_fast),
    journalNotifierProvider.overrideWith((ref) => _NoopJournal(ref)),
    lessonsNotifierProvider.overrideWith((ref) => _NoopLessons(ref)),
  ]);
  addTearDown(c.dispose);
  return c;
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  setUp(() => SharedPreferences.setMockInitialValues({}));

  test('default budget outlasts the server\'s own stuck-run window', () {
    const cfg = RoomRecoveryConfig();
    expect(cfg.maxWait, greaterThan(const Duration(minutes: 30)));
    expect(cfg.maxWait, greaterThan(const Duration(seconds: 90) * 10));
  });

  test('keeps waiting through a long run and lands on the verdict', () async {
    // 60 polls x 3 s = 180 s at the real interval: the old 90 s budget would
    // have bounced the user out long before this run completed.
    final api = _Api(
      onGetRoom: (call) async =>
          call < 60 ? _snap('running', agents: call ~/ 10) : _snap('completed', agents: 12),
    );
    final c = _container(api);
    final sub = c.listen(roomNotifierProvider('AAPL'), (_, __) {},
        fireImmediately: true);
    addTearDown(sub.close);

    await c.read(roomNotifierProvider('AAPL').notifier).start();
    final s = sub.read();
    expect(api.getRoomCalls, 60);
    expect(s.done, isTrue);
    expect(s.verdict, isNotNull);
    expect(s.reconnecting, isFalse);
    expect(s.waitGaveUp, isFalse);
    expect(s.error, isNull);
    expect(s.transcript.length, 12);
  });

  test('shows agents the server has checkpointed while still waiting',
      () async {
    final seen = <int>[];
    late ProviderContainer c;
    final api = _Api(onGetRoom: (call) async {
      seen.add(c.read(roomNotifierProvider('AAPL')).transcript.length);
      return call < 4 ? _snap('running', agents: call) : _snap('completed', agents: 5);
    });
    c = _container(api);
    final sub = c.listen(roomNotifierProvider('AAPL'), (_, __) {},
        fireImmediately: true);
    addTearDown(sub.close);

    await c.read(roomNotifierProvider('AAPL').notifier).start();
    // Grows monotonically across polls (call n saw the n-1 agents of call n-1).
    expect(seen, [0, 1, 2, 3]);
    expect(sub.read().done, isTrue);
  });

  test('a stream that ends cleanly without done resumes the wait', () async {
    final api = _Api(
      breakStream: false,
      onGetRoom: (call) async =>
          call < 3 ? _snap('running') : _snap('completed', agents: 3),
    );
    final c = _container(api);
    final sub = c.listen(roomNotifierProvider('AAPL'), (_, __) {},
        fireImmediately: true);
    addTearDown(sub.close);

    await c.read(roomNotifierProvider('AAPL').notifier).start();
    expect(api.getRoomCalls, 3);
    expect(sub.read().done, isTrue);
    expect(sub.read().streaming, isFalse);
  });

  test('an unreachable server ends in a visible give-up, then CHECK AGAIN '
      'resumes and lands the verdict', () async {
    var reachable = false;
    final api = _Api(onGetRoom: (call) async {
      if (!reachable) throw Exception('network down');
      return _snap('completed', agents: 3);
    });
    final c = _container(api);
    final sub = c.listen(roomNotifierProvider('AAPL'), (_, __) {},
        fireImmediately: true);
    addTearDown(sub.close);

    final n = c.read(roomNotifierProvider('AAPL').notifier);
    await n.start();
    var s = sub.read();
    expect(s.waitGaveUp, isTrue, reason: 'giving up must be an explicit state');
    expect(s.reconnecting, isFalse);
    expect(s.done, isFalse);
    expect(s.verdict, isNull);
    expect(s.runId, 'run-1', reason: 'the run id survives so it can resume');

    reachable = true;
    await n.resumeWaiting();
    s = sub.read();
    expect(s.waitGaveUp, isFalse);
    expect(s.done, isTrue);
    expect(s.verdict, isNotNull);
  });

  test('a run that is gone (404) is reported, not waited on', () async {
    final api = _Api(onGetRoom: (call) async {
      throw DioException(
        requestOptions: RequestOptions(path: '/v1/room/run-1'),
        response: Response(
          requestOptions: RequestOptions(path: '/v1/room/run-1'),
          statusCode: 404,
        ),
      );
    });
    final c = _container(api);
    final sub = c.listen(roomNotifierProvider('AAPL'), (_, __) {},
        fireImmediately: true);
    addTearDown(sub.close);

    await c.read(roomNotifierProvider('AAPL').notifier).start();
    final s = sub.read();
    expect(api.getRoomCalls, 1);
    expect(s.error, isNotNull);
    expect(s.waitGaveUp, isFalse);
    expect(s.reconnecting, isFalse);
  });

  testWidgets('the screen words the give-up honestly and offers CHECK AGAIN',
      (tester) async {
    tester.view.physicalSize = const Size(390, 844);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.reset);

    late _FixedRoomNotifier notifier;
    await tester.pumpWidget(ProviderScope(
      overrides: [
        roomNotifierProvider('AAPL').overrideWith((ref) {
          notifier = _FixedRoomNotifier(
            ref,
            'AAPL',
            const RoomState(runId: 'run-1', waitGaveUp: true),
          );
          return notifier;
        }),
      ],
      child: MaterialApp(
        localizationsDelegates: AppLocalizations.localizationsDelegates,
        supportedLocales: AppLocalizations.supportedLocales,
        home: const RoomScreen(ticker: 'AAPL'),
      ),
    ));
    await tester.pump();

    expect(find.textContaining("can't confirm this Room has finished"),
        findsOneWidget);
    expect(find.textContaining('Journal'), findsWidgets);
    expect(find.textContaining('Reconnect timed out'), findsNothing);

    await tester.tap(find.text('CHECK AGAIN'));
    await tester.pump();
    expect(notifier.resumeCalls, 1);
  });
}

class _FixedRoomNotifier extends RoomNotifier {
  _FixedRoomNotifier(super.ref, super.ticker, RoomState fixed) {
    state = fixed;
  }

  int resumeCalls = 0;

  @override
  Future<void> resumeWaiting() async {
    resumeCalls++;
  }
}
