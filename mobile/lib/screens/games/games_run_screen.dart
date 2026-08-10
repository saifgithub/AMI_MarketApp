/// CR109 — "My run": the player's own book inside one live run.
///
/// Slice 2 shipped a State-B card carrying a return percentage and a Trade
/// button, and nothing else. Design §13.3 specifies four surfaces this
/// screen owes, three of which did not exist until now:
///
///   * **Queued orders** — §13.3 calls it *"the most-seen state in the
///     product"* for players in the Gulf and South-East Asia, because US
///     market hours are their evening and past-midnight. Pending fills,
///     estimated costs, cash committed, cancel any time.
///   * **The empty book** — §13.3: *"the highest-anxiety moment in the
///     product"*, and explicitly *"must not be a blank list."*
///   * **My run** — stake, return, days left, equity curve, book heat.
///   * The positions themselves.
///
/// Two of those absences were worse than missing UI. The ticket has
/// promised *"free to cancel any time before it fills"* (§5.1's own
/// wording) since the day it shipped, with no mechanism anywhere behind the
/// promise. And because queued orders committed no cash, the ticket offered
/// the full stake no matter how much was already queued against it — Saiful,
/// on build 74: *"This was the second order placed. But it is still showing
/// I have 10K. All the Account is wrong."*
///
/// Every number drawn here that came from an estimate says so. That is not
/// decoration: a queued order's cost is recomputed at the CURRENT price and
/// fills at the NEXT OPEN's, and CR040's rule is that the app degrades
/// loudly rather than letting an estimate read as a fact.
///
/// Unreachable in a store build — reached only from `games_home_screen.dart`
/// inside the `/games` subtree, which is const-folded out of any build
/// without `--dart-define=AMI_GAMES=true` (`features/games/games_gate.dart`).
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/games.dart';
import 'package:ami_trade/screens/games/games_trade_ticket_screen.dart';
import 'package:ami_trade/state/games_providers.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:ami_trade/widgets/games/games_close_curve.dart';
import 'package:ami_trade/widgets/hex/glass_panel.dart';
import 'package:ami_trade/widgets/hex/hex_button.dart';
import 'package:ami_trade/widgets/hex/hex_chip.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';

final _money = NumberFormat('#,##0.00');

class GamesRunScreen extends ConsumerWidget {
  const GamesRunScreen({super.key, required this.runId});

  final String runId;

