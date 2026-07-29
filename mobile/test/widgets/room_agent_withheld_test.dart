/// CR098-MOBILE-LIVE — the locked-chair / roster-countdown surface for
/// `agent_withheld` (roster tenure pull-back), plus `withheld_tenure` on the
/// existing CR090 `live_data_notice` card.
///
/// Two layers proven here:
///   1. `RoomNotifier.start()` end-to-end: a real `agent_withheld` event,
///      shaped exactly like `parseRoomSseEvent` emits it, drives the
///      notifier's own switch and lands in `RoomState.withheldAgents` +
///      `order` — not just a fixture-seeded state (acceptance #3).
///   2. `RoomScreen` renders the locked chair inline, in seat, with a
///      roster-level (never per-agent) countdown, and the `withheld_tenure`
///      live-data-notice case renders distinctly from `withheld_paid` /
///      `unavailable` with its own CTA (D1) — a mutation swapping it onto
///      the credits CTA fails the last test in this file.
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
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

/// Replays a canned event sequence as if already parsed by
/// `parseRoomSseEvent` — no real HTTP/SSE involved, but the exact shape
/// `parseRoomSseEvent('agent_withheld', ...)` returns (api_client.dart).
class _ScriptedApiClient extends ApiClient {
  _ScriptedApiClient(this.events) : super(baseUrl: 'test://localhost');

  final List<Map<String, dynamic>> events;

  @override
  Stream<Map<String, dynamic>> streamRoom({
    required String userId,
    required String ticker,
    String locale = 'en',
    Map<String, dynamic>? mandateOverride,
  }) {
    return Stream.fromIterable(events);
  }
}

class _FixedRoomNotifier extends RoomNotifier {
  _FixedRoomNotifier(super.ref, super.ticker, RoomState fixed) {
    state = fixed;
  }
}

/// Both notifiers self-refresh on creation AND are refreshed again when a run
/// finishes, so leaving them real makes the run's completion path issue live
/// HTTP against the fake base URL and hang. They are irrelevant to what these
/// tests measure — neutralise them rather than let them decide the result.
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

/// Streams a few events and then throws, the way a real SSE connection dies
/// when the phone sleeps or the network drops mid-run — the path
/// `_recoverViaPolling` exists for. `getRoom` then answers with the backend's
/// persisted final state, which contains **only agents that spoke**: a locked
/// chair is deliberately never in the transcript, so recovery cannot learn
/// about it from the snapshot and must preserve what the stream already told
/// the client.
class _BreakThenRecoverApiClient extends ApiClient {
  _BreakThenRecoverApiClient(
    this.events,
    this.snapshotTranscript, {
    this.breakStream = true,
  }) : super(baseUrl: 'test://localhost');

  final List<Map<String, dynamic>> events;
  final List<RoomTranscriptLine> snapshotTranscript;

  /// When false the stream ends cleanly, so recovery must not run at all —
  /// which is what makes `getRoomCalls` a discriminator rather than a
  /// coincidence.
  final bool breakStream;
  int getRoomCalls = 0;

  @override
  Stream<Map<String, dynamic>> streamRoom({
    required String userId,
    required String ticker,
    String locale = 'en',
    Map<String, dynamic>? mandateOverride,
  }) async* {
    for (final e in events) {
      yield e;
    }
    await Future<void>.delayed(Duration.zero);
    if (breakStream) throw Exception('connection closed');
  }

  @override
  Future<RoomRunSnapshot> getRoom(String runId) async {
    getRoomCalls++;
    return RoomRunSnapshot(
      id: runId,
      userId: 'u1',
      ticker: 'AAPL',
      status: 'completed',
      modelTier: 'mid',
      transcript: snapshotTranscript,
    );
  }
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  setUp(() {
    // CR106: the locked chair (`_WithheldAgentChair`) is a transcript-mode
    // widget, and a finished run now defaults to the board. Declared rather
    // than inherited. The board's own equivalent — the roster gap surviving
    // the same dropped connection, from `agent_withheld` alone with no verdict
    // to read `opinions_not_included` off — is pinned in `room_board_test.dart`.
    SharedPreferences.setMockInitialValues(
      {'ami_room_view_mode': 'transcript'},
    );
  });

