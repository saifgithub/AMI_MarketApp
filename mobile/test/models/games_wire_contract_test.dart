/// CR109 — the client must parse what the backend ACTUALLY sends.
///
/// Both fixtures below are copied verbatim from live Alpha responses, not
/// from the design doc. That distinction is the point of this file: the doc
/// described the fields and never the envelope, and both lanes were unit
/// tested against their own idea of the contract, so both were green while
/// the app was broken.
///
/// Two real failures this pins:
///
///  1. `/v1/games/runs` and `/v1/games/cadences` return a BARE JSON ARRAY.
///     The client asked Dio for `Map<String, dynamic>` and read an envelope
///     (`data['runs']`), so the cast threw and the screen showed
///     "Couldn't load your game runs" sitting on top of an HTTP 200. The
///     server log said success; the user saw failure.
///
///  2. The cadence payload carries the next field FLAT (`field_id`, `state`,
///     `starts_on`, …) rather than nested under `next_field`, and names three
///     keys differently: `state`, `deadline`, `already_held`. Every read was
///     null-safe, so this one did NOT throw — it quietly produced a cadence
///     with no field, no deadline and `alreadyHolds: false`. A silent wrong
///     answer, which is the worse of the two.
library;

import 'package:ami_trade/models/games.dart';
import 'package:flutter_test/flutter_test.dart';

/// Verbatim from `GET /v1/games/cadences` on Alpha, 2026-08-09.
const _liveCadence = <String, dynamic>{
  'cadence': 'week',
  'field_id': 'c1289fe9-2bed-4ee4-a00a-18758df2a648',
  'state': 'entry_open',
  'entry_opens_at': '2026-08-03T09:00:00-04:00',
  'locks_at': '2026-08-10T09:00:00-04:00',
  'starts_on': '2026-08-10',
  'ends_on': '2026-08-14',
  'queue_count': 0,
  'deadline': '2026-08-10T09:00:00-04:00',
  'already_held': false,
};

/// Verbatim from `GET /v1/games/runs` on Alpha, 2026-08-09.
const _liveRun = <String, dynamic>{
  'run_id': '58219342-7206-42e7-9140-7712f0f85726',
  'field_id': 'c1289fe9-2bed-4ee4-a00a-18758df2a648',
  'cadence': 'week',
  'state': 'entered',
  'intent': 'thesis',
  'twr_pct': null,
  'days_left': 5,
  'starts_on': '2026-08-10',
  'ends_on': '2026-08-14',
  'fees_paid': 0.0,
  'trade_count': 0,
};

/// Verbatim from `GET /v1/games/runs/{run_id}` on Alpha, 2026-08-09 — the
/// shape BEFORE `cash_committed` / `cash_available` / `queued_order_count`
/// existed. Kept as a fixture in its own right: the client must still be
/// correct against a server that predates those fields, and the only way to
/// know it is to keep parsing the payload that server sent.
const _liveRunDetailPreCommitted = <String, dynamic>{
  'run_id': '58219342-7206-42e7-9140-7712f0f85726',
  'cadence': 'week',
  'state': 'entered',
  'intent': 'thesis',
  'starts_on': '2026-08-10',
  'ends_on': '2026-08-14',
  'current_cash': 10000.0,
  'total_value': 10000.0,
  'price_source': 'mock_walk',
  'fees_paid': 0.0,
  'trade_count': 0,
  'twr_pct': null,
  'nav_series': [
    {
      'as_of_date': '2026-08-07',
      'nav': 10000.0,
      'cash': 10000.0,
      'price_source': 'cash',
      'capital_event': 'open',
    }
  ],
  'holdings': <dynamic>[],
};

/// Verbatim from `POST /v1/games/runs/{run_id}/trade/quote` on Alpha.
const _liveQuote = <String, dynamic>{
  'ticker': 'AMD',
  'side': 'buy',
  'quantity': 5.1721,
  'price': 483.3599853515625,
  'price_source': 'yfinance',
  'notional': 2499.99,
  'estimated_fee': 2.5,
  'estimated_total': 2502.49,
  'book_percentage': 25.0,
  'market_open': false,
};

