/// CR109 slice 2 — the game's landing surface.
///
/// Per `implementation_plan.md` §8.2 and design §13.3, the game's home is
/// ONE stateful screen in three states, not a lobby — built as the state
/// machine now and filled in across slices:
///
///   * State B — a run is live → ships THIS slice (the run card).
///   * State C — between runs, and State A — never entered → slice 3+.
///     Until a close exists (slice 3) or the first-run duel routing exists
///     (slice 3c), both fall back to the same simple "enter the next
///     weekly field" card. That is correct per §8.2, not a placeholder.
///
/// The five-cadence lobby is a separate route, one tap deeper, and is not
/// built this slice — this screen only ever offers the weekly cadence,
/// which is the only one `games_service` rolls in slice 2
/// (implementation_plan.md §2).
///
/// Unreachable in a store build: this screen has NO entry point of its own
/// (no tab, no card, no settings row, no tap gesture anywhere in the app
/// reaches it) and the `/games` route it sits behind is const-folded out of
/// every build that doesn't pass `--dart-define=AMI_GAMES=1`
/// (`features/games/games_gate.dart`, wired in `app.dart`).
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/games.dart';
import 'package:ami_trade/screens/games/games_entry_sheet.dart';
import 'package:ami_trade/screens/games/games_lobby_screen.dart';
import 'package:ami_trade/screens/games/games_record_screen.dart';
import 'package:ami_trade/screens/games/games_run_screen.dart';
import 'package:ami_trade/screens/games/games_trade_ticket_screen.dart';
import 'package:ami_trade/state/games_providers.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:ami_trade/widgets/games/games_arc_beat.dart';
import 'package:ami_trade/widgets/games/games_queue_note.dart';
import 'package:ami_trade/widgets/hex/glass_panel.dart';
import 'package:ami_trade/widgets/hex/hex_button.dart';
import 'package:ami_trade/widgets/hex/hex_chip.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

class GamesHomeScreen extends ConsumerWidget {
  const GamesHomeScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l = AppLocalizations.of(context);
    final runsAsync = ref.watch(gamesRunsProvider);
    return Scaffold(
      backgroundColor: AmiColors.slate900,
      appBar: AppBar(
        title: Text(l.gamesHomeTitle),
        // CR109 slice 3 — the Record's only entry point this slice
        // (games_record_screen.dart's docstring). Internal navigation
        // inside the already-gated `/games` subtree, not a new top-level
        // entry point.
        actions: [
          IconButton(
            icon: const Icon(Icons.military_tech_outlined),
            tooltip: l.gamesRecordCta,
            onPressed: () => Navigator.of(context).push(
              MaterialPageRoute(builder: (_) => const GamesRecordScreen()),
            ),
          ),
        ],
      ),
      body: SafeArea(
        child: runsAsync.when(
          loading: () => const Center(child: CircularProgressIndicator()),
          error: (e, _) =>
              _ErrorState(onRetry: () => ref.invalidate(gamesRunsProvider)),
          data: (runs) {
            final live = runs.where((r) => r.isLive).toList()
              ..sort(
                (a, b) => (a.daysLeft ?? 1 << 30)
                    .compareTo(b.daysLeft ?? 1 << 30),
              );
            if (live.isNotEmpty) {
              return _StateBLiveRun(
                run: live.first,
                others: live.skip(1).toList(),
              );
            }
            // State A (never entered) and State C (between runs) share this
            // fallback until slice 3 (a close to return from) and slice 3c
            // (the first-run duel) exist — implementation_plan.md §8.2.
            return const _NextFieldFallback();
          },
        ),
      ),
    );
  }
}

class _ErrorState extends StatelessWidget {
  const _ErrorState({required this.onRetry});
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
            Text(
              l.gamesLoadError,
              style: AmiTypography.body,
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: AmiSpacing.m),
            HexButton(label: l.gamesRetry.toUpperCase(), onPressed: onRetry),
          ],
        ),
      ),
    );
  }
}

/// State B — a run is live. The hero is whichever run closes soonest;
/// other live runs (a duel/private field alongside the open weekly, once
/// those ship — §4.1) compress to one line each rather than each getting a
/// full card.
class _StateBLiveRun extends StatelessWidget {
  const _StateBLiveRun({required this.run, required this.others});

