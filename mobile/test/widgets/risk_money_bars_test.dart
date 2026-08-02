// CR136 M09 — bar geometry + the three Rev 4 edge cases.

import 'package:ami_trade/theme/ami_theme.dart';
import 'package:ami_trade/widgets/portfolio_health/risk_money_bars.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

const _rows = <RiskMoneyRow>[
  (ticker: 'NVDA', risk: 0.412, money: 0.30),
  (ticker: 'AAPL', risk: 0.281, money: 0.25),
  (ticker: 'MSFT', risk: 0.190, money: 0.20),
];

Widget _host(Widget child) => MaterialApp(
      home: Scaffold(
        body: SizedBox(width: 300, child: child),
      ),
    );

void main() {
  group('geometry', () {
    test('all-positive shares sit on a [0, 1] axis with the origin at 0', () {
      final g = RiskMoneyBarGeometry.fromRows(_rows);
      expect(g.axisMin, 0.0);
      expect(g.axisMax, 1.0);
      expect(g.originX, 0.0);
      expect(g.hasNegativeGutter, isFalse);
      expect(g.widthOf(0.412), closeTo(0.412, 1e-12));
      expect(g.leftOf(0.412), 0.0);
    });

    test('widths stay proportional to the shares', () {
      final g = RiskMoneyBarGeometry.fromRows(_rows);
      expect(g.widthOf(0.412) / g.widthOf(0.190), closeTo(0.412 / 0.190, 1e-9));
    });

    test('a negative risk share opens a gutter and draws leftward', () {
      const rows = <RiskMoneyRow>[
        (ticker: 'NVDA', risk: 0.502, money: 0.30),
        (ticker: 'TLT', risk: -0.0704, money: 0.20),
      ];
      final g = RiskMoneyBarGeometry.fromRows(rows);
      expect(g.axisMin, closeTo(-0.0704, 1e-12));
      expect(g.axisMax, 1.0);
      expect(g.hasNegativeGutter, isTrue);
      expect(g.originX, closeTo(0.0704 / 1.0704, 1e-9));
      expect(g.leftOf(-0.0704), lessThan(g.originX),
          reason: 'a diversifier subtracts risk — its bar starts left of zero');
      expect(g.leftOf(-0.0704), closeTo(0.0, 1e-12));
      expect(g.widthOf(-0.0704), closeTo(0.0704 / 1.0704, 1e-9));
    });

    test('a share above 100% extends the axis rather than clamping the bar',
        () {
      const rows = <RiskMoneyRow>[
        (ticker: 'NVDA', risk: 1.269, money: 0.42),
      ];
      final g = RiskMoneyBarGeometry.fromRows(rows);
      expect(g.axisMax, closeTo(1.269, 1e-12));
      expect(g.widthOf(1.269), closeTo(1.0, 1e-9),
          reason: 'the longest bar fills the track; clamping it to 100% would '
              'draw a number that was never measured');
      expect(g.widthOf(0.42), closeTo(0.42 / 1.269, 1e-9));
    });

    test('a large money share also extends the axis', () {
      const rows = <RiskMoneyRow>[
        (ticker: 'NVDA', risk: 0.40, money: 1.12),
      ];
      expect(RiskMoneyBarGeometry.fromRows(rows).axisMax, closeTo(1.12, 1e-12));
    });
  });

  group('topRiskMoneyRows', () {
    test('takes the top three by risk share, descending', () {
      final rows = topRiskMoneyRows(const [
        {'ticker': 'KO', 'invested_weight': 0.25, 'risk_share': 0.117},
        {'ticker': 'NVDA', 'invested_weight': 0.30, 'risk_share': 0.412},
        {'ticker': 'MSFT', 'invested_weight': 0.20, 'risk_share': 0.190},
        {'ticker': 'AAPL', 'invested_weight': 0.25, 'risk_share': 0.281},
      ]);
      expect(rows.map((r) => r.ticker), ['NVDA', 'AAPL', 'MSFT']);
    });

    test('a malformed or absent per_holding list yields no rows', () {
      expect(topRiskMoneyRows(null), isEmpty);
      expect(topRiskMoneyRows('nonsense'), isEmpty);
      expect(topRiskMoneyRows(const [
        {'ticker': 'NVDA'},
        {'risk_share': 0.4, 'invested_weight': 0.3},
      ]), isEmpty);
    });
  });

  group('rendering', () {
    testWidgets('both bars of a row share one origin and one scale',
        (tester) async {
      await tester.pumpWidget(_host(RiskMoneyBars(
        rows: const [(ticker: 'NVDA', risk: 0.40, money: 0.20)],
        legend: const SizedBox.shrink(),
        axisMaxLabelStyle: AmiTypography.caption,
      )));

      final bars = find.descendant(
        of: find.byType(RiskMoneyBars),
        matching: find.byType(ClipRRect),
      );
      expect(bars, findsNWidgets(2));
      final risk = tester.getRect(bars.at(0));
      final money = tester.getRect(bars.at(1));

      // Measured off the real RenderBoxes, not off the geometry object — the
      // point of the test is that the widget uses one axis, so re-deriving the
      // expected numbers from that same object would prove nothing.
      expect(risk.left, closeTo(money.left, 0.5),
          reason: 'both bars start at the shared origin');
      // 300pt track: 40% → 120pt solid, 20% → 60pt outlined.
      expect(risk.width, closeTo(120.0, 0.5));
      expect(money.width, closeTo(60.0, 0.5));
    });

    testWidgets('with a negative share, both bars still share the origin',
        (tester) async {
      await tester.pumpWidget(_host(RiskMoneyBars(
        rows: const [(ticker: 'TLT', risk: -0.0704, money: 0.20)],
        legend: const SizedBox.shrink(),
        axisMaxLabelStyle: AmiTypography.caption,
      )));

      final bars = find.descendant(
        of: find.byType(RiskMoneyBars),
        matching: find.byType(ClipRRect),
      );
      final risk = tester.getRect(bars.at(0));
      final money = tester.getRect(bars.at(1));
      final track = tester.getRect(find.byType(RiskMoneyBars));
      // axisMin = -0.0704, axisMax = 1.0, span = 1.0704 → origin at 6.58%.
      final originX = track.left + 300.0 * (0.0704 / 1.0704);

      expect(risk.right, closeTo(originX, 0.5),
          reason: 'a negative bar ends at the origin and grows leftward');
      expect(money.left, closeTo(originX, 0.5),
          reason: 'the positive bar starts at that same origin');
      expect(risk.width, closeTo(300.0 * 0.0704 / 1.0704, 0.5));
    });

    testWidgets('the labelled mark carries both shares as text',
        (tester) async {
      await tester.pumpWidget(_host(RiskMoneyBars(
        rows: _rows,
        legend: const SizedBox.shrink(),
        axisMaxLabelStyle: AmiTypography.caption,
      )));
      expect(find.textContaining('41% / 30%'), findsOneWidget);
      expect(find.text('NVDA'), findsOneWidget);
    });

    testWidgets('painted bars are excluded from semantics', (tester) async {
      await tester.pumpWidget(_host(RiskMoneyBars(
        rows: _rows,
        legend: const SizedBox.shrink(),
        axisMaxLabelStyle: AmiTypography.caption,
      )));
      expect(
        find.descendant(
          of: find.byType(RiskMoneyBars),
          matching: find.byType(ExcludeSemantics),
        ),
        findsNWidgets(_rows.length),
        reason: 'a screen reader cannot read a rectangle; the numbers beside '
            'it are the accessibility surface',
      );
    });

    testWidgets('the axis end label states the real maximum', (tester) async {
      await tester.pumpWidget(_host(RiskMoneyBars(
        rows: const [(ticker: 'NVDA', risk: 1.269, money: 0.42)],
        legend: const SizedBox.shrink(),
        axisMaxLabelStyle: AmiTypography.caption,
      )));
      // The axis label alone, not the row's "127% / 42%" mark — the point is
      // that the track states its own maximum.
      expect(find.text('\u2066127%\u2069'), findsOneWidget);
    });

    testWidgets('the axis does not mirror under RTL', (tester) async {
      await tester.pumpWidget(MaterialApp(
        home: Directionality(
          textDirection: TextDirection.rtl,
          child: Scaffold(
            body: SizedBox(
              width: 300,
              child: RiskMoneyBars(
                rows: _rows,
                legend: const SizedBox.shrink(),
                axisMaxLabelStyle: AmiTypography.caption,
              ),
            ),
          ),
        ),
      ));

      final inner = tester.widget<Directionality>(
        find.descendant(
          of: find.byType(RiskMoneyBars),
          matching: find.byType(Directionality),
        ),
      );
      expect(inner.textDirection, TextDirection.ltr,
          reason: 'a magnitude axis is not a reading order');
    });
  });
}
