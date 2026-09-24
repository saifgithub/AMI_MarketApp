/// CR234 — one Alpaca-linked position, rendered from the SAME
/// `PositionCard` shell AMI's own holdings use.
///
/// Saiful, from a TestFlight screenshot: Alpaca positions rendered as bare
/// text rows ("ASML  x10 $17,220  -$28") with no card, no chevron, no %
/// change, while AMI's positions were full cards. *"The alpaca section
/// needs to be done along the same design as the rest, but with a clear
/// indicator for alpaca paper."*
///
/// The stop chip is populated from Alpaca's own OPEN bracket orders
/// (`alpacaOpenOrdersProvider`), not invented — a position with no matching
/// resting stop-loss leg shows no chip, the same "absence is information"
/// rule `_HoldingCard` already applies to AMI's own unprotected positions.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/alpaca.dart';
import 'package:ami_trade/screens/sim/ticker_detail_screen.dart';
import 'package:ami_trade/state/alpaca_providers.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:ami_trade/widgets/alpaca/alpaca_badge.dart';
import 'package:ami_trade/widgets/sim/position_card.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';

/// Reads the position's protective stop off Alpaca's own open orders — a
/// bracket's stop-loss leg is a child order on the SAME symbol with a
/// `stop_price` set (see `AlpacaOrder.legs`), matching CR234's own
/// `_AlpacaBracketLegLine` reasoning: a stop leg carries `stop_price`, a
/// target leg carries `limit_price`, and Alpaca never sends both on one
/// bracket child.
double? _stopFor(String symbol, List<AlpacaOrder> openOrders) {
  for (final o in openOrders) {
    if (o.symbol != symbol) continue;
    for (final leg in o.legs) {
      if (leg.stopPrice != null) return leg.stopPrice;
    }
    // A stop can also be its own top-level order (not nested under a
    // bracket parent) if the user placed one directly — same symbol, a
    // stop type, still open.
    if (o.type == 'stop' && o.stopPrice != null) return o.stopPrice;
  }
  return null;
}

class AlpacaPositionCard extends ConsumerWidget {
  const AlpacaPositionCard({super.key, required this.position});
  final AlpacaPosition position;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l = AppLocalizations.of(context);
    final fmt = NumberFormat('#,##0.00');
    final entry = position.avgEntryPrice;
    final mark = entry == null || position.qty == 0
        ? null
        : (position.marketValue / position.qty);
    final pct = (entry == null || entry == 0 || mark == null)
        ? 0.0
        : ((mark - entry) / entry) * 100;

    final openOrders = ref.watch(alpacaOpenOrdersProvider).valueOrNull ?? const [];
    final stop = _stopFor(position.symbol, openOrders);

    return PositionCard(
      ticker: position.symbol,
      subtitle: entry == null
          ? '${position.qty.toStringAsFixed(position.qty == position.qty.floorToDouble() ? 0 : 2)} sh'
          : '${position.qty.toStringAsFixed(position.qty == position.qty.floorToDouble() ? 0 : 2)} sh · \$${fmt.format(entry)}',
      pctChange: pct,
      badge: const AlpacaBadge(),
      stopLabel:
          stop == null ? null : '${l.tradeTicketLabelStop} \$${fmt.format(stop)}',
      detailBuilder: (context) => _detail(context, l, fmt),
    );
  }

  List<Widget> _detail(BuildContext context, AppLocalizations l, NumberFormat fmt) {
    final pl = position.unrealizedPl;
    final plColor = pl >= 0 ? AmiColors.hexGreen : AmiColors.hexRed;
    return [
      const Padding(
        padding: EdgeInsets.symmetric(vertical: AmiSpacing.s),
        child: Divider(height: 1, color: AmiColors.slate700),
      ),
      Text(
        '\$${fmt.format(position.marketValue)} · '
        '${pl >= 0 ? '+' : ''}\$${fmt.format(pl)}',
        style: AmiTypography.labelMono.copyWith(color: plColor, fontSize: 12),
      ),
      const SizedBox(height: AmiSpacing.s),
      Align(
        alignment: AlignmentDirectional.centerStart,
        child: TextButton(
          onPressed: () => Navigator.of(context).push(MaterialPageRoute<void>(
            builder: (_) => TickerDetailScreen(ticker: position.symbol),
          )),
          child: Text(l.positionPerLotDetail,
              style: AmiTypography.labelMono
                  .copyWith(color: AmiColors.hexCyan, fontSize: 11)),
        ),
      ),
    ];
  }
}