/// Verbatim from `GET /v1/games/runs/{run_id}/orders` on Alpha,
/// 2026-08-10, immediately after promoting the endpoint. One of three rows
/// returned for a run with three orders standing.
const _liveQueuedOrder = <String, dynamic>{
  'id': '1651e130-1490-402c-b7e4-fb0f2ed17695',
  'ticker': 'AAPL',
  'side': 'buy',
  'quantity': 1.5958,
  'queued_at': '2026-08-09T21:48:19.859314+00:00',
  'est_price': 313.3299865722656,
  'price_source': 'yfinance',
  'est_notional': 500.01,
  'est_fee': 1.0,
  'est_total': 501.01,
  // Added 2026-08-10 when the list started carrying refusals too. Explicit
  // on every row so the client never has to infer which kind it is holding.
  'state': 'queued',
};

/// Verbatim shape of a REFUSED row from the same endpoint — an order the
/// open would not take. Before this, `list_queued_orders` filtered to
/// `state == "queued"` and the row simply vanished overnight: some orders
/// filled, some gone, and nothing anywhere saying which or why.
const _liveRefusedOrder = <String, dynamic>{
  'id': '9f1a0c33-1111-4444-8888-aaaabbbbcccc',
  'ticker': 'BAC',
  'side': 'buy',
  'quantity': 7.5323,
  'queued_at': '2026-08-10T02:11:04.120031+00:00',
  'state': 'refused',
  'cancel_reason': r'insufficient cash: need $476.82, have $12.00',
};

/// Verbatim from `GET /v1/games/runs/{run_id}` on Alpha, 2026-08-10, with
/// three orders queued against a 10,000 stake and nothing filled yet.
/// `nav_series` trimmed to one point; everything else is untouched.
///
/// Note what is NOT here: `days_left`. The run SUMMARY carries it, the run
/// DETAIL does not — see the test below.
const _liveRunDetail = <String, dynamic>{
  'run_id': '58219342-7206-42e7-9140-7712f0f85726',
  'cadence': 'week',
  'state': 'entered',
  'intent': 'thesis',
  'starts_on': '2026-08-10',
  'ends_on': '2026-08-14',
  'current_cash': 10000.0,
  'cash_committed': 6139.93,
  'cash_available': 3860.07,
  'queued_order_count': 3,
  'total_value': 10000.0,
  'price_source': 'mock_walk',
  'fees_paid': 0.0,
  'trade_count': 0,
  'twr_pct': null,
  'nav_series': <dynamic>[
    {
      'as_of_date': '2026-08-07',
      'nav': 10000.0,
      'cash': 10000.0,
      'price_source': 'cash',
      'capital_event': 'open',
    },
  ],
  'holdings': <dynamic>[],
};

