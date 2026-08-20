/// CR173 slice 2 — the carousel's cards.
///
/// Each one answers a question the old Floor made you go and look for:
/// *how am I doing* (card 1), *what did my team decide* (card 2), *what's
/// moving where I look* (card 3, SECTOR WATCH — CR183, the cheap
/// yfinance-headline version §3 always allowed), and *what did my team decide
/// that I never acted on* (card 4, NOT ACTIONED — CR184, a scorecard of the
/// team's judgement in both directions, never a prompt to trade).
///
/// **Day-0 is a state, not an edge case** (acceptance #4). Card 1 always
/// renders, and the number it shows on a brand-new account is the real
/// configured stake read off the portfolio — never a literal, because the
/// server's stake is $10,000 and the mock-up's was $100,000, and a hardcoded
/// figure is wrong the first time either moves. Card 2 teaches instead of
/// collapsing: "no verdicts yet" says what fills it. Card 3 teaches too.
/// Card 4 collapses — the screen omits it entirely when every call is
/// actioned, because "nothing outstanding" needs no permanent card.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/screens/floor/floor_providers.dart';
import 'package:ami_trade/screens/floor/team_calls_data.dart';
import 'package:ami_trade/screens/sim/ticker_detail_screen.dart';
import 'package:ami_trade/state/sim_providers.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:ami_trade/widgets/floor/floor_carousel.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';

final _money = NumberFormat.currency(symbol: r'$', decimalDigits: 0);
final _day = DateFormat.MMMd();

class PortfolioAnswerCard extends ConsumerWidget {
  const PortfolioAnswerCard({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l = AppLocalizations.of(context);
    final p = ref.watch(simNotifierProvider).portfolio;

    // Not yet loaded is not "you have nothing". A zero here would be the first
    // number a user sees on the Floor and it would be a lie about their money.
    if (p == null) {
      return Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          FloorCardLabel(
              label: l.floorCardPortfolio, color: AmiColors.hexGreen),
          const SizedBox(height: AmiSpacing.s),
          Text(l.floorCardPortfolioLoading,
              style: AmiTypography.caption.copyWith(color: AmiColors.textLow)),
        ],
      );
    }

    final untouched = p.holdings.isEmpty && p.totalValue == p.startingCapital;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      mainAxisSize: MainAxisSize.min,
      children: [
        FloorCardLabel(label: l.floorCardPortfolio, color: AmiColors.hexGreen),
        const SizedBox(height: 2),
        Text(_money.format(p.totalValue),
            style: AmiTypography.statMid.copyWith(color: AmiColors.textHigh)),
        const SizedBox(height: 2),
        Text(
          // Day 0: the stake, said as a stake. There is no "+0.0% all-time" to
          // report on a portfolio that has never traded, and printing one
          // implies a measurement nobody made.
          untouched
              ? l.floorCardPortfolioDayZero(_money.format(p.startingCapital))
              : l.floorCardPortfolioSummary(
                  '${p.pnlPct >= 0 ? '+' : ''}${p.pnlPct.toStringAsFixed(1)}%',
                  _money.format(p.currentCash),
                  p.holdings.length,
                ),
          maxLines: 2,
          overflow: TextOverflow.ellipsis,
          style: AmiTypography.caption.copyWith(color: AmiColors.textMed),
        ),
      ],
    );
  }
}

class TeamCallsAnswerCard extends ConsumerWidget {
  const TeamCallsAnswerCard({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l = AppLocalizations.of(context);
    final async = ref.watch(teamCallsProvider);

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      mainAxisSize: MainAxisSize.min,
      children: [
        FloorCardLabel(label: l.floorCardCalls, color: AmiColors.hexCyan),
        const SizedBox(height: AmiSpacing.xs),
        Flexible(
          child: async.when(
            loading: () => const SizedBox.shrink(),
            // The card says the reading failed rather than showing an empty
            // list, which would read as "your team has decided nothing".
            error: (_, __) => Text(l.floorCardCallsUnavailable,
                style:
                    AmiTypography.caption.copyWith(color: AmiColors.textLow)),
            data: (calls) => calls.isEmpty
                ? Text(l.floorCardCallsEmpty,
                    style: AmiTypography.caption
                        .copyWith(color: AmiColors.textLow))
                : Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      for (final call in calls.take(kCallsCardRows))
                        TeamCallRow(call: call, compact: true),
                    ],
                  ),
          ),
        ),
      ],
    );
  }
}

