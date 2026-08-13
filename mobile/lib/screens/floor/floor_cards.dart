/// CR173 slice 2 — the carousel's cards.
///
/// Each one answers a question the old Floor made you go and look for:
/// *how am I doing* (card 1) and *what did my team decide* (card 2). SECTOR
/// WATCH is card 3 and is deliberately absent — §3 parks it behind the News
/// analyst's live-feed gap, and the carousel ships with two cards rather than a
/// third one full of nothing.
///
/// **Day-0 is a state, not an edge case** (acceptance #4). Card 1 always
/// renders, and the number it shows on a brand-new account is the real
/// configured stake read off the portfolio — never a literal, because the
/// server's stake is $10,000 and the mock-up's was $100,000, and a hardcoded
/// figure is wrong the first time either moves. Card 2 teaches instead of
/// collapsing: "no verdicts yet" says what fills it.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/screens/floor/floor_providers.dart';
import 'package:ami_trade/screens/floor/team_calls_data.dart';
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
