/// Sim Portfolio screen.
///
/// CR120 Phase 1 — three growing lists (holdings, watchlist, trade history)
/// used to render as one interleaved `ListView(children:)`. They are now
/// three segmented tabs — POSITIONS / WATCHLIST / HISTORY — each lazily
/// built, under a pinned value card that never scrolls away.
///
/// **Open trades live on the Positions (landing) tab, never History.** An
/// open trade is money at risk with a stop that can fire; History is closed
/// trades only, and its count excludes them (§4.1). Closed trades default to
/// the last 25 with the covered span stated as dates — a view default with
/// an in-place `SHOW ALL` escape hatch onto the Portfolio's own data, never
/// a fetch limit (§2, §3). The win/loss/hit-rate/net summary above the cap
/// is computed over every closed trade, not the visible slice.
///
/// Tab selection is `State`, nothing more — no `SharedPreferences` key, no
/// persistence across cold start (D5). `home_shell.dart` already wraps the
/// five nav destinations in an `IndexedStack`, so this State (and therefore
/// the selected tab) survives in-app navigation and bottom-nav round trips
/// for free, and resets to Positions on a fresh launch.
///
/// Pull-to-refresh re-evaluates open trades server-side (stop/target sweep)
/// so trades that hit while the user is on this screen show as won/lost.
library;

import 'dart:math' as math;

import 'package:ami_trade/features/tour/portfolio_tour.dart';
import 'package:ami_trade/features/nav/ami_tab.dart';
import 'package:ami_trade/features/tour/tour_providers.dart';
import 'package:ami_trade/features/tour/tour_service.dart';
import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/sim.dart';
import 'package:ami_trade/models/watchlist.dart';
import 'package:ami_trade/screens/sim/ticker_detail_screen.dart';
import 'package:ami_trade/screens/sim/trade_ticket_sheet.dart';
import 'package:ami_trade/models/alpaca.dart';
import 'package:ami_trade/services/ads/ads_models.dart';
import 'package:ami_trade/state/alpaca_providers.dart';
import 'package:ami_trade/state/journal_providers.dart';
import 'package:ami_trade/state/onboarding_providers.dart';
import 'package:ami_trade/state/sim_providers.dart';
import 'package:ami_trade/widgets/sim/resting_orders_section.dart';
import 'package:ami_trade/widgets/sim/short_positions_section.dart';
import 'package:ami_trade/state/watchlist_providers.dart';
import 'package:ami_trade/screens/you/you_providers.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:ami_trade/widgets/hex/ami_screen_header.dart';
import 'package:ami_trade/theme/hex_clipper.dart';
import 'package:ami_trade/widgets/ads/ad_slot.dart';
import 'package:ami_trade/widgets/empty_state.dart';
import 'package:ami_trade/widgets/hex/hex_button.dart';
import 'package:ami_trade/widgets/hex/hex_chip.dart';
import 'package:ami_trade/widgets/hex/hex_toast.dart';
import 'package:ami_trade/widgets/portfolio_equity_chart.dart';
import 'package:ami_trade/widgets/portfolio_health/health_card.dart';
import 'package:ami_trade/widgets/ticker_not_found_panel.dart';
import 'package:ami_trade/widgets/trade_row.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';
import 'package:tutorial_coach_mark/tutorial_coach_mark.dart';

/// Wraps a numeric run (sign + digits, optionally a parenthesised percent)
/// in Unicode directional isolates so RTL reordering cannot scramble it.
/// CR106's T-BIDI trap, live in the prototype: `+$5,423.69 (+5.33%)`
/// reordered to `(5.33%+` under `dir: rtl`. The layout mirrors; the digits
/// must not.
String _isolateNumeric(String s) => '\u2066$s\u2069';

const int _closedTradeCap = 25;

class PortfolioScreen extends ConsumerStatefulWidget {
  const PortfolioScreen({super.key});

  @override
  ConsumerState<PortfolioScreen> createState() => _PortfolioScreenState();
}

class _PortfolioScreenState extends ConsumerState<PortfolioScreen> {
  final _headerKey = GlobalKey();
  final _valueCardKey = GlobalKey();
  final _watchlistTabKey = GlobalKey();

  // CR120/D5 — tab selection is State and nothing else. No prefs key, no
  // staleness rule, none of CR106's T-MODESIDE trap surface. Doing nothing
  // beyond this int is the whole implementation.
  int _selectedTab = 0;

  void _runTour() {
    final l = AppLocalizations.of(context);
    TutorialCoachMark(
      targets: buildPortfolioTargets(
        l: l,
        headerKey: _headerKey,
        valueCardKey: _valueCardKey,
        // CR120 — the watchlist section moved to its own tab, so the tour
        // now points at the tab-bar segment (always on-screen from
        // Positions) rather than content that may be off the active tab.
        watchlistKey: _watchlistTabKey,
      ),
      hideSkip: true,
      colorShadow: Colors.black,
      opacityShadow: 0.88,
      pulseEnable: false,
      beforeFocus: (target) async {
        final ctx = target.keyTarget?.currentContext;
        if (ctx == null) return;
        final contents = target.contents ?? const [];
        final tooltipAbove =
            contents.isNotEmpty && contents.first.align == ContentAlign.top;
        await Scrollable.ensureVisible(
          ctx,
          duration: const Duration(milliseconds: 350),
          alignment: tooltipAbove ? 0.85 : 0.15,
        );
      },
      onFinish: () {
        if (!mounted) return;
        HexToast.show(
          context,
          AppLocalizations.of(context).tourCompletionPortfolio,
          accent: AmiColors.hexCyan,
          icon: Icons.check_circle_outline,
        );
      },
    ).show(context: context);
  }

  @override
  Widget build(BuildContext context) {
    // Fire tour when Portfolio tab (index 1) becomes active for the first time.
    ref.listen<AmiTab>(activeTabProvider, (prev, next) async {
      if (next != AmiTab.portfolio) return;
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
            AmiScreenHeader(
              key: _headerKey,
              title: AppLocalizations.of(context).portfolioHeading,
              titleColor: AmiColors.hexCyan,
              actions: [
                IconButton(
                  icon: const Icon(Icons.add_circle_outline,
                      color: AmiColors.hexCyan),
                  tooltip:
                      AppLocalizations.of(context).portfolioNewTradeTooltip,
                  onPressed: () => TradeTicketSheet.show(context),
                ),
              ],
            ),
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
      // DEF254 — the copy said "Try again." and there was nothing to tap; the
      // user's only recourse was to leave the tab and come back. The button
      // renders only when `errorRetryable` says the same request could
      // succeed, so the sentence and the affordance are decided by one call
      // (`isRetryable`, in `SimNotifier.refresh`) rather than two places.
      final l = AppLocalizations.of(context);
      return Padding(
        padding: const EdgeInsets.all(AmiSpacing.l),
        child: Center(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(state.error!,
                  style: AmiTypography.body, textAlign: TextAlign.center),
              if (state.errorRetryable) ...[
                const SizedBox(height: AmiSpacing.l),
                HexButton(
                  label: l.portfolioRetry,
                  onPressed: () =>
                      ref.read(simNotifierProvider.notifier).refresh(),
                ),
              ],
            ],
          ),
        ),
      );
    }
    final p = state.portfolio;
    if (p == null) return const SizedBox.shrink();

    // CR188 slice 3 — `status` is NOT a position predicate. It carries "the
    // ledger still needs this row"; the screen used to read it as "there is a
    // live position here", and those stopped being the same thing when slice 2
    // made ticket-sell the only exit. A BUY row deliberately outlives its
    // shares (closing it would double-subtract the exit — DEF316), and a SELL
    // row is `open` forever by design (DEF319's premise).
    //
    // So Positions renders from HOLDINGS and History is a TRANSACTION LOG —
    // every fill, buys and sells, because a purchase happened whether or not
    // the ledger still needs its row. Neither tab consults `status`.
    final transactions = state.trades.toList()
      ..sort((a, b) =>
          (b.closedAt ?? b.openedAt).compareTo(a.closedAt ?? a.openedAt));

