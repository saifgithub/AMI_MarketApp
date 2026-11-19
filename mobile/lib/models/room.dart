/// Convene the Room — client-side models.
/// Mirrors backend/app/schemas/room.py.
library;

import 'package:ami_trade/models/option_proposal.dart';

/// CR106 B1 — where one price on a verdict came from.
///
/// `unknown` is a value the wire sent that this build does not recognise, kept
/// distinct from `null` (the field was absent, i.e. the run predates B1). Both
/// suppress the risk/reward ribbon; only the second suppresses the whole
/// provenance treatment, because a level we cannot attribute is not the same
/// thing as a run that recorded no attributions.
enum LevelSource { pm, trader, amiDefault, unknown }

LevelSource _levelSourceFrom(Object? raw) {
  switch (raw) {
    case 'pm':
      return LevelSource.pm;
    case 'trader':
      return LevelSource.trader;
    case 'ami_default':
      return LevelSource.amiDefault;
    default:
      return LevelSource.unknown;
  }
}

class RoomVerdict {
  const RoomVerdict({
    required this.action,
    required this.reason,
    required this.violations,
    required this.overriddenFromLlm,
    this.sizePct,
    this.entry,
    this.target,
    this.stop,
    this.timeHorizonDays,
    this.opinionsNotIncluded = const [],
    this.levelProvenance,
    this.structure,
    this.decisionRecord,
    this.nextConveneDelta,
    this.streetComparison,
  });

  /// 'APPROVE' | 'REJECT' | 'MODIFY' | 'PASS' | 'NO_VERDICT'.
  ///
  /// The enum grows — `NO_VERDICT` (CR098 Amendment 2) is the proof. Treat any
  /// value you do not recognise as a non-approval and render it neutrally
  /// rather than switching on an exhaustive list that a backend release can
  /// invalidate.
  final String action;
  final double? sizePct;
  final double? entry;
  final double? target;
  final double? stop;
  final int? timeHorizonDays;
  final String reason;
  final List<String> violations;
  final bool overriddenFromLlm;

  /// `AgentId` values that were NOT in the room for this run (CR098 D3).
  /// Always present on the wire, empty on an ordinary full-roster run — so
  /// empty must render nothing at all, never an empty header (D4).
  final List<String> opinionsNotIncluded;

  /// CR106 B1 — `entry` / `stop` / `target` → where each price came from.
  ///
  /// `null` means the run predates the field, NOT that everything came from the
  /// PM. The board never infers it: an entry with no provenance renders in the
  /// plain metric list with no ribbon and no ratio (T-PROV / T-BACKFILL).
  final Map<String, LevelSource>? levelProvenance;

  /// CR172 — the option structure the Room costed and the CIO chose, if any.
  ///
  /// Parsed by [OptionProposal.fromJson], the SAME parser the `/propose`
  /// surface uses, because the server sends the same shape to both. That is
  /// the whole point of it being one shape: the ticket renders a structure
  /// identically however the user arrived at it, and a field cannot exist on
  /// one route and be missing on the other.
  ///
  /// `null` is an equity verdict — or a mandate that does not permit
  /// derivatives, or a run that predates the field. It is never "a structure
  /// with no legs"; the server does not emit one.
  final OptionProposal? structure;

  /// CR266 — the typed decision record behind this verdict (evidence score
  /// and threshold, the computed action set and size, unresolved objections,
  /// evidence availability, and the contested flag with its reasons).
  ///
  /// `null` means the run predates the field or ran with the gate off — never
  /// "a clean decision": `contested` inside stays `bool?` for the same reason
  /// `levelProvenance` stays null instead of defaulting to "all PM".
  final DecisionRecord? decisionRecord;

  /// CR219 R60 / CR266 — "what changed since your last convene on this name".
  /// `null` on a first convene, when the only prior was an outage abstain, or
  /// on a run that predates the field; absence, never a "nothing changed".
  final NextConveneDelta? nextConveneDelta;

  /// CR260 / CR267 WP-21b — how the Room's call sits against the Street's
  /// consensus rating, computed by the backend AFTER the verdict. `null` on a
  /// run that predates the field; a run with no usable Street data carries an
  /// explicit `unavailable` block instead (see [StreetComparison.isAvailable]).
  final StreetComparison? streetComparison;

  bool get isApprove => action == 'APPROVE';

  /// Whether this verdict is asking the user to consent to an option
  /// structure. An APPROVE with a structure is the only state that does.
  bool get isOptionApprove => isApprove && structure != null;
  bool get isReject => action == 'REJECT';
  bool get isPass => action == 'PASS';

