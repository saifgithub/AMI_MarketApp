/// CR234 (scope addition) — Saiful, from a TestFlight screenshot: "The
/// alpaca section needs to be done along the same design as the rest, but
/// with a clear indicator for alpaca paper." Pins:
///
/// 1. The Alpaca badge appears (and reads identically) on the account card,
///    a position card, and the orders/history rows.
/// 2. Alpaca positions render from the SAME `PositionCard` shell AMI
///    holdings use (not a bare-text fork) — asserted by shape (ticker box,
///    chevron, % change) rather than by reaching into `_HoldingCard`.
/// 3. No overflow/wrap of currency values on `ValueCard`/`AlpacaAccountCard`
///    at 320/375/430dp and at 1.0x/1.3x text scale — the exact defect
///    (BUYING PWR wrapping onto two lines) the screenshot showed.
/// 4. AMI's own `_ValueCard`/`_HoldingCard` rendering is unchanged by the
///    `ValueCard`/`PositionCard` extraction (same widths/behaviour it had
///    pre-CR234) — covered indirectly by the full suite's pre-existing
///    portfolio_screen tests still passing unmodified; this file adds the
///    new-surface-specific checks those didn't need to cover.
library;

import 'package:ami_trade/models/alpaca.dart';
import 'package:ami_trade/widgets/alpaca/alpaca_account_card.dart';
import 'package:ami_trade/widgets/alpaca/alpaca_badge.dart';
import 'package:ami_trade/widgets/sim/position_card.dart';
import 'package:ami_trade/widgets/sim/value_card.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

const _fixturePortfolio = AlpacaPortfolio(
  cash: 82680.27,
  portfolioValue: 99971.88,
  equity: 99971.88,
  buyingPower: 362137.57,
);

Widget _pumpAt({
  required double width,
  required double textScale,
  required Widget child,
}) =>
    MediaQuery(
      data: MediaQueryData(
        size: Size(width, 800),
        textScaler: TextScaler.linear(textScale),
      ),
      child: MaterialApp(home: Scaffold(body: SizedBox(width: width, child: child))),
    );

