/// CR173 slice 1 — the live Room's four-stage narrative, as pure data.
///
/// Zero new data: the four stages are a **fold of the six `RoomPhase`s** the app
/// already carries (`agent.dart`), and every seat state is derived from
/// `RoomState` alone. Nothing here reads a provider, builds a widget or talks to
/// the network, so the whole narrative is testable without pumping a frame —
/// which is the point, because the honesty rules CR173 §5.9 names (DEF059,
/// DEF174) are claims about *what the states mean*, not about how they look.
///
/// **The fold is contiguous, and it has to be** (CR173 Amendment A). The run
/// order is fixed by `room_runner.PHASES`: ANALYSTS → RESEARCHERS → SYNTHESIS →
/// EXECUTION → RISK → VERDICT. A fold that skipped around it would light a stage
/// and then un-light it when an earlier one started — a progress bar that runs
/// backwards. `EXECUTION` (the Trader) joins RISK REVIEW rather than being
/// dropped: the Trader drafts the ticket the three debators stress, and eleven
/// seats on a surface whose rows carry desk counts is a firm that lost a member.
///
/// **The seat states are the roster's own** — [seatStateFor] is the single
/// derivation, used by this narrative AND by the 12-seat roster behind WATCH THE
/// FLOOR. Two renderers of the same fact, computing it twice, is how they come
/// to disagree (DEF098); §5.9's "seat states map 1:1" is enforced by there being
/// one function, not by two copies staying in step.
library;

import 'package:ami_trade/models/agent.dart';
import 'package:ami_trade/state/room_providers.dart';

/// What one of the twelve is doing, right now.
///
/// Lifted verbatim out of `room_screen.dart`'s `_AgentStatusRow`, which is still
/// the only renderer of the roster — it now reads this instead of re-deriving.
enum RoomSeatState {
  /// Its turn has not come.
  waiting,

  /// It is the active agent and the stream is still open.
  thinking,

  /// `agent_done` landed, whatever it recorded.
  responded,

  /// It started and the run stopped without ever completing its turn — a
  /// stream break or a reconnect timeout catching an agent mid-turn. Must read
  /// as neither RESPONDED (a lie) nor an unending spinner (DEF059).
  interrupted,

  /// CR098 — off the roster on account tenure. It will never report, so it is
  /// excluded from desk counts and shown as a locked chair.
  withheld,
}

/// The four rows of the narrative, in run order.
enum RoomStage { analystDesk, researchDebate, riskReview, pmVerdict }

/// Which row each of the six phases folds into (CR173 Amendment A).
const Map<RoomPhase, RoomStage> kPhaseStage = {
  RoomPhase.analysts: RoomStage.analystDesk,
  RoomPhase.researchers: RoomStage.researchDebate,
  RoomPhase.synthesis: RoomStage.researchDebate,
  RoomPhase.execution: RoomStage.riskReview,
  RoomPhase.risk: RoomStage.riskReview,
  RoomPhase.verdict: RoomStage.pmVerdict,
};

/// Each row's members, in speaking order.
///
/// Derived from `kAgentPhase` rather than listed, so a roster change reaches
/// this narrative by construction. `kAgentPhase` is a literal map, so its
/// iteration order IS the run order — the same property `kCombVoices` already
/// relies on.
final Map<RoomStage, List<String>> kStageAgents = () {
  final out = {for (final s in RoomStage.values) s: <String>[]};
  for (final e in kAgentPhase.entries) {
    out[kPhaseStage[e.value]!]!.add(e.key);
  }
  return {
    for (final e in out.entries) e.key: List<String>.unmodifiable(e.value),
  };
}();

/// The label the backend streams (`{"label": "ANALYSTS"}`, `room.py:15`) → its
/// stage.
///
/// **Unknown labels return null, not stage one.** The phase vocabulary has grown
/// before and will again; a value we do not recognise must leave every row
/// un-highlighted rather than put the marker on a stage that is not running
/// (DEF210 — a wrong-but-known value is indistinguishable from a right one).
RoomStage? stageForPhaseLabel(String? label) {
  switch (label) {
    case 'ANALYSTS':
      return RoomStage.analystDesk;
    case 'RESEARCHERS':
    case 'SYNTHESIS':
      return RoomStage.researchDebate;
    case 'EXECUTION':
    case 'RISK':
      return RoomStage.riskReview;
    case 'VERDICT':
      return RoomStage.pmVerdict;
    default:
      return null;
  }
}

