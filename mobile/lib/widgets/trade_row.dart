/// Single-row renderer for a sim trade — status pill + side/qty/ticker line
/// + stop/target/closed-price subline + close action.
///
/// Shared between the Portfolio screen (full trade list) and the Holding
/// Detail screen (filtered to one ticker).
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/sim.dart';
import 'package:ami_trade/state/sim_providers.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';

class TradeRow extends ConsumerWidget {
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
  Widget build(BuildContext context, WidgetRef ref) {
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
          if (trade.isOpen)
            IconButton(
              icon: const Icon(Icons.close, size: 16, color: AmiColors.textLow),
              tooltip: AppLocalizations.of(context).portfolioCloseTooltip,
              onPressed: () =>
                  ref.read(simNotifierProvider.notifier).closeTrade(trade.id),
            )
          else if (trade.realisedPnl != 0)
            Text(
              '${trade.realisedPnl >= 0 ? '+' : ''}\$${fmt.format(trade.realisedPnl)}',
              style: AmiTypography.labelMono.copyWith(color: _accent),
            ),
        ],
      ),
    );
  }
}
