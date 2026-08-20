/// CR173 slice 2 — YOUR TEAM'S CALLS, as data.
///
/// Carousel card 2 and the list screen it opens read the same rows: the
/// `ROOM_RUN` journal entries the Decision Journal already holds. No new table,
/// no new endpoint — §4's inventory is explicit that the only candidate backend
/// surface in this CR is the price lookup, and this is not it.
///
/// **What "delta since" can honestly mean.** A verdict record does not store
/// the price at the moment it landed. What it stores is the entry the PM
/// *named*, and only on an APPROVE — a PASS proposes no level at all. So the
/// delta is measured against that entry and labelled as such, and a PASS row
/// carries a dash rather than a zero. The alternative (a number computed from
/// whatever price happened to be nearby) is the `?? 0` family: an unmeasured
/// value and a real one rendered identically.
library;

import 'package:ami_trade/models/journal.dart';
import 'package:ami_trade/models/sim.dart';

class TeamCall {
  const TeamCall({
    required this.ticker,
    required this.action,
    required this.at,
    this.entry,
    this.runId,
    this.reason,
    this.actioned,
  });

  final String ticker;

  /// The wire action, **unmapped**. APPROVE and PASS are the vocabulary every
  /// surface says (acceptance #6); anything else — REJECT, MODIFY, NO_VERDICT,
  /// or a value added after this build — is rendered by `room.dart`'s
  /// neutral-unknown rule at the widget, never bucketed here.
  final String action;

  final DateTime at;

  /// The level the PM named. Null on anything that is not an APPROVE, and null
  /// on an APPROVE that recorded no entry — both are "no reference price", and
  /// neither may become a zero.
  final double? entry;

  /// `reference_id` — the run, so a row can reopen its settled Verdict Board.
  final String? runId;

  final String? reason;

  /// CR184 — whether this verdict was executed in the training ledger
  /// (server-side join, `JournalEntry.actioned` passed through unmapped).
  /// `false` is the only value that puts a call on the NOT ACTIONED card;
  /// `null` is N/A (verdict-less, or a backend without the field) and must
  /// never be treated as false.
  final bool? actioned;

  bool get hasReference => entry != null;
}

/// Newest first. Entries that are not room runs, or whose run never reached a
/// verdict, are **dropped rather than counted** — a run that failed before
/// ruling is not a call the team made, and showing it as one would put a row on
/// the card with nothing behind it.
List<TeamCall> teamCallsFrom(List<JournalEntry> entries, {int? limit}) {
  final calls = <TeamCall>[];
  for (final e in entries) {
    if (e.entryType != JournalEntryType.roomRun) continue;
    final v = e.payload['verdict'];
    if (v is! Map) continue;
    final action = v['action'];
    if (action is! String || action.isEmpty) continue;
    final ticker = e.ticker;
    if (ticker == null || ticker.isEmpty) continue;
    calls.add(TeamCall(
      ticker: ticker,
      action: action,
      at: e.createdAt,
      entry: action == 'APPROVE' ? _asDouble(v['entry']) : null,
      runId: e.referenceId,
      reason: v['reason'] as String?,
      actioned: e.actioned,
    ));
  }
  calls.sort((a, b) => b.at.compareTo(a.at));
  if (limit != null && calls.length > limit) {
    return List<TeamCall>.unmodifiable(calls.take(limit));
  }
  return List<TeamCall>.unmodifiable(calls);
}

/// The wire carries JSON numbers, which arrive as `int` or `double` depending
/// on whether the value had a fractional part. A hard cast to `double` throws
/// on `118`; a silent `?? 0` would price a trade at zero.
double? _asDouble(Object? v) => v is num ? v.toDouble() : null;

/// The change from the level the PM named to the price now, in percent.
///
/// Null when either side is missing, and the caller must render that as "no
/// reading" — never as `0.0%`, which is a real and different answer (CR040).
double? deltaSinceEntry({required double? entry, required double? now}) {
  if (entry == null || now == null || entry == 0) return null;
  return ((now - entry) / entry) * 100;
}

/// CR184 — the calls the NOT ACTIONED card shows: verdicts the server says
/// were never executed (`actioned == false`; null is N/A, never false),
/// deduped to the latest convene per ticker, newest first.
///
/// The input is [teamCallsFrom]'s output, already sorted newest-first, and
/// that order is the ONLY order — the CR's acceptance says selection must
/// never be ranked by regret, so no delta is consulted here and none may be.
List<TeamCall> unactionedFrom(List<TeamCall> calls, {int limit = 2}) {
  final seen = <String>{};
  final out = <TeamCall>[];
  for (final c in calls) {
    if (c.actioned != false) continue;
    if (!seen.add(c.ticker)) continue;
    out.add(c);
    if (out.length == limit) break;
  }
  return List<TeamCall>.unmodifiable(out);
}

/// CR184 — the smallest `/v1/sim/history` period token that still reaches
/// back to [at]. Daily candles; the margins are under each period's trading-
/// day span so a convene near the boundary still lands inside the window.
String historyPeriodFor({required DateTime at, required DateTime now}) {
  final days = now.difference(at).inDays;
  if (days <= 4) return '1w';
  if (days <= 26) return '1m';
  if (days <= 85) return '3m';
  if (days <= 360) return '1y';
  return '5y';
}

/// CR184 — the reconstructed reference price for a PASS: the close of the
/// last trading day on or before the convene ([at]), read from the daily
/// candles. A PASS names no entry level, so this disclosed close is the only
/// honest thing a delta can be measured against.
///
/// Null — rendered as a dash, never a number — when the history could not be
/// read, when it is not live-sourced (a mock-walk candle's close is fabricated
/// by construction, CR040), or when no candle predates the convene. The
/// returned `date` is the candle's own day so the disclosure ("vs close on
/// {date}") states what was actually measured, weekends included.
({double close, DateTime date})? conveneDayClose({
  required SimHistory? history,
  required DateTime at,
}) {
  if (history == null || !history.isLivePrice) return null;
  SimCandle? last;
  for (final c in history.candles) {
    if (c.dateTime.isAfter(at)) continue;
    if (last == null || c.t > last.t) last = c;
  }
  if (last == null) return null;
  return (close: last.c, date: last.dateTime);
}
