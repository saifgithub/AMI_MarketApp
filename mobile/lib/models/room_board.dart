/// CR106 — the Verdict Board's view-model: one shape, two surfaces.
///
/// The live Room and the Decision Journal replay render the SAME run through
/// what used to be two entirely separate code paths, and the Journal's had
/// quietly fallen a whole CR behind — no markdown, no metric rows, no hex
/// avatars, `NO_VERDICT` bucketed as a rejection, and CR098's withheld-analyst
/// disclosure missing altogether (`DEF143`). That is DEF098's named failure
/// class — two renderers of the same data, neither a superset of the other —
/// and rebuilding the board twice would recreate the bug this CR is fixing
/// (CR106 T-TWICE).
///
/// So: one widget, two mappers. `room_screen.dart` maps its live `RoomState`
/// into [RoomBoardData]; `journal_detail_screen.dart` maps the frozen payload
/// into the same thing. Neither screen owns board layout, and
/// `test_cr106_board_parity` asserts they produce identical boards for every
/// field both surfaces carry.
///
/// Everything the board cannot honestly draw is nullable, and null means
/// **not recorded** — never a default. A Journal entry written before a field
/// existed will never have it, and re-fetching the run does not fix that (the
/// snapshot and the row are the same JSONB, written in the same moment). So the
/// board degrades **per entry**, and never backfills (T-BACKFILL).
library;

import 'package:ami_trade/models/room.dart';
import 'package:flutter/foundation.dart';

/// The five hero states, plus one for a wire value this build does not know.
///
/// `noResult` is a run that finished with no verdict at all — reachable today
/// and currently rendered as a single bare sentence. An outage must never be
/// shaped like an outcome, so it gets its own state rather than sharing one.
enum VerdictOutcome {
  approve,
  pass,
  reject,
  noVerdict,
  noResult,

  /// A verdict whose `action` this build does not recognise.
  ///
  /// CR106 §6 T-UNKNOWN asks for this to render as `NO RESULT`. It does not,
  /// deliberately: `NO RESULT` asserts the run failed, and a run that produced
  /// a verdict in a vocabulary we have not shipped yet has not failed. It gets
  /// the neutral, no-glyph treatment — the same "we are not asserting an
  /// outcome" shape as `NO_VERDICT` — with the raw token as its heading, which
  /// is also what CR098 acceptance #9 settled on for the same problem. The trap
  /// T-UNKNOWN actually names — a new backend action silently becoming a real
  /// outcome — is closed either way, and this closes it without inventing a
  /// failure that did not happen.
  unknown,
}

/// One of the eleven voices in the consensus comb. The Portfolio Manager is
/// **not** among them: its position IS the hero tile, `_parse_pm_verdict` is
/// the sole decision path, and the safety floor can override even that. Eleven
/// hexes under `THE PM DECIDES — THIS IS NOT A VOTE` beats twelve under a
/// disclaimer nobody reads (T-VOTE).
@immutable
class RoomVoice {
  const RoomVoice({
    required this.agentId,
    required this.content,
    this.stance,
    this.conviction,
    this.headline,
    this.stanceRecorded = false,
    this.withheld = false,
  });

  final String agentId;
  final String content;

  /// `for` / `against` / `neutral`, or null for "stated no view".
  final String? stance;

  /// `low` / `medium` / `high`, or null. Null renders no conviction bar AND no
  /// track — an empty track would read as "low", which is a different claim.
  final String? conviction;

  /// The agent's own headline number. Already capped server-side; a headline
  /// that was too long arrives null rather than cut.
  final String? headline;

  /// Whether the payload carried a stance field at all — see
  /// [RoomTranscriptLine.stanceRecorded].
  final bool stanceRecorded;

  /// A tenure-withheld analyst: it has no content because it was never in the
  /// room. Its hex sits in the roster gap, dashed and unfilled, and its row
  /// reads `NOT HEARD` with no jump action — a trip to an empty row is a
  /// wasted one.
  final bool withheld;

  bool get isFor => stance == 'for';
  bool get isAgainst => stance == 'against';
  bool get isNeutral => stance == 'neutral';

  /// True when this voice belongs in the comb's gutter rather than a band.
  bool get statedNoView => stance == null;
}

@immutable
class RoomBoardData {
  const RoomBoardData({
    required this.ticker,
    required this.outcome,
    required this.actionToken,
    required this.reason,
    required this.voices,
    this.sizePct,
    this.entry,
    this.stop,
    this.target,
    this.horizonDays,
    this.violations = const [],
    this.overriddenFromLlm = false,
    this.opinionsNotIncluded = const [],
    this.levelProvenance,
    this.isRecord = false,
    this.recordedAt,
    this.runId,
  });

  final String ticker;
  final VerdictOutcome outcome;

  /// The raw wire value. Rendered as the heading only for [VerdictOutcome
  /// .unknown]; every known outcome uses its own translated string.
  final String actionToken;

  final String reason;
  final List<RoomVoice> voices;

  final double? sizePct;
  final double? entry;
  final double? stop;
  final double? target;
  final int? horizonDays;

  final List<String> violations;
  final bool overriddenFromLlm;
  final List<String> opinionsNotIncluded;
  final Map<String, LevelSource>? levelProvenance;

  /// True on the Journal. A journal entry is a **record, not a setup**: a June
  /// entry's `$118.20` is not a live price, so there is no trade ticket
  /// (T-STALE) and the geometry carries the run date.
  final bool isRecord;
  final DateTime? recordedAt;

