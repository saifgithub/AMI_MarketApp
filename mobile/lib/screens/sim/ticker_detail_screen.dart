/// Ticker Detail — full-screen view for a single ticker.
///
/// Surfaced by tapping a holding card or a watchlist row on the Portfolio
/// tab, or by tapping `SEE CHART` on a Room verdict card. Adapts to context:
/// held → Position card; watched-only → Watching card; neither (closed
/// position, removed from watchlist mid-session) → empty card.
///
/// Section order (per AT:R40 plan): status → chart → actions → earnings →
/// news → trade-history. Chart / news / earnings ship in Bundles 2-5; this
/// file lays out the chrome and routes around the COMING SOON placeholder.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/agent.dart';
import 'package:ami_trade/models/sim.dart';
import 'package:ami_trade/models/watchlist.dart';
import 'package:ami_trade/screens/agent/one_on_one_screen.dart';
import 'package:ami_trade/screens/room/room_screen.dart';
import 'package:ami_trade/screens/sim/chart_fullscreen_screen.dart';
import 'package:ami_trade/screens/sim/trade_ticket_sheet.dart';
import 'package:ami_trade/state/sim_providers.dart';
import 'package:ami_trade/state/ticker_history_provider.dart';
import 'package:ami_trade/services/celebration.dart';
import 'package:ami_trade/state/watchlist_providers.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:ami_trade/widgets/empty_state.dart';
import 'package:ami_trade/widgets/ticker_chart.dart';
import 'package:ami_trade/widgets/trade_row.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';
import 'package:url_launcher/url_launcher.dart';

class TickerDetailScreen extends ConsumerStatefulWidget {
  const TickerDetailScreen({super.key, required this.ticker});

  final String ticker;

  @override
  ConsumerState<TickerDetailScreen> createState() => _TickerDetailScreenState();
}

class _TickerDetailScreenState extends ConsumerState<TickerDetailScreen> {
  // Guard against the OrientationBuilder firing multiple landscape pushes
  // for a single rotation. Reset when the fullscreen route pops.
  bool _fullscreenPushed = false;

