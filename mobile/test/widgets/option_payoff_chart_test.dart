/// CR172 §12 — the payoff diagram, and the one thing it must never do.
///
/// `it draws nothing when the server sent no curve` is the load-bearing test.
/// The alternative — an axis with no line, or worse, a curve this widget
/// derived itself — is a chart that failed rendered as a chart that is empty
/// (CR040), and on this surface the picture is what the user actually reads.
///
/// `payoffAt` is exact between vertices, and that is a fact about options
/// rather than a tolerance: a structure's expiry payoff IS piecewise-linear
/// with kinks only at the strikes, so interpolating between two server
/// vertices is the function, not an approximation of it.
library;

import 'package:ami_trade/models/option_proposal.dart';
import 'package:ami_trade/widgets/sim/option_payoff_chart.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

// A bull call spread 195/205: −490 below 195, +510 above 205.
const _spread = <({double price, double pnl})>[
  (price: 0.0, pnl: -490.0),
  (price: 195.0, pnl: -490.0),
  (price: 205.0, pnl: 510.0),
  (price: 307.5, pnl: 510.0),
];

// A long call at 195 for 9.10 — terminal segment SLOPES, unlike the spread.
const _longCall = <({double price, double pnl})>[
  (price: 0.0, pnl: -910.0),
  (price: 195.0, pnl: -910.0),
  (price: 292.5, pnl: 8840.0),
];

void main() {
  group('interpolation', () {
    test('a vertex returns its own value', () {
      expect(payoffAt(_spread, 195.0), -490.0);
      expect(payoffAt(_spread, 205.0), 510.0);
    });

    test('between vertices it is exactly linear', () {
      // Halfway up the spread's ramp: −490 → +510 over 195 → 205, so 200 is
      // exactly the midpoint, +10.
      expect(payoffAt(_spread, 200.0), closeTo(10.0, 1e-9));
      // And a quarter of the way.
      expect(payoffAt(_spread, 197.5), closeTo(-240.0, 1e-9));
    });

    test('outside the curve it clamps rather than extrapolating', () {
      // Tested on the LONG CALL, not the spread: a spread's terminal segments
      // are flat, so clamping and extrapolating return the same number and the
      // assertion would hold under either. An uncapped structure is the only
      // fixture where the two behaviours differ — extrapolating past 292.5
      // would keep climbing past 8840, inventing profit beyond the data the
      // server actually sent.
      expect(payoffAt(_longCall, 10000.0), 8840.0);
      expect(payoffAt(_longCall, 400.0), 8840.0);
      // The low side likewise: the long call's first segment is flat, so the
      // spread's is used here only to pin the floor.
      expect(payoffAt(_spread, -5.0), -490.0);
    });

    test('clamping holds on BOTH ends of a sloped curve', () {
      // A synthetic curve sloped at both ends, so neither clamp can pass by
      // coincidence of a flat segment.
      const sloped = <({double price, double pnl})>[
        (price: 100.0, pnl: -200.0),
        (price: 150.0, pnl: 0.0),
        (price: 200.0, pnl: 400.0),
      ];
      expect(payoffAt(sloped, 50.0), -200.0);
      expect(payoffAt(sloped, 1000.0), 400.0);
      // And it still interpolates correctly in between.
      expect(payoffAt(sloped, 175.0), closeTo(200.0, 1e-9));
    });

    test('an empty curve has no answer, rather than a zero', () {
      expect(payoffAt(const [], 195.0), isNull);
    });

    test('the loss floor is the max loss, at every price below the strike', () {
      for (final p in [0.0, 50.0, 150.0, 194.99]) {
        expect(payoffAt(_spread, p), -490.0, reason: 'at $p');
      }
    });
  });

  group('the widget', () {
    Future<void> pump(WidgetTester tester,
        List<({double price, double pnl})> curve) async {
      await tester.pumpWidget(MaterialApp(
        home: Scaffold(
          body: OptionPayoffChart(curve: curve, spot: 195.42,
              breakEvens: const [199.9]),
        ),
      ));
      await tester.pumpAndSettle();
    }

    // Asserted on the chart's own rendered SIZE rather than on the presence
    // of a CustomPaint: Scaffold and Material each build CustomPaints of their
    // own, so `findsNothing` on that type passes for reasons unrelated to this
    // widget — a green test proving nothing.
    testWidgets('it occupies no space when the server sent no curve',
        (tester) async {
      await pump(tester, const []);
      expect(tester.getSize(find.byType(OptionPayoffChart)), Size.zero);
    });

    testWidgets('a single vertex is not a curve and draws nothing',
        (tester) async {
      await pump(tester, const [(price: 195.0, pnl: -490.0)]);
      expect(tester.getSize(find.byType(OptionPayoffChart)), Size.zero);
    });

    testWidgets('a real curve takes its declared height', (tester) async {
      await pump(tester, _spread);
      expect(tester.getSize(find.byType(OptionPayoffChart)).height, 160);
    });
  });

  group('the model', () {
    test('the curve is parsed from the wire as vertices', () {
      final p = OptionProposal.fromJson({
        'strategy_name': 'bull_call_spread',
        'underlying': 'AAPL',
        'legs': const [],
        'compliance': {'passed': true},
        'payoff_curve': [
          [0.0, -490.0],
          [195.0, -490.0],
          [205.0, 510.0],
        ],
      });
      expect(p.payoffCurve.length, 3);
      expect(p.payoffCurve.first.price, 0.0);
      expect(p.payoffCurve.last.pnl, 510.0);
    });

    test('a malformed point is skipped, never coerced to zero', () {
      // A (price, pnl) pair this client could not read must not become
      // (0, 0) — that is a vertex the structure does not have, and it would
      // bend the drawn curve through the origin.
      final p = OptionProposal.fromJson({
        'strategy_name': 'long_call',
        'underlying': 'AAPL',
        'legs': const [],
        'compliance': {'passed': true},
        'payoff_curve': [
          [0.0, -910.0],
          ['nonsense', 5.0],
          [195.0],
          [292.5, 8840.0],
        ],
      });
      expect(p.payoffCurve.length, 2);
      expect(p.payoffCurve.map((e) => e.price), [0.0, 292.5]);
    });

    test('an absent curve is empty, not null', () {
      final p = OptionProposal.fromJson({
        'strategy_name': 'long_call',
        'underlying': 'AAPL',
        'legs': const [],
        'compliance': {'passed': true},
      });
      expect(p.payoffCurve, isEmpty);
    });
  });
}
