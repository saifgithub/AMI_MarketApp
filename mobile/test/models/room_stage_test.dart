/// CR173 slice 1 §5.9 — the four-stage narrative, tested where it actually
/// lives.
///
/// The acceptance is three claims, and none of them is about pixels: the fold
/// keeps all twelve seats, the desk counts can be reached, and a stage row's
/// state is the seat state under a different name. `room_stage.dart` is pure,
/// so those are testable directly rather than inferred from a rendered frame —
/// which matters, because the failure mode here is a *plausible* lie (a desk
/// stuck at 3/4, a stalled run wearing a spinner), and a widget test that only
/// checks something rendered would pass through every one of them.
library;

import 'package:ami_trade/models/agent.dart';
import 'package:ami_trade/models/room_stage.dart';
import 'package:ami_trade/state/room_providers.dart';
import 'package:flutter_test/flutter_test.dart';

const _analysts = [
  'fundamentals_analyst',
  'market_analyst',
  'news_analyst',
  'social_media_analyst',
];

WithheldAgentInfo _withheldInfo(String id) =>
    WithheldAgentInfo(agentId: id, reason: 'tenure');

AgentStance _spoke({String? headline}) =>
    AgentStance(stance: 'bull', headline: headline, recorded: true);

RoomState _live({
  String? phase,
  String? active,
  List<String> order = const [],
  Map<String, AgentStance> stances = const {},
  Map<String, WithheldAgentInfo> withheld = const {},
  bool streaming = true,
  bool reconnecting = false,
}) =>
    RoomState(
      phase: phase,
      activeAgent: active,
      order: order,
      agentStances: stances,
      withheldAgents: withheld,
      streaming: streaming,
      reconnecting: reconnecting,
    );