    return RefreshIndicator(
      color: AmiColors.hexCyan,
      onRefresh: () async {
        await Future.wait<void>([
          ref.read(simNotifierProvider.notifier).refresh(),
          ref.read(watchlistNotifierProvider.notifier).refresh(),
        ]);
        ref.invalidate(alpacaStatusProvider);
        ref.invalidate(alpacaPortfolioProvider);
        ref.invalidate(alpacaPositionsProvider);
      },
      child: Column(
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(
              AmiSpacing.m,
              AmiSpacing.m,
              AmiSpacing.m,
              AmiSpacing.s,
            ),
            child: _ValueCard(key: _valueCardKey, portfolio: p),
          ),
          _PortfolioTabBar(
            watchlistTabKey: _watchlistTabKey,
            selected: _selectedTab,
            onSelect: (i) => setState(() => _selectedTab = i),
            positionsCount: p.holdings.length + p.shorts.length,
            watchlistCount: restingOrderCount(state),
            historyCount: transactions.length,
            hasOpenTrade: p.holdings.isNotEmpty ||
                p.shorts.isNotEmpty ||
                hasAnyRestingOrders(state),
          ),
          Expanded(
            // CR120/D5 — same IndexedStack technique home_shell.dart already
            // uses for the bottom-nav tabs: every segment's State lives for
            // the whole time PortfolioScreen is mounted, so switching
            // segments never rebuilds the others from scratch, and the
            // in-place SHOW ALL expansion on History survives a trip to
            // another segment and back.
            child: IndexedStack(
              index: _selectedTab,
              children: [
                _PositionsTab(
                  holdings: p.holdings,
                  // CR170 — a user whose only activity is a resting order has
                  // traded; telling them otherwise is a hint that contradicts
                  // the Orders tab beside it.
                  hasRestingOrders: hasAnyRestingOrders(state),
                  hasShorts: p.shorts.isNotEmpty,
                  sharesCommitted: p.sharesCommitted,
                  onTradeTicket: () => TradeTicketSheet.show(context),
                ),
                const _OrdersTab(),
                _HistoryTab(closedTrades: transactions, watchlist: watchlist),
              ],
            ),
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
    final pnlText = _isolateNumeric(
      '${pnl >= 0 ? '+' : ''}\$${fmt.format(pnl)} '
      '(${pnlPct >= 0 ? '+' : ''}${pnlPct.toStringAsFixed(2)}%)',
    );
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
                  style: AmiTypography.labelMono
                      .copyWith(color: AmiColors.hexCyan)),
              const Spacer(),
              _QuoteSourcePill(portfolio: portfolio),
            ],
          ),
          const SizedBox(height: AmiSpacing.xs),
          // CR014/D3: count-up on change. No `begin` ⇒ no sweep on first open;
          // a changed total animates from the previous frame's value.
          TweenAnimationBuilder<double>(
            tween: Tween<double>(end: portfolio.totalValue),
            duration: const Duration(milliseconds: 400),
            curve: Curves.easeOutCubic,
            builder: (context, value, _) => Text('\$${fmt.format(value)}',
                style:
                    AmiTypography.statBig.copyWith(color: AmiColors.textHigh)),
          ),
          const SizedBox(height: AmiSpacing.s),
          Row(
            children: [
              Icon(
                pnl >= 0 ? Icons.trending_up : Icons.trending_down,
                color: accent,
                size: 16,
              ),
              const SizedBox(width: 4),
              // CR120/§9 acceptance 9 — a bare Text here has no width bound;
              // a Spacer only claims leftover space, it does not shrink its
              // siblings, so a long P&L run (or 1.15 text scale) overflowed
              // the row instead of clipping cleanly. Flexible + ellipsis
              // keeps this row from ever throwing a RenderFlex error.
              Flexible(
                child: Text(
                  pnlText,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: AmiTypography.statSmall.copyWith(color: accent),
                ),
              ),
              const SizedBox(width: AmiSpacing.s),
              Text(AppLocalizations.of(context).portfolioCash,
                  style: AmiTypography.labelMono.copyWith(fontSize: 10)),
              const SizedBox(width: 6),
              Flexible(
                child: Text(
                  '\$${fmt.format(portfolio.currentCash)}',
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  textAlign: TextAlign.end,
                  style: AmiTypography.statSmall,
                ),
              ),
            ],
          ),
          // CR170 §6 — cash the resting book has spoken for. Shown only when
          // there IS a book: on a portfolio with no working orders, COMMITTED
          // $0 / AVAILABLE $x is two labels restating the cash figure directly
          // above them.
          if (portfolio.restingOrderCount > 0) ...[
            const SizedBox(height: AmiSpacing.xs),
            Row(
              children: [
                Text(AppLocalizations.of(context).portfolioCashCommitted,
                    style: AmiTypography.labelMono.copyWith(fontSize: 10)),
                const SizedBox(width: 6),
                Flexible(
                  child: Text(
                    '\$${fmt.format(portfolio.cashCommitted)}',
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: AmiTypography.caption
                        .copyWith(color: AmiColors.hexCyan),
                  ),
                ),
                const SizedBox(width: AmiSpacing.s),
                Text(AppLocalizations.of(context).portfolioCashAvailable,
                    style: AmiTypography.labelMono.copyWith(fontSize: 10)),
                const SizedBox(width: 6),
                Flexible(
                  child: Text(
                    '\$${fmt.format(portfolio.cashAvailable)}',
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    textAlign: TextAlign.end,
                    style: AmiTypography.caption.copyWith(
                      color: portfolio.isOverCommitted
                          ? AmiColors.hexAmber
                          : AmiColors.textHigh,
                    ),
                  ),
                ),
              ],
            ),
            // The server deliberately does not floor `cash_available` at zero,
            // so that this state is reachable and visible rather than hidden
            // behind a clamp. Saying nothing here would waste that.
            if (portfolio.isOverCommitted) ...[
              const SizedBox(height: AmiSpacing.xs),
              Text(
                AppLocalizations.of(context).portfolioOverCommitted(
                  fmt.format(portfolio.cashAvailable.abs()),
                ),
                style:
                    AmiTypography.caption.copyWith(color: AmiColors.hexAmber),
              ),
            ],
          ],
          if (portfolio.drawdownPct > 0) ...[
            const SizedBox(height: AmiSpacing.xs),
            Text(
              AppLocalizations.of(context).portfolioDrawdown(
                portfolio.drawdownPct.toStringAsFixed(1),
              ),
              style: AmiTypography.caption.copyWith(
                color: portfolio.drawdownPct > 20
                    ? AmiColors.hexAmber
                    : AmiColors.textLow,
              ),
            ),
          ],
        ],
      ),
    );
  }
}

// ── Segmented tab bar (CR120/D1) ────────────────────────────────────────
//
// One `ClipPath` around the whole bar — not one per segment. Two
// independently-clipped segments are two chips with a gap between them,
// whatever their geometry (DEF146), which is exactly the "not hex design"
// report this same shape produced on the Room's BOARD|TRANSCRIPT toggle.
// `room_view_mode_toggle.dart` is the worked example this copies.

class _PortfolioTabBar extends StatelessWidget {
  const _PortfolioTabBar({
    required this.watchlistTabKey,
    required this.selected,
    required this.onSelect,
    required this.positionsCount,
    required this.watchlistCount,
    required this.historyCount,
    required this.hasOpenTrade,
  });

