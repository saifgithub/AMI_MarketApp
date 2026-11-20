/// DEF507 — a desk whose own call failed shows AMI's standing guidance
/// labelled as such, never as that desk's live call.
///
/// The server marks the turn (`scripted: true` on `agent_token` / `agent_done`,
/// and on the stored transcript line). Pinned here: the parser keeps the flag
/// only when true (an older server omits it and the turn reads as live), the
/// notifier records the desk on the first token, the snapshot rebuild does the
/// same for recovery, and the transcript row says "standing guidance" instead
/// of quoting the scripted text as the desk's gist.
///
/// The SSE strings are transcribed from `backend/app/api/room.py` (the
/// `tok`/`done` dicts) as written for DEF507.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/journal.dart';
import 'package:ami_trade/models/room.dart';
import 'package:ami_trade/models/room_board.dart';
import 'package:ami_trade/models/room_board_mappers.dart';
import 'package:ami_trade/services/api/api_client.dart';
import 'package:ami_trade/state/journal_providers.dart';
import 'package:ami_trade/state/lessons_providers.dart';
import 'package:ami_trade/state/onboarding_providers.dart';
import 'package:ami_trade/state/room_providers.dart';
import 'package:ami_trade/widgets/room/room_transcript_rows.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

const _scriptedText =
    'Translating the synthesis: BUY MSFT at \$498.30. Stop \$468.40, '
    'target \$540.00.';

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

Future<void> _pump(WidgetTester t, Widget child) async {
  await t.pumpWidget(
    MaterialApp(
      localizationsDelegates: AppLocalizations.localizationsDelegates,
      supportedLocales: AppLocalizations.supportedLocales,
      home: Scaffold(body: SingleChildScrollView(child: child)),
    ),
  );
  await t.pumpAndSettle();
}

