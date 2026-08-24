/// CR172 §12 — the option book on the Portfolio screen.
///
/// The tests that carry the weight are the two about what must NOT appear.
///
/// `no profit or loss is shown anywhere` guards the reason this card looks
/// unlike a holding card: there is no option marks feed, so no P&L is
/// computable, and the obvious placeholder — `$0.00` — reads as *flat*. Flat is
/// a measurement. Not-measured is not. Rendering the second as the first is the
/// DEF059 shape, and on a position whose whole point is that it decays it would
/// be actively misleading.
///
/// `a spread renders as one structure, not two loose legs` guards the grouping.
/// The Room prices a structure and the user consents to a structure; showing
/// two independent rows invites acting on half a position whose risk only makes
/// sense whole.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/sim.dart';
import 'package:ami_trade/widgets/sim/option_positions_section.dart';
import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:flutter_test/flutter_test.dart';

Map<String, dynamic> _leg({
  String right = 'call',
  double strike = 195,
  double quantity = 1,
  double premium = 9.1,
  String expiry = '2026-10-07',
  int dte = 45,
  String strategyId = 's1',
  String strategyName = 'long_call',
  double collateral = 0,
}) =>
    {
      'id': 'leg-$right-$strike-$strategyId',
      'occ_symbol': 'AAPL261007C00195000',
      'underlying': 'AAPL',
      'right': right,
      'strike': strike,
      'expiry': expiry,
      'quantity': quantity,
      'avg_premium': premium,
      'multiplier': 100.0,
      'collateral_posted': collateral,
      'strategy_id': strategyId,
      'strategy_name': strategyName,
      'days_to_expiry': dte,
      'opened_at': '2026-08-23T02:14:07Z',
    };

List<SimOptionLeg> _legs(List<Map<String, dynamic>> raw) =>
    raw.map(SimOptionLeg.fromJson).toList();

Future<void> _pump(WidgetTester tester, List<SimOptionLeg> legs) async {
  final structures = SimOptionStructure.group(legs);
  await tester.pumpWidget(MaterialApp(
    localizationsDelegates: const [
      AppLocalizations.delegate,
      GlobalMaterialLocalizations.delegate,
      GlobalWidgetsLocalizations.delegate,
    ],
    supportedLocales: AppLocalizations.supportedLocales,
    home: Scaffold(
      body: ListView(
        children: [
          for (final s in structures) OptionStructureCard(structure: s),
        ],
      ),
    ),
  ));
  await tester.pumpAndSettle();
}