  final GlobalKey watchlistTabKey;
  final int selected;
  final ValueChanged<int> onSelect;
  final int positionsCount;
  final int watchlistCount;
  final int historyCount;
  final bool hasOpenTrade;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    return Container(
      height: 44,
      padding:
          const EdgeInsets.symmetric(horizontal: AmiSpacing.m, vertical: 6),
      decoration: const BoxDecoration(
        color: AmiColors.glassChrome,
        border: Border(bottom: BorderSide(color: AmiColors.slate700)),
      ),
      child: ClipPath(
        clipper: const FlatTopHexagonBarClipper(endInset: 8),
        child: Row(
          children: [
            Expanded(
              child: _TabSegment(
                label: '${l.portfolioTabPositions} $positionsCount',
                active: selected == 0,
                onTap: () => onSelect(0),
                trailing: hasOpenTrade ? _LivePip(active: selected == 0) : null,
              ),
            ),
            Container(width: 1, height: 32, color: AmiColors.slate700),
            Expanded(
              key: watchlistTabKey,
              child: _TabSegment(
                label: '${l.portfolioTabOrders} $watchlistCount',
                active: selected == 1,
                onTap: () => onSelect(1),
              ),
            ),
            Container(width: 1, height: 32, color: AmiColors.slate700),
            Expanded(
              child: _TabSegment(
                label: '${l.portfolioTabHistory} $historyCount',
                active: selected == 2,
                onTap: () => onSelect(2),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _TabSegment extends StatelessWidget {
  const _TabSegment({
    required this.label,
    required this.active,
    required this.onTap,
    this.trailing,
  });

  final String label;
  final bool active;
  final VoidCallback onTap;
  final Widget? trailing;

  @override
  Widget build(BuildContext context) {
    return Semantics(
      selected: active,
      button: true,
      child: GestureDetector(
        onTap: onTap,
        behavior: HitTestBehavior.opaque,
        // DEF146 — no clipper, no border, no FittedBox here. The parent
        // clips the whole bar; shrinking the label to fit is CR108's
        // failure over again — the bar is sized so it does not have to.
        child: AnimatedContainer(
          duration: AmiMotion.normal,
          curve: AmiMotion.easeOut,
          height: 32,
          alignment: Alignment.center,
          color: active ? AmiColors.hexBlue : AmiColors.slate800,
          child: Row(
            mainAxisSize: MainAxisSize.min,
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Flexible(
                child: Text(
                  label,
                  maxLines: 1,
                  softWrap: false,
                  overflow: TextOverflow.visible,
                  style: AmiTypography.labelMono.copyWith(
                    fontSize: 10,
                    color: active ? Colors.white : AmiColors.textMed,
                  ),
                ),
              ),
              if (trailing != null) ...[
                const SizedBox(width: 4),
                trailing!,
              ],
            ],
          ),
        ),
      ),
    );
  }
}

/// The Positions tab's live indicator — present whenever the user has money at
/// risk, whether or not Positions is the selected segment (§4.1/2b). Cyan,
/// never amber: an open position is a state, not a warning.
///
/// CR188 slice 3 — that used to mean "an open trade row exists", which stopped
/// implying live risk: a BUY row outlives its shares by design and a SELL row
/// is `open` forever. It now means a holding, a short, or a working order.
class _LivePip extends StatelessWidget {
  const _LivePip({required this.active});
  final bool active;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: 6,
      height: 6 / (2 / math.sqrt(3)),
      child: ClipPath(
        clipper: const FlatTopRegularHexagon(),
        child: ColoredBox(
          color: active ? AmiColors.textHigh : AmiColors.hexCyan,
        ),
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
          const Icon(Icons.lightbulb_outline,
              color: AmiColors.hexCyan, size: 32),
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

/// CR188 slice 3 — a position, dense by default and expandable in place.
///
/// Saiful: *"Have the tiles small enough to show a lot of tiles, and make them
/// expandable to see details."* Collapsed is one line so a whole book is
/// scannable (CR120 acceptance 1 pins this tab at ≤ 4 screens); tapping opens
/// the numbers underneath rather than navigating away, so comparing two
/// positions costs no screen transitions.
///
/// The **stop chip is the protection indicator** and it carries CR189's
/// position-level level — blended across live lots, server-derived off the same
/// `blended_bracket` the sweep fires on. Its absence is information too: a
/// position with no stop shows no chip, and says so when opened.
class _HoldingCard extends StatefulWidget {
  const _HoldingCard({required this.holding, this.committed = 0});
  final SimHolding holding;

  /// CR170 §6 — shares of this ticker a live resting SELL has spoken for.
  final double committed;

  @override
  State<_HoldingCard> createState() => _HoldingCardState();
}

class _HoldingCardState extends State<_HoldingCard> {
  bool _open = false;

  @override
  Widget build(BuildContext context) {
    final h = widget.holding;
    final l = AppLocalizations.of(context);
    final pnl = h.unrealisedPnl;
    final pct =
        h.avgCost == 0 ? 0.0 : ((h.mark - h.avgCost) / h.avgCost) * 100;
    final accent = pnl >= 0 ? AmiColors.hexGreen : AmiColors.hexRed;
    final fmt = NumberFormat('#,##0.00');

    return Padding(
      padding: const EdgeInsets.only(bottom: 6),
      child: InkWell(
        onTap: () => setState(() => _open = !_open),
        borderRadius: BorderRadius.circular(AmiRadii.card),
        child: Container(
          padding: const EdgeInsets.symmetric(
            horizontal: AmiSpacing.m,
            vertical: AmiSpacing.s,
          ),
          decoration: BoxDecoration(
            color: AmiColors.slate800,
            borderRadius: BorderRadius.circular(AmiRadii.card),
            border: Border.all(
              color: _open ? AmiColors.hexCyan.withValues(alpha: 0.45)
                           : AmiColors.slate700,
            ),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  SizedBox(
                    width: 66,
                    child: Text(h.ticker,
                        style: AmiTypography.statMid
                            .copyWith(color: AmiColors.textHigh)),
                  ),
                  Expanded(
                    child: Text(
                      '${h.quantity.toStringAsFixed(0)} sh · \$${fmt.format(h.avgCost)}',
                      style: AmiTypography.caption,
                    ),
                  ),
                  if (h.stop != null) ...[
                    HexChip(
                      label:
                          '${l.tradeTicketLabelStop} \$${fmt.format(h.stop)}',
                      color: AmiColors.hexAmber,
                      variant: HexChipVariant.tinted,
                      fontSize: 10,
                    ),
                    const SizedBox(width: AmiSpacing.s),
                  ],
                  Text(
                    _isolateNumeric(
                      '${pct >= 0 ? '+' : ''}${pct.toStringAsFixed(1)}%',
                    ),
                    style: AmiTypography.labelMono
                        .copyWith(color: accent, fontSize: 12),
                  ),
                  Icon(_open ? Icons.expand_more : Icons.chevron_right,
                      color: AmiColors.textLow, size: 18),
                ],
              ),
              if (_open) ..._detail(context, h, l, fmt, accent, pnl),
            ],
          ),
        ),
      ),
    );
  }

  List<Widget> _detail(
    BuildContext context,
    SimHolding h,
    AppLocalizations l,
    NumberFormat fmt,
    Color accent,
    double pnl,
  ) {
    String away(double level) {
      final d = (h.mark - level).abs() / (h.mark == 0 ? 1 : h.mark) * 100;
      return l.positionDistanceAway('${d.toStringAsFixed(1)}%');
    }

    return [
      const Padding(
        padding: EdgeInsets.symmetric(vertical: AmiSpacing.s),
        child: Divider(height: 1, color: AmiColors.slate700),
      ),
      Text(
        _isolateNumeric(
          '\$${fmt.format(h.mark)} · \$${fmt.format(h.value)} · '
          '${pnl >= 0 ? '+' : ''}\$${fmt.format(pnl)}',
        ),
        style: AmiTypography.labelMono.copyWith(color: accent, fontSize: 12),
      ),
      const SizedBox(height: 4),
      // CR189 — the POSITION's levels, not any one lot's. Distance is the
      // number a user actually acts on; the price alone does not say how close
      // they are to losing the position.
      if (h.stop != null)
        Text(
          _isolateNumeric(
            '${l.tradeTicketLabelStop} \$${fmt.format(h.stop)} — ${away(h.stop!)}',
          ),
          style: AmiTypography.caption.copyWith(color: AmiColors.hexAmber),
        ),
      if (h.target != null)
        Text(
          _isolateNumeric(
            '${l.tradeTicketLabelTarget} \$${fmt.format(h.target)} — ${away(h.target!)}',
          ),
          style: AmiTypography.caption.copyWith(color: AmiColors.hexGreen),
        ),
      // Stated, never warned about. A missing stop is a fact about the
      // position; telling the user what to do about it would be advice, and
      // this app does not give any.
      if (!h.isProtected)
        Text(l.positionUnprotected,
            style: AmiTypography.caption.copyWith(color: AmiColors.textLow)),
      if (widget.committed > 0)
        Text(
          l.portfolioSharesCommitted(widget.committed.toStringAsFixed(0)),
          style: AmiTypography.caption.copyWith(color: AmiColors.hexCyan),
        ),
      const SizedBox(height: AmiSpacing.s),
      Row(
        children: [
          _TileAction(
            label: l.positionSell,
            onTap: () => TradeTicketSheet.show(
              context,
              sellTicker: h.ticker,
              sellQuantity: h.quantity,
            ),
          ),
          const SizedBox(width: AmiSpacing.s),
          _TileAction(
            label: l.positionPerLotDetail,
            onTap: () => Navigator.of(context).push(MaterialPageRoute<void>(
              builder: (_) => TickerDetailScreen(ticker: h.ticker),
            )),
          ),
        ],
      ),
    ];
  }
}

class _TileAction extends StatelessWidget {
  const _TileAction({required this.label, required this.onTap});
  final String label;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(4),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
        decoration: BoxDecoration(
          border: Border.all(color: AmiColors.hexCyan.withValues(alpha: 0.5)),
          borderRadius: BorderRadius.circular(4),
        ),
        child: Text(label,
            style: AmiTypography.labelMono
                .copyWith(color: AmiColors.hexCyan, fontSize: 11)),
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

// ── Positions tab (holdings + open trades) — CR120 §4.1 ─────────────────

class _PositionsTab extends StatelessWidget {
  const _PositionsTab({
    required this.holdings,
    required this.hasRestingOrders,
    required this.hasShorts,
    required this.sharesCommitted,
    required this.onTradeTicket,
  });

  final List<SimHolding> holdings;
  final bool hasRestingOrders;

  /// CR171 — an open short is a position, and it lives in its own table rather
  /// than in [holdings]. Without this the new-trader hint would tell a user
  /// with a live short that they have not traded yet.
  final bool hasShorts;

  /// CR170 §6 — per-ticker shares committed to resting sells, as the server
  /// computed them. Threaded down rather than watched per row: one read of
  /// the provider, not one per holding.
  final Map<String, double> sharesCommitted;
  final VoidCallback onTradeTicket;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    return CustomScrollView(
      key: const PageStorageKey('portfolioPositionsScroll'),
      slivers: [
        SliverPadding(
          padding: const EdgeInsets.all(AmiSpacing.m),
          sliver: SliverToBoxAdapter(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // CR109 slice 1 — the equity curve. Training-portfolio only,
                // additive: no game surface, no new nav destination.
                const PortfolioEquityChart(),
                const _SectorAllocationSection(),
                const PortfolioHealthCard(),
                // Below the book, above holdings: a short is a live position
                // like a holding, but it is not one — the user owes the
                // shares — so it gets its own group rather than a row inside
                // HOLDINGS with a badge on it.
                const ShortPositionsSection(),
                if (holdings.isEmpty && !hasRestingOrders && !hasShorts) ...[
                  _NewTraderHint(onTradeTicket: onTradeTicket),
                  // CR122 — Sim Portfolio empty state (no positions) is an
                  // approved ad placement (ads.md:42). Self-gating slot.
                  const AdSlot(
                      placement: AdPlacement.simPortfolioEmptyState),
                ] else ...[
                  const SizedBox(height: AmiSpacing.s),
                  if (holdings.isNotEmpty)
                    Padding(
                      padding:
                          const EdgeInsets.symmetric(vertical: AmiSpacing.s),
                      child: Text(l.portfolioHoldings,
                          style: AmiTypography.labelMono),
                    ),
                ],
              ],
            ),
          ),
        ),
        if (holdings.isNotEmpty)
          SliverPadding(
            padding: const EdgeInsets.symmetric(horizontal: AmiSpacing.m),
            sliver: SliverList.builder(
              itemCount: holdings.length,
              itemBuilder: (context, i) => _HoldingCard(
                holding: holdings[i],
                committed:
                    sharesCommitted[holdings[i].ticker.toUpperCase()] ?? 0,
              ),
            ),
          ),
        const SliverPadding(
          padding: EdgeInsets.symmetric(horizontal: AmiSpacing.m),
          sliver: SliverToBoxAdapter(child: _AlpacaPortfolioSection()),
        ),
        const SliverToBoxAdapter(child: SizedBox(height: AmiSpacing.m)),
      ],
    );
  }
}

// ── Sector allocation donut (CR100/CR026) — now inside Positions ────────

class _SectorAllocationSection extends ConsumerWidget {
  const _SectorAllocationSection();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final async = ref.watch(sectorAllocationProvider);
    return async.when(
      data: (a) => a.allocation.isEmpty
          ? const SizedBox.shrink()
          : _SectorAllocationCard(allocation: a),
      loading: () => const SizedBox.shrink(),
      error: (_, __) => const SizedBox.shrink(),
    );
  }
}

class _SectorAllocationCard extends StatelessWidget {
  const _SectorAllocationCard({required this.allocation});

  final SectorAllocation allocation;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final compliance = allocation.compliance;
    // Deterministic order: known sectors by descending weight, "Other" last
    // — keeps the legend stable across refreshes and the disclosed
    // unclassified bucket visually distinct from the ranked sectors.
    final entries = allocation.allocation.entries.toList()
      ..sort((a, b) {
        if (a.key == 'Other') return 1;
        if (b.key == 'Other') return -1;
        return b.value.compareTo(a.value);
      });

    return Container(
      padding: const EdgeInsets.all(AmiSpacing.m),
      decoration: BoxDecoration(
        color: AmiColors.slate800,
        borderRadius: BorderRadius.circular(AmiRadii.card),
        border: Border.all(color: AmiColors.slate700),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(l.portfolioSectorAllocationHeading,
              style: AmiTypography.labelMono),
          const SizedBox(height: AmiSpacing.s),
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              SizedBox(
                width: 72,
                height: 72,
                child: CustomPaint(
                  painter: _DonutPainter(entries: entries),
                ),
              ),
              const SizedBox(width: AmiSpacing.m),
              Expanded(child: _SectorLegend(entries: entries)),
            ],
          ),
          // Breach line reads straight off the response — never re-derives
          // "Other" into a breach (DEF059 inversion guard) and never
          // hard-codes the 0.40 mandate default.
          if (!compliance.compliant && compliance.maxSectorName != null) ...[
            const SizedBox(height: AmiSpacing.s),
            Text(
              l.portfolioSectorBreach(
                compliance.maxSectorName!,
                (compliance.maxSector * 100).toStringAsFixed(0),
                (compliance.maxAllowed * 100).toStringAsFixed(0),
              ),
              style: AmiTypography.caption.copyWith(color: AmiColors.hexRed),
            ),
          ],
        ],
      ),
    );
  }
}

