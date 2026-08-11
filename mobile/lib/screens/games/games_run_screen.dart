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
import 'package:ami_trade/screens/games/games_board_screen.dart';
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
                // Directly under the header, above the cash panel: at alpha
                // field sizes the duel IS the competition (§11.1), and
                // burying the only opponent the player has below their own
                // balance would make the screen about accounting again.
                if (detail.duel != null) ...[
                  const SizedBox(height: AmiSpacing.m),
                  _DuelCard(duel: detail.duel!, daysLeft: detail.daysLeft),
                ],
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
                  _Positions(detail: detail, runId: runId),
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
                const SizedBox(height: AmiSpacing.s),
                // The board is a separate screen rather than a section here:
                // it reads every entrant's NAV series, and this screen is
                // re-read on every size drag of the ticket.
                SizedBox(
                  width: double.infinity,
                  child: HexButton(
                    label: l.gamesBoardCta,
                    variant: HexButtonVariant.outlined,
                    onPressed: () =>
                        GamesBoardScreen.push(context, runId: runId),
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
/// The head-to-head — CR109 slice 3b, §11.1's *"You vs VECTOR_11. 3 days
/// left. They're 1.1% ahead"*.
///
/// Every number here is a PERCENTAGE. §6.1's invariant is that no entrant's
/// AMI Cash is ever rendered for anyone else, and a duel is the surface
/// where the temptation is strongest — it is the only place two books are
/// deliberately put side by side.
///
/// The lead is read from the server's signed [GameDuel.leadPct] rather than
/// subtracted here. A client that got the sign backwards would tell a losing
/// player they were ahead, which is a worse failure than showing nothing.
class _DuelCard extends StatelessWidget {
  const _DuelCard({required this.duel, this.daysLeft});
  final GameDuel duel;
  final int? daysLeft;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final lead = duel.leadPct;
    // Three states, not two. An UNKNOWN gap is drawn neutrally — never as
    // level, and never in the colour of a lead nobody has yet.
    final Color accent;
    final String line;
    if (lead == null) {
      accent = AmiColors.textLow;
      line = l.gamesDuelNotStarted;
    } else if (lead > 0) {
      accent = AmiColors.hexGreen;
      line = l.gamesDuelAhead(lead.abs().toStringAsFixed(2));
    } else if (lead < 0) {
      accent = AmiColors.hexRed;
      line = l.gamesDuelBehind(lead.abs().toStringAsFixed(2));
    } else {
      accent = AmiColors.textLow;
      line = l.gamesDuelLevel;
    }

    return GlassPanel(
      accentColor: accent,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Text(
                duel.isFirstRun
                    ? l.gamesDuelFirstRunHeading
                    : l.gamesDuelHeading,
                style: AmiTypography.labelMono
                    .copyWith(color: AmiColors.textLow),
              ),
              const Spacer(),
              if (duel.pointsAtStake != null)
                Text(
                  l.gamesDuelAtStake(duel.pointsAtStake!),
                  style: AmiTypography.caption,
                ),
            ],
          ),
          const SizedBox(height: AmiSpacing.xs),
          Text(
            l.gamesDuelVersus(duel.opponentHandle),
            style: AmiTypography.h4.copyWith(color: AmiColors.textHigh),
          ),
          // The desk's published rule, shown rather than hidden. The
          // first-run duel is "beat the Index Desk", and a player who did not
          // know their opponent was the benchmark would be reading a
          // different result than the one they got.
          if (duel.opponentIsDesk && duel.opponentDeskRule != null) ...[
            const SizedBox(height: AmiSpacing.xs),
            Text(duel.opponentDeskRule!, style: AmiTypography.caption),
          ],
          const SizedBox(height: AmiSpacing.s),
          Text(line, style: AmiTypography.body.copyWith(color: accent)),
          if (duel.isLive && daysLeft != null) ...[
            const SizedBox(height: AmiSpacing.xs),
            Text(l.gamesDuelDaysLeft(daysLeft!), style: AmiTypography.caption),
          ],
          if (!duel.isLive && duel.outcome != null) ...[
            const SizedBox(height: AmiSpacing.xs),
            Text(
              switch (duel.outcome!) {
                'won' => l.gamesDuelWon(duel.pointsDelta),
                'lost' => l.gamesDuelLost(duel.pointsDelta),
                'draw' => l.gamesDuelDraw,
                // A void is stated, never silently drawn as a draw — the run
                // was not measurable, which is a different thing from a tie.
                _ => l.gamesDuelVoid,
              },
              style: AmiTypography.caption,
            ),
          ],
        ],
      ),
    );
  }
}

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
  const _Positions({required this.detail, required this.runId});
  final GameRunDetail detail;
  final String runId;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    if (detail.holdings.isEmpty && detail.shorts.isEmpty) {
      return const SizedBox.shrink();
    }
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        if (detail.holdings.isNotEmpty) ...[
          Text(l.gamesRunPositionsHeading,
              style: AmiTypography.labelMono.copyWith(color: AmiColors.textLow)),
          const SizedBox(height: AmiSpacing.s),
          for (final h in detail.holdings)
            _PositionRow(holding: h, runId: runId),
        ],
        // Shorts sit under their own heading rather than mixed into the
        // list. They are a different instrument in the way that matters to
        // a player reading quickly: the P&L runs the other way, and the loss
        // has no floor. A row that looked like the ones above but behaved
        // backwards is exactly the misread this separation prevents.
        if (detail.shorts.isNotEmpty) ...[
          if (detail.holdings.isNotEmpty) const SizedBox(height: AmiSpacing.m),
          Text(l.gamesRunShortsHeading,
              style: AmiTypography.labelMono.copyWith(color: AmiColors.textLow)),
          const SizedBox(height: AmiSpacing.s),
          for (final s in detail.shorts) _ShortRow(short: s, runId: runId),
        ],
      ],
    );
  }
}

