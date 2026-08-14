/// CR171 — the short book, on the Portfolio screen.
///
/// Two groups, and the second is the one that had to exist. Open shorts render
/// as their own list rather than inside HOLDINGS, because a short is not a
/// holding: the user owes the shares. Rendering it as a holding would put a
/// green "value" on a position whose worth to the book FALLS as the number in
/// front of the user rises.
///
/// **Recently closed** renders §7's report. A margin close has no warning, no
/// grace period and no notification by design — *"a user asleep in Riyadh
/// cannot act on it anyway"* — which makes the after-the-fact report the only
/// thing standing between the mechanic and the games lane's *"the order simply
/// VANISHED overnight"* defect, on a much bigger number. The server already
/// logged it; a log informs the operator, not the person it happened to.
///
/// **Renders nothing when there are no shorts**, which is almost every
/// portfolio. An empty "short positions" heading on every screen in the app is
/// the placeholder CR040 forbids.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/sim.dart';
import 'package:ami_trade/screens/sim/trade_ticket_sheet.dart';
import 'package:ami_trade/state/sim_providers.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
// `intl` exports its own `TextDirection`, which shadows `dart:ui`'s and makes
// `TextDirection.ltr` an undefined getter.
import 'package:intl/intl.dart' hide TextDirection;

final _money = NumberFormat('#,##0.00');

/// The sentence a closed short is reported with.
///
/// Exported so a test can assert the wording per reason without building the
/// widget tree, and — more to the point — so `margin` can never fall through
/// to the same sentence as `user`. "You covered this" and "AMI closed this for
/// you" are different events, and a user who reads the first about the second
/// learns the wrong lesson about the mechanic that just cost them money.
String closedShortSentence(AppLocalizations l, SimClosedShort s) {
  final qty = s.quantity.toStringAsFixed(0);
  final price = _money.format(s.closePrice ?? 0);
  switch (s.closeReason) {
    case 'margin':
      return l.shortClosedMargin(qty, s.ticker, price);
    case 'stop':
      return l.shortClosedBracket(qty, s.ticker, price, l.shortClosedStopWord);
    case 'target':
      return l.shortClosedBracket(
          qty, s.ticker, price, l.shortClosedTargetWord);
    default:
      return l.shortClosedByYou(qty, s.ticker, price);
  }
}

class ShortPositionsSection extends ConsumerWidget {
  const ShortPositionsSection({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final p = ref.watch(simNotifierProvider).portfolio;
    if (p == null) return const SizedBox.shrink();
    final open = p.shorts;
    final closed = p.closedShorts;
    if (open.isEmpty && closed.isEmpty) return const SizedBox.shrink();
    final l = AppLocalizations.of(context);

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        if (open.isNotEmpty) ...[
          Padding(
            padding: const EdgeInsets.symmetric(vertical: AmiSpacing.s),
            child: Text(l.portfolioShortsHeading, style: AmiTypography.labelMono),
          ),
          for (final s in open) ShortPositionCard(short: s),
        ],
        if (closed.isNotEmpty) ...[
          Padding(
            padding: const EdgeInsets.symmetric(vertical: AmiSpacing.s),
            child: Text(
              l.portfolioShortsClosedHeading,
              style: AmiTypography.labelMono.copyWith(color: AmiColors.textLow),
            ),
          ),
          for (final s in closed) ClosedShortCard(short: s),
        ],
      ],
    );
  }
}

class ShortPositionCard extends StatelessWidget {
  const ShortPositionCard({super.key, required this.short});
  final SimShort short;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final pnl = short.unrealisedPnl;
    final pnlColor = pnl >= 0 ? AmiColors.hexGreen : AmiColors.hexRed;
    final sign = pnl >= 0 ? '+' : '−';
    final ratio = short.marginRatio;
    final near = short.isNearMargin;