/// CR118: the legend used to render every sector inline, so the card's height
/// was a function of how diversified the portfolio is — the one thing the
/// product tells the user to increase. At the GICS level the backend
/// classifies to, a well-spread portfolio reaches 11 sectors plus Cash plus
/// Other, which pushed holdings and trades off the first screen.
///
/// Fixed, not maximum: the card's footprint is constant whatever the
/// allocation. Rows have a fixed extent so "does it scroll" is arithmetic
/// rather than text measurement, which is what makes it testable.
const double _kSectorLegendRowHeight = 22;

/// 4.5 rows. The half-row at the cut IS the scroll affordance — a list clipped
/// with no cue reads as a rendering bug, which is how the same pattern produced
/// clipped-CTA reports under DEF075.
///
/// CR118 says "approximately the donut's height" (72). Read as a sizing hint,
/// not a hard number: 3.5 rows would be 77 and closer, but it would make the
/// reporter's own 4-sector portfolio start scrolling — a present regression for
/// the person who filed a forward-looking request. 4.5 rows keeps every typical
/// allocation static and still bounds the card.
const double _kSectorLegendViewportHeight = _kSectorLegendRowHeight * 4.5;

@visibleForTesting
bool sectorLegendScrolls(int sectorCount) =>
    sectorCount * _kSectorLegendRowHeight > _kSectorLegendViewportHeight;