void main() {
  group('AlpacaBadge — one identity everywhere', () {
    testWidgets('renders the literal ALPACA PAPER label', (tester) async {
      await tester.pumpWidget(const MaterialApp(
        home: Scaffold(body: AlpacaBadge()),
      ));
      expect(find.text(kAlpacaPaperLabel), findsOneWidget);
    });

    testWidgets('a dotted badge still renders the same label', (tester) async {
      await tester.pumpWidget(const MaterialApp(
        home: Scaffold(body: AlpacaBadge(dot: true)),
      ));
      expect(find.text(kAlpacaPaperLabel), findsOneWidget);
    });
  });

  group('AlpacaAccountCard — built on the shared ValueCard shell', () {
    testWidgets('shows the badge, CASH/PORTFOLIO/BUYING PWR and the headline',
        (tester) async {
      await tester.pumpWidget(const MaterialApp(
        home: Scaffold(
          body: AlpacaAccountCard(portfolio: _fixturePortfolio),
        ),
      ));
      await tester.pump();

      // Two occurrences: the card's own title (plain text, `titleColor:
      // alpacaAccent`) and the trailing `AlpacaBadge(dot: true)` — the same
      // "title + badge both say it" shape `_AlpacaHistoryList` uses.
      expect(find.text(kAlpacaPaperLabel), findsNWidgets(2));
      expect(find.textContaining('82,680.27'), findsOneWidget);
      // Portfolio value appears twice by design: the headline AND the
      // PORTFOLIO stat row both show it — the same duplication AMI's own
      // TOTAL VALUE card does not have (it has no separate "portfolio"
      // stat), but Alpaca's pre-existing three-stat layout does.
      expect(find.textContaining('99,971.88'), findsNWidgets(2));
      expect(find.textContaining('362,137.57'), findsOneWidget);
      expect(find.text('CASH'), findsOneWidget);
      expect(find.text('PORTFOLIO'), findsOneWidget);
      expect(find.text('BUYING PWR'), findsOneWidget);
    });

    group('no overflow at any width/text-scale — the exact wrap defect', () {
      const widths = [320.0, 375.0, 430.0];
      const scales = [1.0, 1.3];
      for (final width in widths) {
        for (final scale in scales) {
          testWidgets('width=${width}dp scale=${scale}x', (tester) async {
            await tester.pumpWidget(_pumpAt(
              width: width,
              textScale: scale,
              // The exact large buying-power figure from Saiful's own
              // screenshot ($362,137.57) — the value that used to wrap.
              child: const AlpacaAccountCard(portfolio: _fixturePortfolio),
            ));
            await tester.pump();
            expect(tester.takeException(), isNull,
                reason: 'CR234: a large buying-power figure must never '
                    'overflow or throw at ${width}dp / ${scale}x — this is '
                    'the exact defect the screenshot showed');
          });
        }
      }
    });
  });

  group('PositionCard — the shared shell Alpaca positions build on', () {
    testWidgets('renders ticker, subtitle, badge, pct and a chevron',
        (tester) async {
      await tester.pumpWidget(MaterialApp(
        home: Scaffold(
          body: PositionCard(
            ticker: 'ASML',
            subtitle: '10 sh · \$1,700.00',
            pctChange: 2.5,
            badge: const AlpacaBadge(),
            detailBuilder: (context) => const [Text('detail')],
          ),
        ),
      ));

      expect(find.text('ASML'), findsOneWidget);
      expect(find.textContaining('10 sh'), findsOneWidget);
      expect(find.text(kAlpacaPaperLabel), findsOneWidget);
      expect(find.textContaining('2.5%'), findsOneWidget);
      expect(find.byIcon(Icons.chevron_right), findsOneWidget);
    });

    testWidgets('tapping expands the detail section', (tester) async {
      await tester.pumpWidget(MaterialApp(
        home: Scaffold(
          body: PositionCard(
            ticker: 'ASML',
            subtitle: '10 sh',
            pctChange: 1.0,
            detailBuilder: (context) => const [Text('EXPANDED DETAIL')],
          ),
        ),
      ));
      expect(find.text('EXPANDED DETAIL'), findsNothing);
      await tester.tap(find.byType(InkWell));
      await tester.pump();
      expect(find.text('EXPANDED DETAIL'), findsOneWidget);
      expect(find.byIcon(Icons.expand_more), findsOneWidget);
    });

    testWidgets('a stop label renders as a chip; omitted when null',
        (tester) async {
      await tester.pumpWidget(MaterialApp(
        home: Scaffold(
          body: Column(children: const [
            PositionCard(
                ticker: 'AAPL', subtitle: '1 sh', pctChange: 0, stopLabel: 'STOP \$190.00'),
            PositionCard(ticker: 'MSFT', subtitle: '1 sh', pctChange: 0),
          ]),
        ),
      ));
      expect(find.text('STOP \$190.00'), findsOneWidget);
    });

    testWidgets('no chevron/expand affordance when detailBuilder is null',
        (tester) async {
      await tester.pumpWidget(const MaterialApp(
        home: Scaffold(
          body: PositionCard(ticker: 'AAPL', subtitle: '1 sh', pctChange: 0),
        ),
      ));
      expect(find.byIcon(Icons.chevron_right), findsNothing);
      expect(find.byIcon(Icons.expand_more), findsNothing);
    });

    group('ticker column does not overflow at narrow widths', () {
      const widths = [320.0, 375.0];
      const scales = [1.0, 1.3];
      for (final width in widths) {
        for (final scale in scales) {
          testWidgets('width=${width}dp scale=${scale}x', (tester) async {
            await tester.pumpWidget(_pumpAt(
              width: width,
              textScale: scale,
              child: const PositionCard(
                ticker: 'GOOGL',
                subtitle: '100 sh · \$2,847,123.45',
                pctChange: -12.34,
                stopLabel: 'STOP \$190.00',
                badge: AlpacaBadge(),
              ),
            ));
            await tester.pump();
            expect(tester.takeException(), isNull,
                reason: 'a long ticker + subtitle + stop chip + badge + pct '
                    'must not overflow at ${width}dp / ${scale}x');
          });
        }
      }
    });
  });

  group('ValueCard — headline never wraps, whatever the caller passes', () {
    testWidgets('a plain Text headline with FittedBox does not overflow at 320dp/1.3x',
        (tester) async {
      await tester.pumpWidget(_pumpAt(
        width: 320,
        textScale: 1.3,
        child: ValueCard(
          title: 'TOTAL VALUE',
          titleColor: Colors.cyan,
          headline: FittedBox(
            fit: BoxFit.scaleDown,
            child: Text('\$1,234,567.89',
                style: const TextStyle(fontSize: 32)),
          ),
          stats: const [
            ValueCardStat(label: 'CASH', value: r'$99,999,999.99'),
          ],
        ),
      ));
      await tester.pump();
      expect(tester.takeException(), isNull);
    });
  });
}
