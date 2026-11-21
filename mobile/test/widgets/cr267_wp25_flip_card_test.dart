/// CR267 WP-25 — "Changed from X to Y" on the Verdict Board and in the Journal.
///
/// Pinned: a flip shows the card with the changed inputs' own summary lines; a
/// non-flip shows nothing; the same-inputs flip says the inputs were unchanged;
/// a flip whose inputs could not be compared says that and never claims
/// "unchanged"; the answers list appears only when answers are available, with
/// human question labels and before -> after; the Journal list tile carries a
/// one-line form and the detail screen the full section.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/agent.dart';
import 'package:ami_trade/models/journal.dart';
import 'package:ami_trade/models/mandate.dart';
import 'package:ami_trade/models/room.dart';
import 'package:ami_trade/models/room_board.dart';
import 'package:ami_trade/screens/journal/journal_detail_screen.dart';
import 'package:ami_trade/screens/journal/journal_screen.dart';
import 'package:ami_trade/state/journal_providers.dart';
import 'package:ami_trade/state/mandate_providers.dart';
import 'package:ami_trade/widgets/room/room_board.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

RoomVoice _voice(String id) => RoomVoice(
      agentId: id,
      content: 'A contribution.',
      stance: 'for',
      conviction: 'high',
      stanceRecorded: true,
    );

FlipExplainer _flip({
  List<FlipChangedInput> inputs = const [
    FlipChangedInput(
        kind: FlipInputKind.price, summary: 'Price moved +4.2% since 12 Nov.'),
    FlipChangedInput(kind: FlipInputKind.news, summary: '3 new headlines.'),
  ],
  bool compared = true,
  bool same = false,
  bool answers = false,
  List<FlipChangedAnswer> changed = const [],
}) =>
    FlipExplainer(
      previousRunId: 'r0',
      previousAction: 'PASS',
      newAction: 'APPROVE',
      changedInputs: inputs,
      inputsCompared: compared,
      sameInputsFlip: same,
      answersAvailable: answers,
      changedAnswers: changed,
    );

RoomBoardData _board(FlipExplainer? flip) => RoomBoardData(
      ticker: 'NVDA',
      outcome: VerdictOutcome.approve,
      actionToken: 'APPROVE',
      reason: 'Synthesis defended; mandate clears.',
      flipExplainer: flip,
      voices: [for (final a in kCombVoices) _voice(a.id)],
    );

Future<void> _pumpBoard(WidgetTester t, RoomBoardData data) async {
  await t.pumpWidget(MaterialApp(
    localizationsDelegates: AppLocalizations.localizationsDelegates,
    supportedLocales: AppLocalizations.supportedLocales,
    home: Scaffold(body: SingleChildScrollView(child: RoomBoard(data: data))),
  ));
  await t.pumpAndSettle();
}

const _sameInputsLine =
    "Inputs were the same as your last Room on this name. The Room's own debate reached a different call.";
const _notComparedLine =
    "The two Rooms' inputs could not be compared, so what changed is not shown.";

class _FixedMandate extends MandateNotifier {
  _FixedMandate(super.ref) {
    state = MandateState(
      mandate: UserMandate.fromJson({'user_id': 'u1', 'plan': 'trial_trader'}),
    );
  }
  @override
  Future<void> refresh() async {}
}

class _ScriptedJournal extends JournalNotifier {
  _ScriptedJournal(super.ref, List<JournalEntry> entries) {
    state = JournalState(entries: entries, retentionLoaded: true);
  }
  @override
  Future<void> refresh({JournalEntryType? filterType, String? q}) async {}
}

JournalEntry _roomEntry(Map<String, dynamic> verdict) => JournalEntry(
      id: 'e1',
      userId: 'u1',
      entryType: JournalEntryType.roomRun,
      title: 'Room on NVDA',
      createdAt: DateTime.utc(2026, 11, 20),
      agentsInvolved: const [],
      tags: const ['room'],
      ticker: 'NVDA',
      payload: {
        'verdict': verdict,
        'transcript': const [
          {'agent_id': 'bull_researcher', 'content': 'x', 'stance': 'FOR'},
        ],
      },
    );