  group('agent_withheld reaches RoomState via the real notifier', () {
    test('populates withheldAgents and mirrors the agentId into order', () async {
      const ticker = 'AAPL';
      final fake = _ScriptedApiClient([
        {'kind': 'phase', 'label': 'ANALYSTS'},
        {
          'kind': 'agent_withheld',
          'agent_id': 'market_analyst',
          'reason': 'upgrade',
          'next_step_agent': 'social_media_analyst',
          'next_step_days': 4,
        },
      ]);
      final container = ProviderContainer(
        overrides: [apiClientProvider.overrideWithValue(fake)],
      );
      addTearDown(container.dispose);

      await container.read(roomNotifierProvider(ticker).notifier).start();

      final state = container.read(roomNotifierProvider(ticker));
      expect(state.withheldAgents['market_analyst'], isNotNull);
      expect(state.withheldAgents['market_analyst']!.nextStepAgentId,
          'social_media_analyst');
      expect(state.withheldAgents['market_analyst']!.nextStepDays, 4);
      expect(state.order, contains('market_analyst'));
      // Never in transcript — a locked chair has no streamed text.
      expect(state.transcript.containsKey('market_analyst'), isFalse);
    });

    test('next_step both null is preserved as null, not defaulted', () async {
      const ticker = 'MSFT';
      final fake = _ScriptedApiClient([
        {
          'kind': 'agent_withheld',
          'agent_id': 'social_media_analyst',
          'reason': 'upgrade',
          'next_step_agent': null,
          'next_step_days': null,
        },
      ]);
      final container = ProviderContainer(
        overrides: [apiClientProvider.overrideWithValue(fake)],
      );
      addTearDown(container.dispose);

      await container.read(roomNotifierProvider(ticker).notifier).start();

      final info = container
          .read(roomNotifierProvider(ticker))
          .withheldAgents['social_media_analyst']!;
      expect(info.nextStepAgentId, isNull);
      expect(info.nextStepDays, isNull);
    });
  });

