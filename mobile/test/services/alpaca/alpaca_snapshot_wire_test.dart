/// CR202 — what the device uploads to the backend.
///
/// The wire shape has to match `backend/app/schemas/alpaca.py` exactly, and
/// the position cap has to match its MAX_POSITIONS: the backend rejects an
/// over-long list wholesale, so a client that sends 150 positions loses the
/// overlay entirely rather than getting a truncated one. Trimming here, to the
/// largest positions, is what keeps that from happening silently.
///
/// Also covers Alpaca's string-typed numerics — the pre-CR202 models cast
/// `as num`, which was safe only because the AMI backend had already coerced
/// them. Parsing Alpaca's own JSON directly, that cast would throw on every
/// real response.
library;

import 'package:ami_trade/models/alpaca.dart';
import 'package:flutter_test/flutter_test.dart';

AlpacaPosition _pos(String symbol, double marketValue, {double qty = 1}) =>
    AlpacaPosition(
      symbol: symbol,
      qty: qty,
      marketValue: marketValue,
      unrealizedPl: 0,
    );

void main() {
  group('parsing Alpaca JSON', () {
    test('accepts the strings Alpaca actually sends', () {
      final p = AlpacaPortfolio.fromJson(const {
        'cash': '12450.32',
        'portfolio_value': '48320.00',
        'equity': '48320.00',
        'buying_power': '24900.64',
      });
      expect(p.cash, closeTo(12450.32, 0.001));
      expect(p.portfolioValue, closeTo(48320.0, 0.001));
      expect(p.buyingPower, closeTo(24900.64, 0.001));
    });

    test('still accepts plain numbers', () {
      final p = AlpacaPortfolio.fromJson(const {
        'cash': 100,
        'portfolio_value': 200.5,
        'equity': 200.5,
        'buying_power': 50,
      });
      expect(p.cash, 100);
      expect(p.portfolioValue, 200.5);
    });

    test('a garbage or missing field reads as 0 rather than throwing', () {
      final p = AlpacaPortfolio.fromJson(const {'cash': 'n/a'});
      expect(p.cash, 0);
      expect(p.buyingPower, 0);
    });

    test('positions parse from Alpaca string quantities', () {
      final pos = AlpacaPosition.fromJson(const {
        'symbol': 'AAPL',
        'qty': '10',
        'market_value': '2150.00',
        'unrealized_pl': '-85.25',
      });
      expect(pos.symbol, 'AAPL');
      expect(pos.qty, 10);
      expect(pos.marketValue, closeTo(2150.0, 0.001));
      expect(pos.unrealizedPl, closeTo(-85.25, 0.001));
    });
  });

  group('wire shape', () {
    test('field names match the backend schema', () {
      final snap = AlpacaSnapshot(
        portfolio: const AlpacaPortfolio(
          cash: 1.0,
          portfolioValue: 2.0,
          equity: 2.0,
          buyingPower: 3.0,
        ),
        positions: [_pos('AAPL', 10)],
      );
      final json = snap.toWireJson();

      expect(json.keys.toSet(),
          {'cash', 'portfolio_value', 'buying_power', 'positions'});
      expect((json['positions'] as List).first,
          {'symbol': 'AAPL', 'qty': 1.0, 'market_value': 10.0, 'unrealized_pl': 0.0});
    });

    test('equity is not sent — the backend never rendered it', () {
      final snap = AlpacaSnapshot(
        portfolio: const AlpacaPortfolio(
          cash: 1.0, portfolioValue: 2.0, equity: 999.0, buyingPower: 3.0),
        positions: const [],
      );
      expect(snap.toWireJson().containsKey('equity'), isFalse);
    });

    test('trims to the cap, keeping the largest positions', () {
      final many = List.generate(150, (i) => _pos('AAPL', i.toDouble()));
      final snap = AlpacaSnapshot(
        portfolio: const AlpacaPortfolio(
          cash: 1.0, portfolioValue: 2.0, equity: 2.0, buyingPower: 3.0),
        positions: many,
      );
      final positions = snap.toWireJson()['positions'] as List;

      expect(positions.length, AlpacaSnapshot.maxPositions);
      expect((positions.first as Map)['market_value'], 149.0,
          reason: 'the largest position must survive the trim');
      expect((positions.last as Map)['market_value'], 50.0);
    });

    test('a short list is untouched', () {
      final snap = AlpacaSnapshot(
        portfolio: const AlpacaPortfolio(
          cash: 1.0, portfolioValue: 2.0, equity: 2.0, buyingPower: 3.0),
        positions: [_pos('AAPL', 1), _pos('MSFT', 2)],
      );
      expect((snap.toWireJson()['positions'] as List).length, 2);
    });
  });

  // DEF419-MOBILE round 2 (MAJOR-2, auditor u66) — `toMandateSnapshotJson()`
  // feeds the safety floor and had no test of its own, which is how MAJOR-1
  // (filter-before-cap ordering) shipped unguarded. Covers the
  // `AccountSnapshotIn` shape (`backend/app/schemas/alpaca.py`), the short
  // exclusion, and — the auditor's exact probe — that a short-heavy book at
  // or above the position cap no longer empties the snapshot.
  group('mandate snapshot shape (toMandateSnapshotJson)', () {
    test('field names and kind match AccountSnapshotIn', () {
      final snap = AlpacaSnapshot(
        portfolio: const AlpacaPortfolio(
          cash: 500.0, portfolioValue: 2000.0, equity: 2000.0, buyingPower: 1000.0),
        positions: [_pos('AAPL', 10)],
      );
      final json = snap.toMandateSnapshotJson();

      expect(json.keys.toSet(), {'kind', 'equity', 'cash', 'positions'});
      expect(json['kind'], 'alpaca_paper');
      expect(json['equity'], 2000.0);
      expect(json['cash'], 500.0);
      expect((json['positions'] as List).first,
          {'ticker': 'AAPL', 'qty': 1.0, 'market_value': 10.0});
    });

    test('equity IS sent — unlike toWireJson, the mandate check needs it', () {
      final snap = AlpacaSnapshot(
        portfolio: const AlpacaPortfolio(
          cash: 1.0, portfolioValue: 2.0, equity: 999.0, buyingPower: 3.0),
        positions: const [],
      );
      expect(snap.toMandateSnapshotJson()['equity'], 999.0);
    });

    test('a short position (negative qty) is dropped, not sent negative', () {
      final snap = AlpacaSnapshot(
        portfolio: const AlpacaPortfolio(
          cash: 1.0, portfolioValue: 2.0, equity: 2.0, buyingPower: 3.0),
        positions: [
          _pos('AAPL', 500, qty: 10),
          _pos('TSLA', 300, qty: -5),
        ],
      );
      final positions = snap.toMandateSnapshotJson()['positions'] as List;

      expect(positions.length, 1);
      expect((positions.single as Map)['ticker'], 'AAPL');
    });

    test('trims to the cap, keeping the largest LONG positions', () {
      final many = List.generate(150, (i) => _pos('AAPL$i', i.toDouble()));
      final snap = AlpacaSnapshot(
        portfolio: const AlpacaPortfolio(
          cash: 1.0, portfolioValue: 2.0, equity: 2.0, buyingPower: 3.0),
        positions: many,
      );
      final positions = snap.toMandateSnapshotJson()['positions'] as List;

      expect(positions.length, AlpacaSnapshot.maxPositions);
      expect((positions.first as Map)['market_value'], 149.0,
          reason: 'the largest position must survive the trim');
    });

    test(
        'filter runs before the cap: shorts at the cap boundary no longer '
        'empty the snapshot (auditor u66 round-1 probe, 100 short + 20 long)',
        () {
      final shorts = List.generate(
          100, (i) => _pos('SHORT$i', 1000.0 + i, qty: -1));
      final longs =
          List.generate(20, (i) => _pos('LONG$i', 500.0 + i, qty: 1));
      final snap = AlpacaSnapshot(
        portfolio: const AlpacaPortfolio(
          cash: 1.0, portfolioValue: 2.0, equity: 2.0, buyingPower: 3.0),
        // Shorts carry the LARGER |marketValue|, so a cap-before-filter bug
        // sorts them to the front, fills all 100 slots, and the where()
        // afterwards drops every one of them — 0 positions out.
        positions: [...shorts, ...longs],
      );
      final positions = snap.toMandateSnapshotJson()['positions'] as List;

      expect(positions.length, 20,
          reason: 'every real long position must survive; only the '
              '(higher-value) shorts are excluded');
      expect(positions.every((p) => (p as Map)['ticker'].startsWith('LONG')),
          isTrue);
    });

    test('under the cap, ordering does not matter — all longs pass through',
        () {
      final snap = AlpacaSnapshot(
        portfolio: const AlpacaPortfolio(
          cash: 1.0, portfolioValue: 2.0, equity: 2.0, buyingPower: 3.0),
        positions: [
          _pos('SHORT', 900, qty: -1),
          _pos('AAPL', 100, qty: 1),
          _pos('MSFT', 200, qty: 1),
        ],
      );
      final positions = snap.toMandateSnapshotJson()['positions'] as List;
      expect(positions.length, 2);
    });
  });
}