Map<String, dynamic> _flipJson({bool same = false, bool compared = true}) => {
      'previous_run_id': 'r0',
      'previous_action': 'PASS',
      'new_action': 'APPROVE',
      'changed_inputs': same || !compared
          ? const []
          : [
              {'kind': 'price', 'summary': 'Price moved +4.2% since 12 Nov.'},
              {'kind': 'news', 'summary': '3 new headlines.'},
            ],
      'inputs_compared': compared,
      'same_inputs_flip': same,
      'changed_answers': const [],
      'answers_available': false,
    };

Future<void> _pumpJournal(WidgetTester t, JournalEntry entry,
    {required Widget home}) async {
  await t.pumpWidget(ProviderScope(
    overrides: [
      mandateNotifierProvider.overrideWith((ref) => _FixedMandate(ref)),
      journalNotifierProvider
          .overrideWith((ref) => _ScriptedJournal(ref, [entry])),
    ],
    child: MaterialApp(
      localizationsDelegates: AppLocalizations.localizationsDelegates,
      supportedLocales: AppLocalizations.supportedLocales,
      home: home,
    ),
  ));
  await t.pumpAndSettle();
}

void main() {
  setUp(() => SharedPreferences.setMockInitialValues({}));

  group('verdict card', () {
    testWidgets('a flip shows the card, the heading and the input summaries',
        (t) async {
      await _pumpBoard(t, _board(_flip()));
      expect(t.takeException(), isNull);
      expect(find.byKey(const Key('roomFlipCard')), findsOneWidget);
      expect(find.text('CHANGED FROM PASS TO APPROVE'), findsOneWidget);
      expect(find.text('Price moved +4.2% since 12 Nov.'), findsOneWidget);
      expect(find.text('3 new headlines.'), findsOneWidget);
      expect(find.text(_sameInputsLine), findsNothing);
      expect(find.text(_notComparedLine), findsNothing);
    });

    testWidgets('a non-flip shows nothing', (t) async {
      await _pumpBoard(t, _board(null));
      expect(find.byKey(const Key('roomFlipCard')), findsNothing);
      expect(find.textContaining('CHANGED FROM'), findsNothing);
    });

    testWidgets("the same-inputs flip says so, in the Room's own voice",
        (t) async {
      await _pumpBoard(t, _board(_flip(inputs: const [], same: true)));
      expect(find.text(_sameInputsLine), findsOneWidget);
      expect(find.textContaining('the AI'), findsNothing);
      expect(find.text(_notComparedLine), findsNothing);
    });

    testWidgets('inputs that could not be compared are never called unchanged',
        (t) async {
      await _pumpBoard(t, _board(_flip(inputs: const [], compared: false)));
      expect(find.text(_notComparedLine), findsOneWidget);
      expect(find.text(_sameInputsLine), findsNothing);
      expect(find.textContaining('same'), findsNothing);
      expect(find.textContaining('unchanged'), findsNothing);
    });

    testWidgets(
        'compared false wins even if the server also set same_inputs_flip',
        (t) async {
      await _pumpBoard(
          t, _board(_flip(inputs: const [], compared: false, same: true)));
      expect(find.text(_notComparedLine), findsOneWidget);
      expect(find.text(_sameInputsLine), findsNothing);
    });

    testWidgets('answers list shows only when available, with human labels',
        (t) async {
      const changed = [
        FlipChangedAnswer(
            question: 'catalyst_in_horizon', before: 'no', after: 'yes'),
        FlipChangedAnswer(
            question: 'bear_objection_answered',
            before: 'not asked',
            after: 'yes'),
        FlipChangedAnswer(
            question: 'terminal_vulnerability', before: 'yes', after: 'no'),
        FlipChangedAnswer(
            question: 'event_risk_wait', before: 'yes', after: 'no'),
        FlipChangedAnswer(
            question: 'thesis_material_directional',
            before: 'no',
            after: 'yes'),
        FlipChangedAnswer(
            question: 'trade_proposed', before: 'no', after: 'yes'),
        FlipChangedAnswer(
            question: 'some_new_question', before: 'a', after: 'b'),
      ];
      await _pumpBoard(t, _board(_flip(answers: true, changed: changed)));
      expect(find.text('ANSWERS THAT CHANGED'), findsOneWidget);
      expect(find.text('Catalyst inside the horizon'), findsOneWidget);
      expect(find.text('no → yes'), findsNWidgets(3));
      expect(find.text('not asked → yes'), findsOneWidget);
      expect(find.text('Bear objection answered'), findsOneWidget);
      expect(find.text('Terminal vulnerability'), findsOneWidget);
      expect(find.text('Event risk: wait'), findsOneWidget);
      expect(find.text('Thesis is material and directional'), findsOneWidget);
      expect(find.text('Trade proposed'), findsOneWidget);
      expect(find.text('some new question'), findsOneWidget);
      expect(find.text('catalyst_in_horizon'), findsNothing);
    });

    testWidgets('answers unavailable: no answers section, no apology',
        (t) async {
      final e = FlipExplainer(
        previousRunId: 'r0',
        previousAction: 'PASS',
        newAction: 'APPROVE',
        changedInputs: _flip().changedInputs,
        answersAvailable: false,
        answersUnavailableReason: 'previous_run_without_coded_rule',
        changedAnswers: const [
          FlipChangedAnswer(
              question: 'trade_proposed', before: 'no', after: 'yes'),
        ],
      );
      await _pumpBoard(t, _board(e));
      expect(find.byKey(const Key('roomFlipCard')), findsOneWidget);
      expect(find.text('ANSWERS THAT CHANGED'), findsNothing);
      expect(find.text('Trade proposed'), findsNothing);
      expect(find.textContaining('unavailable'), findsNothing);
      expect(find.textContaining('previous_run_without'), findsNothing);
    });
  });

  group('journal', () {
    testWidgets('the list tile carries the one-line form with the first input',
        (t) async {
      await _pumpJournal(
        t,
        _roomEntry({
          'action': 'APPROVE',
          'reason': 'r',
          'flip_explainer': _flipJson(),
        }),
        home: const Scaffold(body: JournalScreen(embedded: true)),
      );
      expect(find.byKey(const Key('roomFlipJournalLine')), findsOneWidget);
      expect(
        find.text(
            'Changed from PASS to APPROVE: Price moved +4.2% since 12 Nov.'),
        findsOneWidget,
      );
      expect(find.text('3 new headlines.'), findsNothing);
    });

    testWidgets('the one-liner uses the same-inputs line when that is the case',
        (t) async {
      await _pumpJournal(
        t,
        _roomEntry({
          'action': 'APPROVE',
          'reason': 'r',
          'flip_explainer': _flipJson(same: true),
        }),
        home: const Scaffold(body: JournalScreen(embedded: true)),
      );
      expect(find.text('Changed from PASS to APPROVE: $_sameInputsLine'),
          findsOneWidget);
    });

    testWidgets('an entry without the block shows no one-liner', (t) async {
      await _pumpJournal(
        t,
        _roomEntry({'action': 'APPROVE', 'reason': 'r'}),
        home: const Scaffold(body: JournalScreen(embedded: true)),
      );
      expect(find.byKey(const Key('roomFlipJournalLine')), findsNothing);
    });

    testWidgets('the detail view carries the full section', (t) async {
      await _pumpJournal(
        t,
        _roomEntry({
          'action': 'APPROVE',
          'reason': 'r',
          'flip_explainer': _flipJson(),
        }),
        home: const JournalDetailScreen(entryId: 'e1'),
      );
      expect(find.byKey(const Key('roomFlipCard')), findsOneWidget);
      expect(find.text('CHANGED FROM PASS TO APPROVE'), findsOneWidget);
      expect(find.text('Price moved +4.2% since 12 Nov.'), findsOneWidget);
      expect(find.text('3 new headlines.'), findsOneWidget);
    });
  });
}