/// One open SHORT — CR109 Amendment G, and the only way out of one.
///
/// COVER buys the whole position back; there is no partial. The backend
/// refuses a partial cover for the same reason it refuses a sell that
/// crosses zero (one action, one cost basis), so the button offers what the
/// server will actually accept rather than letting the player discover the
/// rule as a rejected order.
class _ShortRow extends StatelessWidget {
  const _ShortRow({required this.short, required this.runId});
  final GameShort short;
  final String runId;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final pnl = short.unrealisedPnl;
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
                Row(
                  children: [
                    Text(short.ticker, style: AmiTypography.dataMd),
                    const SizedBox(width: AmiSpacing.xs),
                    // Labelled on the row itself, not only under the
                    // heading — a player scrolling past the heading must
                    // still be able to tell which way this position points.
                    Text(l.gamesShortBadge,
                        style: AmiTypography.caption
                            .copyWith(color: AmiColors.hexRed)),
                  ],
                ),
                Text(
                  l.gamesRunShortSub(
                    short.quantity.toStringAsFixed(4),
                    _money.format(short.entryPrice),
                  ),
                  style: AmiTypography.caption,
                ),
              ],
            ),
          ),
          Column(
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              Text(_money.format(short.value), style: AmiTypography.dataMd),
              Text(
                '$sign${_money.format(pnl.abs())} '
                '(${short.unrealisedPct.toStringAsFixed(1)}%)',
                style: AmiTypography.caption.copyWith(color: color),
              ),
            ],
          ),
          const SizedBox(width: AmiSpacing.s),
          HexButton(
            label: l.gamesCoverCta,
            variant: HexButtonVariant.outlined,
            onPressed: () => GamesTradeTicketScreen.show(
              context,
              runId: runId,
              coverTicker: short.ticker,
              coverQuantity: short.quantity,
            ),
          ),
        ],
      ),
    );
  }
}

/// One held position — and, since DEF259, the only way to get out of one.
///
/// The row shipped read-only for as long as the game has existed: the ticket
/// hard-coded `side: 'buy'` and nothing anywhere called the notifier's
/// `pickSide`, so a position could be opened and never closed. In a contest
/// scored on P&L that is not a missing convenience, it is a missing half of
/// the game — the only exit was the run ending.
class _PositionRow extends StatelessWidget {
  const _PositionRow({required this.holding, required this.runId});
  final GameHolding holding;
  final String runId;

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
          const SizedBox(width: AmiSpacing.s),
          // Per row, not one SELL button at the bottom: the thing being sold
          // is a specific position, and a ticket that opened without knowing
          // which would have to ask again.
          HexButton(
            label: l.gamesSellCta,
            variant: HexButtonVariant.outlined,
            onPressed: () => GamesTradeTicketScreen.show(
              context,
              runId: runId,
              sellTicker: holding.ticker,
              heldQuantity: holding.quantity,
            ),
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