  /// Present only on a live run — the trade ticket needs it to link the trade
  /// back to the verdict.
  final String? runId;

  bool get isApprove => outcome == VerdictOutcome.approve;

  /// PASS, NO_VERDICT and an unrecognised action all get the neutral treatment.
  /// PASS is a "not now" and NO_VERDICT is a professional refusal; neither is a
  /// turn-down, and the reject accent states the opposite.
  bool get isNeutral =>
      outcome == VerdictOutcome.pass ||
      outcome == VerdictOutcome.noVerdict ||
      outcome == VerdictOutcome.unknown;

  bool get isReject => outcome == VerdictOutcome.reject;
  bool get isNoVerdict => outcome == VerdictOutcome.noVerdict;
  bool get isNoResult => outcome == VerdictOutcome.noResult;

  // ── the comb ────────────────────────────────────────────────────────────

  /// Whether ANY voice recorded a stance field. False for a run that predates
  /// B2 — the comb then renders one honest sentence instead of three empty
  /// bands and eleven hexes in a gutter, which would read as "nobody had a
  /// view" rather than "we did not record this".
  bool get stancesRecorded => voices.any((v) => v.stanceRecorded);

  List<RoomVoice> get voicesFor => voices.where((v) => v.isFor).toList();
  List<RoomVoice> get voicesAgainst =>
      voices.where((v) => v.isAgainst).toList();
  List<RoomVoice> get voicesNeutral =>
      voices.where((v) => v.isNeutral).toList();

  /// Voices with no stance. A separate gutter, never a lane.
  List<RoomVoice> get voicesNotStated =>
      voices.where((v) => v.statedNoView && !v.withheld).toList();

  /// The withheld analysts' own hexes — the roster gap.
  List<RoomVoice> get voicesWithheld =>
      voices.where((v) => v.withheld).toList();

  /// Who was not in the room, from BOTH sources.
  ///
  /// `opinions_not_included` is the verdict's deterministic disclosure and is
  /// the only source the Journal has. The live stream also emits an
  /// `agent_withheld` event per analyst, which arrives long BEFORE the verdict
  /// — and on a run that never reaches a verdict (a dropped socket, an outage)
  /// it is the only source there is. Taking the union means a lost connection
  /// cannot silently drop the disclosure, which is exactly the failure the
  /// CR098 round-1 audit caught on the transcript path.
  List<String> get withheldAnalystIds {
    final ids = <String>[...opinionsNotIncluded];
    for (final v in voicesWithheld) {
      if (!ids.contains(v.agentId)) ids.add(v.agentId);
    }
    return ids;
  }

  /// Counted over non-null stances only, so the caption reads `9 STATED A VIEW`
  /// rather than a total that always sums to 11 (T-SUM11).
  int get statedCount => voices.where((v) => !v.statedNoView).length;

  // ── the risk/reward ribbon ──────────────────────────────────────────────

  LevelSource? sourceFor(String key) => levelProvenance?[key];

  bool get _levelsCoherent =>
      entry != null &&
      stop != null &&
      target != null &&
      stop! > 0 &&
      stop! < entry! &&
      entry! < target!;

  /// **No provenance → no ribbon** (T-PROV). The geometry *is* the claim: a
  /// to-scale bar that draws a minted `entry * 0.94` stop at the same weight as
  /// a price the PM chose is a confident lie, and clamping the `reason`
  /// sentence that used to be the only disclosure behind a `WHY` expander while
  /// promoting the same numbers into a graphic would be a net loss of honesty.
  /// Without it the levels render as the plain metric list, captioned.
  bool get showsRibbon =>
      isApprove && levelProvenance != null && _levelsCoherent;

  /// Computed from the same three prices the widget draws — never accepted from
  /// the wire, where a sent value that disagreed with the drawn geometry would
  /// be a visible lie. Mirrors `trading_math/trade.py::risk_reward`.
  double? get riskReward {
    if (!_levelsCoherent) return null;
    final risk = entry! - stop!;
    if (risk <= 0) return null;
    return (target! - entry!) / risk;
  }

  /// Where the entry marker sits along the stop→target track, 0..1.
  double get entryFraction {
    if (!_levelsCoherent) return 0.5;
    final span = target! - stop!;
    if (span <= 0) return 0.5;
    return ((entry! - stop!) / span).clamp(0.0, 1.0);
  }

  /// The levels AMI minted rather than anyone stating — drives the hollow caps
  /// and the one-line footnote.
  List<String> get derivedLevelKeys {
    final p = levelProvenance;
    if (p == null) return const [];
    return [
      for (final k in const ['entry', 'stop', 'target'])
        if (p[k] == LevelSource.amiDefault || p[k] == LevelSource.trader) k,
    ];
  }
}

/// Map a wire `action` token to an outcome. Unknown tokens land on
/// [VerdictOutcome.unknown] rather than defaulting into a real outcome — the
/// enum has grown twice already (PASS, then NO_VERDICT) and will grow again.
VerdictOutcome outcomeFromAction(String? action) {
  switch (action) {
    case 'APPROVE':
      return VerdictOutcome.approve;
    case 'PASS':
      return VerdictOutcome.pass;
    case 'REJECT':
      return VerdictOutcome.reject;
    case 'NO_VERDICT':
      return VerdictOutcome.noVerdict;
    case null:
    case '':
      return VerdictOutcome.noResult;
    default:
      return VerdictOutcome.unknown;
  }
}
