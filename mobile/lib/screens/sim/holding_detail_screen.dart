/// Holding Detail — full-screen view for a single open position.
///
/// Surfaced by tapping a holding card on the Portfolio tab. Aggregates
/// the position summary, agent quick-actions (trade more / ask analyst /
/// convene / close), and the user's trade history filtered to this
/// ticker. Future increments will add a chart, news, and earnings calendar
/// to this same surface (see AT:R40 plan).
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/agent.dart';
import 'package:ami_trade/models/sim.dart';
import 'package:ami_trade/screens/agent/one_on_one_screen.dart';
import 'package:ami_trade/screens/room/room_screen.dart';
import 'package:ami_trade/screens/sim/trade_ticket_sheet.dart';
import 'package:ami_trade/state/sim_providers.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:ami_trade/widgets/trade_row.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';

class HoldingDetailScreen extends ConsumerWidget {
  const HoldingDetailScreen({super.key, required this.ticker});

  final String ticker;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l = AppLocalizations.of(context);
    final state = ref.watch(simNotifierProvider);
    final portfolio = state.portfolio;
    final holding = portfolio?.holdings.firstWhere(
      (h) => h.ticker == ticker,
      orElse: () => SimHolding(
        ticker: ticker,
        quantity: 0,
        avgCost: 0,
        mark: 0,
        value: 0,
        unrealisedPnl: 0,
        openedAt: DateTime.now(),
      ),
    );
    final trades = state.trades.where((t) => t.ticker == ticker).toList();

    return Scaffold(
      backgroundColor: AmiColors.slate900,
      appBar: AppBar(
        backgroundColor: AmiColors.glassChrome,
        elevation: 0,
        iconTheme: const IconThemeData(color: AmiColors.hexCyan),
        title: Text(
          ticker,
          style: AmiTypography.labelMono.copyWith(color: AmiColors.hexCyan),
        ),
      ),
      body: SafeArea(
        child: RefreshIndicator(
          color: AmiColors.hexCyan,
          onRefresh: () =>
              ref.read(simNotifierProvider.notifier).refresh(),
          child: ListView(
            padding: const EdgeInsets.all(AmiSpacing.m),
            children: [
              if (holding != null && holding.quantity > 0)
                _PositionCard(holding: holding)
              else
                _ClosedPositionCard(ticker: ticker),
              const SizedBox(height: AmiSpacing.m),
              _QuickActions(
                ticker: ticker,
                hasOpenPosition: holding != null && holding.quantity > 0,
                hasOpenTrades: trades.any((t) => t.isOpen),
              ),
              const SizedBox(height: AmiSpacing.l),
              Padding(
                padding: const EdgeInsets.symmetric(vertical: AmiSpacing.s),
                child: Text(
                  l.holdingDetailTradesHeading(ticker),
                  style: AmiTypography.labelMono,
                ),
              ),
              if (trades.isEmpty)
                Padding(
                  padding: const EdgeInsets.all(AmiSpacing.s),
                  child: Text(
                    l.holdingDetailNoTrades,
                    style: AmiTypography.caption,
                  ),
                )
              else
                for (final t in trades) TradeRow(trade: t),
              const SizedBox(height: AmiSpacing.xl),
              _ComingSoonCard(),
              const SizedBox(height: AmiSpacing.xxl),
            ],
          ),
        ),
      ),
    );
  }
}


class _PositionCard extends StatelessWidget {
  const _PositionCard({required this.holding});

  final SimHolding holding;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final fmt = NumberFormat('#,##0.00');
    final pnl = holding.unrealisedPnl;
    final pct = holding.avgCost == 0
        ? 0.0
        : ((holding.mark - holding.avgCost) / holding.avgCost) * 100;
    final accent = pnl >= 0 ? AmiColors.hexGreen : AmiColors.hexRed;
    final openedFmt = DateFormat.yMMMd();

    return Container(
      padding: const EdgeInsets.all(AmiSpacing.m),
      decoration: BoxDecoration(
        color: AmiColors.slate800,
        borderRadius: BorderRadius.circular(AmiRadii.sheet),
        border: Border.all(color: AmiColors.slate700),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(l.holdingDetailValue,
              style: AmiTypography.labelMono.copyWith(color: AmiColors.hexCyan)),
          const SizedBox(height: AmiSpacing.xs),
          Text('\$${fmt.format(holding.value)}',
              style: AmiTypography.statBig.copyWith(color: AmiColors.textHigh)),
          const SizedBox(height: AmiSpacing.m),
          _StatRow(
            label: l.holdingDetailQty,
            value: holding.quantity.toStringAsFixed(0),
          ),
          _StatRow(
            label: l.holdingDetailAvgCost,
            value: '\$${fmt.format(holding.avgCost)}',
          ),
          _StatRow(
            label: l.holdingDetailMark,
            value: '\$${fmt.format(holding.mark)}',
          ),
          const Divider(height: 24, color: AmiColors.slate700),
          Row(
            children: [
              Icon(
                pnl >= 0 ? Icons.trending_up : Icons.trending_down,
                color: accent,
                size: 16,
              ),
              const SizedBox(width: 4),
              Text(
                '${pnl >= 0 ? '+' : ''}\$${fmt.format(pnl)} '
                '(${pct >= 0 ? '+' : ''}${pct.toStringAsFixed(2)}%)',
                style: AmiTypography.statSmall.copyWith(color: accent),
              ),
            ],
          ),
          const SizedBox(height: AmiSpacing.xs),
          Text(
            l.holdingDetailOpened(openedFmt.format(holding.openedAt)),
            style: AmiTypography.caption,
          ),
        ],
      ),
    );
  }
}