  final GameRunSummary run;
  final List<GameRunSummary> others;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final twr = run.twrPct ?? 0;
    final twrColor = twr >= 0 ? AmiColors.hexGreen : AmiColors.hexRed;
    final sign = twr >= 0 ? '+' : '';
    return SingleChildScrollView(
      padding: const EdgeInsets.all(AmiSpacing.m),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          GlassPanel(
            // Execution-family accent (hexGreen) — this card is where the
            // player acts, not an analyst read (design rule: colour by
            // agent family, never a hard-coded CTA hue).
            accentColor: AmiColors.hexGreen,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    HexChip(
                      label: run.cadence.toUpperCase(),
                      color: AmiColors.hexGreen,
                      variant: HexChipVariant.tinted,
                    ),
                    const Spacer(),
                    // CR109 slice 5 — the period arc's beat, on the card the
                    // player sees on every visit (design §10). Two of the
                    // six phases are the ones worth interrupting for: entries
                    // about to close, and the final stretch. The rest fall
                    // through to the plain days-left line, because a chip
                    // that is always lit stops being read.
                    if (run.phase == GameArcPhase.entryOpen &&
                        run.locksAt != null)
                      Text(
                        l.gamesArcEntryClosesIn(
                          formatCountdown(
                            run.locksAt!.difference(DateTime.now()),
                          ),
                        ),
                        style: AmiTypography.caption
                            .copyWith(color: AmiColors.hexAmber),
                      )
                    else if (run.phase == GameArcPhase.finalStretch &&
                        run.daysLeft != null)
                      Text(
                        '${l.gamesArcFinalStretchTitle} · '
                        '${l.gamesArcDaysLeft(run.daysLeft!)}',
                        style: AmiTypography.caption
                            .copyWith(color: AmiColors.hexAmber),
                      )
                    else if (run.daysLeft != null)
                      Text(
                        l.gamesDaysLeft(run.daysLeft!),
                        style: AmiTypography.caption,
                      ),
                  ],
                ),
                const SizedBox(height: AmiSpacing.s),
                Text(
                  '$sign${twr.toStringAsFixed(2)}%',
                  style: AmiTypography.statBig.copyWith(color: twrColor),
                ),
                Row(
                  children: [
                    Text(l.gamesTwrLabel, style: AmiTypography.caption),
                    const SizedBox(width: AmiSpacing.xs),
                    // Behind the ⓘ here too. This card is seen on every visit
                    // to the game, so a paragraph that never changes is the
                    // definition of copy that stops being read.
                    const GamesQueueInfoIcon(),
                  ],
                ),
                const SizedBox(height: AmiSpacing.m),
                Row(
                  children: [
                    // "My run" leads. The card shows a return percentage and
                    // nothing about the book behind it — cash, positions and
                    // the orders waiting on the open all live one tap in
                    // (§13.3), and until this button existed there was no
                    // tap that reached them.
                    Expanded(
                      child: HexButton(
                        label: l.gamesRunTitle.toUpperCase(),
                        color: AmiColors.hexCyan,
                        onPressed: () =>
                            GamesRunScreen.push(context, runId: run.runId),
                      ),
                    ),
                    const SizedBox(width: AmiSpacing.s),
                    Expanded(
                      child: HexButton(
                        label: l.gamesTradeCta.toUpperCase(),
                        color: AmiColors.hexGreen,
                        onPressed: () => GamesTradeTicketScreen.show(
                          context,
                          runId: run.runId,
                        ),
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ),
          if (others.isNotEmpty) ...[
            const SizedBox(height: AmiSpacing.l),
            Text(
              l.gamesOtherRunsHeading,
              style: AmiTypography.labelMono
                  .copyWith(color: AmiColors.textLow),
            ),
            const SizedBox(height: AmiSpacing.s),
            for (final o in others) _OtherRunLine(run: o),
          ],
        ],
      ),
    );
  }
}

class _OtherRunLine extends StatelessWidget {
  const _OtherRunLine({required this.run});
  final GameRunSummary run;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final twr = run.twrPct ?? 0;
    final color = twr >= 0 ? AmiColors.hexGreen : AmiColors.hexRed;
    final sign = twr >= 0 ? '+' : '';
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(
        children: [
          Text(run.cadence.toUpperCase(), style: AmiTypography.caption),
          const Spacer(),
          Text(
            '$sign${twr.toStringAsFixed(2)}%',
            style: AmiTypography.bodySm.copyWith(color: color),
          ),
          if (run.daysLeft != null) ...[
            const SizedBox(width: AmiSpacing.s),
            Text(l.gamesDaysLeft(run.daysLeft!), style: AmiTypography.caption),
          ],
        ],
      ),
    );
  }
}

/// States A + C's shared fallback until slice 3 / 3c: a single card for the
/// next weekly field, not the five-cadence lobby.
class _NextFieldFallback extends ConsumerWidget {
  const _NextFieldFallback();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l = AppLocalizations.of(context);
    final cadencesAsync = ref.watch(gamesCadencesProvider);
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(AmiSpacing.l),
        child: cadencesAsync.when(
          loading: () => const CircularProgressIndicator(),
          error: (e, _) => _ErrorState(
            onRetry: () => ref.invalidate(gamesCadencesProvider),
          ),
          data: (cadences) {
            GameCadenceInfo weekly = const GameCadenceInfo(cadence: 'week');
            for (final c in cadences) {
              if (c.isWeekly) {
                weekly = c;
                break;
              }
            }
            final entrants = weekly.nextField?.entrantCount ?? 0;
            return Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                const Icon(Icons.flag_outlined,
                    color: AmiColors.textLow, size: 40),
                const SizedBox(height: AmiSpacing.m),
                Text(
                  l.gamesFallbackHeading,
                  style: AmiTypography.h4,
                  textAlign: TextAlign.center,
                ),
                const SizedBox(height: AmiSpacing.xs),
                Text(
                  l.gamesFallbackBody,
                  style: AmiTypography.body.copyWith(
                    color: AmiColors.textLow,
                  ),
                  textAlign: TextAlign.center,
                ),
                if (entrants > 0) ...[
                  const SizedBox(height: AmiSpacing.m),
                  Text(
                    l.gamesFieldEntrantCount(entrants),
                    style: AmiTypography.caption,
                  ),
                ],
                const SizedBox(height: AmiSpacing.l),
                SizedBox(
                  width: double.infinity,
                  child: HexButton(
                    label: l.gamesEnterCta.toUpperCase(),
                    color: AmiColors.hexGreen,
                    onPressed: weekly.alreadyHolds
                        ? null
                        : () => GamesEntrySheet.show(context, cadence: 'week'),
                  ),
                ),
                const SizedBox(height: AmiSpacing.s),
                // Weekly keeps its one-tap entry above; the other four
                // cadences (slice 6) live one tap deeper so the first-entry
                // screen stays the single uncluttered choice §13.3 fences.
                SizedBox(
                  width: double.infinity,
                  child: HexButton(
                    label: l.gamesLobbyCta,
                    variant: HexButtonVariant.outlined,
                    onPressed: () => GamesLobbyScreen.push(context),
                  ),
                ),
              ],
            );
          },
        ),
      ),
    );
  }
}