  void _pushFullscreen() {
    if (_fullscreenPushed) return;
    _fullscreenPushed = true;
    Navigator.of(context)
        .push(MaterialPageRoute<void>(
          builder: (_) => ChartFullscreenScreen(ticker: widget.ticker),
        ))
        .then((_) {
      if (mounted) {
        setState(() => _fullscreenPushed = false);
      } else {
        _fullscreenPushed = false;
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    return OrientationBuilder(
      builder: (context, orientation) {
        // Side-effect: rotation to landscape pushes the fullscreen route.
        // The fullscreen route is the only one that unlocks orientation,
        // so this callback only fires landscape AFTER the route is already
        // visible — unless the user is rotating the device against the
        // app-wide portrait lock, which we treat as an explicit ask.
        if (orientation == Orientation.landscape && !_fullscreenPushed) {
          WidgetsBinding.instance.addPostFrameCallback((_) => _pushFullscreen());
        }
        return _buildPortrait(context);
      },
    );
  }

  Widget _buildPortrait(BuildContext context) {
    final l = AppLocalizations.of(context);
    final ticker = widget.ticker;
    final simState = ref.watch(simNotifierProvider);
    final watchlistState = ref.watch(watchlistNotifierProvider);
    final portfolio = simState.portfolio;

    SimHolding? heldHolding;
    if (portfolio != null) {
      try {
        heldHolding = portfolio.holdings.firstWhere((h) => h.ticker == ticker);
      } catch (_) {
        heldHolding = null;
      }
    }
    final isHeld = heldHolding != null && heldHolding.quantity > 0;

    WatchlistEntry? watchedEntry;
    try {
      watchedEntry =
          watchlistState.items.firstWhere((e) => e.ticker == ticker);
    } catch (_) {
      watchedEntry = null;
    }
    final isWatched = watchedEntry != null;

    final trades = simState.trades.where((t) => t.ticker == ticker).toList();
    final hasOpenTrades = trades.any((t) => t.isOpen);

    final earningsAsync = ref.watch(tickerEarningsProvider(ticker));
    final newsAsync = ref.watch(tickerNewsProvider(ticker));

    Widget statusCard;
    if (isHeld) {
      // Position card wins when held — strictly more informative.
      statusCard = _PositionCard(holding: heldHolding);
    } else if (isWatched) {
      statusCard = _WatchingCard(entry: watchedEntry);
    } else {
      // Rare mid-session state: user closed every open trade and is not on
      // the watchlist. Don't break the screen.
      statusCard = _EmptyStateCard(ticker: ticker);
    }

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
          onRefresh: () async {
            await Future.wait<void>([
              ref.read(simNotifierProvider.notifier).refresh(),
              ref.read(watchlistNotifierProvider.notifier).refresh(),
            ]);
          },
          child: ListView(
            padding: const EdgeInsets.all(AmiSpacing.m),
            children: [
              statusCard,
              const SizedBox(height: AmiSpacing.m),
              TickerChart(
                ticker: ticker,
                height: 220,
                onExpand: _pushFullscreen,
              ),
              const SizedBox(height: AmiSpacing.m),
              _PrimaryAction(ticker: ticker, isHeld: isHeld),
              const SizedBox(height: AmiSpacing.s),
              _SecondaryActions(
                ticker: ticker,
                isWatched: isWatched,
                hasOpenTrades: hasOpenTrades,
              ),
              const SizedBox(height: AmiSpacing.l),
              earningsAsync.when(
                data: (e) => (!e.hasData && !e.hasDividendData)
                    ? const SizedBox.shrink()
                    : Padding(
                        padding: const EdgeInsets.only(bottom: AmiSpacing.s),
                        child: Wrap(
                          spacing: AmiSpacing.s,
                          runSpacing: AmiSpacing.s,
                          children: [
                            if (e.hasData) _EarningsPill(earnings: e),
                            // CR100/CR030 — hidden when both dividend
                            // fields are null (non-payer / no window).
                            if (e.hasDividendData) _DividendChip(earnings: e),
                          ],
                        ),
                      ),
                loading: () => const SizedBox.shrink(),
                error: (_, __) => const SizedBox.shrink(),
              ),
              if (isHeld)
                _LotsSection(ticker: ticker),
              newsAsync.when(
                data: (n) => n.articles.isEmpty
                    ? const SizedBox.shrink()
                    : Padding(
                        padding:
                            const EdgeInsets.only(bottom: AmiSpacing.m),
                        child: _NewsSection(articles: n.articles),
                      ),
                loading: () => const SizedBox.shrink(),
                error: (_, __) => const SizedBox.shrink(),
              ),
              Padding(
                padding: const EdgeInsets.symmetric(vertical: AmiSpacing.s),
                child: Text(
                  l.tickerDetailTradesHeading(ticker),
                  style: AmiTypography.labelMono,
                ),
              ),
              if (trades.isEmpty)
                AmiEmptyState(
                  icon: Icons.receipt_long_outlined,
                  title: l.tickerDetailNoTrades,
                )
              else
                for (final t in trades) TradeRow(trade: t),
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
          Text(l.tickerDetailValue,
              style: AmiTypography.labelMono.copyWith(color: AmiColors.hexCyan)),
          const SizedBox(height: AmiSpacing.xs),
          Text('\$${fmt.format(holding.value)}',
              style: AmiTypography.statBig.copyWith(color: AmiColors.textHigh)),
          const SizedBox(height: AmiSpacing.m),
          _StatRow(
            label: l.tickerDetailQty,
            value: holding.quantity.toStringAsFixed(0),
          ),
          _StatRow(
            label: l.tickerDetailAvgCost,
            value: '\$${fmt.format(holding.avgCost)}',
          ),
          _StatRow(
            label: l.tickerDetailMark,
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
            l.tickerDetailOpened(openedFmt.format(holding.openedAt)),
            style: AmiTypography.caption,
          ),
        ],
      ),
    );
  }
}


class _WatchingCard extends StatelessWidget {
  const _WatchingCard({required this.entry});

  final WatchlistEntry entry;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final fmt = NumberFormat('#,##0.00');
    final dayPct = entry.dayChangePct;
    final accent = (dayPct ?? 0) >= 0 ? AmiColors.hexGreen : AmiColors.hexRed;
    final addedFmt = DateFormat.yMMMd();

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
          Text(l.tickerDetailWatchingHeading,
              style: AmiTypography.labelMono.copyWith(color: AmiColors.hexAmber)),
          const SizedBox(height: AmiSpacing.xs),
          Text(
            entry.price == null ? '—' : '\$${fmt.format(entry.price)}',
            style: AmiTypography.statBig.copyWith(color: AmiColors.textHigh),
          ),
          if (dayPct != null) ...[
            const SizedBox(height: AmiSpacing.xs),
            Row(
              children: [
                Icon(
                  dayPct >= 0 ? Icons.trending_up : Icons.trending_down,
                  color: accent,
                  size: 16,
                ),
                const SizedBox(width: 4),
                Text(
                  '${dayPct >= 0 ? '+' : ''}${dayPct.toStringAsFixed(2)}% '
                  '${l.tickerDetailToday}',
                  style: AmiTypography.statSmall.copyWith(color: accent),
                ),
              ],
            ),
          ],
          if (entry.notes != null && entry.notes!.trim().isNotEmpty) ...[
            const SizedBox(height: AmiSpacing.m),
            Text(
              '"${entry.notes}"',
              style: AmiTypography.body.copyWith(
                  fontStyle: FontStyle.italic, color: AmiColors.textLow),
            ),
          ],
          const SizedBox(height: AmiSpacing.s),
          Text(
            l.tickerDetailAdded(addedFmt.format(entry.addedAt)),
            style: AmiTypography.caption,
          ),
        ],
      ),
    );
  }
}


