/// CR266 — the two new Verdict Board cards: the contested card and the
/// next-convene change card.
///
/// The pinned refusals are the point: an old verdict with no record shows no
/// contested card (never a fabricated "not contested"), an absent price move
/// shows no "0.0%", an empty changed-field list shows no "nothing changed"
/// line, and the signed price move cannot invert under RTL (T-BIDI). A test
/// that only checked the happy render would pass a board that invents.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/agent.dart';
import 'package:ami_trade/models/room.dart';
import 'package:ami_trade/models/room_board.dart';
import 'package:ami_trade/widgets/room/room_board.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

RoomVoice _voice(String agentId) => RoomVoice(
      agentId: agentId,
      content: 'A contribution.',
      stance: 'for',
      conviction: 'high',
      stanceRecorded: true,
    );

RoomBoardData _board({
  VerdictOutcome outcome = VerdictOutcome.approve,
  double? sizePct = 3.0,
  DecisionRecord? decisionRecord,
  NextConveneDelta? nextConveneDelta,
}) =>
    RoomBoardData(
      ticker: 'AAPL',
      outcome: outcome,
      actionToken: switch (outcome) {
        VerdictOutcome.approve => 'APPROVE',
        VerdictOutcome.pass => 'PASS',
        _ => 'APPROVE',
      },
      reason: 'Synthesis defended; mandate clears.',
      sizePct: sizePct,
      entry: 150,
      stop: 141,
      target: 172,
      horizonDays: 42,
      levelProvenance: const {
        'entry': LevelSource.pm,
        'stop': LevelSource.pm,
        'target': LevelSource.pm,
      },
      decisionRecord: decisionRecord,
      nextConveneDelta: nextConveneDelta,
      voices: [for (final a in kCombVoices) _voice(a.id)],
    );

NextConveneDelta _delta({
  double? priceMovePct = 2.43,
  List<SheetFieldTransition> changedFields = const [
    SheetFieldTransition(
      field: 'margin_trend',
      fromState: 'LIVE',
      toState: 'UNAVAILABLE',
    ),
  ],
  String? priorKillCriterion = 'Gross margin compression below 38%.',
}) =>
    NextConveneDelta(
      priorDate: DateTime.utc(2026, 10, 20, 14, 30),
      priorAction: 'PASS',
      priceMovePct: priceMovePct,
      changedFields: changedFields,
      priorKillCriterion: priorKillCriterion,
    );

Future<void> _pump(WidgetTester t, RoomBoardData data,
    {TextDirection textDirection = TextDirection.ltr}) async {
  await t.pumpWidget(
    MaterialApp(
      localizationsDelegates: AppLocalizations.localizationsDelegates,
      supportedLocales: AppLocalizations.supportedLocales,
      home: Directionality(
        textDirection: textDirection,
        child: Scaffold(
          body: SingleChildScrollView(child: RoomBoard(data: data)),
        ),
      ),
    ),
  );
  await t.pumpAndSettle();
}