class _SectorLegend extends StatefulWidget {
  const _SectorLegend({required this.entries});

  final List<MapEntry<String, double>> entries;

  @override
  State<_SectorLegend> createState() => _SectorLegendState();
}

class _SectorLegendState extends State<_SectorLegend> {
  // Its own controller. This list is nested inside the screen's scroll view;
  // without one it would attach to the inherited PrimaryScrollController and
  // drive the outer list instead of itself.
  final ScrollController _controller = ScrollController();

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final scrolls = sectorLegendScrolls(widget.entries.length);

    Widget list = ListView.builder(
      controller: _controller,
      // A fitting legend must not swallow drags meant for the outer list.
      physics: scrolls
          ? const ClampingScrollPhysics()
          : const NeverScrollableScrollPhysics(),
      padding: EdgeInsets.zero,
      itemExtent: _kSectorLegendRowHeight,
      itemCount: widget.entries.length,
      itemBuilder: (context, i) => _SectorLegendRow(
        sector: widget.entries[i].key,
        weight: widget.entries[i].value,
      ),
    );

    if (scrolls) {
      // DEF170: the fade means "more below" — it must stop signalling once
      // there genuinely is nothing below. `hasClients` is false on the very
      // first build (before the ScrollView attaches), when `scrolls` being
      // true already means the list starts scrolled-to-top with content
      // hidden, so falling back to `true` there is correct, not a guess.
      list = AnimatedBuilder(
        animation: _controller,
        builder: (context, child) {
          final hasMoreBelow =
              !_controller.hasClients || _controller.position.extentAfter > 0;
          if (!hasMoreBelow) return child!;
          return ShaderMask(
            shaderCallback: (rect) => const LinearGradient(
              begin: Alignment.topCenter,
              end: Alignment.bottomCenter,
              colors: [Colors.white, Colors.white, Colors.transparent],
              stops: [0.0, 0.8, 1.0],
            ).createShader(rect),
            blendMode: BlendMode.dstIn,
            child: child,
          );
        },
        child: list,
      );
    }

    return SizedBox(
      key: const ValueKey('sector-legend'),
      height: _kSectorLegendViewportHeight,
      child: list,
    );
  }
}

class _SectorLegendRow extends StatelessWidget {
  const _SectorLegendRow({required this.sector, required this.weight});

  final String sector;
  final double weight;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final color = _sectorColor(sector);
    final label = sector == 'Other' ? l.portfolioSectorOtherLabel : sector;
    return Padding(
      padding: const EdgeInsets.only(bottom: 4),
      child: Row(
        children: [
          Container(
            width: 8,
            height: 8,
            decoration: BoxDecoration(color: color, shape: BoxShape.circle),
          ),
          const SizedBox(width: 6),
          Expanded(
            child: Text(
              label,
              style: AmiTypography.caption,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
            ),
          ),
          Text(
            '${(weight * 100).toStringAsFixed(1)}%',
            style: AmiTypography.labelMono.copyWith(fontSize: 11),
          ),
        ],
      ),
    );
  }
}

/// Deterministic sector -> color mapping. "Other" always renders neutral
/// gray — never the red/amber palette a breach indicator would use, per the
/// DEF059 inversion guard (the "Other" bucket is disclosed, never a breach).
Color _sectorColor(String sector) {
  if (sector == 'Other') return AmiColors.slate500;
  // DEF149: uninvested cash is its own slice now. Deliberately neutral and dimmer
  // than a sector — it is the part of the portfolio that is NOT an allocation
  // decision, and it never counts toward a concentration breach. Without this it
  // would draw a hash-assigned sector colour and read as a holding.
  if (sector == 'Cash') return AmiColors.slate700;
  const palette = [
    AmiColors.hexCyan,
    AmiColors.hexPurple,
    AmiColors.hexAmber,
    AmiColors.hexGreen,
    AmiColors.hexPink,
    AmiColors.hexBlue,
    AmiColors.hexOrange500,
    AmiColors.hexIndigo600,
  ];
  return palette[sector.hashCode.abs() % palette.length];
}

class _DonutPainter extends CustomPainter {
  const _DonutPainter({required this.entries});

  final List<MapEntry<String, double>> entries;

  @override
  void paint(Canvas canvas, Size size) {
    final total = entries.fold<double>(0, (sum, e) => sum + e.value);
    if (total <= 0) return;
    final rect = Rect.fromLTWH(0, 0, size.width, size.height);
    const strokeWidth = 12.0;
    var startAngle = -1.5707963267948966; // -pi/2, start at 12 o'clock
    for (final e in entries) {
      final sweep = (e.value / total) * 6.283185307179586; // 2*pi
      final paint = Paint()
        ..color = _sectorColor(e.key)
        ..style = PaintingStyle.stroke
        ..strokeWidth = strokeWidth
        ..strokeCap = StrokeCap.butt;
      canvas.drawArc(
        rect.deflate(strokeWidth / 2),
        startAngle,
        sweep,
        false,
        paint,
      );
      startAngle += sweep;
    }
  }

  @override
  bool shouldRepaint(covariant _DonutPainter oldDelegate) =>
      !identical(oldDelegate.entries, entries);
}

// ── Watchlist tab (A18) — CR120 §6 defect 6: ticker is the loud element ──

/// CR188 slice 3 — the ORDERS tab, in the slot the watchlist used to hold.
///
/// Saiful: *"Here we have all 'outstanding' trades. Financial items that have
/// yet to be realized."* Reads `sim_resting_orders` and nothing else, so it
/// needs no status predicate over `sim_trades` — which is the structural point
/// of the three-tab split.
///
/// A resting SELL against shares the user holds is deliberately **not** here:
/// it is protection on a position, so it belongs on that position's tile
/// (Saiful: *"Resting sell - tile only. Keep orders on actual manual request"*).
/// A sell with nothing behind it would open a short, has no tile to live on,
/// and does appear here.
class _OrdersTab extends ConsumerWidget {
  const _OrdersTab();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return CustomScrollView(
      key: const PageStorageKey('portfolioOrdersScroll'),
      slivers: const [
        SliverPadding(
          padding: EdgeInsets.symmetric(horizontal: AmiSpacing.m),
          sliver: SliverToBoxAdapter(child: RestingOrdersSection()),
        ),
      ],
    );
  }
}

/// CR188 slice 3 — the watchlist as SLIVERS, spliced into History.
///
/// It stopped being a tab: Saiful's structure puts everything with no live
/// claim on the book together — *"History + watch list is now just
/// information, no financial."* The slot it used to occupy is the Orders tab.
///
/// Returned as slivers rather than a widget so it composes into History's own
/// `CustomScrollView` — one scroll, not a nested one, which is what keeps the
/// SHOW ALL expansion above it behaving.
List<Widget> _watchlistSlivers(
  BuildContext context,
  WidgetRef ref,
  WatchlistState state,
) {
  final l = AppLocalizations.of(context);
  return [
        SliverPadding(
          padding: const EdgeInsets.fromLTRB(
            AmiSpacing.m,
            AmiSpacing.m,
            AmiSpacing.m,
            0,
          ),
          sliver: SliverToBoxAdapter(
            child: Row(
              children: [
                Text(l.watchlistHeading, style: AmiTypography.labelMono),
                const Spacer(),
                TextButton.icon(
                  onPressed: () => _showAddDialog(context, ref),
                  icon:
                      const Icon(Icons.add, color: AmiColors.hexCyan, size: 16),
                  label: Text(
                    l.watchlistAdd,
                    style: AmiTypography.labelMono
                        .copyWith(color: AmiColors.hexCyan),
                  ),
                ),
              ],
            ),
          ),
        ),
        if (state.items.isEmpty)
          SliverPadding(
            padding: const EdgeInsets.symmetric(horizontal: AmiSpacing.m),
            sliver: SliverToBoxAdapter(
              child: AmiEmptyState(
                icon: Icons.visibility_outlined,
                title: l.watchlistEmptyTitle,
                body: l.watchlistEmpty,
                ctaLabel: l.watchlistAdd,
                onCta: () => _showAddDialog(context, ref),
              ),
            ),
          )
        else
          SliverPadding(
            padding: const EdgeInsets.all(AmiSpacing.m),
            sliver: SliverList.builder(
              itemCount: state.items.length,
              itemBuilder: (context, i) => _WatchlistRow(entry: state.items[i]),
            ),
          ),
        const SliverToBoxAdapter(child: SizedBox(height: AmiSpacing.xxl)),
  ];
}