class _EmptyStateCard extends StatelessWidget {
  const _EmptyStateCard({required this.ticker});

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
          const Icon(Icons.search, color: AmiColors.textLow, size: 32),
          const SizedBox(height: AmiSpacing.s),
          Text(
            l.tickerDetailNoPosition(ticker),
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


class _PrimaryAction extends StatelessWidget {
  const _PrimaryAction({required this.ticker, required this.isHeld});

  final String ticker;
  final bool isHeld;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    return SizedBox(
      width: double.infinity,
      child: ElevatedButton.icon(
        style: ElevatedButton.styleFrom(
          backgroundColor: AmiColors.hexGreen,
          foregroundColor: AmiColors.slate900,
          padding: const EdgeInsets.symmetric(vertical: AmiSpacing.m),
        ),
        icon: Icon(isHeld ? Icons.add : Icons.arrow_upward),
        label: Text(
          isHeld ? l.tickerDetailActionTradeMore : l.tickerDetailActionTrade,
          style: AmiTypography.labelMono,
        ),
        onPressed: () => TradeTicketSheet.show(context, tickerPrefill: ticker),
      ),
    );
  }
}


class _SecondaryActions extends ConsumerWidget {
  const _SecondaryActions({
    required this.ticker,
    required this.isWatched,
    required this.hasOpenTrades,
  });

  final String ticker;
  final bool isWatched;
  final bool hasOpenTrades;

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

  Future<void> _toggleWatch(BuildContext context, WidgetRef ref) async {
    final notifier = ref.read(watchlistNotifierProvider.notifier);
    if (isWatched) {
      await notifier.remove(ticker);
    } else {
      await notifier.add(ticker);
      if (context.mounted) {
        Celebrate.micro(context, accent: AmiColors.hexCyan);
      }
    }
  }

