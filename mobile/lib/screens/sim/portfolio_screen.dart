/// Sim Portfolio screen.
///
/// Shows cash + holdings + total value + P&L + drawdown. Each holding card
/// surfaces unrealised P&L and a quick "close" action. Below: open trades
/// (with stop/target marks) and closed trade history.
///
/// Pull-to-refresh re-evaluates open trades server-side (stop/target sweep)
/// so trades that hit while the user is on this screen show as won/lost.
library;

import 'package:ami_trade/features/tour/portfolio_tour.dart';
import 'package:ami_trade/features/tour/tour_providers.dart';
import 'package:ami_trade/features/tour/tour_service.dart';
import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/sim.dart';
import 'package:ami_trade/models/watchlist.dart';
import 'package:ami_trade/screens/sim/trade_ticket_sheet.dart';
import 'package:ami_trade/state/sim_providers.dart';
import 'package:ami_trade/state/watchlist_providers.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:ami_trade/widgets/hex/hex_chip.dart';
import 'package:ami_trade/widgets/watchlist_sheet.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';
import 'package:tutorial_coach_mark/tutorial_coach_mark.dart';

class PortfolioScreen extends ConsumerStatefulWidget {
  const PortfolioScreen({super.key});

  @override
  ConsumerState<PortfolioScreen> createState() => _PortfolioScreenState();
}

class _PortfolioScreenState extends ConsumerState<PortfolioScreen> {
  final _headerKey = GlobalKey();
  final _valueCardKey = GlobalKey();
  final _watchlistKey = GlobalKey();

  void _runTour() {
    final l = AppLocalizations.of(context);
    TutorialCoachMark(
      targets: buildPortfolioTargets(
        l: l,
        headerKey: _headerKey,
        valueCardKey: _valueCardKey,
        watchlistKey: _watchlistKey,
      ),
      hideSkip: true,
      colorShadow: Colors.black,
      opacityShadow: 0.88,
      pulseEnable: false,
      beforeFocus: (target) async {
        final ctx = target.keyTarget?.currentContext;
        if (ctx != null) {
          await Scrollable.ensureVisible(
            ctx,
            duration: const Duration(milliseconds: 350),
            alignment: 0.5,
          );
        }
      },
      onFinish: () {
        if (!mounted) return;
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(
          content: Text(AppLocalizations.of(context).tourCompletionPortfolio),
          backgroundColor: AmiColors.hexCyan,
          behavior: SnackBarBehavior.floating,
        ));
      },
    ).show(context: context);
  }

  @override
  Widget build(BuildContext context) {
    // Fire tour when Portfolio tab (index 1) becomes active for the first time.
    ref.listen<int>(activeTabIndexProvider, (prev, next) async {
      if (next != 1) return;
      final service = ref.read(tourServiceProvider);
      if (await service.hasSeen(TourSection.portfolio)) return;
      await service.markSeen(TourSection.portfolio);
      if (!mounted) return;
      _runTour();
    });

    final state = ref.watch(simNotifierProvider);
    final watchlist = ref.watch(watchlistNotifierProvider);
    return Scaffold(
      backgroundColor: AmiColors.slate900,
      body: SafeArea(
        child: Column(
          children: [
            _Header(key: _headerKey, onTradeTicket: () => TradeTicketSheet.show(context)),
            Expanded(child: _body(context, state, watchlist)),
          ],
        ),
      ),
    );
  }

  Widget _body(
    BuildContext context,
    SimState state,
    WatchlistState watchlist,
  ) {
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
      onRefresh: () async {
        await Future.wait<void>([
          ref.read(simNotifierProvider.notifier).refresh(),
          ref.read(watchlistNotifierProvider.notifier).refresh(),
        ]);
      },
      child: ListView(
        padding: const EdgeInsets.all(AmiSpacing.m),
        children: [
          _ValueCard(key: _valueCardKey, portfolio: p),
          const SizedBox(height: AmiSpacing.m),
          _WatchlistSection(key: _watchlistKey, state: watchlist),
          const SizedBox(height: AmiSpacing.m),
          if (p.holdings.isEmpty)
            _NewTraderHint(onTradeTicket: () => TradeTicketSheet.show(context))
          else ...[
            Padding(
              padding: const EdgeInsets.symmetric(vertical: AmiSpacing.s),
              child: Text(AppLocalizations.of(context).portfolioHoldings,
                  style: AmiTypography.labelMono),
            ),
            for (final h in p.holdings) _HoldingCard(holding: h),
          ],
          const SizedBox(height: AmiSpacing.l),
          Padding(
            padding: const EdgeInsets.symmetric(vertical: AmiSpacing.s),
            child: Text(AppLocalizations.of(context).portfolioTrades,
                style: AmiTypography.labelMono),
          ),
          if (state.trades.isEmpty)
            Padding(
              padding: const EdgeInsets.all(AmiSpacing.s),
              child: Text(AppLocalizations.of(context).portfolioNoTrades,
                  style: AmiTypography.caption),
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
  const _Header({super.key, required this.onTradeTicket});
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
          Text(AppLocalizations.of(context).portfolioHeading,
              style: AmiTypography.labelMono.copyWith(color: AmiColors.hexCyan)),
          const Spacer(),
          IconButton(
            icon: const Icon(Icons.add_circle_outline, color: AmiColors.hexCyan),
            tooltip: AppLocalizations.of(context).portfolioNewTradeTooltip,
            onPressed: onTradeTicket,
          ),
        ],
      ),
    );
  }
}