void main() {
  setUp(() => SharedPreferences.setMockInitialValues({}));
  late AppLocalizations l;
  setUpAll(() async {
    l = await AppLocalizations.delegate.load(const Locale('en'));
  });

  group('wire parsing', () {
    test('agent_token keeps scripted only when true', () {
      final scripted = parseRoomSseEvent('agent_token',
          '{"agent_id": "trader", "text": "S", "scripted": true}');
      expect(scripted!['scripted'], isTrue);
      final live =
          parseRoomSseEvent('agent_token', '{"agent_id": "trader", "text": "L"}');
      expect(live!.containsKey('scripted'), isFalse);
    });

    test('agent_done keeps scripted only when true, old server omits it', () {
      final scripted = parseRoomSseEvent('agent_done',
          '{"agent_id": "trader", "stance": null, "scripted": true}');
      expect(scripted!['scripted'], isTrue);
      final old =
          parseRoomSseEvent('agent_done', '{"agent_id": "trader"}');
      expect(old, isNotNull);
      expect(old!.containsKey('scripted'), isFalse);
    });

    test('snapshot transcript parses scripted, and a missing field is false',
        () {
      final snap = RoomRunSnapshot.fromJson({
        'id': 'r1',
        'user_id': 'u1',
        'ticker': 'MSFT',
        'transcript': [
          {'agent_id': 'trader', 'content': 'x', 'scripted': true},
          {'agent_id': 'market_analyst', 'content': 'y', 'scripted': false},
          {'agent_id': 'bull_researcher', 'content': 'z'},
        ],
      });
      expect(snap.transcript.map((t) => t.scripted), [true, false, false]);
    });
  });

  group('notifier', () {
    Future<RoomState> run(List<Map<String, dynamic>> events) async {
      final container = ProviderContainer(overrides: [
        apiClientProvider.overrideWithValue(_ScriptedApiClient(events)),
        journalNotifierProvider.overrideWith((ref) => _NoopJournal(ref)),
        lessonsNotifierProvider.overrideWith((ref) => _NoopLessons(ref)),
      ]);
      addTearDown(container.dispose);
      final sub = container.listen(roomNotifierProvider('MSFT'), (_, __) {},
          fireImmediately: true);
      addTearDown(sub.close);
      await container.read(roomNotifierProvider('MSFT').notifier).start();
      return sub.read();
    }

    test('only the desk the server marked is recorded as scripted', () async {
      final s = await run([
        {'kind': 'started', 'run_id': 'r1'},
        {
          'kind': 'agent_token',
          'agent_id': 'trader',
          'text': 'BUY ',
          'scripted': true
        },
        {
          'kind': 'agent_token',
          'agent_id': 'trader',
          'text': 'MSFT.',
          'scripted': true
        },
        {'kind': 'agent_done', 'agent_id': 'trader', 'scripted': true},
        {'kind': 'agent_token', 'agent_id': 'market_analyst', 'text': 'Up.'},
        {'kind': 'agent_done', 'agent_id': 'market_analyst'},
        {'kind': 'done', 'run_id': 'r1'},
      ]);
      expect(s.scriptedAgents, {'trader'});
      expect(s.transcript['trader'], 'BUY MSFT.');
    });

    test('an old server (no field anywhere) leaves every desk live', () async {
      final s = await run([
        {'kind': 'started', 'run_id': 'r1'},
        {'kind': 'agent_token', 'agent_id': 'trader', 'text': 'BUY.'},
        {'kind': 'agent_done', 'agent_id': 'trader'},
        {'kind': 'done', 'run_id': 'r1'},
      ]);
      expect(s.scriptedAgents, isEmpty);
    });

    test('a backup restart voids the scripted marks with the turns', () async {
      final s = await run([
        {'kind': 'started', 'run_id': 'r1'},
        {
          'kind': 'agent_token',
          'agent_id': 'trader',
          'text': 'S',
          'scripted': true
        },
        {'kind': 'provider_switch', 'text': 'Switching to the backup.'},
        {'kind': 'agent_token', 'agent_id': 'trader', 'text': 'Live.'},
        {'kind': 'agent_done', 'agent_id': 'trader'},
        {'kind': 'done', 'run_id': 'r1'},
      ]);
      expect(s.scriptedAgents, isEmpty);
    });
  });

  group('rows', () {
    testWidgets('a scripted turn shows the standing-guidance label, not its '
        'gist', (t) async {
      await _pump(
        t,
        TranscriptRow(
          voice: const RoomVoice(
              agentId: 'trader', content: _scriptedText, scripted: true),
          expanded: false,
          onToggle: () {},
        ),
      );
      expect(find.text(l.roomScriptedLabel), findsOneWidget);
      expect(find.byKey(const Key('scriptedTurnLabel')), findsOneWidget);
      expect(find.textContaining('BUY MSFT'), findsNothing,
          reason: 'collapsed, the scripted text must not read as the desk\'s call');
    });

    testWidgets('a live turn has no label', (t) async {
      await _pump(
        t,
        TranscriptRow(
          voice: const RoomVoice(
              agentId: 'trader',
              content: 'Entry 498.3, stop 468.4, target 540.',
              headline: 'Entry 498.3'),
          expanded: true,
          onToggle: () {},
        ),
      );
      expect(find.text(l.roomScriptedLabel), findsNothing);
      expect(find.byKey(const Key('scriptedTurnNote')), findsNothing);
      expect(find.text('Entry 498.3'), findsOneWidget);
    });

    testWidgets('expanded, a scripted turn carries the chip and the AMI note',
        (t) async {
      await _pump(
        t,
        TranscriptRow(
          voice: const RoomVoice(
              agentId: 'trader', content: _scriptedText, scripted: true),
          expanded: true,
          onToggle: () {},
        ),
      );
      expect(find.byKey(const Key('scriptedTurnNote')), findsOneWidget);
      expect(find.text(l.roomScriptedNote), findsOneWidget);
      expect(l.roomScriptedNote, contains('AMI'));
      expect(l.roomScriptedNote.toLowerCase(), isNot(contains('the ai')));
    });

    testWidgets('only the scripted desk is labelled among several', (t) async {
      await _pump(
        t,
        RoomTranscriptRows(voices: const [
          RoomVoice(
              agentId: 'trader', content: _scriptedText, scripted: true),
          RoomVoice(
              agentId: 'market_analyst',
              content: 'Trend is up.',
              headline: 'Trend up'),
        ]),
      );
      expect(find.byKey(const Key('scriptedTurnLabel')), findsOneWidget);
      expect(find.text('Trend up'), findsOneWidget);
    });
  });

  group('mapping', () {
    test('room state marks only the scripted desks on the transcript voices',
        () {
      final voices = transcriptVoicesFromRoomState(const RoomState(
        transcript: {'trader': _scriptedText, 'market_analyst': 'Up.'},
        scriptedAgents: {'trader'},
      ));
      expect(voices.firstWhere((v) => v.agentId == 'trader').scripted, isTrue);
      expect(
          voices.firstWhere((v) => v.agentId == 'market_analyst').scripted,
          isFalse);
    });

    test('a Journal payload row carries the mark, and an old row reads live',
        () {
      final entry = JournalEntry.fromJson({
        'id': 'e1',
        'user_id': 'u1',
        'entry_type': 'room_run',
        'title': 't',
        'summary': 's',
        'created_at': '2026-11-20T00:00:00Z',
        'tags': const [],
        'agents_involved': const [],
        'outcome': 'pending',
        'payload': {
          'transcript': [
            {'agent_id': 'trader', 'content': _scriptedText, 'scripted': true},
            {'agent_id': 'market_analyst', 'content': 'Up.'},
          ],
        },
      });
      final voices = transcriptVoicesFromJournalEntry(entry);
      expect(voices.firstWhere((v) => v.agentId == 'trader').scripted, isTrue);
      expect(
          voices.firstWhere((v) => v.agentId == 'market_analyst').scripted,
          isFalse);
    });
  });
}