  Future<void> _closeAll(BuildContext context, WidgetRef ref) async {
    final l = AppLocalizations.of(context);
    final confirm = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: AmiColors.slate800,
        title: Text(l.tickerDetailClosePositionConfirmTitle(ticker),
            style: AmiTypography.labelMono.copyWith(color: AmiColors.hexCyan)),
        content: Text(l.tickerDetailClosePositionConfirmBody,
            style: AmiTypography.body),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(false),
            child: Text(l.actionCancel),
          ),
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(true),
            child: Text(
              l.tickerDetailClosePositionConfirmCta,
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
        _Chip(
          icon: Icons.chat_bubble_outline,
          label: l.tickerDetailActionAsk,
          color: AmiColors.hexCyan,
          onTap: () => _ask(context),
        ),
        _Chip(
          icon: Icons.groups_outlined,
          label: l.tickerDetailActionConvene,
          color: AmiColors.hexPurple,
          onTap: () => _convene(context),
        ),
        _Chip(
          icon: isWatched ? Icons.star : Icons.star_border,
          label: l.tickerDetailActionWatch,
          color: AmiColors.hexAmber,
          onTap: () => _toggleWatch(context, ref),
        ),
        if (hasOpenTrades)
          _Chip(
            icon: Icons.do_disturb_alt_outlined,
            label: l.tickerDetailActionClose,
            color: AmiColors.hexRed,
            onTap: () => _closeAll(context, ref),
          ),
      ],
    );
  }
}


class _Chip extends StatelessWidget {
  const _Chip({
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




/// Amber pill showing upcoming earnings within 90 days.
/// Only rendered when SimEarnings.hasData is true.
class _EarningsPill extends StatelessWidget {
  const _EarningsPill({required this.earnings});

  final SimEarnings earnings;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final dateStr = _fmtEarningsDate(earnings.earningsDate);
    final eps = earnings.epsEstimate;

    return Container(
      width: double.infinity,
      padding: const EdgeInsets.symmetric(
          horizontal: AmiSpacing.m, vertical: AmiSpacing.s),
      decoration: BoxDecoration(
        color: AmiColors.hexAmber.withValues(alpha: 0.10),
        borderRadius: BorderRadius.circular(AmiRadii.card),
        border: Border.all(color: AmiColors.hexAmber.withValues(alpha: 0.45)),
      ),
      child: Row(
        children: [
          const Icon(Icons.calendar_today_outlined,
              color: AmiColors.hexAmber, size: 14),
          const SizedBox(width: AmiSpacing.s),
          Text(
            earnings.quarter ?? '',
            style: AmiTypography.labelMono
                .copyWith(color: AmiColors.hexAmber, fontSize: 11),
          ),
          if (dateStr != null) ...[
            Text(
              ' · $dateStr',
              style: AmiTypography.labelMono
                  .copyWith(color: AmiColors.textMed, fontSize: 11),
            ),
          ],
          if (eps != null) ...[
            Text(
              ' · ${l.tickerDetailNewsEpsEstimate('\$${eps.toStringAsFixed(2)}')}',
              style: AmiTypography.labelMono
                  .copyWith(color: AmiColors.textLow, fontSize: 11),
            ),
          ],
        ],
      ),
    );
  }

  /// Format "YYYY-MM-DD" → "Jul 25".
  static String? _fmtEarningsDate(String? iso) {
    if (iso == null) return null;
    try {
      final dt = DateTime.parse(iso);
      return DateFormat.MMMd().format(dt);
    } catch (_) {
      return iso;
    }
  }
}


/// CR100/CR030 — dividend sub-chip beside the earnings pill. The caller
/// already checks `hasDividendData`; this widget renders whichever of the
/// two fields is present (either alone is enough to show the chip).
class _DividendChip extends StatelessWidget {
  const _DividendChip({required this.earnings});

  final SimEarnings earnings;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final dateStr = _fmtDate(earnings.exDividendDate);
    final rate = earnings.dividendRate;
    return Container(
      padding: const EdgeInsets.symmetric(
          horizontal: AmiSpacing.m, vertical: AmiSpacing.s),
      decoration: BoxDecoration(
        color: AmiColors.hexGreen.withValues(alpha: 0.10),
        borderRadius: BorderRadius.circular(AmiRadii.card),
        border: Border.all(color: AmiColors.hexGreen.withValues(alpha: 0.45)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          const Icon(Icons.payments_outlined,
              color: AmiColors.hexGreen, size: 14),
          const SizedBox(width: AmiSpacing.s),
          if (dateStr != null)
            Text(
              l.tickerDetailDividendExDate(dateStr),
              style: AmiTypography.labelMono
                  .copyWith(color: AmiColors.hexGreen, fontSize: 11),
            ),
          if (dateStr != null && rate != null) const SizedBox(width: 6),
          if (rate != null)
            Text(
              l.tickerDetailDividendRate('\$${rate.toStringAsFixed(2)}'),
              style: AmiTypography.labelMono
                  .copyWith(color: AmiColors.textMed, fontSize: 11),
            ),
        ],
      ),
    );
  }

  /// Format "YYYY-MM-DD" → "Aug 15".
  static String? _fmtDate(String? iso) {
    if (iso == null) return null;
    try {
      final dt = DateTime.parse(iso);
      return DateFormat.MMMd().format(dt);
    } catch (_) {
      return iso;
    }
  }
}


/// CR100/CR029 — per-lot cost-basis cards, shown only for a held ticker.
/// Entry point into the FIFO reconstruction: each buy lot's entry, how much
/// is still open vs. closed, and its realised/unrealised P&L.
class _LotsSection extends ConsumerWidget {
  const _LotsSection({required this.ticker});