  static Future<void> push(BuildContext context, {required String runId}) {
    return Navigator.of(context).push(
      MaterialPageRoute(builder: (_) => GamesRunScreen(runId: runId)),
    );
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l = AppLocalizations.of(context);
    final detailAsync = ref.watch(gamesRunDetailProvider(runId));

    return Scaffold(
      backgroundColor: AmiColors.slate900,
      appBar: AppBar(title: Text(l.gamesRunTitle)),
      body: SafeArea(
        child: detailAsync.when(
          loading: () => const Center(child: CircularProgressIndicator()),
          error: (_, __) => _Retry(
            onRetry: () => ref.invalidate(gamesRunDetailProvider(runId)),
          ),
          data: (detail) => RefreshIndicator(
            onRefresh: () async {
              ref.invalidate(gamesRunDetailProvider(runId));
              ref.invalidate(gamesQueuedOrdersProvider(runId));
            },
            child: ListView(
              padding: const EdgeInsets.all(AmiSpacing.m),
              children: [
                _Header(detail: detail),
                const SizedBox(height: AmiSpacing.m),
                _CashPanel(detail: detail),
                if (detail.navSeries.length >= 2) ...[
                  const SizedBox(height: AmiSpacing.m),
                  GamesCloseCurve(points: detail.navSeries),
                ],
                const SizedBox(height: AmiSpacing.m),
                _BookHeat(detail: detail),
                const SizedBox(height: AmiSpacing.l),
                if (detail.isEmptyBook)
                  _EmptyBook(detail: detail)
                else
                  _Positions(detail: detail),
                const SizedBox(height: AmiSpacing.l),
                _QueuedOrders(runId: runId),
                if (detail.tradeCount > 0) ...[
                  const SizedBox(height: AmiSpacing.l),
                  Text(
                    l.gamesRunFeesPaid(
                      _money.format(detail.feesPaid),
                      detail.tradeCount,
                    ),
                    style: AmiTypography.caption,
                  ),
                ],
                const SizedBox(height: AmiSpacing.l),
                SizedBox(
                  width: double.infinity,
                  child: HexButton(
                    label: l.gamesTradeCta.toUpperCase(),
                    color: AmiColors.hexGreen,
                    onPressed: () =>
                        GamesTradeTicketScreen.show(context, runId: runId),
                  ),
                ),
                const SizedBox(height: AmiSpacing.l),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _Retry extends StatelessWidget {
  const _Retry({required this.onRetry});
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(AmiSpacing.l),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(l.gamesLoadError,
                style: AmiTypography.body, textAlign: TextAlign.center),
            const SizedBox(height: AmiSpacing.m),
            HexButton(label: l.gamesRetry.toUpperCase(), onPressed: onRetry),
          ],
        ),
      ),
    );
  }
}

/// Book value, return, days left — and, when the marks behind that book
/// value came from the mock walk rather than the live feed, a line saying
/// so. A simulated valuation drawn as a real one is the CR040 failure.
class _Header extends StatelessWidget {
  const _Header({required this.detail});
  final GameRunDetail detail;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final twr = detail.twrPct ?? 0;
    final twrColor = twr >= 0 ? AmiColors.hexGreen : AmiColors.hexRed;
    final sign = twr >= 0 ? '+' : '';
    return GlassPanel(
      accentColor: AmiColors.hexGreen,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              HexChip(
                label: detail.cadence.toUpperCase(),
                color: AmiColors.hexGreen,
                variant: HexChipVariant.tinted,
              ),
              const Spacer(),
              if (detail.daysLeft != null)
                Text(l.gamesDaysLeft(detail.daysLeft!),
                    style: AmiTypography.caption),
            ],
          ),
          const SizedBox(height: AmiSpacing.s),
          Text(l.gamesRunBookValue, style: AmiTypography.caption),
          Text(
            _money.format(detail.stake),
            style: AmiTypography.statBig.copyWith(color: AmiColors.textHigh),
          ),
          const SizedBox(height: AmiSpacing.xs),
          Row(
            children: [
              Text(
                '$sign${twr.toStringAsFixed(2)}%',
                style: AmiTypography.dataMd.copyWith(color: twrColor),
              ),
              const SizedBox(width: AmiSpacing.s),
              Text(l.gamesTwrLabel, style: AmiTypography.caption),
            ],
          ),
          if (!detail.marksAreLive) ...[
            const SizedBox(height: AmiSpacing.s),
            _Caveat(text: l.gamesRunMarksStaleNote),
          ],
        ],
      ),
    );
  }
}

/// Cash, committed, available, invested — four numbers that must reconcile
/// on screen, because the first version of this screen showed one of them
/// and let the player infer the rest wrongly.
class _CashPanel extends StatelessWidget {
  const _CashPanel({required this.detail});
  final GameRunDetail detail;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final invested = detail.stake - detail.cash;
    return Container(
      padding: const EdgeInsets.all(AmiSpacing.m),
      decoration: BoxDecoration(
        color: AmiColors.slate800,
        borderRadius: BorderRadius.circular(AmiRadii.card),
        border: Border.all(color: AmiColors.slate700),
      ),
      child: Column(
        children: [
          _kv(l.gamesRunCashLabel, _money.format(detail.cash)),
          if (detail.cashCommitted > 0)
            _kv(
              l.gamesRunCommittedLabel,
              '−${_money.format(detail.cashCommitted)}',
              color: AmiColors.hexAmber,
            ),
          _kv(
            l.gamesRunAvailableLabel,
            _money.format(detail.cashAvailable),
            emphasis: true,
          ),
          if (invested > 0.005)
            _kv(l.gamesRunInvestedLabel, _money.format(invested)),
        ],
      ),
    );
  }

  Widget _kv(String k, String v, {Color? color, bool emphasis = false}) =>
      Padding(
        padding: const EdgeInsets.symmetric(vertical: 3),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Text(k, style: AmiTypography.caption),
            Text(
              v,
              style: (emphasis ? AmiTypography.dataMd : AmiTypography.bodySm)
                  .copyWith(color: color ?? AmiColors.textHigh),
            ),
          ],
        ),
      );
}