class _ClosedPositionCard extends StatelessWidget {
  const _ClosedPositionCard({required this.ticker});

  final String ticker;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    return Container(
      padding: const EdgeInsets.all(AmiSpacing.l),
      decoration: BoxDecoration(
        color: AmiColors.slate800,
        borderRadius: BorderRadius.circular(AmiRadii.sheet),
        border: Border.all(color: AmiColors.slate700),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.center,
        children: [
          const Icon(Icons.history, color: AmiColors.textLow, size: 32),
          const SizedBox(height: AmiSpacing.s),
          Text(
            l.holdingDetailNoOpenPosition(ticker),
            style: AmiTypography.body,
            textAlign: TextAlign.center,
          ),
        ],
      ),
    );
  }
}


class _StatRow extends StatelessWidget {
  const _StatRow({required this.label, required this.value});

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(
        children: [
          Text(label, style: AmiTypography.labelMono.copyWith(fontSize: 11)),
          const Spacer(),
          Text(value, style: AmiTypography.statSmall),
        ],
      ),
    );
  }
}


class _QuickActions extends ConsumerWidget {
  const _QuickActions({
    required this.ticker,
    required this.hasOpenPosition,
    required this.hasOpenTrades,
  });

  final String ticker;
  final bool hasOpenPosition;
  final bool hasOpenTrades;

  void _trade(BuildContext context) {
    TradeTicketSheet.show(context, tickerPrefill: ticker);
  }

  void _ask(BuildContext context) {
    Navigator.of(context).push(MaterialPageRoute<void>(
      builder: (_) => OneOnOneScreen(agent: agentById('market_analyst')),
    ));
  }

  void _convene(BuildContext context) {
    Navigator.of(context).push(MaterialPageRoute<void>(
      builder: (_) => RoomScreen(ticker: ticker),
    ));
  }

  Future<void> _closeAll(BuildContext context, WidgetRef ref) async {
    final l = AppLocalizations.of(context);
    final confirm = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: AmiColors.slate800,
        title: Text(l.holdingDetailClosePositionConfirmTitle(ticker),
            style: AmiTypography.labelMono.copyWith(color: AmiColors.hexCyan)),
        content: Text(l.holdingDetailClosePositionConfirmBody,
            style: AmiTypography.body),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(false),
            child: Text(l.actionCancel),
          ),
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(true),
            child: Text(
              l.holdingDetailClosePositionConfirmCta,
              style: const TextStyle(color: AmiColors.hexRed),
            ),
          ),
        ],
      ),
    );
    if (confirm != true) return;
    final state = ref.read(simNotifierProvider);
    final openForTicker =
        state.trades.where((t) => t.ticker == ticker && t.isOpen).toList();
    for (final t in openForTicker) {
      await ref.read(simNotifierProvider.notifier).closeTrade(t.id);
    }
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l = AppLocalizations.of(context);
    return Wrap(
      spacing: 8,
      runSpacing: 8,
      children: [
        _ActionChip(
          icon: Icons.shopping_cart_outlined,
          label: l.holdingDetailActionTrade,
          color: AmiColors.hexGreen,
          onTap: () => _trade(context),
        ),
        _ActionChip(
          icon: Icons.chat_bubble_outline,
          label: l.watchlistAskMarketAnalyst,
          color: AmiColors.hexCyan,
          onTap: () => _ask(context),
        ),
        _ActionChip(
          icon: Icons.groups_outlined,
          label: l.watchlistConveneRoom,
          color: AmiColors.hexPurple,
          onTap: () => _convene(context),
        ),
        if (hasOpenTrades)
          _ActionChip(
            icon: Icons.do_disturb_alt_outlined,
            label: l.holdingDetailActionClose,
            color: AmiColors.hexRed,
            onTap: () => _closeAll(context, ref),
          ),
      ],
    );
  }
}


class _ActionChip extends StatelessWidget {
  const _ActionChip({
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
      borderRadius: BorderRadius.circular(AmiRadii.card),
      child: Container(
        padding: const EdgeInsets.symmetric(
            horizontal: AmiSpacing.m, vertical: AmiSpacing.s),
        decoration: BoxDecoration(
          color: color.withValues(alpha: 0.12),
          borderRadius: BorderRadius.circular(AmiRadii.card),
          border: Border.all(color: color.withValues(alpha: 0.5)),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, color: color, size: 16),
            const SizedBox(width: 6),
            Text(label,
                style: AmiTypography.labelMono.copyWith(
                    color: color, fontSize: 11)),
          ],
        ),
      ),
    );
  }
}


class _ComingSoonCard extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    return Container(
      padding: const EdgeInsets.all(AmiSpacing.m),
      decoration: BoxDecoration(
        color: AmiColors.slate800.withValues(alpha: 0.6),
        borderRadius: BorderRadius.circular(AmiRadii.card),
        border: Border.all(
            color: AmiColors.slate700, style: BorderStyle.solid, width: 1),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(l.holdingDetailComingSoonHeading,
              style: AmiTypography.labelMono.copyWith(color: AmiColors.textLow)),
          const SizedBox(height: AmiSpacing.xs),
          Text(l.holdingDetailComingSoonBody,
              style: AmiTypography.caption),
        ],
      ),
    );
  }
}