  group('the locked chair survives a dropped connection (audit round 1 MAJOR)',
      () {
    /// `_recoverViaPolling` rebuilds `order` from the snapshot transcript, and
    /// `RoomScreen` renders chairs by iterating `order` — so before the fix an
    /// ordinary mid-run disconnect finished the run with the analyst simply
    /// missing: no chair, no countdown, no upgrade path, `error == null`. The
    /// user is told nothing and concludes they got the full roster, which is
    /// the DEF059 fail-open class the gate on this lane exists for.
    test('recovery re-seats the withheld agent into order', () async {
      const ticker = 'AAPL';
      final fake = _BreakThenRecoverApiClient(
        [
          {'kind': 'started', 'run_id': 'run-1'},
          {'kind': 'phase', 'label': 'ANALYSTS'},
          {
            'kind': 'agent_withheld',
            'agent_id': 'market_analyst',
            'reason': 'upgrade',
            'next_step_agent': 'social_media_analyst',
            'next_step_days': 4,
          },
        ],
        const [
          RoomTranscriptLine(
              agentId: 'news_analyst', content: 'Headlines are mixed.'),
          RoomTranscriptLine(
              agentId: 'pm', content: 'Holding for now.'),
        ],
      );
      final container = ProviderContainer(
        overrides: [
          apiClientProvider.overrideWithValue(fake),
          journalNotifierProvider.overrideWith((ref) => _NoopJournal(ref)),
          lessonsNotifierProvider.overrideWith((ref) => _NoopLessons(ref)),
        ],
      );
      addTearDown(container.dispose);
      // Held from the start: the provider is autoDispose and self-starting, so
      // reading `.notifier` and re-reading the provider after real async work
      // can otherwise observe a fresh element and an empty state.
      final sub = container.listen(
        roomNotifierProvider(ticker),
        (_, __) {},
        fireImmediately: true,
      );
      addTearDown(sub.close);

      await container.read(roomNotifierProvider(ticker).notifier).start();
      final state = sub.read();

      expect(fake.getRoomCalls, greaterThan(0), reason: 'recovery must run');
      expect(state.done, isTrue);
      expect(state.error, isNull);
      // The snapshot never mentions market_analyst — only the stream did.
      expect(state.withheldAgents['market_analyst'], isNotNull);
      expect(state.order, contains('market_analyst'));
      // Seated ahead of the agents that spoke, as D4 asks.
      expect(state.order.indexOf('market_analyst'),
          lessThan(state.order.indexOf('news_analyst')));
      // Still never in the transcript.
      expect(state.transcript.containsKey('market_analyst'), isFalse);
    });

    testWidgets('and the chair still renders after recovery', (t) async {
      const ticker = 'AAPL';
      final fake = _BreakThenRecoverApiClient(
        [
          {'kind': 'started', 'run_id': 'run-1'},
          {
            'kind': 'agent_withheld',
            'agent_id': 'market_analyst',
            'reason': 'upgrade',
            'next_step_agent': 'social_media_analyst',
            'next_step_days': 4,
          },
        ],
        const [
          RoomTranscriptLine(
              agentId: 'news_analyst', content: 'Headlines are mixed.'),
        ],
      );
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
      // `testWidgets` runs inside a fake-async zone where real timers never
      // fire, and both the scripted stream and the polling loop await real
      // Futures — so the drive has to happen in the real zone or it parks
      // forever. Only the render below needs the fake clock.
      RoomState? recoveredOrNull;
      await t.runAsync(() async {
        await container.read(roomNotifierProvider(ticker).notifier).start();
        recoveredOrNull = sub.read();
      });
      final recovered = recoveredOrNull!;
      expect(recovered.order, contains('market_analyst'));

      await t.pumpWidget(
        ProviderScope(
          overrides: [
            roomNotifierProvider(ticker).overrideWith(
                (ref) => _FixedRoomNotifier(ref, ticker, recovered)),
          ],
          child: MaterialApp(
            localizationsDelegates: AppLocalizations.localizationsDelegates,
            supportedLocales: AppLocalizations.supportedLocales,
            home: RoomScreen(ticker: ticker),
          ),
        ),
      );
      await t.pump();

      expect(find.textContaining('off your roster'), findsOneWidget);
      expect(t.takeException(), isNull);
    });
  });

  group('a malformed agent_withheld does not kill the run (round 1 MINOR)', () {
    /// The case forwards raw `dynamic`, so a hard cast threw inside `await for`
    /// — where the generic catch reads any throw as a dropped socket. One bad
    /// field therefore aborted the live stream, diverted to polling recovery,
    /// and lost every later event, reporting nothing to the user.
    for (final bad in <String, Map<String, dynamic>>{
      'agent_id absent': {'kind': 'agent_withheld', 'reason': 'upgrade'},
      'agent_id non-String': {'kind': 'agent_withheld', 'agent_id': 7},
      'next_step_days as String': {
        'kind': 'agent_withheld',
        'agent_id': 'market_analyst',
        'next_step_days': '4',
      },
      'reason non-String': {
        'kind': 'agent_withheld',
        'agent_id': 'market_analyst',
        'reason': 7,
      },
    }.entries) {
      test(bad.key, () async {
        const ticker = 'AAPL';
        final fake = _BreakThenRecoverApiClient([
          {'kind': 'started', 'run_id': 'run-1'},
          bad.value,
          {
            'kind': 'agent_token',
            'agent_id': 'news_analyst',
            'text': 'Headlines are mixed.',
          },
        ], const [], breakStream: false);
        final container = ProviderContainer(
          overrides: [apiClientProvider.overrideWithValue(fake)],
        );
        addTearDown(container.dispose);
        final sub = container.listen(
          roomNotifierProvider(ticker),
          (_, __) {},
          fireImmediately: true,
        );
        addTearDown(sub.close);

        await container.read(roomNotifierProvider(ticker).notifier).start();
        final state = sub.read();

        // The event after the malformed one still landed — proof the stream
        // was never aborted.
        expect(state.transcript['news_analyst'], 'Headlines are mixed.');
        // And the run never fell into the disconnect path at all.
        expect(fake.getRoomCalls, 0);
        expect(state.error, isNull);
      });
    }
  });