/// Design §10.4's book-heat gauge: what share of the book sits in its
/// single largest position.
///
/// A measurement, not a rule. The game has no diversification requirement
/// and this must never read as one — hence no red zone, no threshold, no
/// advice. It is the same mirror-surface posture CR134 §21 requires of the
/// modeled-cost line on the ticket: show the number, say nothing about it.
class _BookHeat extends StatelessWidget {
  const _BookHeat({required this.detail});
  final GameRunDetail detail;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final book = detail.stake;
    GameHolding? top;
    for (final h in detail.holdings) {
      if (top == null || h.marketValue > top.marketValue) top = h;
    }
    final pct = (top == null || book <= 0)
        ? 0.0
        : (top.marketValue / book * 100).clamp(0.0, 100.0);

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(l.gamesRunHeatHeading,
            style: AmiTypography.labelMono.copyWith(color: AmiColors.textLow)),
        const SizedBox(height: AmiSpacing.xs),
        ClipRRect(
          borderRadius: BorderRadius.circular(3),
          child: Stack(
            children: [
              Container(height: 6, color: AmiColors.slate700),
              FractionallySizedBox(
                widthFactor: (pct / 100).clamp(0.0, 1.0),
                child: Container(height: 6, color: AmiColors.hexCyan),
              ),
            ],
          ),
        ),
        const SizedBox(height: AmiSpacing.xs),
        Text(
          top == null
              ? l.gamesRunHeatAllCash
              : l.gamesRunHeatConcentration(
                  pct.toStringAsFixed(0), top.ticker),
          style: AmiTypography.caption,
        ),
      ],
    );
  }
}

class _Positions extends StatelessWidget {
  const _Positions({required this.detail});
  final GameRunDetail detail;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    if (detail.holdings.isEmpty) return const SizedBox.shrink();
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(l.gamesRunPositionsHeading,
            style: AmiTypography.labelMono.copyWith(color: AmiColors.textLow)),
        const SizedBox(height: AmiSpacing.s),
        for (final h in detail.holdings) _PositionRow(holding: h),
      ],
    );
  }
}

class _PositionRow extends StatelessWidget {
  const _PositionRow({required this.holding});
  final GameHolding holding;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final pnl = holding.unrealisedPnl;
    final color = pnl >= 0 ? AmiColors.hexGreen : AmiColors.hexRed;
    final sign = pnl >= 0 ? '+' : '−';
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: AmiSpacing.xs),
      child: Row(
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(holding.ticker, style: AmiTypography.dataMd),
                Text(
                  l.gamesRunPositionSub(
                    holding.quantity.toStringAsFixed(4),
                    _money.format(holding.avgCost),
                  ),
                  style: AmiTypography.caption,
                ),
              ],
            ),
          ),
          Column(
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              Text(_money.format(holding.marketValue),
                  style: AmiTypography.dataMd),
              Text(
                '$sign${_money.format(pnl.abs())} '
                '(${holding.unrealisedPct.toStringAsFixed(1)}%)',
                style: AmiTypography.caption.copyWith(color: color),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

/// §13.3's empty book — *"the highest-anxiety moment in the product"*, which
/// that section says explicitly must not be a blank list. What it asks for
/// is the clock, one action, and the honest note that nothing stops the
/// player putting the whole stake in one name.
///
/// The copy states the absence of rules as a fact and stops. It does not
/// suggest a size, a name, or a number of positions — the game is a
/// no-rules field by design (§7), and a nudge here would be advice, which
/// this product is not licensed to give.
class _EmptyBook extends StatelessWidget {
  const _EmptyBook({required this.detail});
  final GameRunDetail detail;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(AmiSpacing.m),
      decoration: BoxDecoration(
        color: AmiColors.slate800,
        borderRadius: BorderRadius.circular(AmiRadii.card),
        border: Border.all(color: AmiColors.slate700),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(l.gamesRunEmptyBookHeading, style: AmiTypography.h4),
          const SizedBox(height: AmiSpacing.xs),
          Text(
            l.gamesRunEmptyBookBody(
              _money.format(detail.cashAvailable),
              l.gamesRunDaysToDeploy(detail.daysLeft ?? 0),
            ),
            style: AmiTypography.body.copyWith(color: AmiColors.textLow),
          ),
        ],
      ),
    );
  }
}

