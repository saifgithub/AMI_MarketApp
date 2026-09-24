/// CR234 — the Alpaca-linked account card, rendered from the SAME
/// `ValueCard` shell AMI's own TOTAL VALUE card uses.
///
/// Saiful, from a TestFlight screenshot: the Alpaca account card's BUYING
/// PWR value wrapped onto two lines ("$362,137.5" / "7") — a value AMI's
/// own card, built with `Flexible`+`ellipsis` throughout, never allows.
/// *"The alpaca section needs to be done along the same design as the
/// rest, but with a clear indicator for alpaca paper."*
///
/// The headline (Alpaca's own portfolio value) is wrapped in a `FittedBox`
/// here — unlike AMI's card, which never needed one pre-CR234 — because a
/// fresh Alpaca paper account routinely starts at six figures and this is
/// the exact value that used to overflow.
library;

import 'package:ami_trade/models/alpaca.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:ami_trade/widgets/alpaca/alpaca_badge.dart';
import 'package:ami_trade/widgets/sim/value_card.dart';
import 'package:flutter/material.dart';
import 'package:intl/intl.dart';

class AlpacaAccountCard extends StatelessWidget {
  const AlpacaAccountCard({super.key, required this.portfolio});
  final AlpacaPortfolio portfolio;

  @override
  Widget build(BuildContext context) {
    final fmt = NumberFormat.currency(symbol: r'$', decimalDigits: 2);
    return ValueCard(
      title: kAlpacaPaperLabel,
      titleColor: alpacaAccent,
      trailing: const AlpacaBadge(dot: true),
      headline: FittedBox(
        fit: BoxFit.scaleDown,
        alignment: AlignmentDirectional.centerStart,
        child: Text(fmt.format(portfolio.portfolioValue),
            maxLines: 1,
            style: AmiTypography.statBig.copyWith(color: AmiColors.textHigh)),
      ),
      statsLayout: ValueCardStatsLayout.columns,
      stats: [
        ValueCardStat(label: 'CASH', value: fmt.format(portfolio.cash)),
        ValueCardStat(
            label: 'PORTFOLIO', value: fmt.format(portfolio.portfolioValue)),
        ValueCardStat(
            label: 'BUYING PWR', value: fmt.format(portfolio.buyingPower)),
      ],
    );
  }
}