/// The one derivation of a seat's state. See the library comment.
RoomSeatState seatStateFor(RoomState state, String agentId) {
  if (state.withheldAgents.containsKey(agentId)) return RoomSeatState.withheld;
  if (state.agentStances.containsKey(agentId)) return RoomSeatState.responded;
  // Gated on `streaming`: once the stream itself has stopped, a lingering
  // `activeAgent` from before the break is not "in progress" anymore — it is
  // the interrupted case below.
  if (state.streaming && state.activeAgent == agentId) {
    return RoomSeatState.thinking;
  }
  final started = state.order.contains(agentId);
  if (started && !state.streaming && !state.reconnecting) {
    return RoomSeatState.interrupted;
  }
  return RoomSeatState.waiting;
}

/// A stage row's own state. Four values, and they are the four seat states
/// under different names — that 1:1 correspondence is CR173 §5.9, and it is
/// what lets a user read a row without opening it.
enum RoomStageStatus {
  /// No member has moved. (seat: waiting)
  waiting,

  /// Somebody on this desk is working, or has reported while others have not.
  /// (seat: thinking)
  active,

  /// Every member that can report has. (seat: responded)
  done,

  /// A member started and the run stopped without finishing its turn. The row
  /// says so rather than sitting on `active` forever (seat: interrupted).
  interrupted,
}

class RoomStageSeat {
  const RoomStageSeat({required this.agentId, required this.seat});

  final String agentId;
  final RoomSeatState seat;

  Agent get agent => agentById(agentId);
}

class RoomStageView {
  const RoomStageView({
    required this.stage,
    required this.status,
    required this.seats,
  });

  final RoomStage stage;
  final RoomStageStatus status;

  /// Every member, in speaking order — **including** withheld ones, which is
  /// why the count below is computed rather than `seats.length`. A locked chair
  /// that vanished from the desk it belongs to would take CR098's whole
  /// disclosure with it.
  final List<RoomStageSeat> seats;

  /// Members that can still report. A withheld analyst never will, so counting
  /// it would pin the row at `3/4` for the rest of the run — a finished desk
  /// reading as one still waiting.
  Iterable<RoomStageSeat> get reportable =>
      seats.where((s) => s.seat != RoomSeatState.withheld);

  int get reportedCount =>
      reportable.where((s) => s.seat == RoomSeatState.responded).length;

  int get reportableCount => reportable.length;

  /// Members with something to say on the row itself: the ones that have
  /// reported, plus the one currently working.
  Iterable<RoomStageSeat> get spoken => seats.where((s) =>
      s.seat == RoomSeatState.responded ||
      s.seat == RoomSeatState.thinking ||
      s.seat == RoomSeatState.interrupted);
}

/// The whole narrative for one `RoomState`. Always four rows, always in order —
/// a stage never disappears, because "this desk has not started" is a state the
/// user should be able to see.
List<RoomStageView> stagesFromRoomState(RoomState state) {
  final live = stageForPhaseLabel(state.phase);
  return [
    for (final stage in RoomStage.values)
      () {
        final seats = [
          for (final id in kStageAgents[stage]!)
            RoomStageSeat(agentId: id, seat: seatStateFor(state, id)),
        ];
        return RoomStageView(
          stage: stage,
          status: _statusFor(seats, isLivePhase: live == stage),
          seats: seats,
        );
      }(),
  ];
}

RoomStageStatus _statusFor(
  List<RoomStageSeat> seats, {
  required bool isLivePhase,
}) {
  final reportable =
      seats.where((s) => s.seat != RoomSeatState.withheld).toList();

  // An interrupted member outranks everything: the desk stopped mid-turn, and
  // any other reading of that is the DEF059 inversion — a stalled run wearing
  // the appearance of a running one.
  if (reportable.any((s) => s.seat == RoomSeatState.interrupted)) {
    return RoomStageStatus.interrupted;
  }
  // Every member withheld — unreachable today (CR098 keeps Fundamentals on the
  // roster), and deliberately NOT `done`: a desk that never sat is not a desk
  // that finished.
  if (reportable.isEmpty) return RoomStageStatus.waiting;

  if (reportable.every((s) => s.seat == RoomSeatState.responded)) {
    return RoomStageStatus.done;
  }
  if (isLivePhase ||
      reportable.any((s) =>
          s.seat == RoomSeatState.thinking ||
          s.seat == RoomSeatState.responded)) {
    return RoomStageStatus.active;
  }
  return RoomStageStatus.waiting;
}
