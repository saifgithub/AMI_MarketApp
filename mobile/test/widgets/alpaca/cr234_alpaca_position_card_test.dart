/// CR234 (scope addition) — `AlpacaPositionCard`'s own logic: the stop chip
/// is read off Alpaca's own OPEN bracket orders (`alpacaOpenOrdersProvider`),
/// never invented, matching CR189's "the position's actual stop, not a
/// guess" rule already applied to AMI holdings.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/alpaca.dart';
import 'package:ami_trade/state/alpaca_providers.dart';
import 'package:ami_trade/widgets/alpaca/alpaca_badge.dart';
import 'package:ami_trade/widgets/alpaca/alpaca_position_card.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

Future<void> _pump(
  WidgetTester tester, {
  required AlpacaPosition position,
  List<AlpacaOrder> openOrders = const [],
}) async {
  await tester.pumpWidget(ProviderScope(
    overrides: [
      alpacaOpenOrdersProvider.overrideWith((ref) async => openOrders),
    ],
    child: MaterialApp(
      localizationsDelegates: AppLocalizations.localizationsDelegates,
      supportedLocales: AppLocalizations.supportedLocales,
      home: Scaffold(body: AlpacaPositionCard(position: position)),
    ),
  ));
  await tester.pump();
}

void main() {
  group('AlpacaPositionCard — the shared PositionCard shell', () {
    testWidgets('renders the ticker, badge and a % change from entry price',
        (tester) async {
      await _pump(
        tester,
        position: const AlpacaPosition(
          symbol: 'ASML',
          qty: 10,
          marketValue: 18500,
          unrealizedPl: 500,
          avgEntryPrice: 1800,
        ),
      );
      expect(find.text('ASML'), findsOneWidget);
      expect(find.text(kAlpacaPaperLabel), findsOneWidget);
      // mark = 18500/10 = 1850; pct = (1850-1800)/1800*100 ≈ +2.8%
      expect(find.textContaining('+2.8%'), findsOneWidget);
    });

    testWidgets('no avg entry price on the wire renders a neutral 0.0%, no throw',
        (tester) async {
      await _pump(
        tester,
        position: const AlpacaPosition(
          symbol: 'AAPL',
          qty: 1,
          marketValue: 150,
          unrealizedPl: 0,
        ),
      );
      expect(tester.takeException(), isNull);
      expect(find.textContaining('0.0%'), findsOneWidget);
    });

    testWidgets('a matching open bracket stop leg renders as the stop chip',
        (tester) async {
      await _pump(
        tester,
        position: const AlpacaPosition(
          symbol: 'ASML',
          qty: 10,
          marketValue: 17220,
          unrealizedPl: -28,
          avgEntryPrice: 1722.8,
        ),
        openOrders: const [
          AlpacaOrder(
            id: 'ord_parent',
            symbol: 'ASML',
            side: 'buy',
            qty: 10,
            status: 'new',
            type: 'limit',
            limitPrice: 1700.0,
            legs: [
              AlpacaOrder(
                id: 'leg_stop',
                symbol: 'ASML',
                side: 'sell',
                qty: 10,
                status: 'held',
                stopPrice: 1619.15,
              ),
            ],
          ),
        ],
      );
      expect(find.textContaining('1,619.15'), findsOneWidget);
    });

    testWidgets('no matching open order shows no stop chip', (tester) async {
      await _pump(
        tester,
        position: const AlpacaPosition(
          symbol: 'NFLX',
          qty: 1,
          marketValue: 72,
          unrealizedPl: 0,
          avgEntryPrice: 72,
        ),
        openOrders: const [
          AlpacaOrder(
            id: 'ord_other',
            symbol: 'AAPL',
            side: 'buy',
            qty: 5,
            status: 'new',
          ),
        ],
      );
      expect(find.textContaining('STOP'), findsNothing);
    });
  });
}