void main() {
  group('queued-order payload', () {
    test('reads the id under `id`, which is what the router returns', () {
      final o = GameQueuedOrder.fromJson(_liveQueuedOrder);
      expect(
        o.orderId,
        '1651e130-1490-402c-b7e4-fb0f2ed17695',
        reason: 'the cancel endpoint is keyed on this; an empty id sends the '
            'player a cancel for nothing',
      );
      expect(o.ticker, 'AAPL');
      expect(o.quantity, 1.5958);
      expect(o.estTotal, 501.01);
      expect(o.estFee, 1.0);
      expect(o.estimateIsLive, isTrue);
    });

    test('a queued row declares its state rather than implying it', () {
      final o = GameQueuedOrder.fromJson(_liveQueuedOrder);
      expect(o.state, 'queued');
      expect(o.isRefused, isFalse);
    });

    test('a refused row carries WHY, and is not mistaken for pending', () {
      final o = GameQueuedOrder.fromJson(_liveRefusedOrder);
      expect(o.isRefused, isTrue);
      expect(
        o.cancelReason,
        contains('insufficient cash'),
        reason: 'the server already knows exactly why; dropping the reason is '
            'what turned a refusal into a disappearance',
      );
      expect(o.ticker, 'BAC');
      expect(o.quantity, 7.5323);
    });

    test('a mock_walk estimate is not live', () {
      final o = GameQueuedOrder.fromJson(
        {..._liveQueuedOrder, 'price_source': 'mock_walk'},
      );
      expect(o.estimateIsLive, isFalse);
    });
  });

  group('run-detail payload', () {
    test('committed and available cash read under the names sent', () {
      final d = GameRunDetail.fromJson(_liveRunDetail);
      expect(d.cash, 10000.0);
      expect(d.cashCommitted, 6139.93);
      expect(
        d.cashAvailable,
        3860.07,
        reason: 'what the ticket may size against. Sizing against `cash` let '
            'a player commit several times their book',
      );
      expect(d.queuedOrderCount, 3);
    });

    test('days_left is ABSENT here and is derived from ends_on', () {
      // The run summary sends `days_left`; this payload does not. Reading it
      // straight gave null, which the empty-book copy rendered as "0 days to
      // deploy it" on a run with days to go — a confident wrong number in
      // the one place §13.3 requires the clock.
      expect(_liveRunDetail.containsKey('days_left'), isFalse);
      final d = GameRunDetail.fromJson(_liveRunDetail);
      expect(d.endsOn, DateTime.parse('2026-08-14'));
      expect(
        d.daysLeft,
        isNotNull,
        reason: 'derived from ends_on, which the payload does carry',
      );
    });

    test('an empty book is never caveated as simulated', () {
      // Live Alpha reports `price_source: mock_walk` on a book with no
      // holdings, because the snapshot echoes the provider regardless. The
      // value is the cash balance; no mark was consulted. Caveating it
      // teaches the player to ignore the caveat that matters.
      expect(_liveRunDetail['price_source'], 'mock_walk');
      final d = GameRunDetail.fromJson(_liveRunDetail);
      expect(d.holdings, isEmpty);
      expect(d.marksAreLive, isTrue);
    });

    test('mock marks on a book WITH holdings still carry the caveat', () {
      final d = GameRunDetail.fromJson({
        ..._liveRunDetail,
        'holdings': [
          {'ticker': 'AAPL', 'quantity': 2.0, 'avg_cost': 310.0, 'mark': 313.33},
        ],
      });
      expect(d.marksAreLive, isFalse);
    });
  });

  group('cadence payload — the flat shape the backend really sends', () {
    test('resolves the next field even though it is not nested', () {
      final c = GameCadenceInfo.fromJson(_liveCadence);
      expect(
        c.nextField,
        isNotNull,
        reason: 'a null field renders an entry card that cannot say when '
            'entry closes — the silent half of this defect',
      );
      expect(c.nextField!.fieldId, 'c1289fe9-2bed-4ee4-a00a-18758df2a648');
      expect(c.nextField!.startsOn, DateTime.parse('2026-08-10'));
    });

    test('reads state / deadline / already_held under the names sent', () {
      final c = GameCadenceInfo.fromJson(_liveCadence);
      expect(c.entryState, 'entry_open');
      expect(c.queueDeadline, isNotNull);
      expect(c.alreadyHolds, isFalse);
    });

    test('already_held true is not silently dropped', () {
      final c = GameCadenceInfo.fromJson({..._liveCadence, 'already_held': true});
      expect(
        c.alreadyHolds,
        isTrue,
        reason: 'dropping this shows "enter this field" to a player who is '
            'already in, and the enter call then 409s',
      );
    });

    test('still accepts the nested/enveloped shape, if it ever ships', () {
      final c = GameCadenceInfo.fromJson({
        'cadence': 'week',
        'next_field': {'field_id': 'abc', 'starts_on': '2026-08-10'},
        'entry_state': 'entry_open',
        'queue_deadline': '2026-08-10T09:00:00-04:00',
        'already_holds': true,
      });
      expect(c.nextField!.fieldId, 'abc');
      expect(c.entryState, 'entry_open');
      expect(c.alreadyHolds, isTrue);
    });
  });

  group('run payload', () {
    test('parses the live shape', () {
      final r = GameRunSummary.fromJson(_liveRun);
      expect(r.runId, '58219342-7206-42e7-9140-7712f0f85726');
      expect(r.cadence, 'week');
      expect(r.daysLeft, 5);
      expect(r.twrPct, isNull, reason: 'no NAV history yet — null, not 0.0');
    });
  });

  group('run DETAIL payload — the one that sized every order to zero', () {
    test('cash comes through, under the name the backend actually sends', () {
      final d = GameRunDetail.fromJson(_liveRunDetailPreCommitted);
      expect(
        d.cash,
        10000.0,
        reason: 'read as `cash` while the backend sends `current_cash`, this '
            'defaulted to 0.0 — so the ticket sized every order as a '
            'percentage of ZERO and the confirm card showed 0.0000 shares, '
            '0.0% of book and the 1.00 minimum-fee floor',
      );
      expect(d.stake, 10000.0, reason: 'sent as `total_value`');
    });

    test('the NAV series parses, and a cash day is not a caveat', () {
      final d = GameRunDetail.fromJson(_liveRunDetailPreCommitted);
      expect(d.navSeries, hasLength(1));
      expect(
        d.navSeries.single.isLive,
        isTrue,
        reason: '`cash` means NAV was known exactly, not estimated — it must '
            'not be dashed on the curve like a simulated price',
      );
    });

    test('no field silently defaults away', () {
      final d = GameRunDetail.fromJson(_liveRunDetailPreCommitted);
      expect(d.runId, isNotEmpty);
      expect(d.cadence, 'week');
      expect(d.state, 'entered');
      expect(d.startsOn, DateTime.parse('2026-08-10'));
      expect(d.endsOn, DateTime.parse('2026-08-14'));
    });

    test('a server with no cash_available still yields a safe one', () {
      // The fallback is `cash − committed`, and with neither field sent that
      // is just cash. A client that hard-required the new keys would size
      // every order against 0 the moment it met an older backend — the
      // failure this whole file exists to stop, arriving from the other
      // direction.
      final d = GameRunDetail.fromJson(_liveRunDetailPreCommitted);
      expect(d.cashCommitted, 0.0);
      expect(d.cashAvailable, 10000.0);
      expect(d.queuedOrderCount, 0);
    });
  });

  group('trade result — the payload that claimed a fill that never happened', () {
    /// Verbatim from `POST /v1/games/runs/{run_id}/trade` on Alpha, outside
    /// market hours. Note there is no `status` key at all.
    const liveQueued = <String, dynamic>{
      'queued': true,
      'filled': false,
      'fee': null,
      'next_open_at': '2026-08-10T13:30:00+00:00',
    };

    test('a queued order reports QUEUED, not filled', () {
      final r = GameTradeResult.fromJson(liveQueued);
      expect(
        r.isQueued,
        isTrue,
        reason: 'the client read j["status"] and defaulted to "filled" — so '
            'every out-of-hours order told the player it had EXECUTED. The '
            'market was shut and nothing had happened',
      );
      expect(r.isFilled, isFalse);
      expect(r.queuedFor, isNotNull, reason: 'sent as next_open_at');
    });

    test('a real fill still reports filled', () {
      final r = GameTradeResult.fromJson({
        'queued': false,
        'filled': true,
        'fee': 2.5,
        'quantity': 5.1721,
        'price': 483.36,
      });
      expect(r.isFilled, isTrue);
      expect(r.isQueued, isFalse);
      expect(r.shares, 5.1721);
      expect(r.fee, 2.5);
    });

    test('an unrecognised payload claims NEITHER', () {
      // The important one. With no information the old default asserted a
      // fill; absent information must never become a positive claim about a
      // position in a scored contest.
      final r = GameTradeResult.fromJson(<String, dynamic>{});
      expect(r.isFilled, isFalse);
      expect(r.isQueued, isFalse);
      expect(r.status, 'unknown');
    });
  });

  group('quote payload', () {
    test('shares and fee read under the backend\'s names', () {
      final q = GameTradeQuote.fromJson(_liveQuote);
      expect(
        q.shares,
        5.1721,
        reason: 'sent as `quantity`; reading only `shares` showed 0.0000 on '
            'the confirm card for a real order',
      );
      expect(
        q.estFee,
        2.5,
        reason: 'sent as `estimated_fee`; reading only `est_fee` showed a '
            'zero trading cost, which is the one number the ticket exists to '
            'disclose',
      );
      expect(q.price, closeTo(483.36, 0.01));
      expect(q.bookPercentage, 25.0);
    });

    test('the queue flag is derived from market_open, which is what is sent', () {
      final q = GameTradeQuote.fromJson(_liveQuote);
      expect(
        q.willQueue,
        isTrue,
        reason: 'the seventh instance of this file\'s own bug class: there is '
            'no `will_queue` key on the wire at all — the backend sends '
            '`market_open`, its inverse — so the client defaulted to false '
            'and the confirm card silently dropped the queue note on the '
            'path §5.1 calls NORMAL for this audience',
      );
      expect(q.mayQueue, isTrue);
    });
  });
}