/// §13.3's Queued-orders surface.
///
/// Its own provider rather than a slice of the run detail, because it is a
/// heavier call (it quotes every open order) and the ticket re-reads the run
/// detail on every size change.
class _QueuedOrders extends ConsumerWidget {
  const _QueuedOrders({required this.runId});
  final String runId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l = AppLocalizations.of(context);
    final ordersAsync = ref.watch(gamesQueuedOrdersProvider(runId));
    return ordersAsync.when(
      loading: () => const SizedBox.shrink(),
      // A failed orders call must not blank the section: the player has
      // orders they cannot see, and an empty space says the opposite.
      error: (_, __) => _Retry(
        onRetry: () => ref.invalidate(gamesQueuedOrdersProvider(runId)),
      ),
      data: (all) {
        if (all.isEmpty) return const SizedBox.shrink();
        final orders = all.where((o) => !o.isRefused).toList();
        // Orders the OPEN would not take. They live in the same payload
        // because they are the same objects at a later moment, but they are
        // a different kind of news — nothing is pending, nothing can be
        // cancelled, and the only useful thing is why.
        final refused = all.where((o) => o.isRefused).toList();
        final anyStale = orders.any((o) => !o.estimateIsLive);
        return Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            if (orders.isNotEmpty) ...[
              Text(
                l.gamesRunQueuedHeading,
                style:
                    AmiTypography.labelMono.copyWith(color: AmiColors.hexAmber),
              ),
              const SizedBox(height: AmiSpacing.s),
              for (final o in orders)
                _QueuedOrderRow(runId: runId, order: o),
              const SizedBox(height: AmiSpacing.xs),
              _Caveat(
                text: anyStale
                    ? l.gamesRunQueuedStaleNote
                    : l.gamesRunQueuedEstimateNote,
              ),
            ],
            if (refused.isNotEmpty) ...[
              const SizedBox(height: AmiSpacing.l),
              Text(
                l.gamesRunRefusedHeading,
                style:
                    AmiTypography.labelMono.copyWith(color: AmiColors.hexRed),
              ),
              const SizedBox(height: AmiSpacing.s),
              for (final o in refused) _RefusedOrderRow(order: o),
              const SizedBox(height: AmiSpacing.xs),
              Text(l.gamesRunRefusedNote, style: AmiTypography.caption),
            ],
          ],
        );
      },
    );
  }
}

class _QueuedOrderRow extends ConsumerStatefulWidget {
  const _QueuedOrderRow({required this.runId, required this.order});
  final String runId;
  final GameQueuedOrder order;

  @override
  ConsumerState<_QueuedOrderRow> createState() => _QueuedOrderRowState();
}

class _QueuedOrderRowState extends ConsumerState<_QueuedOrderRow> {
  bool _busy = false;

