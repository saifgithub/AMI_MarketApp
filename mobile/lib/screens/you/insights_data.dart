/// CR178 — INSIGHTS, the aggregation half.
///
/// Pure: journal entries in, counts out. No widgets, no network, no `ref`. The
/// cards are the easy part; what is worth testing is whether the numbers are
/// the ones the schema can actually support, so the numbers live where they can
/// be tested without pumping a screen.
///
/// **Three rules run through all of it, and each exists because of a specific
/// way this could lie:**
///
///   1. **A figure that cannot be derived is not rendered** (CR040). Two panels
///      the design wanted are absent rather than zeroed — see
///      [InsightsData.notMeasured].
///   2. **A degenerate ratio is not a finding.** Every card carries an
///      empty-state threshold, because a `1/1` bar reading 100% is the failure
///      mode: it is not a weak signal, it is no signal wearing a strong one.
///   3. **The window is named, and named honestly.** The journal read caps at
///      100 entries, so past that an unlabelled aggregate would describe *the
///      most recent 100* while presenting itself as all-time. Under 100, saying
///      "last 100" is the same lie pointing the other way, so [windowIsCapped]
///      distinguishes them.
library;

import 'package:ami_trade/models/journal.dart';
import 'package:flutter/foundation.dart';

/// What `GET /v1/journal/{user}` returns at most (`limit: int = 100`,
/// `backend/app/api/journal.py`). INSIGHTS aggregates client-side, so this is
/// also the window every card describes.
///
/// Saiful, 2026-08-13: *"Yes, just the last 100."* Rejected: paging until
/// exhausted on the client (N round trips per tab open, worsening forever) and
/// a backend aggregate endpoint (correct, but the one thing that would stop
/// CR133/CR178 being a pure frontend build). Recency is also the more useful
/// window: an all-time average quietly flattens the month a trader actually
/// changed how they trade.
const int kInsightsWindow = 100;

/// How a closed trade ended. The buckets are the tags `api/sim.py` writes, and
/// they are disjoint by construction: an auto-close tags `won` or `lost`, a
/// manual close tags `manual`.
enum TradeEnding { won, lost, manual }

/// The PM's ruling. `noVerdict` is **its own outcome**, never folded into
/// `reject`: CR098 built it for the case where the PM declines to rule because
/// the run had no market read. Folding it in tells the user their idea was
/// turned down when it was never judged.
enum VerdictOutcome { approve, modify, reject, pass, noVerdict }

@immutable
class TradesCard {
  const TradesCard({required this.counts, required this.unclassified});

  /// Only the endings that actually occurred. A zero bucket is omitted rather
  /// than drawn at length zero — an empty bar reads as a measured zero.
  final Map<TradeEnding, int> counts;

  /// Closed trades whose tags matched no known ending. Disclosed rather than
  /// dropped: silently discarding rows makes every percentage below wrong by
  /// an amount nobody can see.
  final int unclassified;

  int get total => counts.values.fold(0, (a, b) => a + b) + unclassified;
}

@immutable
class VerdictCard {
  const VerdictCard({required this.counts, required this.noVerdictRecorded});

  final Map<VerdictOutcome, int> counts;

  /// Room runs whose `payload.verdict` is null — failed or cancelled before the
  /// PM ruled. **Excluded from the mix, never counted as PASS**, and surfaced
  /// so the totals reconcile.
  final int noVerdictRecorded;

  int get ruled => counts.values.fold(0, (a, b) => a + b);
}

@immutable
class AnalystCount {
  const AnalystCount({required this.agentId, required this.count});
  final String agentId;
  final int count;
}

@immutable
class LimitMove {
  const LimitMove({
    required this.field,
    required this.from,
    required this.to,
  });

  /// The mandate field, as it is spelled on the wire.
  final String field;
  final num from;
  final num to;

  /// A limit that got *looser* is the one worth noticing — it is the user
  /// giving themselves more rope, and doing it right after a loss is the habit
  /// the product exists to change. Larger caps and larger drawdowns are looser;
  /// so is a larger position or trade count.
  bool get loosened => to > from;
}

@immutable
class MandateCard {
  const MandateCard({required this.editCount, required this.moves});

  /// Number of `MANDATE_EDIT` **entries**, not fields changed. The Day Trader
  /// preset sets seven limits in one edit, and rendering that as seven
  /// loosenings would describe a spree that never happened.
  final int editCount;

  /// Net movement per field across the window, earliest `before` → latest
  /// `after`. A field edited and then edited back does not appear.
  final List<LimitMove> moves;
}

@immutable
class ChallengeRow {
  const ChallengeRow({
    required this.type,
    required this.attempts,
    required this.correct,
  });
  final String type;
  final int attempts;
  final int correct;
}

