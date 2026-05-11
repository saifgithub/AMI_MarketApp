/// Sim Portfolio screen.
///
/// Shows cash + holdings + total value + P&L + drawdown. Each holding card
/// surfaces unrealised P&L and a quick "close" action. Below: open trades
/// (with stop/target marks) and closed trade history.
///
/// Pull-to-refresh re-evaluates open trades server-side (stop/target sweep)
/// so trades that hit while the user is on this screen show as won/lost.
library;

import 'package:ami_trade/models/sim.dart';
import 'package:ami_trade/screens/sim/trade_ticket_sheet.dart';
import 'package:ami_trade/state/sim_providers.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';

class PortfolioScreen extends ConsumerWidget {
  const PortfolioScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(simNotifierProvider);
    return Scaffold(
      backgroundColor: AmiColors.slate900,
      body: SafeArea(
        child: Column(
          children: [
            _Header(onTradeTicket: () => TradeTicketSheet.show(context)),
            Expanded(child: _body(context, ref, state)),
          ],
        ),
      ),
    );
  }

  Widget _body(BuildContext context, WidgetRef ref, SimState state) {
    if (state.loading && state.portfolio == null) {
      return const Center(child: CircularProgressIndicator());
    }
    if (state.error != null && state.portfolio == null) {
      return Padding(
        padding: const EdgeInsets.all(AmiSpacing.l),
        child: Center(child: Text(state.error!, style: AmiTypography.body)),
      );
    }
    final p = state.portfolio;
    if (p == null) return const SizedBox.shrink();
    return RefreshIndicator(
      color: AmiColors.hexCyan,
      onRefresh: () => ref.read(simNotifierProvider.notifier).refresh(),
      child: ListView(
        padding: const EdgeInsets.all(AmiSpacing.m),
        children: [
          _ValueCard(portfolio: p),
          const SizedBox(height: AmiSpacing.m),
          if (p.holdings.isEmpty)
            _NewTraderHint(onTradeTicket: () => TradeTicketSheet.show(context))
          else ...[
            Padding(
              padding: const EdgeInsets.symmetric(vertical: AmiSpacing.s),
              child: Text('HOLDINGS', style: AmiTypography.labelMono),
            ),
            for (final h in p.holdings) _HoldingCard(holding: h),
          ],
          const SizedBox(height: AmiSpacing.l),
          Padding(
            padding: const EdgeInsets.symmetric(vertical: AmiSpacing.s),
            child: Text('TRADES', style: AmiTypography.labelMono),
          ),
          if (state.trades.isEmpty)
            const Padding(
              padding: EdgeInsets.all(AmiSpacing.s),
              child: Text('No trades yet.', style: AmiTypography.caption),
            )
          else
            for (final t in state.trades) _TradeRow(trade: t, ref: ref),
          const SizedBox(height: AmiSpacing.xxl),
        ],
      ),
    );
  }
}


class _Header extends StatelessWidget {
  const _Header({required this.onTradeTicket});
  final VoidCallback onTradeTicket;

  @override
  Widget build(BuildContext context) {
    return Container(
      height: 64,
      padding: const EdgeInsets.symmetric(horizontal: AmiSpacing.m),
      decoration: const BoxDecoration(
        color: AmiColors.glassChrome,
        border: Border(bottom: BorderSide(color: AmiColors.slate700)),
      ),
      child: Row(
        children: [
          Text('PORTFOLIO',
              style: AmiTypography.labelMono.copyWith(color: AmiColors.hexCyan)),
          const Spacer(),
          IconButton(
            icon: const Icon(Icons.add_circle_outline, color: AmiColors.hexCyan),
            tooltip: 'New trade',
            onPressed: onTradeTicket,
          ),
        ],
      ),
    );
  }
}


class _ValueCard extends StatelessWidget {
  const _ValueCard({required this.portfolio});
  final SimPortfolio portfolio;