  /// CR098 Amendment 2 — the PM declined to call a trade because the session
  /// ran without a market read. Every level field is null in this state, and
  /// it is a professional refusal, NOT a rejection: rendering it in the
  /// reject treatment tells the user their thesis was turned down.
  bool get isNoVerdict => action == 'NO_VERDICT';

  factory RoomVerdict.fromJson(Map<String, dynamic> j) {
    return RoomVerdict(
      action: j['action'] as String? ?? 'PASS',
      sizePct: (j['size_pct'] as num?)?.toDouble(),
      entry: (j['entry'] as num?)?.toDouble(),
      target: (j['target'] as num?)?.toDouble(),
      stop: (j['stop'] as num?)?.toDouble(),
      timeHorizonDays: (j['time_horizon_days'] as num?)?.toInt(),
      reason: j['reason'] as String? ?? '',
      violations: ((j['violations'] as List?) ?? const [])
          .whereType<String>()
          .toList(),
      overriddenFromLlm: (j['overridden_from_llm'] as bool?) ?? false,
      // `whereType`, not `cast`: `cast` defers the type error to first read, so
      // one non-String on the wire would throw inside build() rather than here.
      opinionsNotIncluded: ((j['opinions_not_included'] as List?) ?? const [])
          .whereType<String>()
          .toList(),
      levelProvenance: parseLevelProvenance(j['level_provenance']),
      structure: j['structure'] is Map
          ? OptionProposal.fromJson(
              (j['structure'] as Map).cast<String, dynamic>())
          : null,
      decisionRecord: j['decision_record'] is Map
          ? DecisionRecord.fromJson(
              (j['decision_record'] as Map).cast<String, dynamic>())
          : null,
      nextConveneDelta: j['next_convene_delta'] is Map
          ? NextConveneDelta.fromJson(
              (j['next_convene_delta'] as Map).cast<String, dynamic>())
          : null,
      streetComparison: j['street_comparison'] is Map
          ? StreetComparison.fromJson(
              (j['street_comparison'] as Map).cast<String, dynamic>())
          : null,
    );
  }
}

/// CR260 / CR267 WP-21b — the Room's call against the Street's consensus
/// rating, exactly as the backend computed it (never client-derived).
///
/// Mirrors `backend/app/schemas/room.py::StreetComparison`. Nothing here is
/// defaulted into a reading: a Street rating, analyst count or mean target the
/// server did not send stays `null`, and the card renders the
/// "no Street rating available" state for [isAvailable] == false rather than an
/// empty or zero rating.
class StreetComparison {
  const StreetComparison({
    required this.status,
    required this.sourceLabel,
    required this.roomAction,
    required this.agreement,
    this.unavailableReason,
    this.streetRating,
    this.streetStance,
    this.analystCount,
    this.targetMean,
    this.asOf,
    this.approvedAgainstStreetSell = false,
    this.reasonsFromNarrowAnswers = const [],
  });

  factory StreetComparison.fromJson(Map<String, dynamic> j) {
    return StreetComparison(
      status: j['status'] as String? ?? 'unavailable',
      sourceLabel: j['source_label'] as String? ?? '',
      unavailableReason: j['unavailable_reason'] as String?,
      streetRating: j['street_rating'] as String?,
      streetStance: j['street_stance'] as String?,
      analystCount: (j['analyst_count'] as num?)?.toInt(),
      targetMean: (j['target_mean'] as num?)?.toDouble(),
      asOf: j['as_of'] as String?,
      roomAction: j['room_action'] as String? ?? '',
      agreement: j['agreement'] as String? ?? 'not_comparable',
      approvedAgainstStreetSell:
          (j['approved_against_street_sell'] as bool?) ?? false,
      reasonsFromNarrowAnswers:
          ((j['reasons_from_narrow_answers'] as List?) ?? const [])
              .whereType<String>()
              .toList(),
    );
  }

  /// 'available' | 'unavailable'. Anything else is treated as unavailable.
  final String status;

  /// Names the data source; always sent, shown verbatim on the card.
  final String sourceLabel;
  final String? unavailableReason;

  /// The feed's own rating word ("strong buy", "buy", "hold", "underperform",
  /// "sell") and its three-way bucket: 'buy' | 'hold' | 'sell'.
  final String? streetRating;
  final String? streetStance;
  final int? analystCount;
  final double? targetMean;

  /// Fact-sheet date (YYYY-MM-DD) the rating was read.
  final String? asOf;
  final String roomAction;

  /// 'agree' | 'differ' | 'not_comparable'.
  final String agreement;

  /// The Room approved a name the Street rates Sell/Underperform.
  final bool approvedAgainstStreetSell;

  /// WP-22 hook: empty until the narrow-question judge exists.
  final List<String> reasonsFromNarrowAnswers;

