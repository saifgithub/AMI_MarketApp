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
import 'package:ami_trade/features/tour/tour_providers.dart';
import 'package:ami_trade/features/tour/tour_service.dart';
import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/sim.dart';
import 'package:ami_trade/models/watchlist.dart';
import 'package:ami_trade/screens/sim/ticker_detail_screen.dart';
import 'package:ami_trade/screens/sim/trade_ticket_sheet.dart';
import 'package:ami_trade/models/alpaca.dart';
import 'package:ami_trade/state/alpaca_providers.dart';
import 'package:ami_trade/state/journal_providers.dart';
import 'package:ami_trade/state/onboarding_providers.dart';
import 'package:ami_trade/state/sim_providers.dart';
import 'package:ami_trade/state/watchlist_providers.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:ami_trade/theme/hex_clipper.dart';
import 'package:ami_trade/widgets/confirm_ticker_match.dart';
import 'package:ami_trade/widgets/empty_state.dart';
import 'package:ami_trade/widgets/hex/hex_chip.dart';
import 'package:ami_trade/widgets/hex/hex_toast.dart';
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
            _Header(
                key: _headerKey,
                onTradeTicket: () => TradeTicketSheet.show(context)),
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

    final openTrades = state.trades.where((t) => t.isOpen).toList();
    final closedTrades = state.trades.where((t) => !t.isOpen).toList()
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
            positionsCount: p.holdings.length,
            watchlistCount: watchlist.items.length,
            historyCount: closedTrades.length,
            hasOpenTrade: openTrades.isNotEmpty,
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
                  openTrades: openTrades,
                  onTradeTicket: () => TradeTicketSheet.show(context),
                ),
                _WatchlistTab(state: watchlist),
                _HistoryTab(closedTrades: closedTrades),
              ],
            ),
          ),
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
              style:
                  AmiTypography.labelMono.copyWith(color: AmiColors.hexCyan)),
          const Spacer(),
          IconButton(
            icon:
                const Icon(Icons.add_circle_outline, color: AmiColors.hexCyan),
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
                label: '${l.portfolioTabWatchlist} $watchlistCount',
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

/// The Positions tab's live indicator — present whenever an open trade
/// exists, whether or not Positions is the selected segment (§4.1/2b). Cyan,
/// never amber: an open position is a state, not a warning.
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
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: InkWell(
        onTap: () => Navigator.of(context).push(MaterialPageRoute<void>(
          builder: (_) => TickerDetailScreen(ticker: holding.ticker),
        )),
        borderRadius: BorderRadius.circular(AmiRadii.card),
        child: Container(
          // CR120 §9 acceptance 1 — this list is one of three growing lists
          // the CR exists to keep scannable; a tighter row (vertical s
          // instead of m) is what buys back screens at the heavy profile
          // without hiding any content.
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
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(holding.ticker,
                        style: AmiTypography.statMid
                            .copyWith(color: AmiColors.textHigh)),
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
                    _isolateNumeric(
                      '${pnl >= 0 ? '+' : ''}\$${fmt.format(pnl)} '
                      '(${pct >= 0 ? '+' : ''}${pct.toStringAsFixed(2)}%)',
                    ),
                    style: AmiTypography.labelMono
                        .copyWith(color: accent, fontSize: 11),
                  ),
                ],
              ),
              const SizedBox(width: AmiSpacing.s),
              const Icon(Icons.chevron_right,
                  color: AmiColors.textLow, size: 18),
            ],
          ),
        ),
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
    required this.openTrades,
    required this.onTradeTicket,
  });

  final List<SimHolding> holdings;
  final List<SimTrade> openTrades;
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
                const _SectorAllocationSection(),
                if (holdings.isEmpty && openTrades.isEmpty)
                  _NewTraderHint(onTradeTicket: onTradeTicket)
                else ...[
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
              itemBuilder: (context, i) => _HoldingCard(holding: holdings[i]),
            ),
          ),
        if (holdings.isNotEmpty || openTrades.isNotEmpty)
          SliverPadding(
            padding: const EdgeInsets.fromLTRB(
              AmiSpacing.m,
              AmiSpacing.m,
              AmiSpacing.m,
              AmiSpacing.s,
            ),
            sliver: SliverToBoxAdapter(
              child:
                  Text(l.portfolioOpenTrades, style: AmiTypography.labelMono),
            ),
          ),
        if (openTrades.isEmpty && (holdings.isNotEmpty))
          SliverPadding(
            padding: const EdgeInsets.symmetric(horizontal: AmiSpacing.m),
            sliver: SliverToBoxAdapter(
              child: Text(l.portfolioNoOpenPositions,
                  style:
                      AmiTypography.caption.copyWith(color: AmiColors.textLow)),
            ),
          )
        else if (openTrades.isNotEmpty)
          SliverPadding(
            padding: const EdgeInsets.symmetric(horizontal: AmiSpacing.m),
            sliver: SliverList.builder(
              itemCount: openTrades.length,
              itemBuilder: (context, i) => TradeRow(trade: openTrades[i]),
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

class _WatchlistTab extends ConsumerWidget {
  const _WatchlistTab({required this.state});
  final WatchlistState state;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l = AppLocalizations.of(context);
    return CustomScrollView(
      key: const PageStorageKey('portfolioWatchlistScroll'),
      slivers: [
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
              style:
                  AmiTypography.labelMono.copyWith(color: AmiColors.hexCyan)),
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

  // CR128: existence check + "did you mean X" confirmation before a ticker
  // is added — previously any string was accepted (the store only rejected
  // empty input). Shown as a nested dialog on top of the add dialog, which
  // stays open until a valid ticker is resolved.
  Future<void> _commit(BuildContext ctx, WidgetRef ref, String raw) async {
    final typed = raw.trim().toUpperCase();
    if (typed.isEmpty) return;
    final result = await ref.read(apiClientProvider).validateTicker(typed);
    if (!ctx.mounted) return;
    String? ticker;
    if (result.exists) {
      ticker = typed;
    } else if (result.suggestion != null) {
      ticker = await confirmTickerMatch(
        ctx,
        typed: typed,
        suggestedTicker: result.suggestion!.ticker,
        suggestedCompanyName: result.suggestion!.companyName,
        exchange: result.suggestion!.exchange,
      );
    } else {
      ScaffoldMessenger.of(ctx).showSnackBar(
        SnackBar(content: Text(AppLocalizations.of(ctx).tickerNotFound(typed))),
      );
      return;
    }
    if (ticker == null || !ctx.mounted) return;
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
                SizedBox(
                  width: 72,
                  child: Text(entry.ticker,
                      style: AmiTypography.statMid
                          .copyWith(color: AmiColors.textHigh)),
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

class _HistoryTab extends ConsumerStatefulWidget {
  const _HistoryTab({required this.closedTrades});
  final List<SimTrade> closedTrades;

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

    final won = closed.where((t) => t.realisedPnl > 0).length;
    final lost = closed.length - won;
    final hitRate = closed.isEmpty ? 0.0 : won / closed.length * 100;
    final net = closed.fold<double>(0, (s, t) => s + t.realisedPnl);

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
                    l.portfolioClosedScope(closed.length),
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
                      : '${closed.length} ${l.portfolioClosed}',
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
            child: _JournalPointer(journal: journal, closedTrades: closed),
          ),
        ),
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
          onTap: () =>
              ref.read(activeTabIndexProvider.notifier).state = 2, // Journal
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
