/// Reusable watchlist ticker action sheet.
///
/// Used by both the Portfolio watchlist rows and the TickerTape widget.
/// Pass showRemove: true only when the ticker is known to be in the user's
/// watchlist (Portfolio tab); the tape omits it for default filler tickers.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/agent.dart';
import 'package:ami_trade/screens/agent/one_on_one_screen.dart';
import 'package:ami_trade/screens/room/convene_sheet.dart';
import 'package:ami_trade/screens/sim/trade_ticket_sheet.dart';
import 'package:ami_trade/state/watchlist_providers.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';

void showWatchlistSheet(
  BuildContext context,
  WidgetRef ref, {
  required String ticker,
  double? price,
  String? notes,
  bool showRemove = false,
}) {
  final l = AppLocalizations.of(context);
  showModalBottomSheet<void>(
    context: context,
    backgroundColor: AmiColors.slate800,
    shape: const RoundedRectangleBorder(
      borderRadius: BorderRadius.vertical(top: Radius.circular(16)),
    ),
    builder: (sheetCtx) => SafeArea(
      child: Padding(
        padding: const EdgeInsets.all(AmiSpacing.l),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                // DEF341 — same one-token rule as the Portfolio watchlist row:
                // a ticker never wraps or overflows, it scales down beside the
                // price when space runs out.
                Flexible(
                  child: FittedBox(
                    fit: BoxFit.scaleDown,
                    alignment: AlignmentDirectional.centerStart,
                    child: Text(
                      ticker,
                      maxLines: 1,
                      style:
                          AmiTypography.h2.copyWith(color: AmiColors.hexCyan),
                    ),
                  ),
                ),
                const SizedBox(width: AmiSpacing.s),
                if (price != null)
                  Text(
                    NumberFormat.simpleCurrency(decimalDigits: 2).format(price),
                    style: AmiTypography.statMid,
                  ),
              ],
            ),
            if (notes != null && notes.isNotEmpty) ...[
              const SizedBox(height: AmiSpacing.s),
              Text(notes, style: AmiTypography.body),
            ],
            const SizedBox(height: AmiSpacing.l),
            _SheetAction(
              icon: Icons.shopping_cart_outlined,
              label: l.watchlistOpenTradeTicket,
              color: AmiColors.hexGreen,
              onTap: () {
                Navigator.of(sheetCtx).pop();
                TradeTicketSheet.show(context, tickerPrefill: ticker);
              },
            ),
            _SheetAction(
              icon: Icons.chat_bubble_outline,
              label: l.watchlistAskMarketAnalyst,
              color: AmiColors.hexCyan,
              onTap: () {
                Navigator.of(sheetCtx).pop();
                Navigator.of(context).push(
                  MaterialPageRoute<void>(
                    builder: (_) =>
                        OneOnOneScreen(agent: agentById('market_analyst')),
                  ),
                );
              },
            ),
            _SheetAction(
              icon: Icons.groups_outlined,
              label: l.watchlistConveneRoom,
              color: AmiColors.hexPurple,
              onTap: () {
                Navigator.of(sheetCtx).pop();
                ConveneSheet.show(context);
              },
            ),
            if (showRemove)
              _SheetAction(
                icon: Icons.delete_outline,
                label: l.watchlistRemove,
                color: AmiColors.hexRed,
                onTap: () {
                  Navigator.of(sheetCtx).pop();
                  ref
                      .read(watchlistNotifierProvider.notifier)
                      .remove(ticker);
                },
              ),
          ],
        ),
      ),
    ),
  );
}

class _SheetAction extends StatelessWidget {
  const _SheetAction({
    required this.icon,
    required this.label,
    required this.color,
    required this.onTap,
  });

  final IconData icon;
  final String label;
  final Color color;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: onTap,
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: AmiSpacing.s),
        child: Row(
          children: [
            Icon(icon, color: color),
            const SizedBox(width: AmiSpacing.s),
            Text(
              label,
              style: AmiTypography.labelMono.copyWith(color: color),
            ),
          ],
        ),
      ),
    );
  }
}