  bool get isAvailable => status == 'available' && streetStance != null;
  bool get agrees => agreement == 'agree';
  bool get differs => agreement == 'differ';
}

/// Shared by [RoomVerdict.fromJson] and the Journal's payload mapper so the
/// two surfaces cannot disagree about what a provenance map means (T-TWICE).
/// An absent or non-map value stays `null` — "not recorded", never inferred.
Map<String, LevelSource>? parseLevelProvenance(Object? raw) {
  if (raw is! Map) return null;
  final out = <String, LevelSource>{};
  for (final key in const ['entry', 'stop', 'target']) {
    final v = raw[key];
    if (v != null) out[key] = _levelSourceFrom(v);
  }
  return out.isEmpty ? null : out;
}

/// A recorded list of strings, or null when the field was absent. A list that
/// IS present stays a list even when empty or partly unreadable — "recorded
/// nothing" and "not recorded" are different facts (T-BACKFILL), and one bad
/// element must not throw inside build() (`whereType`, not `cast`).
List<String>? parseStringListOrNull(Object? raw) {
  if (raw is! List) return null;
  return raw.whereType<String>().toList();
}

/// CR266 — the typed record behind one verdict, as computed by the backend
/// evidence gate (never client-derived).
///
/// Every field is nullable because the whole record is absent on runs that
/// predate it or ran with the gate off, and individually nullable because the
/// backend fails closed per field (an uncomputable evidence score is null
/// with an explicit reason elsewhere, not a silent 0). Read these the way
/// `levelProvenance` is read: absence is absence, never a default. In
/// particular [contested] must stay `bool?` — the board renders the contested
/// card only on an explicit `true`, and an old verdict must never surface as
/// "not contested".
class DecisionRecord {
  const DecisionRecord({
    this.score,
    this.threshold,
    this.allowedActions,
    this.computedSizePct,
    this.unresolvedObjections,
    this.unresolvedObjectionIds,
    this.evidenceAvailable,
    this.evidenceSource,
    this.contested,
    this.contestedReasons,
  });

  factory DecisionRecord.fromJson(Map<String, dynamic> j) {
    final rawEvidenceAvailable = j['evidence_available'];
    final rawContested = j['contested'];
    return DecisionRecord(
      score: (j['score'] as num?)?.toDouble(),
      threshold: (j['threshold'] as num?)?.toDouble(),
      allowedActions: parseStringListOrNull(j['allowed_actions']),
      computedSizePct: (j['computed_size_pct'] as num?)?.toDouble(),
      unresolvedObjections: parseStringListOrNull(j['unresolved_objections']),
      unresolvedObjectionIds:
          parseStringListOrNull(j['unresolved_objection_ids']),
      evidenceAvailable: rawEvidenceAvailable is bool
          ? rawEvidenceAvailable
          : null,
      evidenceSource: j['evidence_source'] as String?,
      contested: rawContested is bool ? rawContested : null,
      contestedReasons: parseStringListOrNull(j['contested_reasons']),
    );
  }

  final double? score;
  final double? threshold;
  final List<String>? allowedActions;

  /// The size the evidence curve computed within the mandate cap — distinct
  /// from `RoomVerdict.sizePct`, which is what the final verdict carried.
  final double? computedSizePct;
  final List<String>? unresolvedObjections;
  final List<String>? unresolvedObjectionIds;
  final bool? evidenceAvailable;
  final String? evidenceSource;
  final bool? contested;
  final List<String>? contestedReasons;
}

/// CR219 R60 — one fact-sheet field whose liveness changed between the prior
/// convene and this one, both states read straight off the two runs' recorded
/// `sheet_state` maps. `fromState`/`toState` are wire tokens such as `LIVE`,
/// `UNAVAILABLE`, `WITHHELD_PAID` — rendered as-is, never re-derived.
class SheetFieldTransition {
  const SheetFieldTransition({
    required this.field,
    required this.fromState,
    required this.toState,
  });

  factory SheetFieldTransition.fromJson(Map<String, dynamic> j) =>
      SheetFieldTransition(
        field: j['field'] as String? ?? '',
        fromState: j['from_state'] as String? ?? '',
        toState: j['to_state'] as String? ?? '',
      );

  final String field;
  final String fromState;
  final String toState;
}

/// CR219 R60 — "what changed since your last convene", built server-side from
/// the prior run's persisted verdict and this run's fact sheet. Absent on a
/// first convene or when the only prior was an outage abstain — the board
/// renders no card at all in that case rather than a "no changes" line.
///
/// [changedFields] degrades per entry: a prior run that predates `sheet_state`
/// leaves it empty while the action/date lines stay usable, so empty means
/// "not recorded then", not "nothing changed".
class NextConveneDelta {
  const NextConveneDelta({
    required this.priorDate,
    required this.priorAction,
    this.priceMovePct,
    this.changedFields = const [],
    this.priorKillCriterion,
  });