  @override
  Widget build(BuildContext context) {
    final pnl = portfolio.totalPnl;
    final pnlPct = portfolio.pnlPct;
    final accent = pnl >= 0 ? AmiColors.hexGreen : AmiColors.hexRed;
    final fmt = NumberFormat('#,##0.00');
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
          Text('TOTAL VALUE',
              style: AmiTypography.labelMono.copyWith(color: AmiColors.hexCyan)),
          const SizedBox(height: AmiSpacing.xs),
          Text('\$${fmt.format(portfolio.totalValue)}',
              style: AmiTypography.statBig.copyWith(color: AmiColors.textHigh)),
          const SizedBox(height: AmiSpacing.s),
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
                '(${pnl >= 0 ? '+' : ''}${pnlPct.toStringAsFixed(2)}%)',
                style: AmiTypography.statSmall.copyWith(color: accent),
              ),
              const Spacer(),
              Text('CASH', style: AmiTypography.labelMono.copyWith(fontSize: 10)),
              const SizedBox(width: 6),
              Text('\$${fmt.format(portfolio.currentCash)}',
                  style: AmiTypography.statSmall),
            ],
          ),
          if (portfolio.drawdownPct > 0) ...[
            const SizedBox(height: AmiSpacing.xs),
            Text(
              'Drawdown: ${portfolio.drawdownPct.toStringAsFixed(1)}%',
              style: AmiTypography.caption.copyWith(
                color: portfolio.drawdownPct > 20 ? AmiColors.hexAmber : AmiColors.textLow,
              ),
            ),
          ],
        ],
      ),
    );
  }
}


class _NewTraderHint extends StatelessWidget {
  const _NewTraderHint({required this.onTradeTicket});
  final VoidCallback onTradeTicket;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(AmiSpacing.l),
      decoration: BoxDecoration(
        color: AmiColors.slate800,
        borderRadius: BorderRadius.circular(AmiRadii.card),
        border: Border.all(color: AmiColors.slate700),
      ),
      child: Column(
        children: [
          const Icon(Icons.lightbulb_outline, color: AmiColors.hexCyan, size: 32),
          const SizedBox(height: AmiSpacing.s),
          const Text('Start sim trading', style: AmiTypography.h4),
          const SizedBox(height: AmiSpacing.xs),
          Text(
            'Convene the Room to get a verdict, then open a trade — or '
            'place one directly from here. Your PM\'s safety floor runs '
            'on every submit.',
            textAlign: TextAlign.center,
            style: AmiTypography.body.copyWith(color: AmiColors.textLow),
          ),
          const SizedBox(height: AmiSpacing.m),
          ElevatedButton.icon(
            style: ElevatedButton.styleFrom(
              backgroundColor: AmiColors.hexCyan,
              foregroundColor: AmiColors.slate900,
            ),
            icon: const Icon(Icons.add),
            label: const Text('NEW TRADE'),
            onPressed: onTradeTicket,
          ),
        ],
      ),
    );
  }
}


class _HoldingCard extends StatelessWidget {
  const _HoldingCard({required this.holding});
  final SimHolding holding;

  @override
  Widget build(BuildContext context) {
    final pnl = holding.unrealisedPnl;
    final pct = holding.avgCost == 0
        ? 0.0
        : ((holding.mark - holding.avgCost) / holding.avgCost) * 100;
    final accent = pnl >= 0 ? AmiColors.hexGreen : AmiColors.hexRed;
    final fmt = NumberFormat('#,##0.00');
    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.all(AmiSpacing.m),
      decoration: BoxDecoration(
        color: AmiColors.slate800,
        borderRadius: BorderRadius.circular(AmiRadii.card),
        border: Border.all(color: AmiColors.slate700),
      ),
      child: Row(
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(holding.ticker,
                    style: AmiTypography.statMid.copyWith(color: AmiColors.textHigh)),
                const SizedBox(height: 2),
                Text(
                  '${holding.quantity.toStringAsFixed(0)} @ \$${fmt.format(holding.avgCost)}',
                  style: AmiTypography.caption,
                ),
              ],
            ),
          ),
          Column(
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              Text('\$${fmt.format(holding.value)}',
                  style: AmiTypography.statSmall),
              const SizedBox(height: 2),
              Text(
                '${pnl >= 0 ? '+' : ''}\$${fmt.format(pnl)} '
                '(${pct >= 0 ? '+' : ''}${pct.toStringAsFixed(2)}%)',
                style: AmiTypography.labelMono.copyWith(color: accent, fontSize: 11),
              ),
            ],
          ),
        ],
      ),
    );
  }
}


class _TradeRow extends StatelessWidget {
  const _TradeRow({required this.trade, required this.ref});
  final SimTrade trade;
  final WidgetRef ref;

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
          if (trade.isOpen)
            IconButton(
              icon: const Icon(Icons.close, size: 16, color: AmiColors.textLow),
              tooltip: 'Close',
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