Future<void> _showAddDialog(BuildContext context, WidgetRef ref) async {
  await showDialog<void>(
    context: context,
    builder: (_) => const _AddWatchlistTickerDialog(),
  );
}

/// CR128: existence check before a ticker is added — previously any string
/// was accepted (the store only rejected empty input). DEF208: a stateful
/// widget rather than an inline builder, because the not-found answer is
/// now the same live inline panel the trade ticket and Convene use, and
/// that needs somewhere to hold the debounce.
class _AddWatchlistTickerDialog extends ConsumerStatefulWidget {
  const _AddWatchlistTickerDialog();

  @override
  ConsumerState<_AddWatchlistTickerDialog> createState() =>
      _AddWatchlistTickerDialogState();
}

class _AddWatchlistTickerDialogState
    extends ConsumerState<_AddWatchlistTickerDialog> {
  final _ctrl = TextEditingController();
  late final TickerFieldValidator _validator;

  @override
  void initState() {
    super.initState();
    _validator = TickerFieldValidator(
      validate: (t) => ref.read(apiClientProvider).validateTicker(t),
      onChanged: () {
        if (mounted) setState(() {});
      },
    );
    _ctrl.addListener(_onTickerChanged);
  }

  @override
  void dispose() {
    _ctrl.removeListener(_onTickerChanged);
    _validator.dispose();
    _ctrl.dispose();
    super.dispose();
  }

  void _onTickerChanged() => _validator.onTextChanged(_ctrl.text);

  Future<void> _commit() async {
    final typed = _ctrl.text.trim().toUpperCase();
    if (typed.isEmpty || _validator.checking) return;
    if (!await _validator.check(typed)) return;
    if (!mounted) return;
    ref.read(watchlistNotifierProvider.notifier).add(typed);
    Navigator.of(context).pop();
  }

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    return AlertDialog(
      backgroundColor: AmiColors.slate800,
      title: Text(l.portfolioAddDialogTitle,
          style: AmiTypography.labelMono.copyWith(color: AmiColors.hexCyan)),
      content: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          TextField(
            controller: _ctrl,
            autofocus: true,
            decoration: InputDecoration(
              hintText: l.portfolioAddDialogHint,
              hintStyle: const TextStyle(color: AmiColors.textLow),
            ),
            style: AmiTypography.body,
            textCapitalization: TextCapitalization.characters,
            onSubmitted: (_) => _commit(),
          ),
          // DEF208 — the one not-found surface, under the field, exactly as
          // in Convene the Room and the trade ticket.
          if (_validator.unknownTicker != null) ...[
            const SizedBox(height: AmiSpacing.s),
            TickerNotFoundPanel(
              typed: _validator.unknownTicker!,
              suggestion: _validator.suggestion,
              onAccept: (t) {
                _ctrl.text = t;
                _ctrl.selection = TextSelection.collapsed(offset: t.length);
              },
            ),
          ],
        ],
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.of(context).pop(),
          child: Text(l.actionCancel),
        ),
        TextButton(
          onPressed: _validator.checking ? null : _commit,
          child: Text(l.actionAdd),
        ),
      ],
    );
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
    final dayChangePct = entry.dayChangePct;
    return Padding(
      padding: const EdgeInsets.only(bottom: 6),
      child: Dismissible(
        key: ValueKey(entry.id),
        direction: DismissDirection.endToStart,
        // Match Journal's swipe-delete: demand a deliberate swipe past the
        // midpoint before committing (default 0.4 fires on a casual
        // half-swipe — accidental data loss).
        dismissThresholds: const {DismissDirection.endToStart: 0.7},
        background: const _WatchlistDeleteBackground(),
        onDismissed: (_) => _removeWithUndo(context, ref),
        child: InkWell(
          onTap: () => _showRowSheet(context, ref),
          borderRadius: BorderRadius.circular(AmiRadii.card),
          child: Container(
            padding: const EdgeInsets.symmetric(
              horizontal: AmiSpacing.m,
              vertical: AmiSpacing.s,
            ),
            decoration: BoxDecoration(
              color: AmiColors.slate800,
              borderRadius: BorderRadius.circular(AmiRadii.card),
              border: Border.all(color: AmiColors.slate700),
            ),
            child: Row(
              children: [
                // CR120 §6 defect 6 — the ticker is the identity of this row
                // and the price shouted over it (statMid/24px ticker at
                // labelMono/12px). Swapped: ticker is now the loud element,
                // which is how a list scanned by ticker should read.
                // DEF341 — statMid/24px "GOOGL" is wider than this box and
                // wrapped mid-symbol ("GOOG"/"L"). A ticker is one token:
                // scale it down to fit, never break it across lines.
                SizedBox(
                  width: 72,
                  child: FittedBox(
                    fit: BoxFit.scaleDown,
                    alignment: AlignmentDirectional.centerStart,
                    child: Text(entry.ticker,
                        maxLines: 1,
                        style: AmiTypography.statMid
                            .copyWith(color: AmiColors.textHigh)),
                  ),
                ),
                const SizedBox(width: AmiSpacing.s),
                Expanded(
                  child: Text(
                    entry.notes ?? '',
                    style: AmiTypography.caption,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
                Text(priceText, style: AmiTypography.labelMono),
                if (dayChangePct != null)
                  Padding(
                    padding: const EdgeInsets.only(left: 8),
                    child: Text(
                      _isolateNumeric(
                        '${dayChangePct >= 0 ? '+' : ''}${dayChangePct.toStringAsFixed(1)}%',
                      ),
                      style: AmiTypography.caption.copyWith(
                        color: dayChangePct >= 0
                            ? AmiColors.hexGreen
                            : AmiColors.hexRed,
                      ),
                    ),
                  ),
                const SizedBox(width: AmiSpacing.s),
                const Icon(Icons.chevron_right, color: AmiColors.textLow),
              ],
            ),
          ),
        ),
      ),
    );
  }

  void _showRowSheet(BuildContext context, WidgetRef ref) {
    // AT:R40 Bundle 1 — watchlist rows on the Portfolio screen now route to
    // the full TickerDetail surface (chart, news, earnings will land here
    // in Bundles 2-5). The ticker-tape still uses showWatchlistSheet for
    // ambient quick-actions; the sheet widget stays alive for that path.
    Navigator.of(context).push(MaterialPageRoute<void>(
      builder: (_) => TickerDetailScreen(ticker: entry.ticker),
    ));
  }

  void _removeWithUndo(BuildContext context, WidgetRef ref) {
    HapticFeedback.mediumImpact();
    final notifier = ref.read(watchlistNotifierProvider.notifier);
    final messenger = ScaffoldMessenger.of(context);
    final l = AppLocalizations.of(context);
    notifier.remove(entry.ticker);
    messenger.hideCurrentSnackBar();
    messenger.showSnackBar(
      SnackBar(
        content: Text(l.watchlistRemoved),
        duration: const Duration(seconds: 4),
        action: SnackBarAction(
          label: l.watchlistUndo,
          onPressed: () => notifier.add(entry.ticker, notes: entry.notes),
        ),
      ),
    );
  }
}

