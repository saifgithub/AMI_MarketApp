/// CR172 — the re-price sheet, and the four states it must keep apart.
///
/// The one that matters most is `no confirm button exists when the structure
/// could not be priced`. This sheet is the last screen before money moves, and
/// its whole reason for existing is that the user consents to a figure they
/// have seen. A confirm button on a state with no fresh figure would invert
/// that: it would take the user's yes for a price nobody checked, which is the
/// DEF305 shape the step was built to prevent.
///
/// The second is `an unknown baseline draws no row`. A drift table with rows
/// reading `$0.00 → $0.00` says *nothing moved*. That is a claim, and when the
/// baseline was never supplied it is a false one (DEF059).
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/option_proposal.dart';
import 'package:ami_trade/models/option_reprice.dart';
import 'package:ami_trade/widgets/sim/option_reprice_sheet.dart';
import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:flutter_test/flutter_test.dart';

OptionProposal _structure() => OptionProposal.fromJson({
      'strategy_name': 'long_call',
      'contracts': 1,
      'expiry': '2026-10-07',
      'days_to_expiry': 45,
      'underlying': 'AAPL',
      'legs': [
        {
          'right': 'call',
          'strike': 195.0,
          'quantity': 1.0,
          'premium': 9.1,
          'multiplier': 100.0,
          'expiry': '2026-10-07',
        },
      ],
      'metrics': {
        'net_cost': 910.0,
        'max_loss': 910.0,
        'max_gain': null,
        'unbounded_loss': false,
        'unbounded_gain': true,
        'break_evens': [204.1],
        'collateral_required': null,
        'has_uncovered_short_call': false,
        'shares_locked': 0.0,
        'covered_by_shares': false,
      },
      'compliance': {'passed': true},
      'spot': 195.42,
      'priced_at': '2026-08-23T02:14:07Z',
    });

Future<void> _pump(WidgetTester tester, OptionRepriceResult result) async {
  await tester.pumpWidget(MaterialApp(
    localizationsDelegates: const [
      AppLocalizations.delegate,
      GlobalMaterialLocalizations.delegate,
      GlobalWidgetsLocalizations.delegate,
    ],
    supportedLocales: AppLocalizations.supportedLocales,
    home: Scaffold(
      body: OptionRepriceSheet(result: result, ticker: 'AAPL'),
    ),
  ));
  await tester.pumpAndSettle();
}

void main() {
  testWidgets('a priced, unchanged structure confirms rather than hides the step',
      (tester) async {
    await _pump(
      tester,
      OptionRepriceResult(
        repriced: true,
        compliance: const OptionProposalCompliance(passed: true),
        structure: _structure(),
        drift: const OptionPriceDrift(netCostNow: 910.0, spotNow: 195.42),
      ),
    );
    expect(find.text('PRICE CONFIRMED'), findsOneWidget);
    expect(find.text('THE PRICE MOVED'), findsNothing);
    expect(find.text('OPEN AT THIS PRICE'), findsOneWidget);
  });

  testWidgets('a move is headed as one and shows then beside now',
      (tester) async {
    await _pump(
      tester,
      OptionRepriceResult(
        repriced: true,
        compliance: const OptionProposalCompliance(passed: true),
        structure: _structure(),
        drift: const OptionPriceDrift(
          netCostNow: 910.0,
          netCostThen: 860.0,
          netCostChange: 50.0,
          netCostChangePct: 5.81,
          spotThen: 194.0,
          spotNow: 195.42,
          spotChange: 1.42,
          maxLossThen: 860.0,
          maxLossNow: 910.0,
        ),
      ),
    );
    expect(find.text('THE PRICE MOVED'), findsOneWidget);
    expect(find.text('WHEN AMI PROPOSED'), findsOneWidget);
    expect(find.text('\$860.00'), findsWidgets);
    expect(find.text('\$910.00'), findsWidgets);
    expect(find.text('+\$50.00'), findsOneWidget);
    expect(find.text('OPEN AT THIS PRICE'), findsOneWidget);
  });

  testWidgets('an unknown baseline draws no row rather than a row of zeroes',
      (tester) async {
    await _pump(
      tester,
      OptionRepriceResult(
        repriced: true,
        compliance: const OptionProposalCompliance(passed: true),
        structure: _structure(),
        // Everything "then" absent — the server could not state a baseline.
        drift: const OptionPriceDrift(netCostNow: 910.0, spotNow: 195.42),
      ),
    );
    expect(find.text('WHEN AMI PROPOSED'), findsNothing);
    expect(find.text('\$0.00'), findsNothing);
    // The step still happened and still says so.
    expect(find.text('PRICE CONFIRMED'), findsOneWidget);
  });

  testWidgets('a structure that could not be priced offers no confirm at all',
      (tester) async {
    await _pump(
      tester,
      const OptionRepriceResult(
        repriced: false,
        compliance: OptionProposalCompliance(
          passed: false,
          notEvaluated: ['call 195 cannot be transacted right now (no_bid)'],
        ),
      ),
    );
    expect(find.text('AMI CANNOT PRICE THIS RIGHT NOW'), findsOneWidget);
    expect(find.text('OPEN AT THIS PRICE'), findsNothing);
    // The server's own sentence, verbatim — an error state is never an empty
    // state (CR040), and a blank panel teaches that refusals are noise.
    expect(
      find.text('call 195 cannot be transacted right now (no_bid)'),
      findsOneWidget,
    );
  });

  testWidgets('a floor refusal is headed differently from a pricing failure',
      (tester) async {
    // Two different sentences: "we cannot price this" is about the chain,
    // "you may not open this" is about the mandate. Collapsing them would
    // teach the user that a refusal is a glitch.
    await _pump(
      tester,
      OptionRepriceResult(
        repriced: true,
        compliance: const OptionProposalCompliance(
          passed: false,
          violations: ['the move has taken this past your single-name cap'],
        ),
        structure: _structure(),
      ),
    );
    expect(find.text('THE FLOOR NOW REFUSES THIS'), findsOneWidget);
    expect(find.text('AMI CANNOT PRICE THIS RIGHT NOW'), findsNothing);
    expect(find.text('OPEN AT THIS PRICE'), findsNothing);
    expect(
      find.text('the move has taken this past your single-name cap'),
      findsOneWidget,
    );
  });

  testWidgets('the age of the price is stated when the server knew it',
      (tester) async {
    await _pump(
      tester,
      OptionRepriceResult(
        repriced: true,
        compliance: const OptionProposalCompliance(passed: true),
        structure: _structure(),
        drift: const OptionPriceDrift(
          netCostNow: 910.0,
          netCostThen: 860.0,
          netCostChange: 50.0,
          agedSeconds: 245.0,
        ),
      ),
    );
    expect(find.textContaining('4 minutes'), findsOneWidget);
  });
}