@immutable
class ChallengeCard {
  const ChallengeCard({required this.rows, required this.omittedTypes});
  final List<ChallengeRow> rows;

  /// Types that were attempted but fewer than [_minChallengeAttempts] times.
  /// Named, not dropped: "you have not done enough of these yet" is a true
  /// statement about the user's data; silence is a statement about ours.
  final int omittedTypes;
}

/// The two panels CR133 §4.1 specified and the schema cannot support.
///
/// Kept as a named, empty-able list rather than as a comment, because the whole
/// point is that they are **absent from the UI** and that their absence is
/// deliberate rather than an oversight a later session "fixes" by rendering a
/// zero.
enum NotMeasured {
  /// *Voices you actually read.* `room_runner.py` writes **every** agent in the
  /// transcript to `agents_involved`, and all 12 speak every run, so the chart
  /// would report participation and label it readership.
  voicesRead,

  /// *Followed the PM vs overrode.* There is no run→trade link: `reference_id`
  /// holds the run on one entry and the trade on the other. Stamping
  /// `from_run_id` into the `SIM_TRADE` payload would fix it and needs no
  /// migration, but it is not this CR.
  followedVsOverrode,

  /// *How often AMI stopped you.* A trade blocked by the mandate returns before
  /// the journal write, so a working safety floor and an absent one produce
  /// identical history. Filed as CR177.
  safetyFloorStops,
}

const int _minClosedTrades = 3;
const int _minChallengeAttempts = 5;

@immutable
class InsightsData {
  const InsightsData({
    required this.entryCount,
    this.trades,
    this.verdicts,
    this.analysts = const [],
    this.mandate,
    this.challenges,
  });

  /// Entries the window actually returned.
  final int entryCount;

  /// Null when the card is below its threshold — the caller renders nothing,
  /// not an empty card.
  final TradesCard? trades;
  final VerdictCard? verdicts;
  final List<AnalystCount> analysts;
  final MandateCard? mandate;
  final ChallengeCard? challenges;

  /// True when the read hit the cap, so what follows describes the most recent
  /// [kInsightsWindow] decisions rather than all of them.
  bool get windowIsCapped => entryCount >= kInsightsWindow;

  bool get isEmpty =>
      trades == null &&
      verdicts == null &&
      analysts.isEmpty &&
      mandate == null &&
      challenges == null;

  static const notMeasured = NotMeasured.values;
}

/// The limits worth tracking a trajectory for, and how they are spelled in the
/// mandate payload. Read from `payload.before` / `payload.after`, which
/// `api/mandate.py` writes as full model dumps — so every limit's path is
/// reconstructable with no new table.
const List<String> kTrackedLimits = [
  'risk_score',
  'max_drawdown_pct',
  'sector_cap_pct',
  'single_name_cap_pct',
  'max_open_positions',
  'max_trades_per_day',
  'max_trades_per_week',
  'max_open_risk_pct',
  'post_loss_cooldown_hours',
];

TradeEnding? _endingOf(JournalEntry e) {
  if (e.tags.contains('won')) return TradeEnding.won;
  if (e.tags.contains('lost')) return TradeEnding.lost;
  if (e.tags.contains('manual')) return TradeEnding.manual;
  return null;
}

VerdictOutcome? _outcomeOf(String? action) {
  switch (action) {
    case 'APPROVE':
      return VerdictOutcome.approve;
    case 'MODIFY':
      return VerdictOutcome.modify;
    case 'REJECT':
      return VerdictOutcome.reject;
    case 'PASS':
      return VerdictOutcome.pass;
    case 'NO_VERDICT':
      return VerdictOutcome.noVerdict;
  }
  // An action this build does not know. Not folded into anything — the same
  // reasoning as DEF210's null `entryType`: a wrong-but-known bucket is
  // indistinguishable from a right one.
  return null;
}

num? _numAt(Map<String, dynamic>? m, String key) {
  final v = m?[key];
  return v is num ? v : null;
}