void main() {
  group('the contested card', () {
    testWidgets('a contested verdict names the card, reasons and objections',
        (t) async {
      await _pump(
        t,
        _board(
          decisionRecord: const DecisionRecord(
            contested: true,
            contestedReasons: [
              'The desk vote split 6–5 against this action.',
              'Evidence score sat below the approve threshold.',
            ],
            unresolvedObjections: [
              'Bear thesis on gross-margin compression was not answered.',
            ],
            unresolvedObjectionIds: ['bear_researcher'],
          ),
        ),
      );
      expect(t.takeException(), isNull);
      expect(find.text('CONTESTED DECISION'), findsOneWidget);
      expect(
        find.text('• The desk vote split 6–5 against this action.'),
        findsOneWidget,
      );
      expect(
        find.text('• Evidence score sat below the approve threshold.'),
        findsOneWidget,
      );
      expect(find.text('OBJECTIONS NOT RESOLVED'), findsOneWidget);
      expect(
        find.text('• Bear thesis on gross-margin compression was not answered.'),
        findsOneWidget,
      );
      expect(find.text('Raised by Bear Researcher'), findsOneWidget);
    });

    testWidgets('an unresolvable objector id renders as itself, not a name',
        (t) async {
      await _pump(
        t,
        _board(
          decisionRecord: const DecisionRecord(
            contested: true,
            unresolvedObjectionIds: ['future_desk'],
          ),
        ),
      );
      expect(find.text('Raised by future_desk'), findsOneWidget);
      // The Concierge fallback must never be named as an objector.
      expect(find.textContaining('Concierge'), findsNothing);
    });

    testWidgets('contested with no reasons or objections draws the heading '
        'alone — and never a fabricated line', (t) async {
      await _pump(
        t,
        _board(decisionRecord: const DecisionRecord(contested: true)),
      );
      expect(t.takeException(), isNull);
      expect(find.text('CONTESTED DECISION'), findsOneWidget);
      expect(find.text('OBJECTIONS NOT RESOLVED'), findsNothing);
      expect(find.textContaining('Raised by'), findsNothing);
    });

    testWidgets('a recorded contested=false draws no card', (t) async {
      await _pump(
        t,
        _board(decisionRecord: const DecisionRecord(contested: false)),
      );
      expect(find.text('CONTESTED DECISION'), findsNothing);
    });

    testWidgets('an old verdict with no record draws nothing new at all',
        (t) async {
      await _pump(t, _board());
      expect(t.takeException(), isNull);
      expect(find.text('CONTESTED DECISION'), findsNothing);
      expect(find.text('OBJECTIONS NOT RESOLVED'), findsNothing);
      expect(find.text('SINCE YOUR LAST CONVENE'), findsNothing);
      // The rest of the board is untouched.
      expect(find.text('THE ROOM APPROVED'), findsOneWidget);
      expect(find.text('CHIEF INVESTMENT OFFICER'), findsOneWidget);
    });
  });

  group('the next-convene change card', () {
    testWidgets('a full delta draws the date, prior call, move, fields and '
        'kill criterion', (t) async {
      await _pump(t, _board(nextConveneDelta: _delta()));
      expect(t.takeException(), isNull);
      expect(find.text('SINCE YOUR LAST CONVENE'), findsOneWidget);
      expect(find.text('20 OCT 2026'), findsOneWidget);
      expect(find.text('PRIOR CALL'), findsOneWidget);
      // The raw wire token — the same vocabulary the Journal titles use.
      expect(find.text('PASS'), findsOneWidget);
      expect(find.text('PRICE MOVE'), findsOneWidget);
      expect(find.text('+2.4%'), findsOneWidget);
      expect(find.text('KILL CRITERION THEN'), findsOneWidget);
      expect(
        find.text('Gross margin compression below 38%.'),
        findsOneWidget,
      );
      expect(find.text('CHANGED FIELDS'), findsOneWidget);
      expect(find.text('margin_trend'), findsOneWidget);
      expect(find.text('LIVE → UNAVAILABLE'), findsOneWidget);
    });

    testWidgets('a negative move keeps its sign', (t) async {
      await _pump(t, _board(nextConveneDelta: _delta(priceMovePct: -1.12)));
      expect(find.text('-1.1%'), findsOneWidget);
    });

    testWidgets('the price move is locked LTR (T-BIDI)', (t) async {
      await _pump(
        t,
        _board(nextConveneDelta: _delta()),
        textDirection: TextDirection.rtl,
      );
      final move = t
          .widgetList<Text>(find.byType(Text))
          .firstWhere((w) => w.data == '+2.4%');
      expect(move.textDirection, TextDirection.ltr);
      final transition = t
          .widgetList<Text>(find.byType(Text))
          .firstWhere((w) => w.data == 'LIVE → UNAVAILABLE');
      expect(transition.textDirection, TextDirection.ltr);
    });

    testWidgets('no recorded price move → no move row, never a fabricated '
        'zero', (t) async {
      // A PASS board with no kill criterion: nothing on screen carries a
      // percentage of its own, so any '%' could only have come from an
      // invented price move.
      await _pump(
        t,
        _board(
          outcome: VerdictOutcome.pass,
          sizePct: null,
          nextConveneDelta:
              _delta(priceMovePct: null, priorKillCriterion: null),
        ),
      );
      expect(t.takeException(), isNull);
      expect(find.text('PRICE MOVE'), findsNothing);
      final texts = t
          .widgetList<Text>(find.byType(Text))
          .map((w) => w.data ?? '');
      expect(texts.where((s) => s.contains('%')), isEmpty,
          reason: 'any percentage here would be an invented number');
    });

    testWidgets('empty changed fields → no "changed fields" section, never '
        'a "nothing changed" line', (t) async {
      await _pump(
        t,
        _board(nextConveneDelta: _delta(changedFields: const [])),
      );
      expect(t.takeException(), isNull);
      expect(find.text('CHANGED FIELDS'), findsNothing);
      expect(find.text('margin_trend'), findsNothing);
      // The card still carries what the delta DOES record.
      expect(find.text('SINCE YOUR LAST CONVENE'), findsOneWidget);
      expect(find.text('PRIOR CALL'), findsOneWidget);
    });

    testWidgets('no recorded kill criterion → no kill-criterion section',
        (t) async {
      await _pump(
        t,
        _board(nextConveneDelta: _delta(priorKillCriterion: null)),
      );
      expect(find.text('KILL CRITERION THEN'), findsNothing);
    });
  });
}