  factory NextConveneDelta.fromJson(Map<String, dynamic> j) {
    final rawChanged = j['changed_fields'];
    final rawPriorDate = j['prior_date'];
    return NextConveneDelta(
      priorDate:
          DateTime.tryParse(rawPriorDate is String ? rawPriorDate : ''),
      priorAction: j['prior_action'] as String? ?? '',
      priceMovePct: (j['price_move_pct'] as num?)?.toDouble(),
      changedFields: rawChanged is List
          ? [
              for (final m in rawChanged)
                if (m is Map)
                  SheetFieldTransition.fromJson(m.cast<String, dynamic>()),
            ]
          : const [],
      priorKillCriterion: j['prior_kill_criterion'] as String?,
    );
  }

  final DateTime? priorDate;
  final String priorAction;
  final double? priceMovePct;
  final List<SheetFieldTransition> changedFields;
  final String? priorKillCriterion;
}

class RoomTranscriptLine {
  const RoomTranscriptLine({
    required this.agentId,
    required this.content,
    this.stance,
    this.conviction,
    this.headline,
    this.stanceRecorded = false,
  });

  final String agentId;
  final String content;

  /// CR106 B2 — the agent's own stated position: `for` / `against` / `neutral`,
  /// or null when it stated none. Null NEVER means neutral; the comb puts it in
  /// a separate gutter and counts bands over non-null stances only (T-SUM11).
  final String? stance;

  /// `low` / `medium` / `high`, quantised server-side. Null renders no bar and
  /// no track at all — absence must not look like "low".
  final String? conviction;

  /// The agent's own headline number, already length-capped server-side.
  final String? headline;

  /// Whether the payload carried the stance field at all. Distinguishes "this
  /// agent took no side" (recorded, null) from "this run predates B2" (not
  /// recorded) — the comb shows a gutter for the first and one honest sentence
  /// for the second, and never reconstructs either (T-BACKFILL).
  final bool stanceRecorded;
}

class RoomRunSnapshot {
  const RoomRunSnapshot({
    required this.id,
    required this.userId,
    required this.ticker,
    required this.status,
    required this.modelTier,
    required this.transcript,
    this.verdict,
    this.creditCost,
    this.durationMs,
    this.refunded = false,
    this.cioRetryAvailable = false,
    this.cioRetried = false,
  });

  final String id;
  final String userId;
  final String ticker;
  final String status;
  final String modelTier;
  final List<RoomTranscriptLine> transcript;
  final RoomVerdict? verdict;
  final int? creditCost;
  final int? durationMs;

  /// CR237 round 2 (auditor MAJOR-3) — the same three server-computed flags
  /// the `done` SSE event carries, read off the GET payload so a dropped-socket
  /// recovery (`_recoverViaPolling`) still offers "Ask the CIO again" and keeps
  /// the cost line truthful. Absent or non-bool ⇒ false, exactly like the
  /// `done` handler — never inferred from `verdict.reason`.
  final bool refunded;
  final bool cioRetryAvailable;
  final bool cioRetried;

  factory RoomRunSnapshot.fromJson(Map<String, dynamic> j) {
    return RoomRunSnapshot(
      id: j['id'] as String,
      userId: j['user_id'] as String,
      ticker: j['ticker'] as String,
      status: j['status'] as String? ?? 'completed',
      modelTier: j['model_tier'] as String? ?? 'mid',
      transcript: ((j['transcript'] as List?) ?? const [])
          .map((m) => RoomTranscriptLine(
                agentId: (m['agent_id'] as String?) ?? '',
                content: (m['content'] as String?) ?? '',
                stance: m['stance'] as String?,
                conviction: m['conviction'] as String?,
                headline: m['headline'] as String?,
                // Key PRESENCE, not value: a server that predates B2 sends no
                // key at all, and "this run recorded no stances" is a
                // different fact from "this agent stated none" (T-BACKFILL).
                stanceRecorded: m is Map && m.containsKey('stance'),
              ))
          .toList(),
      verdict: j['verdict'] == null
          ? null
          : RoomVerdict.fromJson(j['verdict'] as Map<String, dynamic>),
      creditCost: (j['credit_cost'] as num?)?.toInt(),
      durationMs: (j['duration_ms'] as num?)?.toInt(),
      refunded: j['refunded'] is bool ? j['refunded'] as bool : false,
      cioRetryAvailable: j['cio_retry_available'] is bool
          ? j['cio_retry_available'] as bool
          : false,
      cioRetried: j['cio_retried'] is bool ? j['cio_retried'] as bool : false,
    );
  }
}