/// Card 3 — SECTOR WATCH (CR183). "What's moving where I look?": the
/// top-moving GICS sector among the user's touched tickers, its leader, and
/// the leader's top headline.
///
/// The card is a glance whose real home is the leader's TickerDetail screen
/// (carousel rule 3) — the tap lives here in the body, not on the FloorCard,
/// because the leader is only known once the read lands. Three wire states,
/// three renderings: `empty` teaches (day-0 is a state), `unavailable` — or
/// any state this build has never seen, or an `ok` missing a fact it promises
/// — says the feed could not be read. Never a fabricated 0.0% (CR040).
class SectorWatchAnswerCard extends ConsumerWidget {
  const SectorWatchAnswerCard({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l = AppLocalizations.of(context);
    final async = ref.watch(sectorWatchProvider);

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      mainAxisSize: MainAxisSize.min,
      children: [
        FloorCardLabel(label: l.floorCardSector, color: AmiColors.hexAmber),
        const SizedBox(height: AmiSpacing.xs),
        Flexible(
          child: async.when(
            loading: () => const SizedBox.shrink(),
            error: (_, __) => Text(l.floorCardSectorUnavailable,
                style:
                    AmiTypography.caption.copyWith(color: AmiColors.textLow)),
            data: (w) {
              if (w.state == 'empty') {
                return Text(l.floorCardSectorEmpty,
                    style: AmiTypography.caption
                        .copyWith(color: AmiColors.textLow));
              }
              final sector = w.sector;
              final movePct = w.movePct;
              final leader = w.leader;
              if (w.state != 'ok' ||
                  sector == null ||
                  movePct == null ||
                  leader == null) {
                return Text(l.floorCardSectorUnavailable,
                    style: AmiTypography.caption
                        .copyWith(color: AmiColors.textLow));
              }
              final move =
                  '${movePct >= 0 ? '+' : ''}${movePct.toStringAsFixed(1)}%';
              return InkWell(
                key: const Key('sector_watch_tap'),
                onTap: () =>
                    Navigator.of(context).push(MaterialPageRoute<void>(
                  builder: (_) => TickerDetailScreen(ticker: leader),
                )),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Text(l.floorCardSectorMove(sector, move, leader),
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: AmiTypography.caption
                            .copyWith(color: AmiColors.textHigh)),
                    if (w.headline != null) ...[
                      const SizedBox(height: 2),
                      Text(w.headline!.title,
                          maxLines: 2,
                          overflow: TextOverflow.ellipsis,
                          style: AmiTypography.caption
                              .copyWith(color: AmiColors.textMed)),
                    ],
                  ],
                ),
              );
            },
          ),
        ),
      ],
    );
  }
}

/// Card 4 — NOT ACTIONED (CR184). The last two convenes whose verdict the
/// user never executed, with the move since the call — a scorecard of the
/// team's judgement, shown in both directions with the same neutral framing
/// (a PASS that was right is as eligible as an APPROVE that ran away).
///
/// The screen collapses this card entirely when the list is empty; the empty
/// branch here is only the in-flight race before that collapse lands.
class UnactionedCallsCard extends ConsumerWidget {
  const UnactionedCallsCard({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l = AppLocalizations.of(context);
    final async = ref.watch(unactionedCallsProvider);

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      mainAxisSize: MainAxisSize.min,
      children: [
        FloorCardLabel(label: l.floorCardUnactioned, color: AmiColors.hexPurple),
        const SizedBox(height: AmiSpacing.xs),
        Flexible(
          child: async.when(
            loading: () => const SizedBox.shrink(),
            error: (_, __) => Text(l.floorCardUnactionedUnavailable,
                style:
                    AmiTypography.caption.copyWith(color: AmiColors.textLow)),
            data: (calls) => calls.isEmpty
                ? const SizedBox.shrink()
                : Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      for (final call in calls) _UnactionedRow(call: call),
                    ],
                  ),
          ),
        ),
      ],
    );
  }
}

/// One unactioned call: ticker, the verdict as itself, the move since the
/// call, the day. Same skeleton as [TeamCallRow]; the delta column differs
/// because a PASS here measures against a disclosed reconstructed close
/// instead of always dashing.
class _UnactionedRow extends StatelessWidget {
  const _UnactionedRow({required this.call});

  final TeamCall call;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 1),
      child: Row(
        children: [
          SizedBox(
            width: 52,
            child: Text(call.ticker,
                style: AmiTypography.labelMono
                    .copyWith(fontSize: 11, color: AmiColors.textHigh)),
          ),
          _ActionChip(action: call.action),
          const SizedBox(width: AmiSpacing.s),
          Expanded(child: _UnactionedDelta(call: call)),
          Text(_day.format(call.at),
              style: AmiTypography.caption
                  .copyWith(fontSize: 10, color: AmiColors.textLow)),
        ],
      ),
    );
  }
}

/// The move since the call, framed neutrally — "{delta} since the call" for
/// an APPROVE (measured against the entry the PM named), "{delta} vs close on
/// {date}" for a PASS (measured against the reconstructed convene-day close,
/// disclosed as such). A dash whenever either side of the measurement is
/// missing — an unread quote, a mock-walk history, a level nobody named —
/// because an unmeasured value rendered as 0.0% is a lie (CR040).
class _UnactionedDelta extends ConsumerWidget {
  const _UnactionedDelta({required this.call});