class _ValueCard extends StatelessWidget {
  const _ValueCard({super.key, required this.portfolio});
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
          Row(
            children: [
              Text(AppLocalizations.of(context).portfolioTotalValue,
                  style: AmiTypography.labelMono.copyWith(color: AmiColors.hexCyan)),
              const Spacer(),
              _QuoteSourcePill(portfolio: portfolio),
            ],
          ),
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
              Text(AppLocalizations.of(context).portfolioCash,
                  style: AmiTypography.labelMono.copyWith(fontSize: 10)),
              const SizedBox(width: 6),
              Text('\$${fmt.format(portfolio.currentCash)}',
                  style: AmiTypography.statSmall),
            ],
          ),
          if (portfolio.drawdownPct > 0) ...[
            const SizedBox(height: AmiSpacing.xs),
            Text(
              AppLocalizations.of(context).portfolioDrawdown(
                portfolio.drawdownPct.toStringAsFixed(1),
              ),
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
    final l = AppLocalizations.of(context);
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
          Text(l.portfolioStartSimTrading, style: AmiTypography.h4),
          const SizedBox(height: AmiSpacing.xs),
          Text(
            l.portfolioStartSimTradingBody,
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
            label: Text(l.portfolioNewTrade),
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


/// Tiny indicator next to TOTAL VALUE that tells the user whether marks
/// are real Yahoo quotes or the deterministic mock walk. Green dot = LIVE,
/// amber dot = MOCK. Lets the demo speak honestly about what it's pricing.
class _QuoteSourcePill extends StatelessWidget {
  const _QuoteSourcePill({required this.portfolio});
  final SimPortfolio portfolio;

  @override
  Widget build(BuildContext context) {
    final live = portfolio.isLivePrice;
    final color = live ? AmiColors.hexGreen : AmiColors.hexAmber;
    final l = AppLocalizations.of(context);
    return HexChip(
      label: live ? l.portfolioLive : l.portfolioMock,
      color: color,
      variant: HexChipVariant.tinted,
      showDot: true,
      fontSize: 10,
    );
  }
}


// ── Watchlist (A18) ─────────────────────────────────────────────────────


class _WatchlistSection extends ConsumerWidget {
  const _WatchlistSection({super.key, required this.state});
  final WatchlistState state;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l = AppLocalizations.of(context);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Text(l.watchlistHeading, style: AmiTypography.labelMono),
            const Spacer(),
            TextButton.icon(
              onPressed: () => _showAddDialog(context, ref),
              icon: const Icon(Icons.add, color: AmiColors.hexCyan, size: 16),
              label: Text(
                l.watchlistAdd,
                style: AmiTypography.labelMono.copyWith(color: AmiColors.hexCyan),
              ),
            ),
          ],
        ),
        if (state.items.isEmpty)
          Padding(
            padding: const EdgeInsets.symmetric(vertical: AmiSpacing.s),
            child: Text(
              l.watchlistEmpty,
              style: AmiTypography.caption,
            ),
          )
        else
          for (final w in state.items) _WatchlistRow(entry: w),
      ],
    );
  }

  Future<void> _showAddDialog(BuildContext context, WidgetRef ref) async {
    final ctrl = TextEditingController();
    final l = AppLocalizations.of(context);
    await showDialog<void>(
      context: context,
      builder: (ctx) {
        return AlertDialog(
          backgroundColor: AmiColors.slate800,
          title: Text(l.portfolioAddDialogTitle,
              style: AmiTypography.labelMono.copyWith(color: AmiColors.hexCyan)),
          content: TextField(
            controller: ctrl,
            autofocus: true,
            decoration: InputDecoration(
              hintText: l.portfolioAddDialogHint,
              hintStyle: const TextStyle(color: AmiColors.textLow),
            ),
            style: AmiTypography.body,
            textCapitalization: TextCapitalization.characters,
            onSubmitted: (_) => _commit(ctx, ref, ctrl.text),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.of(ctx).pop(),
              child: Text(l.actionCancel),
            ),
            TextButton(
              onPressed: () => _commit(ctx, ref, ctrl.text),
              child: Text(l.actionAdd),
            ),
          ],
        );
      },
    );
  }

  void _commit(BuildContext ctx, WidgetRef ref, String raw) {
    final ticker = raw.trim();
    if (ticker.isEmpty) return;
    ref.read(watchlistNotifierProvider.notifier).add(ticker);
    Navigator.of(ctx).pop();
  }
}


