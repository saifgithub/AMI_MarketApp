/// Single-row renderer for a sim trade — status pill + side/qty/ticker line
/// + stop/target/closed-price subline + close action.
///
/// Shared between the Portfolio screen (full trade list) and the Holding
/// Detail screen (filtered to one ticker).
library;

import 'package:ami_trade/models/sim.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:flutter/material.dart';
import 'package:intl/intl.dart';

class TradeRow extends StatelessWidget {
  const TradeRow({super.key, required this.trade});

  final SimTrade trade;

  Color get _accent {
    if (trade.status == 'won') return AmiColors.hexGreen;
    if (trade.status == 'lost') return AmiColors.hexRed;
    if (trade.status == 'closed') {
      return trade.realisedPnl >= 0 ? AmiColors.hexGreen : AmiColors.hexRed;
    }
    return AmiColors.hexCyan;
  }

  @override
  Widget build(BuildContext context) {
    final fmt = NumberFormat('#,##0.00');
    return Container(
      margin: const EdgeInsets.only(bottom: 6),
      padding: const EdgeInsets.all(AmiSpacing.s),
      decoration: BoxDecoration(
        color: AmiColors.slate800,
        borderRadius: BorderRadius.circular(AmiRadii.card),
        border: Border.all(color: _accent.withValues(alpha: 0.4)),
      ),
      child: Row(
        children: [
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
            decoration: BoxDecoration(
              color: _accent.withValues(alpha: 0.15),
              borderRadius: BorderRadius.circular(4),
            ),
            child: Text(trade.status.toUpperCase(),
                style: AmiTypography.labelMono.copyWith(color: _accent, fontSize: 10)),
          ),
          const SizedBox(width: AmiSpacing.s),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  '${trade.side.toUpperCase()} ${trade.quantity.toStringAsFixed(0)} ${trade.ticker} @ \$${fmt.format(trade.entryPrice)}',
                  style: AmiTypography.body,
                ),
                const SizedBox(height: 2),
                Text(
                  [
                    if (trade.stop != null) 'stop \$${fmt.format(trade.stop)}',
                    if (trade.target != null) 'target \$${fmt.format(trade.target)}',
                    if (trade.closedPrice != null)
                      'closed \$${fmt.format(trade.closedPrice)}',
                  ].join(' • '),
                  style: AmiTypography.caption,
                ),
              ],
            ),
          ),
          // CR188 slice 2 — the `x` is gone. It closed a TRADE row at market,
          // which is a second mechanic for "sell" with a different object under
          // it and no way to name a price; selling is now one control on the
          // position, reaching every order type. Removing it is also what stops
          // a close from silently orphaning a resting sell on those shares
          // (DEF311's shape, removed rather than guarded against).
          if (!trade.isOpen && trade.realisedPnl != 0)
            Text(
              '${trade.realisedPnl >= 0 ? '+' : ''}\$${fmt.format(trade.realisedPnl)}',
              style: AmiTypography.labelMono.copyWith(color: _accent),
            ),
        ],
      ),
    );
  }
}