  Future<void> _cancel() async {
    final l = AppLocalizations.of(context);
    final o = widget.order;
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: AmiColors.slate800,
        title: Text(l.gamesRunCancelConfirmTitle, style: AmiTypography.h4),
        content: Text(
          l.gamesRunCancelConfirmBody(
            o.side.toUpperCase(),
            o.quantity.toStringAsFixed(4),
            o.ticker,
          ),
          style: AmiTypography.body,
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(false),
            child: Text(l.gamesRunCancelKeep),
          ),
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(true),
            child: Text(
              l.gamesRunCancelCta,
              style: const TextStyle(color: AmiColors.hexRed),
            ),
          ),
        ],
      ),
    );
    if (ok != true || !mounted) return;

    setState(() => _busy = true);
    // The server's own verdict, never "the request did not throw". An order
    // that filled between this list being drawn and the tap comes back
    // `cancelled: false` — telling the player it was cancelled would be the
    // same lie as the `status ?? 'filled'` default that shipped in build 74.
    var cancelled = false;
    try {
      cancelled = await cancelGamesQueuedOrder(
        ref,
        runId: widget.runId,
        orderId: o.orderId,
      );
    } finally {
      if (mounted) setState(() => _busy = false);
    }
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(cancelled
            ? l.gamesRunCancelledToast
            : l.gamesRunCancelRaceToast),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final o = widget.order;
    return Container(
      margin: const EdgeInsets.only(bottom: AmiSpacing.s),
      padding: const EdgeInsets.all(AmiSpacing.s),
      decoration: BoxDecoration(
        color: AmiColors.slate800,
        borderRadius: BorderRadius.circular(AmiRadii.card),
        border: Border.all(color: AmiColors.hexAmber.withValues(alpha: 0.35)),
      ),
      child: Row(
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  '${o.side.toUpperCase()} ${o.ticker}',
                  style: AmiTypography.dataMd,
                ),
                Text(
                  l.gamesRunQueuedSub(
                    o.quantity.toStringAsFixed(4),
                    _money.format(o.estTotal),
                  ),
                  style: AmiTypography.caption,
                ),
              ],
            ),
          ),
          if (_busy)
            const SizedBox(
              width: 18,
              height: 18,
              child: CircularProgressIndicator(strokeWidth: 2),
            )
          else
            TextButton(
              onPressed: _cancel,
              child: Text(
                l.gamesRunCancelCta,
                style: AmiTypography.caption
                    .copyWith(color: AmiColors.hexAmber),
              ),
            ),
        ],
      ),
    );
  }
}

/// A provenance line. Deliberately plain text in [AmiColors.hexAmber]
/// rather than a dimmed style — CR134: *"a dimmed mark reads as absent, not
/// small,"* so a caveat is stated, never faded.
class _Caveat extends StatelessWidget {
  const _Caveat({required this.text});
  final String text;

  @override
  Widget build(BuildContext context) {
    return Text(
      text,
      style: AmiTypography.caption.copyWith(color: AmiColors.hexAmber),
    );
  }
}


/// An order the open would not take.
///
/// It is on this list precisely BECAUSE it will not happen. The refusal
/// carries a perfectly good server-authored reason — *"insufficient cash:
/// need $500.00, have $12.00"* — and the orders list used to filter these
/// out, so the order simply vanished overnight: some filled, some gone,
/// nothing anywhere saying which or why. A thing that fails has to say so.
///
/// No Cancel action, deliberately. There is nothing left to cancel, and an
/// action that cannot act is worse than none.
class _RefusedOrderRow extends StatelessWidget {
  const _RefusedOrderRow({required this.order});

  final GameQueuedOrder order;

  @override
  Widget build(BuildContext context) {
    final o = order;
    return Container(
      margin: const EdgeInsets.only(bottom: AmiSpacing.s),
      padding: const EdgeInsets.all(AmiSpacing.s),
      decoration: BoxDecoration(
        color: AmiColors.slate800,
        borderRadius: BorderRadius.circular(AmiRadii.card),
        border: Border.all(color: AmiColors.hexRed.withValues(alpha: 0.35)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            '${o.side.toUpperCase()} ${o.ticker} · '
            '${o.quantity.toStringAsFixed(4)}',
            style: AmiTypography.dataMd,
          ),
          if (o.cancelReason != null)
            Text(
              o.cancelReason!,
              style: AmiTypography.caption.copyWith(color: AmiColors.hexRed),
            ),
        ],
      ),
    );
  }
}
