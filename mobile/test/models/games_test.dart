/// CR109 slice 2 — `fromJson` parsing for the game's wire models.
///
/// The backend lane (`coder.api`) is landing this contract in parallel, so
/// every model is defensive (nullable reads, `??` fallbacks) — these tests
/// pin that defensiveness as much as the happy path: a response missing an
/// optional field must produce a sensible default, never a parse crash on
/// what is, in every store build, an unreachable route.
library;

import 'package:ami_trade/models/games.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('GameCadenceInfo', () {
    test('parses a full cadence entry', () {
      final c = GameCadenceInfo.fromJson({
        'cadence': 'week',
        'next_field': {
          'field_id': 'f1',
          'entry_opens_at': '2026-08-10T00:00:00Z',
          'locks_at': '2026-08-10T13:30:00Z',
          'starts_on': '2026-08-10',
          'ends_on': '2026-08-14',
          'entrant_count': 12,
        },
        'entry_state': 'not_entered',
        'queue_count': 3,
        'queue_deadline': '2026-08-10T13:30:00Z',
        'already_holds': false,
      });
      expect(c.cadence, 'week');
      expect(c.isWeekly, isTrue);
      expect(c.nextField, isNotNull);
      expect(c.nextField!.fieldId, 'f1');
      expect(c.nextField!.entrantCount, 12);
      expect(c.entryState, 'not_entered');
      expect(c.queueCount, 3);
      expect(c.alreadyHolds, isFalse);
    });

    test('defaults gracefully when next_field and dates are absent', () {
      final c = GameCadenceInfo.fromJson({'cadence': 'month'});
      expect(c.cadence, 'month');
      expect(c.isWeekly, isFalse);
      expect(c.nextField, isNull);
      expect(c.entryState, isNull);
      expect(c.queueCount, 0);
      expect(c.alreadyHolds, isFalse);
    });
  });

  group('GameEntry', () {
    test('accepts either entry_id or id', () {
      final byEntryId = GameEntry.fromJson({
        'entry_id': 'e1',
        'field_id': 'f1',
        'run_id': 'r1',
        'cadence': 'week',
        'state': 'entered',
      });
      expect(byEntryId.entryId, 'e1');

      final byId = GameEntry.fromJson({
        'id': 'e2',
        'field_id': 'f1',
        'run_id': 'r1',
        'cadence': 'week',
        'state': 'entered',
      });
      expect(byId.entryId, 'e2');
    });
  });

  group('GameRunSummary', () {
    test('isLive is true only for entered/active', () {
      for (final state in ['entered', 'active']) {
        final r = GameRunSummary.fromJson({
          'run_id': 'r1',
          'field_id': 'f1',
          'cadence': 'week',
          'state': state,
        });
        expect(r.isLive, isTrue, reason: 'state=$state should be live');
      }
      for (final state in ['finished', 'forfeit', 'void']) {
        final r = GameRunSummary.fromJson({
          'run_id': 'r1',
          'field_id': 'f1',
          'cadence': 'week',
          'state': state,
        });
        expect(r.isLive, isFalse, reason: 'state=$state should not be live');
      }
    });

    test('twrPct and daysLeft are nullable and parse when present', () {
      final r = GameRunSummary.fromJson({
        'run_id': 'r1',
        'field_id': 'f1',
        'cadence': 'week',
        'twr_pct': 2.35,
        'days_left': 3,
      });
      expect(r.twrPct, 2.35);
      expect(r.daysLeft, 3);

      final bare = GameRunSummary.fromJson({
        'run_id': 'r1',
        'field_id': 'f1',
        'cadence': 'week',
      });
      expect(bare.twrPct, isNull);
      expect(bare.daysLeft, isNull);
    });
  });

  group('GameRunDetail', () {
    test('parses stake, cash and a NAV series with per-point provenance', () {
      final d = GameRunDetail.fromJson({
        'run_id': 'r1',
        'field_id': 'f1',
        'cadence': 'week',
        'state': 'active',
        'stake': 10000.0,
        'cash': 4321.5,
        'twr_pct': 1.1,
        'days_left': 2,
        'nav_series': [
          {
            'as_of_date': '2026-08-10',
            'nav': 10000.0,
            'cash': 10000.0,
            'price_source': 'live',
          },
          {
            'as_of_date': '2026-08-11',
            'nav': 10100.0,
            'cash': 4321.5,
            'price_source': 'mock',
          },
        ],
      });
      expect(d.stake, 10000.0);
      expect(d.cash, 4321.5);
      expect(d.navSeries, hasLength(2));
      expect(d.navSeries[0].isLive, isTrue);
      expect(d.navSeries[1].isLive, isFalse);
      expect(d.navSeries[1].priceSource, 'mock');
    });

    test('defaults stake to 10,000 when absent', () {
      final d = GameRunDetail.fromJson({
        'run_id': 'r1',
        'field_id': 'f1',
        'cadence': 'week',
        'state': 'active',
      });
      expect(d.stake, 10000.0);
      expect(d.cash, 0.0);
      expect(d.navSeries, isEmpty);
    });
  });

  group('GameTradeQuote', () {
    test('parses the confirm card numbers', () {
      final q = GameTradeQuote.fromJson({
        'ticker': 'AAPL',
        'side': 'buy',
        'shares': 13.887,
        'price': 180.25,
        'notional': 2500.0,
        'est_fee': 2.5,
        'book_percentage': 25.0,
        'price_source': 'live',
        'will_queue': false,
      });
      expect(q.ticker, 'AAPL');
      expect(q.shares, closeTo(13.887, 1e-6));
      expect(q.estFee, 2.5);
      expect(q.bookPercentage, 25.0);
      expect(q.willQueue, isFalse);
    });

    test('will_queue defaults to false when absent', () {
      final q = GameTradeQuote.fromJson({'ticker': 'AAPL', 'side': 'buy'});
      expect(q.willQueue, isFalse);
    });
  });

  group('GameTradeResult', () {
    test('isQueued reflects status', () {
      final queued = GameTradeResult.fromJson({
        'status': 'queued',
        'ticker': 'AAPL',
        'side': 'buy',
        'queued_for': '2026-08-11T13:30:00Z',
      });
      expect(queued.isQueued, isTrue);
      expect(queued.queuedFor, isNotNull);

      final filled = GameTradeResult.fromJson({
        'status': 'filled',
        'ticker': 'AAPL',
        'side': 'buy',
      });
      expect(filled.isQueued, isFalse);
    });
  });

  // ── CR109 slice 3 — the Close and the Record ────────────────────────────

  group('GameCloseResult', () {
    test('parses a finished, placement-scored run', () {
      final r = GameCloseResult.fromJson({
        'run_id': 'r1',
        'field_id': 'f1',
        'cadence': 'week',
        'state': 'finished',
        'scoring_basis': 'placement',
        'entrant_count': 12,
        'final_rank': 3,
        'career_points_delta': 53,
        'final_twr_pct': 2.3,
        'counterfactual_first_picks_pct': 2.1,
        'counterfactual_index_pct': 0.6,
        'nav_series': [
          {
            'as_of_date': '2026-08-10',
            'nav': 10000.0,
            'cash': 10000.0,
            'price_source': 'live',
          },
          {
            'as_of_date': '2026-08-11',
            'nav': 10230.0,
            'cash': 4321.5,
            'price_source': 'live',
          },
        ],
      });
      expect(r.isVoid, isFalse);
      expect(r.isForfeit, isFalse);
      expect(r.isThinField, isFalse);
      expect(r.rank, 3);
      expect(r.entrantCount, 12);
      expect(r.careerPointsDelta, 53);
      expect(r.counterfactualFirstPicksPct, 2.1);
      expect(r.counterfactualIndexPct, 0.6);
      expect(r.navSeries, hasLength(2));
      expect(r.hasNearMiss, isFalse);
    });

    test('a thin-field (benchmark) run carries alpha_scored and '
        'alpha_display as two distinct, independently-read fields', () {
      final r = GameCloseResult.fromJson({
        'run_id': 'r1',
        'field_id': 'f1',
        'cadence': 'week',
        'state': 'finished',
        'scoring_basis': 'benchmark',
        'entrant_count': 3,
        'alpha_scored': 1.10,
        'alpha_display': 1.35,
      });
      expect(r.isThinField, isTrue);
      expect(r.rank, isNull);
      // Distinct values, neither derivable from the other by construction
      // of this fixture (1.35 - 1.10 = 0.25, an arbitrary gap, not a fixed
      // fee constant this model would ever compute) — proves both are read
      // straight off their own wire fields.
      expect(r.alphaScored, 1.10);
      expect(r.alphaDisplay, 1.35);
      expect(r.alphaScored, isNot(r.alphaDisplay));
    });

    test(
      'parses the shipped games_record_service.py.get_close_payload shape '
      '(alpha_scored_pct / alpha_display_pct / '
      'counterfactual_hold_*_pct / curve / stipend_points)',
      () {
        final r = GameCloseResult.fromJson({
          'run_id': 'r1',
          'field_id': 'f1',
          'cadence': 'week',
          'state': 'finished',
          'scoring_basis': 'benchmark',
          'entrant_count': 3,
          'void_reason': null,
          'rank': null,
          'final_twr_pct': 1.55,
          'alpha_scored_pct': 1.10,
          'alpha_display_pct': 1.35,
          'career_points_delta': 12,
          'stipend_points': 5,
          'fees_paid': 3.2,
          'trade_count': 4,
          'intent': 'thesis',
          'wildness_index': 0.2,
          'counterfactual_hold_index_pct': 0.6,
          'counterfactual_hold_first_picks_pct': 2.1,
          'curve': [
            {'as_of_date': '2026-08-03', 'nav': 10000.0, 'price_source': 'live'},
            {'as_of_date': '2026-08-07', 'nav': 10120.0, 'price_source': 'live'},
          ],
          // The real payload also nests the same data under beats/debrief —
          // this model only needs the flat top-level keys (payload_entry is
          // spread there too), so the nested blocks are irrelevant noise
          // this fixture includes to prove they don't need special handling.
          'beats': {
            'result': {'rank': null, 'career_points_delta': 12},
            'insight': {'kind': 'counterfactual'},
            're_entry': {'cadence': 'week'},
          },
          'debrief': {'fees_paid': 3.2},
        });

        expect(r.alphaScored, 1.10);
        expect(r.alphaDisplay, 1.35);
        expect(r.counterfactualFirstPicksPct, 2.1);
        expect(r.counterfactualIndexPct, 0.6);
        expect(r.navSeries, hasLength(2));
        expect(r.navSeries[0].nav, 10000.0);
        expect(r.stipendPoints, 5);
        // stipendAwarded derives from stipend_points when the server sends
        // no separate stipend_awarded flag (which it doesn't, today).
        expect(r.stipendAwarded, isTrue);
        expect(r.intent, 'thesis');
        expect(r.wildnessIndex, 0.2);
      },
    );

    test('a VOID run parses void_reason and no score fields are required', () {
      final r = GameCloseResult.fromJson({
        'run_id': 'r1',
        'field_id': 'f1',
        'cadence': 'week',
        'state': 'void',
        'void_reason': 'Mock-priced day — Aug 12',
        'stipend_awarded': true,
        'career_points_delta': 5,
      });
      expect(r.isVoid, isTrue);
      expect(r.voidReason, 'Mock-priced day — Aug 12');
      expect(r.stipendAwarded, isTrue);
      expect(r.rank, isNull);
      expect(r.alphaScored, isNull);
      expect(r.alphaDisplay, isNull);
    });

    test('a forfeited run is identified by state alone', () {
      final r = GameCloseResult.fromJson({
        'run_id': 'r1',
        'field_id': 'f1',
        'cadence': 'week',
        'state': 'forfeit',
        'career_points_delta': -6,
      });
      expect(r.isForfeit, isTrue);
      expect(r.isVoid, isFalse);
    });

    test('near-miss requires both label and gap; either alone is absent', () {
      final withBoth = GameCloseResult.fromJson({
        'run_id': 'r1',
        'field_id': 'f1',
        'cadence': 'week',
        'near_miss_label': '2nd place',
        'near_miss_gap_pct': 0.3,
      });
      expect(withBoth.hasNearMiss, isTrue);

      final labelOnly = GameCloseResult.fromJson({
        'run_id': 'r1',
        'field_id': 'f1',
        'cadence': 'week',
        'near_miss_label': '2nd place',
      });
      expect(labelOnly.hasNearMiss, isFalse);
    });

    test('defaults gracefully when only the required fields are present', () {
      final r = GameCloseResult.fromJson({
        'run_id': 'r1',
        'field_id': 'f1',
        'cadence': 'week',
      });
      expect(r.state, 'finished');
      expect(r.scoringBasis, 'placement');
      expect(r.entrantCount, 0);
      expect(r.careerPointsDelta, 0);
      expect(r.navSeries, isEmpty);
      expect(r.tradeCount, 0);
      expect(r.stipendAwarded, isFalse);
    });
  });

  group('GameRecord', () {
    test('parses career points, counts and run history', () {
      final r = GameRecord.fromJson({
        'career_points': 42,
        'entered_count': 5,
        'finished_count': 4,
        'forfeit_count': 1,
        'void_count': 0,
        'run_history': [
          {
            'entry_id': 'e1',
            'run_id': 'r1',
            'cadence': 'week',
            'state': 'finished',
            'closed_at': '2026-08-03T13:30:00Z',
            'final_rank': 3,
            'entrant_count': 12,
            'career_points_delta': 53,
          },
        ],
      });
      expect(r.careerPoints, 42);
      expect(r.enteredCount, 5);
      expect(r.finishedCount, 4);
      expect(r.forfeitCount, 1);
      expect(r.title, isNull);
      expect(r.runHistory, hasLength(1));
      expect(r.runHistory.single.entryId, 'e1');
      expect(r.runHistory.single.runId, 'r1');
      expect(r.runHistory.single.careerPointsDelta, 53);
    });

    test(
      'parses the shipped games_record_service.py.get_record shape '
      '(career_points_net / run_count, and a run_history row with no '
      'entry_id and no closed_at — only run_id and ends_on)',
      () {
        final r = GameRecord.fromJson({
          'career_points_net': 42,
          'forfeit_count': 1,
          'finished_count': 4,
          'void_count': 0,
          'run_count': 5,
          'run_history': [
            {
              'run_id': 'r1',
              'field_id': 'f1',
              'cadence': 'week',
              'state': 'finished',
              'final_twr_pct': 2.3,
              'alpha_scored_pct': 1.1,
              'career_points_delta': 53,
              'starts_on': '2026-08-03',
              'ends_on': '2026-08-07',
            },
          ],
        });
        expect(r.careerPoints, 42);
        expect(r.enteredCount, 5);
        expect(r.finishedCount, 4);
        expect(r.forfeitCount, 1);
        expect(r.runHistory, hasLength(1));
        final entry = r.runHistory.single;
        expect(entry.entryId, '', reason: 'no entry_id on the wire — degrades '
            'to empty, never a crash');
        expect(entry.runId, 'r1');
        expect(entry.careerPointsDelta, 53);
        // closed_at/scored_at are absent on the wire — falls back to
        // ends_on rather than showing no date at all.
        expect(entry.closedAt, isNotNull);
      },
    );

    test('careerPoints is read verbatim — never re-clamped by this model',
        () {
      // The ledger clamps AT WRITE (implementation_plan.md §4.5); a
      // negative value here would only ever occur if that guarantee broke
      // server-side, and this model must still surface it rather than
      // silently floor it, or a regression there becomes invisible here.
      final r = GameRecord.fromJson({'career_points': -7});
      expect(r.careerPoints, -7);
    });

    test('defaults gracefully to a zero-runs record', () {
      final r = GameRecord.fromJson(<String, dynamic>{});
      expect(r.careerPoints, 0);
      expect(r.enteredCount, 0);
      expect(r.finishedCount, 0);
      expect(r.forfeitCount, 0);
      expect(r.runHistory, isEmpty);
    });
  });

  group('GamePersonalRecord', () {
    test('parses a known category with its entry_id', () {
      final pr = GamePersonalRecord.fromJson({
        'kind': 'best_weekly_twr',
        'entry_id': 'e9',
        'value': 4.4,
        'cadence': 'week',
        'achieved_at': '2026-08-03T13:30:00Z',
      });
      expect(pr.kind, 'best_weekly_twr');
      expect(pr.entryId, 'e9');
      expect(pr.value, 4.4);
      expect(pr.achievedAt, isNotNull);
    });

    test('an unrecognised kind still parses, with a title-cased fallback',
        () {
      final pr = GamePersonalRecord.fromJson({
        'kind': 'best_something_new',
        'entry_id': 'e1',
      });
      expect(pr.kind, 'best_something_new');
      expect(pr.fallbackLabel, 'Best Something New');
    });
  });
}