void main() {
  group('the fold — Amendment A', () {
    test('every one of the twelve has a desk, and only one', () {
      final placed = <String>[];
      for (final stage in RoomStage.values) {
        placed.addAll(kStageAgents[stage]!);
      }
      expect(placed.toSet(), kAgentPhase.keys.toSet(),
          reason: 'a seat with no desk is a firm that lost a member, on a '
              'surface whose rows claim to count the firm');
      expect(placed.length, placed.toSet().length, reason: 'no duplicates');
      expect(placed.length, 12);
    });

    test('the Trader is on the risk desk, not missing', () {
      // The prototype's stage subtitles name the members of three rows
      // exactly and leave EXECUTION named by none. Dropping it was the
      // available shortcut; this is the assertion that it was not taken.
      expect(kStageAgents[RoomStage.riskReview], contains('trader'));
    });

    test('the fold is contiguous in run order', () {
      // A non-contiguous fold lights a stage and then un-lights it when an
      // earlier phase starts — a progress bar that runs backwards. Walking the
      // phases in run order, the stage index must never decrease.
      var last = -1;
      for (final phase in RoomPhase.values) {
        final index = RoomStage.values.indexOf(kPhaseStage[phase]!);
        expect(index, greaterThanOrEqualTo(last),
            reason: '$phase folds backwards');
        last = index;
      }
    });

    test('desk sizes are 4 / 3 / 4 / 1', () {
      expect(kStageAgents[RoomStage.analystDesk]!.length, 4);
      expect(kStageAgents[RoomStage.researchDebate]!.length, 3);
      expect(kStageAgents[RoomStage.riskReview]!.length, 4);
      expect(kStageAgents[RoomStage.pmVerdict]!.length, 1);
    });
  });

  group('the phase label is wire data', () {
    test('the six shipped labels map to their stage', () {
      expect(stageForPhaseLabel('ANALYSTS'), RoomStage.analystDesk);
      expect(stageForPhaseLabel('RESEARCHERS'), RoomStage.researchDebate);
      expect(stageForPhaseLabel('SYNTHESIS'), RoomStage.researchDebate);
      expect(stageForPhaseLabel('EXECUTION'), RoomStage.riskReview);
      expect(stageForPhaseLabel('RISK'), RoomStage.riskReview);
      expect(stageForPhaseLabel('VERDICT'), RoomStage.pmVerdict);
    });

    test('an unknown label highlights nothing rather than stage one', () {
      // DEF210 — the phase vocabulary has grown before. A value we do not
      // recognise must leave every row un-highlighted; putting the marker on a
      // stage that is not running is indistinguishable from it being right.
      expect(stageForPhaseLabel('CONCIERGE'), isNull);
      expect(stageForPhaseLabel(null), isNull);
      expect(stageForPhaseLabel('analysts'), isNull);
    });
  });

  group('seat states', () {
    test('responded, thinking, waiting', () {
      final s = _live(
        active: 'market_analyst',
        order: const ['fundamentals_analyst', 'market_analyst'],
        stances: {'fundamentals_analyst': _spoke()},
      );
      expect(seatStateFor(s, 'fundamentals_analyst'), RoomSeatState.responded);
      expect(seatStateFor(s, 'market_analyst'), RoomSeatState.thinking);
      expect(seatStateFor(s, 'news_analyst'), RoomSeatState.waiting);
    });

    test('a stalled turn is interrupted, not thinking and not responded', () {
      // The stream stopped with market_analyst mid-turn. Reading that as
      // "thinking" is an unending spinner; reading it as "responded" is a lie
      // about what the desk heard (DEF059).
      final s = _live(
        active: 'market_analyst',
        order: const ['market_analyst'],
        streaming: false,
      );
      expect(seatStateFor(s, 'market_analyst'), RoomSeatState.interrupted);
    });

    test('a reconnecting run has not stalled', () {
      final s = _live(
        active: 'market_analyst',
        order: const ['market_analyst'],
        streaming: false,
        reconnecting: true,
      );
      expect(seatStateFor(s, 'market_analyst'), RoomSeatState.waiting,
          reason: 'the backend keeps the run alive; this is a wait, not a stop');
    });

    test('withheld outranks everything, including a started turn', () {
      final s = _live(
        order: const ['social_media_analyst'],
        withheld: {'social_media_analyst': _withheldInfo('social_media_analyst')},
      );
      expect(seatStateFor(s, 'social_media_analyst'), RoomSeatState.withheld);
    });
  });

  group('desk counts', () {
    RoomStageView analystDesk(RoomState s) =>
        stagesFromRoomState(s).firstWhere((v) => v.stage == RoomStage.analystDesk);

    test('2 of 4 reported', () {
      final v = analystDesk(_live(
        phase: 'ANALYSTS',
        active: 'news_analyst',
        order: const ['fundamentals_analyst', 'market_analyst', 'news_analyst'],
        stances: {
          'fundamentals_analyst': _spoke(),
          'market_analyst': _spoke(),
        },
      ));
      expect(v.reportedCount, 2);
      expect(v.reportableCount, 4);
    });

    test('a withheld analyst leaves the denominator, so the desk can finish',
        () {
      // The bug this guards: counting a seat that can never report pins the row
      // at 3/4 for the rest of the run — a finished desk reading as one still
      // waiting on somebody.
      final s = _live(
        phase: 'ANALYSTS',
        withheld: {'social_media_analyst': _withheldInfo('social_media_analyst')},
        stances: {
          for (final id in _analysts.take(3)) id: _spoke(),
        },
      );
      final v = analystDesk(s);
      expect(v.reportableCount, 3);
      expect(v.reportedCount, 3);
      expect(v.status, RoomStageStatus.done);
      expect(v.seats.length, 4,
          reason: 'the locked chair still has a seat on its own desk — losing '
              'it would take CR098 disclosure with it');
    });
  });

  group('stage status maps 1:1 onto the seat states', () {
    List<RoomStageView> stages(RoomState s) => stagesFromRoomState(s);

    test('a run that has not started: four waiting rows', () {
      final v = stages(_live(streaming: false));
      expect(v.map((s) => s.status),
          everyElement(RoomStageStatus.waiting));
    });

    test('the phase event alone makes a desk active, before anyone speaks', () {
      // The window between the `phase` event and the first `agent_done` is
      // real. Reading it as "waiting" tells the user nothing is happening while
      // four analysts are running.
      final v = stages(_live(phase: 'ANALYSTS'));
      expect(v.first.status, RoomStageStatus.active);
      expect(v.last.status, RoomStageStatus.waiting);
    });

    test('all members reported ⇒ done', () {
      final v = stages(_live(
        phase: 'RESEARCHERS',
        stances: {for (final id in _analysts) id: _spoke()},
      ));
      expect(v.first.status, RoomStageStatus.done);
    });

    test('an interrupted member outranks a desk that otherwise looks busy', () {
      // fundamentals reported, market stalled. `active` would leave the row
      // spinning forever on a run that has stopped.
      final v = stages(_live(
        phase: 'ANALYSTS',
        active: 'market_analyst',
        order: const ['fundamentals_analyst', 'market_analyst'],
        stances: {'fundamentals_analyst': _spoke()},
        streaming: false,
      ));
      expect(v.first.status, RoomStageStatus.interrupted);
    });

    test('a desk whose only members are withheld is not "done"', () {
      // Unreachable today — CR098 keeps Fundamentals on every roster — but
      // "finished" and "never sat" are different facts and the guard says so.
      final s = _live(
        withheld: {
          for (final id in _analysts) id: _withheldInfo(id),
        },
      );
      expect(stages(s).first.status, RoomStageStatus.waiting);
      expect(stages(s).first.reportableCount, 0);
    });
  });

  test('the narrative is always four rows, in order', () {
    final v = stagesFromRoomState(_live(phase: 'RISK'));
    expect(v.map((s) => s.stage), RoomStage.values,
        reason: 'a desk that has not started is a state the user should see, '
            'not a row that appears out of nowhere when it does');
  });
}