class _WatchlistDeleteBackground extends StatelessWidget {
  const _WatchlistDeleteBackground();

  @override
  Widget build(BuildContext context) {
    return Container(
      alignment: Alignment.centerRight,
      padding: const EdgeInsets.only(right: AmiSpacing.l),
      decoration: BoxDecoration(
        color: AmiColors.hexRed,
        borderRadius: BorderRadius.circular(AmiRadii.card),
      ),
      child: const Icon(Icons.delete_outline, color: Colors.white, size: 24),
    );
  }
}

// ── History tab (closed trades) — CR120 §3, §4.1, D2, D3, D4 ────────────

/// CR188 slice 3 — History is a TRANSACTION LOG plus the watchlist.
///
/// Saiful's structure: *"The current watch list gets moved to history. History
/// + watch list is now just information, no financial."* Positions holds real
/// money, Orders holds what is outstanding, and everything with no live claim
/// on the book lands here.
///
/// `closedTrades` is now **every** fill, not the `!isOpen` subset the name
/// implied. A SELL row is permanently `open` by design, so filtering on status
/// meant a completed sale appeared nowhere in the app — it sat on Positions
/// forever as an OPEN row against zero shares. A purchase and a sale both
/// happened; whether the ledger still needs the row is not the user's concern.
class _HistoryTab extends ConsumerStatefulWidget {
  const _HistoryTab({required this.closedTrades, required this.watchlist});
  final List<SimTrade> closedTrades;
  final WatchlistState watchlist;

  @override
  ConsumerState<_HistoryTab> createState() => _HistoryTabState();
}

class _HistoryTabState extends ConsumerState<_HistoryTab> {
  // CR120/D2 — SHOW ALL is an in-place expansion of the Portfolio's own
  // data, never a fetch or a pushed route. Local State is enough; it is not
  // required to survive a segment switch, only to expand in place.
  bool _showAll = false;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final journal = ref.watch(journalNotifierProvider);
    final closed = widget.closedTrades;

    if (closed.isEmpty) {
      return CustomScrollView(
        key: const PageStorageKey('portfolioHistoryScroll'),
        slivers: [
          SliverPadding(
            padding: const EdgeInsets.all(AmiSpacing.m),
            sliver: SliverToBoxAdapter(
              child: AmiEmptyState(
                icon: Icons.receipt_long_outlined,
                title: l.portfolioNoTrades,
              ),
            ),
          ),
        ],
      );
    }

    final capped = closed.length > _closedTradeCap && !_showAll;
    final visible = capped ? closed.take(_closedTradeCap).toList() : closed;

    // CR188 slice 3 — the LIST is every transaction; the SUMMARY is only over
    // settled ones. They stopped being the same set when History became a
    // transaction log, and `lost = length - won` would then have counted every
    // open buy and every SELL row (permanently `open`, realised 0) as a loss.
    // A sell's P&L is realised on the buy row it closed, so it belongs in the
    // list and not in the tally.
    final settled = closed.where((t) => !t.isOpen).toList();
    final won = settled.where((t) => t.realisedPnl > 0).length;
    final lost = settled.length - won;
    final hitRate = settled.isEmpty ? 0.0 : won / settled.length * 100;
    final net = settled.fold<double>(0, (s, t) => s + t.realisedPnl);

    final dateFmt = DateFormat('d MMM');
    final fromDate = (visible.last.closedAt ?? visible.last.openedAt);
    final toDate = (visible.first.closedAt ?? visible.first.openedAt);

    return CustomScrollView(
      key: const PageStorageKey('portfolioHistoryScroll'),
      slivers: [
        SliverPadding(
          padding: const EdgeInsets.all(AmiSpacing.m),
          sliver: SliverToBoxAdapter(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                _ClosedTradeSummary(
                    won: won, lost: lost, hitRate: hitRate, net: net),
                Padding(
                  padding: const EdgeInsets.only(top: 4),
                  child: Text(
                    l.portfolioClosedScope(settled.length),
                    style: AmiTypography.caption
                        .copyWith(color: AmiColors.textLow),
                  ),
                ),
                const SizedBox(height: AmiSpacing.m),
                Text(
                  capped
                      ? '${l.portfolioLastNClosed(_closedTradeCap)} · '
                          '${l.portfolioClosedSpan(
                          dateFmt.format(fromDate).toUpperCase(),
                          dateFmt.format(toDate).toUpperCase(),
                        )}'
                      : '${settled.length} ${l.portfolioClosed}',
                  style: AmiTypography.labelMono,
                ),
              ],
            ),
          ),
        ),
        SliverPadding(
          padding: const EdgeInsets.symmetric(horizontal: AmiSpacing.m),
          sliver: SliverList.builder(
            itemCount: visible.length,
            itemBuilder: (context, i) => TradeRow(trade: visible[i]),
          ),
        ),
        if (capped)
          SliverPadding(
            padding: const EdgeInsets.symmetric(horizontal: AmiSpacing.m),
            sliver: SliverToBoxAdapter(
              child: Center(
                child: TextButton(
                  onPressed: () => setState(() => _showAll = true),
                  child: Text(
                    l.portfolioShowAll(closed.length),
                    style: AmiTypography.labelMono
                        .copyWith(color: AmiColors.hexCyan),
                  ),
                ),
              ),
            ),
          ),
        SliverPadding(
          padding: const EdgeInsets.fromLTRB(
            AmiSpacing.m,
            AmiSpacing.l,
            AmiSpacing.m,
            0,
          ),
          sliver: SliverToBoxAdapter(
            child: _JournalPointer(journal: journal, closedTrades: settled),
          ),
        ),
        // CR188 slice 3 — the watchlist, as a SECTION of History rather than a
        // tab of its own. Its own heading and its own count: a single
        // "HISTORY 47" mixing 30 fills with 17 watched tickers is not a number
        // anyone can act on.
        ..._watchlistSlivers(context, ref, widget.watchlist),
        const SliverToBoxAdapter(child: SizedBox(height: AmiSpacing.xxl)),
      ],
    );
  }
}

class _ClosedTradeSummary extends StatelessWidget {
  const _ClosedTradeSummary({
    required this.won,
    required this.lost,
    required this.hitRate,
    required this.net,
  });