  Future<void> pumpFixed(WidgetTester t, String ticker, RoomState fixed) {
    return t.pumpWidget(
      ProviderScope(
        overrides: [
          roomNotifierProvider(ticker)
              .overrideWith((ref) => _FixedRoomNotifier(ref, ticker, fixed)),
        ],
        child: MaterialApp(
          localizationsDelegates: AppLocalizations.localizationsDelegates,
          supportedLocales: AppLocalizations.supportedLocales,
          home: RoomScreen(ticker: ticker),
        ),
      ),
    );
  }

  group('locked chair rendering (D3/D4)', () {
    testWidgets(
        'renders in seat with a roster-level countdown naming the OTHER agent',
        (t) async {
      const ticker = 'AAPL';
      await pumpFixed(
        t,
        ticker,
        const RoomState(
          streaming: true,
          order: ['market_analyst'],
          withheldAgents: {
            'market_analyst': WithheldAgentInfo(
              agentId: 'market_analyst',
              reason: 'upgrade',
              nextStepAgentId: 'social_media_analyst',
              nextStepDays: 4,
            ),
          },
        ),
      );
      await t.pump();

      expect(find.textContaining('off your roster'), findsOneWidget);
      // Roster-level: names the NEXT step's agent (Social), never claims
      // the withheld chair (Market) itself is the one returning.
      expect(find.textContaining('Social Media Analyst'), findsOneWidget);
      expect(find.textContaining('4 days'), findsOneWidget);
      expect(t.takeException(), isNull);
    });

    testWidgets('next_step both null omits the countdown, no "null days"',
        (t) async {
      const ticker = 'AAPL';
      await pumpFixed(
        t,
        ticker,
        const RoomState(
          streaming: true,
          order: ['social_media_analyst'],
          withheldAgents: {
            'social_media_analyst': WithheldAgentInfo(
              agentId: 'social_media_analyst',
              reason: 'upgrade',
            ),
          },
        ),
      );
      await t.pump();

      expect(find.textContaining('off your roster'), findsOneWidget);
      expect(find.textContaining('Next roster change'), findsNothing);
      expect(find.textContaining('null'), findsNothing);
      expect(t.takeException(), isNull);
    });

    testWidgets('locked chair sits ahead of a real agent line in the same order',
        (t) async {
      const ticker = 'AAPL';
      await pumpFixed(
        t,
        ticker,
        const RoomState(
          streaming: true,
          order: ['market_analyst', 'fundamentals_analyst'],
          transcript: {'fundamentals_analyst': 'The balance sheet is solid.'},
          withheldAgents: {
            'market_analyst': WithheldAgentInfo(
              agentId: 'market_analyst',
              reason: 'upgrade',
            ),
          },
        ),
      );
      await t.pump();

      final chairFinder = find.textContaining('off your roster');
      final lineFinder = find.textContaining('balance sheet is solid');
      expect(chairFinder, findsOneWidget);
      expect(lineFinder, findsOneWidget);
      final chairY = t.getTopLeft(chairFinder).dy;
      final lineY = t.getTopLeft(lineFinder).dy;
      expect(chairY, lessThan(lineY));
    });
  });

  group('live_data_notice withheld_tenure (CR098 D1)', () {
    testWidgets(
        'renders distinct copy from withheld_paid/unavailable, with its OWN CTA',
        (t) async {
      const ticker = 'AAPL';
      await pumpFixed(
        t,
        ticker,
        const RoomState(
          liveDataNotice: RoomLiveDataNotice(
            news: 'withheld_tenure',
            social: 'unavailable',
            surchargeCharged: 0,
          ),
        ),
      );
      await t.pump();

      expect(find.textContaining('needs a plan upgrade'), findsOneWidget);
      expect(find.text('UPGRADE YOUR PLAN'), findsOneWidget);
      // The DEF059-class inversion this state exists to catch: a tenure
      // withhold must NEVER show the credits CTA (buying credits does
      // nothing for it).
      expect(find.text('UPGRADE FOR LIVE DATA'), findsNothing);
      expect(find.textContaining('needs credits'), findsNothing);
      expect(t.takeException(), isNull);
    });
  });
}