/// Aggregate a journal window into the five cards.
///
/// `entries` is expected newest-first, which is what the journal endpoint
/// returns; only [buildMandateCard]'s trajectory depends on the order and it
/// says so.
InsightsData buildInsights(List<JournalEntry> entries) {
  // ── how your trades ended ──────────────────────────────────────────────
  final closed = entries
      .where((e) =>
          e.entryType == JournalEntryType.simTrade && e.tags.contains('closed'))
      .toList();
  TradesCard? trades;
  if (closed.length >= _minClosedTrades) {
    final counts = <TradeEnding, int>{};
    var unclassified = 0;
    for (final e in closed) {
      final ending = _endingOf(e);
      if (ending == null) {
        unclassified++;
      } else {
        counts[ending] = (counts[ending] ?? 0) + 1;
      }
    }
    trades = TradesCard(counts: counts, unclassified: unclassified);
  }

  // ── what your PM decided ───────────────────────────────────────────────
  final rooms =
      entries.where((e) => e.entryType == JournalEntryType.roomRun).toList();
  VerdictCard? verdicts;
  if (rooms.isNotEmpty) {
    final counts = <VerdictOutcome, int>{};
    var unrecorded = 0;
    for (final e in rooms) {
      final v = e.payload['verdict'];
      if (v is! Map) {
        unrecorded++;
        continue;
      }
      final outcome = _outcomeOf(v['action'] as String?);
      if (outcome == null) {
        unrecorded++;
        continue;
      }
      counts[outcome] = (counts[outcome] ?? 0) + 1;
    }
    // A window of rooms that all failed before ruling has nothing to say about
    // what the PM decides, so it is not a card.
    if (counts.isNotEmpty) {
      verdicts =
          VerdictCard(counts: counts, noVerdictRecorded: unrecorded);
    }
  }

  // ── analysts you sought out ────────────────────────────────────────────
  //
  // Deliberately NOT `ROOM_RUN.agents_involved`: all 12 agents appear in every
  // transcript, so that set measures participation, not who you went to.
  const sought = {
    JournalEntryType.oneOnOne,
    JournalEntryType.agentCoach,
    JournalEntryType.agentUnlock,
  };
  final byAgent = <String, int>{};
  for (final e in entries) {
    if (!sought.contains(e.entryType)) continue;
    if (e.agentsInvolved.isEmpty) continue;
    final id = e.agentsInvolved.first;
    byAgent[id] = (byAgent[id] ?? 0) + 1;
  }
  final analysts = byAgent.entries
      .map((kv) => AnalystCount(agentId: kv.key, count: kv.value))
      .toList()
    ..sort((a, b) => b.count.compareTo(a.count));

  // ── how your mandate has moved ─────────────────────────────────────────
  final edits = entries
      .where((e) => e.entryType == JournalEntryType.mandateEdit)
      .toList();
  final mandate = _buildMandateCard(edits);

  // ── daily challenge by type ────────────────────────────────────────────
  final byType = <String, List<bool>>{};
  for (final e in entries) {
    if (e.entryType != JournalEntryType.dailyChallenge) continue;
    final type = e.payload['type'];
    if (type is! String || type.isEmpty) continue;
    final correct = e.payload['correct'];
    byType.putIfAbsent(type, () => []).add(correct == true);
  }
  final rows = <ChallengeRow>[];
  var omitted = 0;
  for (final kv in byType.entries) {
    if (kv.value.length < _minChallengeAttempts) {
      omitted++;
      continue;
    }
    rows.add(ChallengeRow(
      type: kv.key,
      attempts: kv.value.length,
      correct: kv.value.where((c) => c).length,
    ));
  }
  rows.sort((a, b) => b.attempts.compareTo(a.attempts));
  final challenges = rows.isEmpty
      ? null
      : ChallengeCard(rows: rows, omittedTypes: omitted);

  return InsightsData(
    entryCount: entries.length,
    trades: trades,
    verdicts: verdicts,
    analysts: analysts,
    mandate: mandate,
    challenges: challenges,
  );
}

/// Net movement per limit across the window.
///
/// `edits` arrives newest-first, so the *earliest* `before` is the last
/// element's and the *latest* `after` is the first element's. Getting that
/// backwards silently reverses every "loosened" into "tightened" — a wrong
/// direction reads as confidently as a right one, which is why it is stated
/// here rather than left to the reader.
MandateCard? _buildMandateCard(List<JournalEntry> edits) {
  if (edits.isEmpty) return null;
  final earliest = edits.last.payload['before'];
  final latest = edits.first.payload['after'];
  if (earliest is! Map || latest is! Map) return null;

  final before = Map<String, dynamic>.from(earliest);
  final after = Map<String, dynamic>.from(latest);

  final moves = <LimitMove>[];
  for (final field in kTrackedLimits) {
    final from = _numAt(before, field);
    final to = _numAt(after, field);
    // A limit that was unset at either end has no trajectory. Treating null as
    // zero would invent a move from "no cap" to "cap of 0" — the `?? 0` defect
    // family, where an unmeasured value and a real zero become the same fact.
    if (from == null || to == null) continue;
    if (from == to) continue;
    moves.add(LimitMove(field: field, from: from, to: to));
  }
  return MandateCard(editCount: edits.length, moves: moves);
}
