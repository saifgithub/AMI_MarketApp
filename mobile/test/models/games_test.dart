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
}