class _WatchlistRow extends ConsumerWidget {
  const _WatchlistRow({required this.entry});
  final WatchlistEntry entry;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final priceText = entry.price == null
        ? '—'
        : NumberFormat.simpleCurrency(decimalDigits: 2).format(entry.price);
    return Padding(
      padding: const EdgeInsets.only(bottom: 6),
      child: InkWell(
        onTap: () => _showRowSheet(context, ref),
        borderRadius: BorderRadius.circular(AmiRadii.card),
        child: Container(
          padding: const EdgeInsets.symmetric(
            horizontal: AmiSpacing.m, vertical: AmiSpacing.s,
          ),
          decoration: BoxDecoration(
            color: AmiColors.slate800,
            borderRadius: BorderRadius.circular(AmiRadii.card),
            border: Border.all(color: AmiColors.slate700),
          ),
          child: Row(
            children: [
              SizedBox(
                width: 64,
                child: Text(entry.ticker,
                    style: AmiTypography.labelMono.copyWith(color: AmiColors.textHigh)),
              ),
              const SizedBox(width: AmiSpacing.s),
              Expanded(
                child: Text(
                  entry.notes ?? '',
                  style: AmiTypography.caption,
                  maxLines: 1, overflow: TextOverflow.ellipsis,
                ),
              ),
              Text(priceText, style: AmiTypography.statMid),
              const SizedBox(width: AmiSpacing.s),
              const Icon(Icons.chevron_right, color: AmiColors.textLow),
            ],
          ),
        ),
      ),
    );
  }

  void _showRowSheet(BuildContext context, WidgetRef ref) {
    showWatchlistSheet(
      context,
      ref,
      ticker: entry.ticker,
      price: entry.price,
      notes: entry.notes,
      showRemove: true,
    );
  }
}


