/// CR184 — the NOT ACTIONED card's pure data rules.
///
/// Three contracts pinned here, each one a lie the card could otherwise tell:
///
///  - **selection** ([unactionedFrom]): only `actioned == false` qualifies —
///    `null` is N/A, not false — deduped to the latest convene per ticker,
///    in chronological order and NEVER ranked by the size of the miss (the
///    CR's "selection must never be ranked by regret" acceptance).
///  - **the PASS reference price** ([conveneDayClose]): reconstructed from
///    daily candles, and **null on a mock-walk history** — a delta against a
///    fabricated close is a number that looks measured and is not (CR040).
///  - **the window** ([historyPeriodFor]): the period token must reach the
///    convene day, or the reconstruction silently measures nothing.
library;

import 'package:ami_trade/models/sim.dart';
import 'package:ami_trade/screens/floor/team_calls_data.dart';
import 'package:flutter_test/flutter_test.dart';

TeamCall _call(
  String ticker, {
  required DateTime at,
  bool? actioned,
  String action = 'APPROVE',
  double? entry,
}) =>
    TeamCall(
        ticker: ticker, action: action, at: at, entry: entry, actioned: actioned);

SimHistory _history(String source, List<SimCandle> candles) =>
    SimHistory(ticker: 'AAPL', period: '1m', source: source, candles: candles);

SimCandle _candle(DateTime day, double close) => SimCandle(
    t: day.millisecondsSinceEpoch ~/ 1000, o: close, h: close, l: close,
    c: close, v: 0);

void main() {
  final d1 = DateTime.utc(2026, 8, 10);
  final d2 = DateTime.utc(2026, 8, 12);
  final d3 = DateTime.utc(2026, 8, 14);

  group('unactionedFrom — CR184 selection', () {
    test('only actioned == false qualifies; null is N/A, never false', () {
      final out = unactionedFrom([
        _call('NVDA', at: d3, actioned: true),
        _call('AAPL', at: d2, actioned: false),
        _call('MSFT', at: d1, actioned: null),
      ]);
      expect(out.map((c) => c.ticker), ['AAPL'],
          reason: 'a verdict-less run (null) put on the card would be an '
              'entry that was never actionable shown as a missed one');
    });

    test('dedupes to the latest convene per ticker', () {
      final out = unactionedFrom([
        _call('NVDA', at: d3, actioned: false),
        _call('NVDA', at: d1, actioned: false),
        _call('AAPL', at: d2, actioned: false),
      ]);
      expect(out.map((c) => c.ticker), ['NVDA', 'AAPL']);
      expect(out.first.at, d3, reason: 'latest per ticker, not both');
    });

    test('order is chronological (input order), never regret-ranked', () {
      // The older call has the named entry a big delta could be computed
      // against; if any ranking-by-miss creeps in, it would jump the queue.
      final out = unactionedFrom([
        _call('AAPL', at: d3, actioned: false, action: 'PASS'),
        _call('NVDA', at: d2, actioned: false, entry: 100.0),
        _call('MSFT', at: d1, actioned: false, entry: 1.0),
      ]);
      expect(out.map((c) => c.ticker), ['AAPL', 'NVDA'],
          reason: 'newest two, taken in the order teamCallsFrom sorted them');
    });
  });

  group('conveneDayClose — CR184 PASS reference price', () {
    test('a mock-walk history yields NULL, never its fabricated close', () {
      final h = _history('mock_walk', [_candle(d1, 100.0)]);
      expect(conveneDayClose(history: h, at: d2), isNull,
          reason: 'CR040 — a random walk\'s close is not a price anyone '
              'could have traded at, and a delta against it looks measured');
    });

    test('an unavailable or unread history yields null', () {
      expect(
          conveneDayClose(
              history: _history('unavailable', [_candle(d1, 100.0)]), at: d2),
          isNull);
      expect(conveneDayClose(history: null, at: d2), isNull);
    });

    test('picks the last candle on or before the convene, with its own date',
        () {
      final h = _history('yfinance',
          [_candle(d1, 100.0), _candle(d2, 105.0), _candle(d3, 999.0)]);
      final ref = conveneDayClose(history: h, at: d2.add(const Duration(hours: 14)));
      expect(ref, isNotNull);
      expect(ref!.close, 105.0);
      expect(ref.date, d2,
          reason: 'the disclosure says which day\'s close was measured');
    });

    test('no candle before the convene yields null, not the nearest after',
        () {
      final h = _history('yfinance', [_candle(d3, 999.0)]);
      expect(conveneDayClose(history: h, at: d2), isNull);
    });
  });

  group('historyPeriodFor — the window must reach the convene', () {
    test('grows with the age of the call', () {
      final now = DateTime.utc(2026, 8, 20);
      expect(
          historyPeriodFor(at: now.subtract(const Duration(days: 2)), now: now),
          '1w');
      expect(
          historyPeriodFor(at: now.subtract(const Duration(days: 20)), now: now),
          '1m');
      expect(
          historyPeriodFor(at: now.subtract(const Duration(days: 60)), now: now),
          '3m');
      expect(
          historyPeriodFor(at: now.subtract(const Duration(days: 200)), now: now),
          '1y');
      expect(
          historyPeriodFor(at: now.subtract(const Duration(days: 400)), now: now),
          '5y');
    });
  });
}