  final TeamCall call;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    const dash = Text('—',
        style: TextStyle(fontSize: 11, color: AmiColors.textLow));
    final l = AppLocalizations.of(context);
    final now = ref.watch(callPriceProvider(call.ticker)).valueOrNull;

    if (call.hasReference) {
      final delta = deltaSinceEntry(entry: call.entry, now: now);
      if (delta == null) return dash;
      return _framed(l.floorCardUnactionedSince(_signed(delta)), delta);
    }

    final reference = ref
        .watch(conveneCloseProvider((ticker: call.ticker, at: call.at)))
        .valueOrNull;
    if (reference == null) return dash;
    final delta = deltaSinceEntry(entry: reference.close, now: now);
    if (delta == null) return dash;
    return _framed(
        l.floorCardUnactionedPassReference(
            _signed(delta), _day.format(reference.date)),
        delta);
  }

  static String _signed(double delta) =>
      '${delta >= 0 ? '+' : ''}${delta.toStringAsFixed(1)}%';

  static Widget _framed(String text, double delta) => Text(
        text,
        maxLines: 1,
        overflow: TextOverflow.ellipsis,
        style: AmiTypography.labelMono.copyWith(
          fontSize: 10,
          color: delta >= 0 ? AmiColors.hexGreen : AmiColors.hexRed,
        ),
      );
}

/// One call. Shared by the card and the list screen so the two cannot describe
/// the same verdict differently (DEF098) — the list adds the reason, and that
/// is the only difference.
class TeamCallRow extends ConsumerWidget {
  const TeamCallRow({
    super.key,
    required this.call,
    this.compact = false,
    this.onTap,
  });

  final TeamCall call;
  final bool compact;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l = AppLocalizations.of(context);
    return InkWell(
      onTap: onTap,
      child: Padding(
        padding: EdgeInsets.symmetric(vertical: compact ? 1 : AmiSpacing.s),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisSize: MainAxisSize.min,
          children: [
            Row(
              children: [
                SizedBox(
                  width: 52,
                  child: Text(call.ticker,
                      style: AmiTypography.labelMono
                          .copyWith(fontSize: 11, color: AmiColors.textHigh)),
                ),
                _ActionChip(action: call.action),
                const SizedBox(width: AmiSpacing.s),
                Expanded(child: _Delta(call: call)),
                Text(_day.format(call.at),
                    style: AmiTypography.caption
                        .copyWith(fontSize: 10, color: AmiColors.textLow)),
              ],
            ),
            if (!compact && call.reason != null) ...[
              const SizedBox(height: 2),
              Text(call.reason!,
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                  style:
                      AmiTypography.caption.copyWith(color: AmiColors.textMed)),
            ],
            if (!compact && !call.hasReference) ...[
              const SizedBox(height: 2),
              Text(l.floorCallsNoReferencePrice,
                  style: AmiTypography.caption
                      .copyWith(fontSize: 10, color: AmiColors.textLow)),
            ],
          ],
        ),
      ),
    );
  }
}

/// APPROVE and PASS get their own colour; **everything else is rendered as
/// itself in neutral** — `room.dart`'s neutral-unknown rule (acceptance #6).
/// A REJECT is not a PASS and a value this build has never seen is neither, so
/// neither is folded into the other.
class _ActionChip extends StatelessWidget {
  const _ActionChip({required this.action});

  final String action;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final colour = switch (action) {
      'APPROVE' => AmiColors.hexGreen,
      'PASS' => AmiColors.slate500,
      _ => AmiColors.textMed,
    };
    final label = action == 'NO_VERDICT' ? l.roomVerdictActionNoVerdict : action;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 1),
      decoration: BoxDecoration(
        color: colour.withValues(alpha: 0.14),
        borderRadius: BorderRadius.circular(3),
      ),
      child: Text(label,
          style:
              AmiTypography.labelMono.copyWith(fontSize: 9, color: colour)),
    );
  }
}

/// The move since the level the PM named — and a dash whenever that is not a
/// thing that exists.
///
/// Three distinct outcomes, three renderings: no reference level (a PASS names
/// none), a reference level but no current price (the quote failed), and a real
/// reading. Collapsing any two of them produces a number that looks measured
/// and is not.
class _Delta extends ConsumerWidget {
  const _Delta({required this.call});

  final TeamCall call;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    const dash = Text('—',
        style: TextStyle(fontSize: 11, color: AmiColors.textLow));
    if (!call.hasReference) return dash;

    final price = ref.watch(callPriceProvider(call.ticker));
    final delta = deltaSinceEntry(
        entry: call.entry, now: price.valueOrNull);
    if (delta == null) return dash;

    final up = delta >= 0;
    return Text(
      '${up ? '+' : ''}${delta.toStringAsFixed(1)}%',
      style: AmiTypography.labelMono.copyWith(
        fontSize: 11,
        color: up ? AmiColors.hexGreen : AmiColors.hexRed,
      ),
    );
  }
}
