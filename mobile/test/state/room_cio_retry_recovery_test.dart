/// CR237 round 2 (auditor MAJOR-3) — "Ask the CIO again" survives a dropped
/// socket.
///
/// The retry offer and the cost line are driven by server flags the `done`
/// SSE event carries. When the stream dies mid-run the client never sees
/// `done`; `_recoverViaPolling` rebuilds the result from `GET /v1/room/{id}`
/// instead. These tests prove the GET payload's flags are parsed
/// (`RoomRunSnapshot.fromJson`) and carried onto `RoomState` by the recovery
/// path, so an eligible outage run still shows the button.
library;

import 'package:ami_trade/models/journal.dart';
import 'package:ami_trade/models/room.dart';
import 'package:ami_trade/services/api/api_client.dart';
import 'package:ami_trade/state/journal_providers.dart';
import 'package:ami_trade/state/lessons_providers.dart';
import 'package:ami_trade/state/onboarding_providers.dart';
import 'package:ami_trade/state/room_providers.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

Map<String, dynamic> _payload({Map<String, dynamic> extra = const {}}) => {
      'id': 'run-1',
      'user_id': 'u1',
      'ticker': 'AAPL',
      'status': 'completed',
      'model_tier': 'mid',
      'transcript': [
        {'agent_id': 'news_analyst', 'content': 'Headlines are mixed.'},
      ],
      'verdict': null,
      'credit_cost': 12,
      ...extra,
    };

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

/// Streams `started`, then dies the way a real SSE connection does when the
/// phone sleeps; `getRoom` answers with the persisted run, parsed through the
/// real `RoomRunSnapshot.fromJson`.
class _BreakThenRecoverApiClient extends ApiClient {
  _BreakThenRecoverApiClient(this.snapshotJson)
      : super(baseUrl: 'test://localhost');

  final Map<String, dynamic> snapshotJson;
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
    throw Exception('connection closed');
  }

  @override
  Future<RoomRunSnapshot> getRoom(String runId) async {
    getRoomCalls++;
    return RoomRunSnapshot.fromJson(snapshotJson);
  }
}

Future<RoomState> _recover(Map<String, dynamic> snapshotJson) async {
  const ticker = 'AAPL';
  final fake = _BreakThenRecoverApiClient(snapshotJson);
  final container = ProviderContainer(
    overrides: [
      apiClientProvider.overrideWithValue(fake),
      journalNotifierProvider.overrideWith((ref) => _NoopJournal(ref)),
      lessonsNotifierProvider.overrideWith((ref) => _NoopLessons(ref)),
    ],
  );
  addTearDown(container.dispose);
  final sub = container.listen(
    roomNotifierProvider(ticker),
    (_, __) {},
    fireImmediately: true,
  );
  addTearDown(sub.close);

  await container.read(roomNotifierProvider(ticker).notifier).start();
  expect(fake.getRoomCalls, greaterThan(0), reason: 'recovery must run');
  return sub.read();
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  setUp(() => SharedPreferences.setMockInitialValues({}));

  group('RoomRunSnapshot.fromJson — CR237 flags', () {
    test('parses refunded / cio_retry_available / cio_retried', () {
      final snap = RoomRunSnapshot.fromJson(_payload(extra: {
        'refunded': true,
        'cio_retry_available': true,
        'cio_retried': false,
      }));
      expect(snap.refunded, isTrue);
      expect(snap.cioRetryAvailable, isTrue);
      expect(snap.cioRetried, isFalse);
    });

    test('absent or non-bool keys read as false, never inferred', () {
      final absent = RoomRunSnapshot.fromJson(_payload());
      expect(absent.refunded, isFalse);
      expect(absent.cioRetryAvailable, isFalse);
      expect(absent.cioRetried, isFalse);

      final junk = RoomRunSnapshot.fromJson(_payload(extra: {
        'refunded': 'yes',
        'cio_retry_available': 1,
        'cio_retried': null,
      }));
      expect(junk.refunded, isFalse);
      expect(junk.cioRetryAvailable, isFalse);
      expect(junk.cioRetried, isFalse);
    });
  });

  group('polling recovery carries the flags onto RoomState', () {
    test('an eligible outage run still offers "Ask the CIO again"', () async {
      final state = await _recover(_payload(extra: {
        'refunded': true,
        'cio_retry_available': true,
        'cio_retried': false,
      }));
      expect(state.done, isTrue);
      expect(state.error, isNull);
      expect(state.cioRetryAvailable, isTrue);
      expect(state.refunded, isTrue);
      expect(state.cioRetried, isFalse);
      expect(state.creditCost, 12);
    });

    test('a retried run recovers with cioRetried set', () async {
      final state = await _recover(_payload(extra: {
        'refunded': true,
        'cio_retry_available': false,
        'cio_retried': true,
      }));
      expect(state.cioRetryAvailable, isFalse);
      expect(state.cioRetried, isTrue);
    });
  });
}