void main() {
  group('the model', () {
    test('groups legs by structure and keeps server order', () {
      final legs = _legs([
        _leg(strategyId: 'a', strategyName: 'long_call'),
        _leg(strategyId: 'b', strategyName: 'bull_call_spread', strike: 200),
        _leg(
            strategyId: 'b',
            strategyName: 'bull_call_spread',
            strike: 210,
            quantity: -1),
      ]);
      final groups = SimOptionStructure.group(legs);
      expect(groups.length, 2);
      expect(groups[0].strategyId, 'a');
      expect(groups[0].legs.length, 1);
      expect(groups[1].strategyId, 'b');
      expect(groups[1].legs.length, 2);
      // Leg order within the structure is the order the server sent.
      expect(groups[1].legs[0].strike, 200);
      expect(groups[1].legs[1].strike, 210);
    });

    test('a structure takes the SOONEST expiry of its legs', () {
      // A calendar spread's near leg is the one that stops existing first, so
      // it is what the countdown must describe. Taking the far leg would tell
      // a user they have 90 days when half the position expires in 7.
      final s = SimOptionStructure(
        legs: _legs([
          _leg(strategyId: 'c', expiry: '2026-11-20', dte: 90),
          _leg(strategyId: 'c', expiry: '2026-08-28', dte: 7, quantity: -1),
        ]),
      );
      expect(s.daysToExpiry, 7);
    });

    test('net cost basis nets a credit spread to a credit', () {
      final s = SimOptionStructure(
        legs: _legs([
          _leg(strategyId: 'd', strike: 200, quantity: -1, premium: 8.0),
          _leg(strategyId: 'd', strike: 210, quantity: 1, premium: 3.0),
        ]),
      );
      // −1×8×100 + 1×3×100 = −500 → a $500 credit received.
      expect(s.netCostBasis, -500.0);
    });

    test('a missing days_to_expiry does not pass for "expires today"', () {
      // The server always sends it. Absence means a backend older than CR172,
      // and 0 would render as EXPIRES TODAY — a false, urgent claim. The
      // sentinel renders as EXPIRED instead, which is visibly wrong rather
      // than plausibly wrong.
      final leg = SimOptionLeg.fromJson(_leg()..remove('days_to_expiry'));
      expect(leg.daysToExpiry, lessThan(-1));
      expect(leg.isExpired, isTrue);
    });
  });

  group('the expiry sentence', () {
    late AppLocalizations l;
    setUp(() async {
      l = await AppLocalizations.delegate.load(const Locale('en'));
    });

    test('each boundary gets its own wording', () {
      expect(optionExpirySentence(l, 45), '45 days to expiry');
      expect(optionExpirySentence(l, 2), '2 days to expiry');
      expect(optionExpirySentence(l, 1), 'EXPIRES TOMORROW');
      expect(optionExpirySentence(l, 0), 'EXPIRES TODAY');
      // Never "-3 days to expiry".
      expect(optionExpirySentence(l, -3), 'EXPIRED — AWAITING SETTLEMENT');
    });

    test('zero is not phrased as a count', () {
      // The one day the user most needs to act must not read as though
      // nothing is happening.
      expect(optionExpirySentence(l, 0), isNot(contains('0 days')));
    });
  });

  group('the card', () {
    testWidgets('shows right, strike and expiry — not qty @ avgCost',
        (tester) async {
      await _pump(tester, _legs([_leg()]));
      expect(find.text('LONG 1 CALL \$195'), findsOneWidget);
      expect(find.text('45 days to expiry'), findsOneWidget);
      expect(find.text('7 Oct 2026'), findsOneWidget);
      // The equity-holding phrasing must not appear: it computes
      // (mark − avgCost)/avgCost, which is wrong for a signed short leg.
      expect(find.textContaining('@'), findsNothing);
    });

    testWidgets('no profit or loss is shown anywhere', (tester) async {
      await _pump(tester, _legs([_leg()]));
      // Not a zero, not a percentage, not a signed figure. There is no marks
      // feed, so any of those would be manufactured.
      expect(find.textContaining('%'), findsNothing);
      expect(find.textContaining('\$0.00'), findsNothing);
      expect(find.textContaining('+\$'), findsNothing);
      expect(find.textContaining('−\$'), findsNothing);
      // What it DOES say is what it cost.
      expect(find.text('Paid \$910.00 at open'), findsOneWidget);
    });

    testWidgets('a spread renders as one structure, not two loose legs',
        (tester) async {
      await _pump(
        tester,
        _legs([
          _leg(
              strategyId: 'b',
              strategyName: 'bull_call_spread',
              strike: 200,
              premium: 8.0),
          _leg(
              strategyId: 'b',
              strategyName: 'bull_call_spread',
              strike: 210,
              premium: 3.0,
              quantity: -1),
        ]),
      );
      expect(find.byType(OptionStructureCard), findsOneWidget);
      expect(find.text('BULL CALL SPREAD'), findsOneWidget);
      expect(find.text('LONG 1 CALL \$200'), findsOneWidget);
      expect(find.text('SHORT 1 CALL \$210'), findsOneWidget);
      // One net figure for the structure, not one per leg.
      expect(find.text('Paid \$500.00 at open'), findsOneWidget);
      expect(find.textContaining('at open'), findsOneWidget);
    });

    testWidgets('a credit structure says collected, not paid', (tester) async {
      await _pump(
        tester,
        _legs([
          _leg(
              strategyId: 'd',
              strategyName: 'bear_call_spread',
              strike: 200,
              quantity: -1,
              premium: 8.0,
              collateral: 1000),
          _leg(
              strategyId: 'd',
              strategyName: 'bear_call_spread',
              strike: 210,
              premium: 3.0),
        ]),
      );
      expect(find.text('Collected \$500.00 at open'), findsOneWidget);
      expect(find.textContaining('Paid'), findsNothing);
      // Collateral is disclosed: it is not spent and not a loss, but it is
      // cash the user cannot use.
      expect(find.text('Collateral held: \$1,000.00'), findsOneWidget);
    });

    testWidgets('collateral is omitted when there is none', (tester) async {
      await _pump(tester, _legs([_leg()]));
      expect(find.textContaining('Collateral held'), findsNothing);
    });

    testWidgets('an expired-but-open leg says so instead of showing a count',
        (tester) async {
      await _pump(tester, _legs([_leg(dte: -3)]));
      expect(find.text('EXPIRED — AWAITING SETTLEMENT'), findsOneWidget);
      expect(find.textContaining('days to expiry'), findsNothing);
    });

    testWidgets('legs are dated individually only when expiries differ',
        (tester) async {
      // Vertical: one shared date, stated once below the legs.
      await _pump(
        tester,
        _legs([
          _leg(strategyId: 'v', strike: 200),
          _leg(strategyId: 'v', strike: 210, quantity: -1),
        ]),
      );
      expect(find.text('LONG 1 CALL \$200'), findsOneWidget);
      expect(find.text('7 Oct 2026'), findsOneWidget);

      // Calendar: the legs must be distinguishable from each other.
      await _pump(
        tester,
        // FAR leg deliberately first: a countdown that just reads
        // `legs.first` would print 90 here, and the near leg expires in 26.
        _legs([
          _leg(
              strategyId: 'c',
              strike: 200,
              expiry: '2026-11-20',
              dte: 90,
              quantity: -1),
          _leg(strategyId: 'c', strike: 200, expiry: '2026-09-18', dte: 26),
        ]),
      );
      expect(find.text('LONG 1 CALL \$200 · 18 Sep'), findsOneWidget);
      expect(find.text('SHORT 1 CALL \$200 · 20 Nov'), findsOneWidget);
      expect(find.textContaining('90 days'), findsNothing);
      // Countdown follows the near leg.
      expect(find.text('26 days to expiry'), findsOneWidget);
    });
  });
}