  final String ticker;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final lotsAsync = ref.watch(tickerLotsProvider(ticker));
    return lotsAsync.when(
      data: (h) => h.lots.isEmpty
          ? const SizedBox.shrink()
          : Padding(
              padding: const EdgeInsets.only(bottom: AmiSpacing.m),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    AppLocalizations.of(context).tickerDetailLotsHeading,
                    style: AmiTypography.labelMono,
                  ),
                  const SizedBox(height: AmiSpacing.s),
                  for (final lot in h.lots) _LotCard(lot: lot),
                ],
              ),
            ),
      loading: () => const SizedBox.shrink(),
      error: (_, __) => const SizedBox.shrink(),
    );
  }
}


class _LotCard extends StatelessWidget {
  const _LotCard({required this.lot});

  final Lot lot;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final fmt = NumberFormat('#,##0.00');
    final entryFmt = DateFormat.yMMMd();
    DateTime? entryDate;
    try {
      entryDate = DateTime.parse(lot.entryDate);
    } catch (_) {
      entryDate = null;
    }
    final realised = lot.realisedPnl;
    final realisedAccent = realised >= 0 ? AmiColors.hexGreen : AmiColors.hexRed;
    final unrealised = lot.unrealisedPnl;

    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Container(
        padding: const EdgeInsets.all(AmiSpacing.m),
        decoration: BoxDecoration(
          color: AmiColors.slate800,
          borderRadius: BorderRadius.circular(AmiRadii.card),
          border: Border.all(color: AmiColors.slate700),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Expanded(
                  child: Text(
                    l.tickerDetailLotEntry(
                      entryDate == null
                          ? lot.entryDate
                          : entryFmt.format(entryDate),
                      fmt.format(lot.entryPrice),
                    ),
                    style: AmiTypography.caption,
                  ),
                ),
                _LotStatusChip(status: lot.status),
              ],
            ),
            const SizedBox(height: 4),
            Text(
              l.tickerDetailLotQuantity(
                lot.quantityOpen.toStringAsFixed(2),
                lot.quantityClosed.toStringAsFixed(2),
              ),
              style: AmiTypography.caption.copyWith(color: AmiColors.textLow),
            ),
            const SizedBox(height: 4),
            Row(
              children: [
                Text(
                  l.tickerDetailLotRealised(
                    '${realised >= 0 ? '+' : ''}\$${fmt.format(realised)}',
                  ),
                  style: AmiTypography.labelMono
                      .copyWith(color: realisedAccent, fontSize: 11),
                ),
                const SizedBox(width: AmiSpacing.m),
                // CR029/CR100 — a closed lot's unrealised P&L is absent,
                // not zero; never coerce `unrealised` to 0.00 here.
                Text(
                  unrealised == null
                      ? l.tickerDetailLotUnrealisedUnknown
                      : l.tickerDetailLotUnrealised(
                          '${unrealised >= 0 ? '+' : ''}\$${fmt.format(unrealised)}',
                        ),
                  style: AmiTypography.labelMono.copyWith(
                    color: unrealised == null
                        ? AmiColors.textLow
                        : (unrealised >= 0 ? AmiColors.hexGreen : AmiColors.hexRed),
                    fontSize: 11,
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}


class _LotStatusChip extends StatelessWidget {
  const _LotStatusChip({required this.status});

  final String status;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final String label;
    final Color color;
    switch (status) {
      case 'open':
        label = l.tickerDetailLotStatusOpen;
        color = AmiColors.hexCyan;
        break;
      case 'closed':
        label = l.tickerDetailLotStatusClosed;
        color = AmiColors.textLow;
        break;
      default:
        label = l.tickerDetailLotStatusPartiallyClosed;
        color = AmiColors.hexAmber;
    }
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(4),
        border: Border.all(color: color.withValues(alpha: 0.5)),
      ),
      child: Text(
        label,
        style: AmiTypography.labelMono.copyWith(color: color, fontSize: 9),
      ),
    );
  }
}


/// News section: heading + up to 5 tappable article rows.
class _NewsSection extends StatelessWidget {
  const _NewsSection({required this.articles});