  final int won;
  final int lost;
  final double hitRate;
  final double net;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final total = won + lost;
    final wonFlex = total == 0 ? 1 : won;
    final lostFlex = total == 0 ? 1 : lost;
    final fmt = NumberFormat('#,##0.00');
    final netText =
        _isolateNumeric('${net >= 0 ? '+' : ''}\$${fmt.format(net)}');
    return Container(
      padding: const EdgeInsets.all(AmiSpacing.m),
      decoration: BoxDecoration(
        color: AmiColors.slate800,
        borderRadius: BorderRadius.circular(AmiRadii.card),
        border: Border.all(color: AmiColors.slate700),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (total > 0)
            ClipRRect(
              borderRadius: BorderRadius.circular(3),
              child: SizedBox(
                height: 6,
                child: Row(
                  children: [
                    if (won > 0)
                      Expanded(
                          flex: wonFlex,
                          child: const ColoredBox(color: AmiColors.hexGreen)),
                    if (lost > 0)
                      Expanded(
                          flex: lostFlex,
                          child: const ColoredBox(color: AmiColors.hexRed)),
                  ],
                ),
              ),
            ),
          const SizedBox(height: AmiSpacing.s),
          Wrap(
            spacing: AmiSpacing.m,
            runSpacing: 4,
            children: [
              _StatLabel(label: l.portfolioStatWon, value: '$won'),
              _StatLabel(label: l.portfolioStatLost, value: '$lost'),
              _StatLabel(
                  label: l.portfolioStatHitRate,
                  value: '${hitRate.toStringAsFixed(0)}%'),
              _StatLabel(
                label: l.portfolioStatNet,
                value: netText,
                valueColor: net >= 0 ? AmiColors.hexGreen : AmiColors.hexRed,
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _StatLabel extends StatelessWidget {
  const _StatLabel({required this.label, required this.value, this.valueColor});
  final String label;
  final String value;
  final Color? valueColor;

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Text('$label ',
            style: AmiTypography.caption.copyWith(color: AmiColors.textLow)),
        Text(value,
            style: AmiTypography.labelMono.copyWith(
                color: valueColor ?? AmiColors.textHigh, fontSize: 11)),
      ],
    );
  }
}

/// CR120 §2/§2.1/D3/D4 — the plan-aware Journal pointer. Branches on
/// `retentionDays`/`retentionLoaded`, never on plan name, never on a
/// hardcoded 30. Three states:
///  * unknown (`!retentionLoaded`) — number-less caveat (fail-safe: a
///    spurious warning is recoverable, a missing one is not).
///  * known-unlimited (`retentionLoaded && retentionDays == null`) — no
///    caveat line at all.
///  * known-finite — states how many of the closed trades the Journal
///    will not show, and that nothing is deleted (DEF155).
class _JournalPointer extends ConsumerWidget {
  const _JournalPointer({required this.journal, required this.closedTrades});

  final JournalState journal;
  final List<SimTrade> closedTrades;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l = AppLocalizations.of(context);
    String? caveat;
    if (!journal.retentionLoaded) {
      caveat = l.portfolioJournalRetentionUnknown;
    } else if (journal.retentionDays != null) {
      final days = journal.retentionDays!;
      final cutoff = DateTime.now().subtract(Duration(days: days));
      final older = closedTrades
          .where((t) => (t.closedAt ?? t.openedAt).isBefore(cutoff))
          .length;
      if (older > 0) {
        caveat = l.portfolioJournalRetention(days, older, closedTrades.length);
      }
    }
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        if (caveat != null) ...[
          Text(caveat,
              style: AmiTypography.caption.copyWith(color: AmiColors.hexAmber)),
          const SizedBox(height: AmiSpacing.xs),
        ],
        InkWell(
          // DEF190 — this used to push a second, orphaned JournalScreen on
          // top of HomeShell, which covered the bottom nav (the nav lives in
          // HomeShell's own Scaffold, below whatever gets pushed on top of
          // it) and disconnected from whatever state the real Journal tab
          // held. Switching HomeShell's own tab is what "review in Journal"
          // should have always meant.
          // CR133 §3 — a deep link now needs a tab AND a segment: the Journal
          // is a segment of `YOU`, so setting the tab alone would land on
          // whichever segment `YOU` happens to be showing and leave the
          // Journal one invisible tap away. Segment first, then tab, so
          // `journalVisibleProvider` flips exactly once and the Journal's
          // coach-mark tour fires on arrival rather than on the way past.
          onTap: () {
            ref.read(youSegmentProvider.notifier).state = YouSegment.journal;
            ref.read(activeTabProvider.notifier).state = AmiTab.you;
          },
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(l.portfolioReviewInJournal,
                  style: AmiTypography.labelMono
                      .copyWith(color: AmiColors.hexCyan)),
              const SizedBox(width: 4),
              const Icon(Icons.chevron_right,
                  color: AmiColors.hexCyan, size: 16),
            ],
          ),
        ),
      ],
    );
  }
}

// ── Alpaca paper portfolio section (AT:R45) ────────────────────────────

class _AlpacaPortfolioSection extends ConsumerWidget {
  const _AlpacaPortfolioSection();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final statusAsync = ref.watch(alpacaStatusProvider);
    return statusAsync.when(
      loading: () => const SizedBox.shrink(),
      error: (_, __) => const SizedBox.shrink(),
      data: (status) {
        if (!status.linked) return const SizedBox.shrink();
        return Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const SizedBox(height: AmiSpacing.l),
            Row(
              children: [
                Text('ALPACA PAPER', style: AmiTypography.labelMono),
                const SizedBox(width: AmiSpacing.s),
                Container(
                  width: 8,
                  height: 8,
                  decoration: const BoxDecoration(
                    shape: BoxShape.circle,
                    color: AmiColors.hexGreen,
                  ),
                ),
              ],
            ),
            const SizedBox(height: AmiSpacing.s),
            _AlpacaAccountSummary(),
            const SizedBox(height: AmiSpacing.s),
            _AlpacaPositionsList(),
          ],
        );
      },
    );
  }
}

class _AlpacaAccountSummary extends ConsumerWidget {
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final portfolioAsync = ref.watch(alpacaPortfolioProvider);
    return portfolioAsync.when(
      loading: () => const LinearProgressIndicator(
        backgroundColor: AmiColors.slate800,
        color: AmiColors.hexCyan,
      ),
      error: (_, __) => Text(
        'Could not load Alpaca account',
        style: AmiTypography.caption.copyWith(color: AmiColors.hexRed),
      ),
      data: (p) {
        final fmt = NumberFormat.currency(symbol: r'$', decimalDigits: 2);
        return Container(
          padding: const EdgeInsets.all(AmiSpacing.m),
          decoration: BoxDecoration(
            color: AmiColors.glassChrome,
            borderRadius: BorderRadius.circular(8),
            border: Border.all(color: AmiColors.slate700),
          ),
          child: Row(
            children: [
              _AlpacaStat(label: 'CASH', value: fmt.format(p.cash)),
              const SizedBox(width: AmiSpacing.m),
              _AlpacaStat(
                  label: 'PORTFOLIO', value: fmt.format(p.portfolioValue)),
              const SizedBox(width: AmiSpacing.m),
              _AlpacaStat(
                  label: 'BUYING PWR', value: fmt.format(p.buyingPower)),
            ],
          ),
        );
      },
    );
  }
}

class _AlpacaStat extends StatelessWidget {
  const _AlpacaStat({required this.label, required this.value});
  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Expanded(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(label,
              style: AmiTypography.caption.copyWith(color: AmiColors.slate500)),
          Text(value,
              style:
                  AmiTypography.labelMono.copyWith(color: AmiColors.textHigh)),
        ],
      ),
    );
  }
}

class _AlpacaPositionsList extends ConsumerWidget {
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final positionsAsync = ref.watch(alpacaPositionsProvider);
    return positionsAsync.when(
      loading: () => const SizedBox.shrink(),
      error: (_, __) => const SizedBox.shrink(),
      data: (positions) {
        if (positions.isEmpty) {
          return AmiEmptyState(
            icon: Icons.inbox_outlined,
            title: AppLocalizations.of(context).alpacaNoPositions,
          );
        }
        return Column(
          children:
              positions.map((p) => _AlpacaPositionTile(position: p)).toList(),
        );
      },
    );
  }
}

class _AlpacaPositionTile extends StatelessWidget {
  const _AlpacaPositionTile({required this.position});
  final AlpacaPosition position;

  @override
  Widget build(BuildContext context) {
    final pl = position.unrealizedPl;
    final plColor = pl >= 0 ? AmiColors.hexGreen : AmiColors.hexRed;
    final plSign = pl >= 0 ? '+' : '';
    final fmt = NumberFormat.currency(symbol: r'$', decimalDigits: 0);
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: AmiSpacing.xs),
      child: Row(
        children: [
          Expanded(
            child: Text(
              position.symbol,
              style:
                  AmiTypography.labelMono.copyWith(color: AmiColors.textHigh),
            ),
          ),
          Text(
            '×${position.qty.toStringAsFixed(position.qty == position.qty.floorToDouble() ? 0 : 2)}',
            style: AmiTypography.caption.copyWith(color: AmiColors.slate500),
          ),
          const SizedBox(width: AmiSpacing.s),
          Text(
            fmt.format(position.marketValue),
            style: AmiTypography.caption.copyWith(color: AmiColors.textMed),
          ),
          const SizedBox(width: AmiSpacing.s),
          Text(
            '$plSign${fmt.format(pl)}',
            style: AmiTypography.caption.copyWith(color: plColor),
          ),
        ],
      ),
    );
  }
}
