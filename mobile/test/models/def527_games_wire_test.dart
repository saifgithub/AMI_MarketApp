/// DEF527 — five Games routes sent a different shape from the one the app
/// read, so the Dart models silently defaulted. Each fixture below is the
/// shape `backend/tests/unit/test_def367_games_wire.py` observes from the real
/// routes after the fix, so a drift on either side fails a test on that side.
///
/// The load-bearing one is the trade result: `side` defaulted to `'buy'`, so
/// any order whose side was not read parsed as a buy — a SELL included.
library;

import 'dart:convert';
import 'dart:typed_data';

import 'package:ami_trade/models/games.dart';
import 'package:ami_trade/services/api/api_client.dart';
import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';

class _Adapter implements HttpClientAdapter {
  _Adapter(this.body);
  final Map<String, dynamic> body;
  RequestOptions? last;

  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<Uint8List>? requestStream,
    Future<void>? cancelFuture,
  ) async {
    last = options;
    return ResponseBody.fromBytes(utf8.encode(jsonEncode(body)), 200,
        headers: {
          Headers.contentTypeHeader: [Headers.jsonContentType],
        });
  }

  @override
  void close({bool force = false}) {}
}

void main() {
  group('POST /v1/games/enter', () {
    test('reads the cadence and entry id the server sends', () {
      final e = GameEntry.fromJson({
        'entry_id': 'e-1',
        'run_id': 'r-1',
        'field_id': 'f-1',
        'cadence': 'month',
        'state': 'entered',
        'intent': null,
      });
      expect(e.cadence, 'month',
          reason: 'a Monthly entry must not be relabelled as the default week');
      expect(e.entryId, 'e-1');
    });
  });

  group('GET /v1/games/runs/{id}', () {
    test('reads days_left and field_id', () {
      final d = GameRunDetail.fromJson({
        'run_id': 'r-1',
        'field_id': 'f-1',
        'cadence': 'week',
        'state': 'active',
        'days_left': 3,
        'current_cash': 9000.0,
        'total_value': 10000.0,
      });
      expect(d.daysLeft, 3);
      expect(d.fieldId, 'f-1');
    });
  });

  group('POST /v1/games/runs/{id}/trade', () {
    test('a queued SELL parses as a sell, never a buy', () {
      final r = GameTradeResult.fromJson({
        'queued': true,
        'filled': false,
        'fee': null,
        'next_open_at': '2026-08-10T13:30:00+00:00',
        'ticker': 'AAPL',
        'side': 'sell',
        'quantity': 5.0,
        'price': null,
      });
      expect(r.side, 'sell');
      expect(r.ticker, 'AAPL');
      expect(r.isQueued, isTrue);
    });

    test('a filled SELL parses as a sell with its price', () {
      final r = GameTradeResult.fromJson({
        'queued': false,
        'filled': true,
        'fee': 1.0,
        'ticker': 'AAPL',
        'side': 'sell',
        'quantity': 5.0,
        'price': 190.5,
        'trade': {'ticker': 'AAPL', 'side': 'sell', 'entry_price': 190.5},
      });
      expect(r.side, 'sell');
      expect(r.price, 190.5);
      expect(r.shares, 5.0);
    });

    test('an older nested-only fill still reads side and price from `trade`',
        () {
      final r = GameTradeResult.fromJson({
        'queued': false,
        'filled': true,
        'trade': {'ticker': 'AAPL', 'side': 'sell', 'entry_price': 190.5},
      });
      expect(r.side, 'sell');
      expect(r.ticker, 'AAPL');
      expect(r.price, 190.5);
    });

    test('a payload with no side is NOT a buy', () {
      final r = GameTradeResult.fromJson({'queued': true, 'filled': false});
      expect(r.side, isNot('buy'));
    });
  });

  group('POST /v1/games/runs/{id}/restart', () {
    test('committed is read from the wire in both halves', () {
      expect(
        GameRestartPreview.fromJson({
          'run_id': 'r-1',
          'committed': true,
          'state': 'forfeit',
          'career_points_debit': 5,
        }).committed,
        isTrue,
      );
      expect(
        GameRestartPreview.fromJson({
          'run_id': 'r-1',
          'committed': false,
          'career_points_debit': 5,
        }).committed,
        isFalse,
      );
    });

    test('confirm:true is sent as the `commit` query parameter the route reads',
        () async {
      final adapter = _Adapter({
        'run_id': 'r-1',
        'committed': true,
        'career_points_debit': 5,
      });
      final api =
          ApiClient(baseUrl: 'http://test.invalid', dioAdapter: adapter);
      final r = await api.gamesRestart(runId: 'r-1', confirm: true);
      expect(adapter.last!.queryParameters['commit'], isTrue,
          reason: 'a JSON body `confirm` is ignored by the route, so every '
              'call previewed and no forfeit ever happened');
      expect(r.committed, isTrue);
    });
  });

  group('GET /v1/games/runs/{id}/close', () {
    test('near-miss line appears only when both numbers are sent', () {
      final withBoth = GameCloseResult.fromJson({
        'run_id': 'r-1',
        'field_id': 'f-1',
        'cadence': 'week',
        'near_miss_label': '2nd',
        'near_miss_gap_pct': 0.3,
      });
      expect(withBoth.hasNearMiss, isTrue);
      expect(withBoth.nearMissLabel, '2nd');

      final none = GameCloseResult.fromJson({
        'run_id': 'r-1',
        'field_id': 'f-1',
        'cadence': 'week',
        'near_miss_label': null,
        'near_miss_gap_pct': null,
      });
      expect(none.hasNearMiss, isFalse);
    });
  });
}