  final List<SimNewsArticle> articles;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          l.tickerDetailNewsHeading,
          style: AmiTypography.labelMono,
        ),
        const SizedBox(height: AmiSpacing.s),
        for (final a in articles) _NewsRow(article: a),
      ],
    );
  }
}


class _NewsRow extends StatelessWidget {
  const _NewsRow({required this.article});

  final SimNewsArticle article;

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: () {
        final uri = Uri.tryParse(article.link);
        if (uri != null) {
          launchUrl(uri, mode: LaunchMode.externalApplication);
        }
      },
      borderRadius: BorderRadius.circular(AmiRadii.card),
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: AmiSpacing.s),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              article.title,
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
              style: AmiTypography.body.copyWith(color: AmiColors.textHigh),
            ),
            const SizedBox(height: 3),
            Row(
              children: [
                Text(
                  article.publisher,
                  style: AmiTypography.caption.copyWith(fontSize: 11),
                ),
                const SizedBox(width: AmiSpacing.s),
                Text(
                  '·',
                  style: AmiTypography.caption.copyWith(
                      color: AmiColors.textLow, fontSize: 11),
                ),
                const SizedBox(width: AmiSpacing.s),
                Text(
                  _relativeTime(article.publishedAt),
                  style: AmiTypography.caption.copyWith(
                      color: AmiColors.textLow, fontSize: 11),
                ),
              ],
            ),
            const Divider(height: 12, color: AmiColors.slate700),
          ],
        ),
      ),
    );
  }

  static String _relativeTime(int epochSeconds) {
    final dt = DateTime.fromMillisecondsSinceEpoch(epochSeconds * 1000);
    final diff = DateTime.now().difference(dt);
    if (diff.inMinutes < 5) return 'just now';
    if (diff.inHours < 24) return '${diff.inHours}h ago';
    if (diff.inDays < 7) return '${diff.inDays}d ago';
    return DateFormat.MMMd().format(dt);
  }
}
