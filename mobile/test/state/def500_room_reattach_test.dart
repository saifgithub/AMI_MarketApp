/// DEF500 — reopening onto a Room that is still running.
///
/// AMI-DL-3 (E5-ROOM-01): the app was killed mid-run, reopened, and the Room
/// came back with the desks that had already reported marked NO RESPONSE and
/// no banner. The server now announces `reattached` and replays the run from
/// its first desk; the client must (1) parse the event, (2) rebuild the whole
/// transcript from the replay, (3) say it rejoined a Room in progress.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/journal.dart';
import 'package:ami_trade/screens/room/room_screen.dart';
import 'package:ami_trade/services/api/api_client.dart';
import 'package:ami_trade/state/journal_providers.dart';
import 'package:ami_trade/state/lessons_providers.dart';
import 'package:ami_trade/state/onboarding_providers.dart';
import 'package:ami_trade/state/room_providers.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

class _ScriptedApiClient extends ApiClient {
  _ScriptedApiClient(this.events) : super(baseUrl: 'test://localhost');

  final List<Map<String, dynamic>> events;

  @override
  Stream<Map<String, dynamic>> streamRoom({
    required String userId,
    required String ticker,
    String locale = 'en',
    Map<String, dynamic>? mandateOverride,
    Map<String, dynamic>? alpaca,
  }) =>
      Stream.fromIterable(events);
}

class _NoopJournal extends JournalNotifier {
  _NoopJournal(super.ref);
  @override
  Future<void> refresh({JournalEntryType? filterType, String? q}) async {}
}

class _NoopLessons extends LessonsNotifier {
  _NoopLessons(super.ref);
  @override
  Future<void> refresh() async {}
}

List<Override> _overrides(List<Map<String, dynamic>> events) => [
      apiClientProvider.overrideWithValue(_ScriptedApiClient(events)),
      journalNotifierProvider.overrideWith((ref) => _NoopJournal(ref)),
      lessonsNotifierProvider.overrideWith((ref) => _NoopLessons(ref)),
    ];

void main() {
  setUp(() => SharedPreferences.setMockInitialValues({}));

  test('parseRoomSseEvent understands the reattached event', () {
    final ev = parseRoomSseEvent('reattached', '{"run_id":"r1"}');
    expect(ev, isNotNull);
    expect(ev!['kind'], 'reattached');
  });

  test('a replayed run rebuilds every desk and flags the reattachment',
      () async {
    final container = ProviderContainer(overrides: _overrides([
      {'kind': 'reattached'},
      {'kind': 'started', 'run_id': 'r1'},
      {'kind': 'agent_token', 'agent_id': 'market_analyst', 'text': 'Trend '},
      {'kind': 'agent_token', 'agent_id': 'market_analyst', 'text': 'is up.'},
      {'kind': 'agent_done', 'agent_id': 'market_analyst'},
      {'kind': 'agent_token', 'agent_id': 'bull_researcher', 'text': 'Buy.'},
      {'kind': 'agent_done', 'agent_id': 'bull_researcher'},
      {'kind': 'done', 'run_id': 'r1'},
    ]));
    addTearDown(container.dispose);
    final sub = container.listen(roomNotifierProvider('MSFT'), (_, __) {},
        fireImmediately: true);
    addTearDown(sub.close);

    await container.read(roomNotifierProvider('MSFT').notifier).start();

    final s = sub.read();
    expect(s.reattached, isTrue);
    expect(s.transcript['market_analyst'], 'Trend is up.');
    expect(s.transcript['bull_researcher'], 'Buy.');
    expect(s.order, ['market_analyst', 'bull_researcher']);
  });

  test('a fresh convene is not flagged as reattached', () async {
    final container = ProviderContainer(overrides: _overrides([
      {'kind': 'started', 'run_id': 'r1'},
      {'kind': 'done', 'run_id': 'r1'},
    ]));
    addTearDown(container.dispose);
    final sub = container.listen(roomNotifierProvider('MSFT'), (_, __) {},
        fireImmediately: true);
    addTearDown(sub.close);

    await container.read(roomNotifierProvider('MSFT').notifier).start();

    expect(sub.read().reattached, isFalse);
  });

  Future<void> pumpRoom(WidgetTester t, RoomState fixed) async {
    await t.pumpWidget(
      ProviderScope(
        overrides: [
          roomNotifierProvider('MSFT')
              .overrideWith((ref) => _FixedRoomNotifier(ref, 'MSFT', fixed)),
        ],
        child: MaterialApp(
          localizationsDelegates: AppLocalizations.localizationsDelegates,
          supportedLocales: AppLocalizations.supportedLocales,
          home: const RoomScreen(ticker: 'MSFT'),
        ),
      ),
    );
    await t.pump();
  }

  testWidgets('the Room shows the rejoined banner while the run is in flight',
      (t) async {
    await pumpRoom(
      t,
      const RoomState(streaming: true, reattached: true, runId: 'r1'),
    );
    expect(find.byKey(const Key('roomReattachedBanner')), findsOneWidget);
    final l = AppLocalizations.of(t.element(find.byType(RoomScreen)));
    expect(find.text(l.roomReattachedBanner), findsOneWidget);
  });

  testWidgets('no banner on a fresh run', (t) async {
    await pumpRoom(t, const RoomState(streaming: true, runId: 'r1'));
    expect(find.byKey(const Key('roomReattachedBanner')), findsNothing);
  });

  testWidgets('no banner once the reattached run is done', (t) async {
    await pumpRoom(
      t,
      const RoomState(reattached: true, done: true, runId: 'r1'),
    );
    await t.pumpAndSettle();
    expect(find.byKey(const Key('roomReattachedBanner')), findsNothing);
  });
}

class _FixedRoomNotifier extends RoomNotifier {
  _FixedRoomNotifier(super.ref, super.ticker, RoomState fixed) {
    state = fixed;
  }
}
