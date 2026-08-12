/// CR109 slice 5 — the period arc's beat card (design §10).
///
/// One card, six states, sitting at the top of the run screen: the entry
/// countdown, the bell, the daily standing, the final stretch, the
/// settlement freeze, and closed. §10's table calls the set *"the
/// anticipation engine"* — before this, a run was a screen you visited,
/// remembered to visit, and eventually stopped visiting.
///
/// **The card decides nothing.** Phase, rank, gap and attribution all arrive
/// resolved from `GET /v1/games/runs/{id}/arc`; the only thing computed here
/// is the countdown, because a clock is a client concern. That split is why
/// the near-miss fence holds: §10 forbids a near-miss that points at a loss,
/// and the number needed to write one is not in [GameArc] at all.
///
/// **It never blocks the screen.** A failed or pending arc call renders
/// nothing — the run screen below it is the actual product, and a ceremony
/// that can break a player's access to their own book is not a ceremony.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/games.dart';
import 'package:ami_trade/state/games_providers.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:ami_trade/widgets/hex/glass_panel.dart';
import 'package:ami_trade/widgets/hex/hex_chip.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

/// Ordinals for ranks. Rendered client-side because a rank is a number, not
/// copy — the server sends 4, and every locale's ARB decides how to say it.
String rankOrdinal(int rank) {
  if (rank % 100 >= 11 && rank % 100 <= 13) return '${rank}th';
  switch (rank % 10) {
    case 1:
      return '${rank}st';
    case 2:
      return '${rank}nd';
    case 3:
      return '${rank}rd';
    default:
      return '${rank}th';
  }
}

/// "2h 14m" / "3d 4h" / "8m". Coarse on purpose: a seconds-accurate
/// countdown on an entry deadline is the urgency pattern §10.1's reminder
/// rule exists to keep out of this product.
String formatCountdown(Duration d) {
  if (d.isNegative || d == Duration.zero) return '0m';
  if (d.inDays >= 1) {
    final hours = d.inHours - d.inDays * 24;
    return hours > 0 ? '${d.inDays}d ${hours}h' : '${d.inDays}d';
  }
  if (d.inHours >= 1) {
    final minutes = d.inMinutes - d.inHours * 60;
    return minutes > 0 ? '${d.inHours}h ${minutes}m' : '${d.inHours}h';
  }
  return '${d.inMinutes}m';
}

String _signedPoints(double v) => '${v >= 0 ? '+' : ''}${v.toStringAsFixed(1)}pp';

String _signedPct(double v) => '${v >= 0 ? '+' : ''}${v.toStringAsFixed(2)}%';

class GamesArcBeat extends ConsumerWidget {
  const GamesArcBeat({super.key, required this.runId});

  final String runId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final arcAsync = ref.watch(gamesArcProvider(runId));
    return arcAsync.maybeWhen(
      data: (arc) => _Beat(arc: arc),
      orElse: () => const SizedBox.shrink(),
    );
  }
}

class _Beat extends StatelessWidget {
  const _Beat({required this.arc});

  final GameArc arc;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final (title, accent) = switch (arc.phase) {
      GameArcPhase.entryOpen => (l.gamesArcEntryOpenTitle, AmiColors.hexAmber),
      GameArcPhase.bell => (l.gamesArcBellTitle, AmiColors.hexCyan),
      GameArcPhase.finalStretch =>
        (l.gamesArcFinalStretchTitle, AmiColors.hexAmber),
      GameArcPhase.settling => (l.gamesArcSettlingTitle, AmiColors.hexPurple),
      _ => (l.gamesArcDaysLeft(arc.daysLeft), AmiColors.hexGreen),
    };

    return GlassPanel(
      key: const Key('games_arc_beat'),
      accentColor: accent,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              HexChip(
                label: title.toUpperCase(),
                color: accent,
                variant: HexChipVariant.tinted,
              ),
              const Spacer(),
              if (arc.phase != GameArcPhase.entryOpen &&
                  arc.phase != GameArcPhase.settling)
                Text(l.gamesArcDaysLeft(arc.daysLeft),
                    style: AmiTypography.caption),
            ],
          ),
          const SizedBox(height: AmiSpacing.s),
          ..._body(context, l),
        ],
      ),
    );
  }

  List<Widget> _body(BuildContext context, AppLocalizations l) {
    switch (arc.phase) {
      case GameArcPhase.entryOpen:
        return [
          if (arc.locksAt != null)
            Text(
              l.gamesArcEntryClosesIn(
                formatCountdown(arc.locksAt!.difference(DateTime.now())),
              ),
              style: AmiTypography.body.copyWith(color: AmiColors.textHigh),
            ),
        ];
      case GameArcPhase.bell:
        return [
          Text(l.gamesArcBellBody(arc.entrantCount), style: AmiTypography.body),
        ];
      case GameArcPhase.settling:
        return [
          Text(l.gamesArcSettlingBody, style: AmiTypography.body),
        ];
      default:
        return _standingAndAttribution(l);
    }
  }

  List<Widget> _standingAndAttribution(AppLocalizations l) {
    final widgets = <Widget>[];
    if (!arc.standingsOpen || arc.yourRank == null) {
      // Day one. NEVER a rank of 0 or a gap of 0.0 — an unmeasured run and a
      // run that is exactly flat are different facts, and collapsing them is
      // the `?? 0` class this feature keeps producing.
      widgets.add(Text(l.gamesArcStandingsClosed, style: AmiTypography.body));
    } else {
      widgets.add(Text(
        l.gamesArcStandingLine(rankOrdinal(arc.yourRank!), arc.entrantCount),
        style: AmiTypography.body.copyWith(color: AmiColors.textHigh),
      ));
      // Upward only. There is no downward twin to render because the server
      // sends no number for one (design §10's near-miss fence).
      if (arc.hasGap) {
        widgets.add(const SizedBox(height: AmiSpacing.xs));
        widgets.add(Text(
          l.gamesArcGapLine(
            rankOrdinal(arc.gapToNextRank!),
            arc.gapToNextPct!.toStringAsFixed(1),
          ),
          style: AmiTypography.caption.copyWith(color: AmiColors.hexAmber),
        ));
      }
    }

    final attribution = arc.attribution;
    if (attribution != null) {
      widgets.add(const SizedBox(height: AmiSpacing.s));
      widgets.add(Text(
        arc.yourTwrPct != null
            ? l.gamesArcAttributionLine(
                attribution.ticker,
                _signedPoints(attribution.pctPoints),
                _signedPct(arc.yourTwrPct!),
              )
            : l.gamesArcAttributionNoTotal(
                attribution.ticker,
                _signedPoints(attribution.pctPoints),
              ),
        style: AmiTypography.caption,
      ));
      if (!attribution.isLivePriced) {
        widgets.add(const SizedBox(height: AmiSpacing.xs));
        widgets.add(Text(l.gamesRunMarksStaleNote,
            style: AmiTypography.caption.copyWith(color: AmiColors.hexAmber)));
      }
    }

    // Said out loud, same as the board: a player watching an unchanged rank
    // all afternoon must be told it is supposed to be unchanged.
    if (arc.standingsOpen) {
      widgets.add(const SizedBox(height: AmiSpacing.xs));
      widgets.add(Text(l.gamesBoardUpdatesNote, style: AmiTypography.caption));
    }
    return widgets;
  }
}