    return Container(
      margin: const EdgeInsets.only(bottom: AmiSpacing.s),
      padding: const EdgeInsets.all(AmiSpacing.m),
      decoration: BoxDecoration(
        color: AmiColors.slate800,
        borderRadius: BorderRadius.circular(AmiRadii.card),
        border: Border.all(
          color: near
              ? AmiColors.hexAmber
              : AmiColors.hexRed.withValues(alpha: 0.5),
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Text(short.ticker, style: AmiTypography.dataMd),
                        const SizedBox(width: AmiSpacing.xs),
                        Container(
                          padding: const EdgeInsets.symmetric(
                              horizontal: 6, vertical: 2),
                          decoration: BoxDecoration(
                            borderRadius: BorderRadius.circular(4),
                            border: Border.all(color: AmiColors.hexRed),
                          ),
                          child: Text(
                            l.shortPositionBadge,
                            style: AmiTypography.labelMono
                                .copyWith(fontSize: 9, color: AmiColors.hexRed),
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 2),
                    Directionality(
                      textDirection: TextDirection.ltr,
                      child: Text(
                        l.shortPositionSub(
                          short.quantity.toStringAsFixed(0),
                          _money.format(short.entryPrice),
                        ),
                        style: AmiTypography.caption
                            .copyWith(color: AmiColors.textLow),
                      ),
                    ),
                  ],
                ),
              ),
              Column(
                crossAxisAlignment: CrossAxisAlignment.end,
                children: [
                  // The LEG value, from the server. Never `quantity × mark`:
                  // that number grows as the position goes against the user.
                  Text('\$${_money.format(short.legValue)}',
                      style: AmiTypography.dataMd),
                  Text(
                    '$sign\$${_money.format(pnl.abs())} '
                    '(${short.unrealisedPct.toStringAsFixed(1)}%)',
                    style: AmiTypography.caption.copyWith(color: pnlColor),
                  ),
                ],
              ),
            ],
          ),
          const SizedBox(height: AmiSpacing.xs),
          // §4 — the borrow comes out of cash, not out of the leg above, so
          // without this line the position looks free to hold.
          Text(
            l.shortBorrowLine(
              _money.format(short.borrowAccruedTotal),
              short.borrowRatePct.toStringAsFixed(2),
            ),
            style: AmiTypography.caption.copyWith(color: AmiColors.textLow),
          ),
          if (ratio != null)
            Text(
              l.shortMarginLine(
                ratio.toStringAsFixed(2),
                short.maintenanceMargin.toStringAsFixed(2),
              ),
              style: AmiTypography.caption.copyWith(
                color: near ? AmiColors.hexAmber : AmiColors.textLow,
              ),
            ),
          if (near) ...[
            const SizedBox(height: AmiSpacing.xs),
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Icon(Icons.warning_amber_rounded,
                    size: 14, color: AmiColors.hexAmber),
                const SizedBox(width: 4),
                Expanded(
                  child: Text(l.shortMarginWarning,
                      style: AmiTypography.caption
                          .copyWith(color: AmiColors.hexAmber)),
                ),
              ],
            ),
          ],
          const SizedBox(height: AmiSpacing.xs),
          Align(
            alignment: AlignmentDirectional.centerEnd,
            child: OutlinedButton(
              style: OutlinedButton.styleFrom(
                foregroundColor: AmiColors.hexCyan,
                side: const BorderSide(color: AmiColors.hexCyan),
                visualDensity: VisualDensity.compact,
                padding: const EdgeInsets.symmetric(
                    horizontal: AmiSpacing.m, vertical: 4),
              ),
              onPressed: () => TradeTicketSheet.show(
                context,
                coverTicker: short.ticker,
                coverQuantity: short.quantity,
              ),
              child: Text(l.shortCoverCta,
                  style: AmiTypography.labelMono.copyWith(fontSize: 10)),
            ),
          ),
        ],
      ),
    );
  }
}

class ClosedShortCard extends StatelessWidget {
  const ClosedShortCard({super.key, required this.short});
  final SimClosedShort short;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final forced = short.wasForced;
    final pnl = short.realisedPnl ?? 0;
    final pnlColor = pnl >= 0 ? AmiColors.hexGreen : AmiColors.hexRed;
    final sign = pnl >= 0 ? '+' : '−';

    return Container(
      margin: const EdgeInsets.only(bottom: AmiSpacing.s),
      padding: const EdgeInsets.all(AmiSpacing.m),
      decoration: BoxDecoration(
        color: AmiColors.slate800,
        borderRadius: BorderRadius.circular(AmiRadii.card),
        border: Border.all(
          color: forced ? AmiColors.hexAmber : AmiColors.slate700,
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Icon(
                forced ? Icons.gavel : Icons.check_circle_outline,
                size: 16,
                color: forced ? AmiColors.hexAmber : AmiColors.textLow,
              ),
              const SizedBox(width: 6),
              Expanded(
                child: Text(
                  closedShortSentence(l, short),
                  style: AmiTypography.caption.copyWith(
                    color: forced ? AmiColors.hexAmber : AmiColors.textMed,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 4),
          Directionality(
            textDirection: TextDirection.ltr,
            child: Text(
              l.shortRealisedLine(
                '$sign\$${_money.format(pnl.abs())}',
                _money.format(short.borrowAccruedTotal),
              ),
              style: AmiTypography.caption.copyWith(color: pnlColor),
            ),
          ),
        ],
      ),
    );
  }
}
