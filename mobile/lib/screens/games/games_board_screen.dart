/// CR109 — the field board: where you stand against everyone else.
///
/// Saiful, playing the shipped build: *"How do I see my current standing
/// against the rest of the field in the weekly game?"* The answer was that he
/// couldn't, and underneath that, that there was no field — one human in a
/// weekly run is solitaire with a fee. Slice 3c supplies the opponents (the
/// house desks); this screen is where they become visible.
///
/// Three rules this screen obeys, each of them a design decision rather than a
/// styling choice:
///
///   * **No money, anywhere.** Design §6.1 makes "rank on % TWR, never
///     absolute AMI Cash" an invariant, because a board that ranks money makes
///     capital tier pay-to-win. The wire model carries no currency field, so
///     there is nothing here to render even by accident.
///   * **A desk is always marked as a desk.** §11.2's disclosure decision is
///     Saiful's own: *"if we do not disclose that it's a bot, then if the copy
///     happens (and it can happen off app) the user is copying what they
///     thought is a person!"* Every desk row carries the chip AND its
///     published rule is one tap away.
///   * **Unmeasured is drawn as a dash, never as 0.00%.** An entrant with no
///     completed close has not been measured; rendering that as flat would
///     drop them into the middle of the pack looking deliberate. This is the
///     `?? 0` class that has cost this feature nine defects already.
///
/// Unreachable in a store build — it lives under the `/games` subtree, which
/// is const-folded out without `--dart-define=AMI_GAMES=true`.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/games.dart';
import 'package:ami_trade/state/games_providers.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:ami_trade/widgets/hex/hex_button.dart';
import 'package:ami_trade/widgets/hex/hex_chip.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

class GamesBoardScreen extends ConsumerWidget {
  const GamesBoardScreen({super.key, required this.runId});

  final String runId;

  static Future<void> push(BuildContext context, {required String runId}) {
    return Navigator.of(context).push(
      MaterialPageRoute(builder: (_) => GamesBoardScreen(runId: runId)),
    );
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l = AppLocalizations.of(context);
    final boardAsync = ref.watch(gamesBoardProvider(runId));

    return Scaffold(
      backgroundColor: AmiColors.slate900,
      appBar: AppBar(title: Text(l.gamesBoardTitle)),
      body: SafeArea(
        child: boardAsync.when(
          loading: () => const Center(child: CircularProgressIndicator()),
          error: (_, __) => Center(
            child: Padding(
              padding: const EdgeInsets.all(AmiSpacing.l),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Text(l.gamesLoadError,
                      style: AmiTypography.body, textAlign: TextAlign.center),
                  const SizedBox(height: AmiSpacing.m),
                  HexButton(
                    label: l.gamesRetry.toUpperCase(),
                    onPressed: () => ref.invalidate(gamesBoardProvider(runId)),
                  ),
                ],
              ),
            ),
          ),
          data: (board) => RefreshIndicator(
            onRefresh: () async => ref.invalidate(gamesBoardProvider(runId)),
            child: ListView(
              padding: const EdgeInsets.all(AmiSpacing.m),
              children: [
                _YourStanding(board: board),
                const SizedBox(height: AmiSpacing.m),
                _FieldSummary(board: board),
                const SizedBox(height: AmiSpacing.m),
                if (board.rows.isEmpty)
                  Text(l.gamesBoardEmpty, style: AmiTypography.body)
                else
                  ...board.rows.map((r) => _BoardRow(row: r)),
                const SizedBox(height: AmiSpacing.m),
                // Said out loud rather than left to be inferred: this board is
                // stale by design between closes, and a player who does not
                // know that reads an unchanged number as a broken feature.
                Text(l.gamesBoardUpdatesNote, style: AmiTypography.caption),
                const SizedBox(height: AmiSpacing.l),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

/// The player's own position, or an honest statement that there isn't one yet.
class _YourStanding extends StatelessWidget {
  const _YourStanding({required this.board});
  final GameBoard board;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final rank = board.yourRank;
    final twr = board.yourTwrPct;

    // `rank == null` means no completed close, NOT last place. Two different
    // facts, and the one this renders must be the true one.
    if (rank == null) {
      return _Panel(
        accent: AmiColors.slate700,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(l.gamesBoardNotRankedYet,
                style: AmiTypography.statBig.copyWith(color: AmiColors.textHigh)),
            const SizedBox(height: AmiSpacing.xs),
            Text(l.gamesBoardStandingsClosed, style: AmiTypography.caption),
          ],
        ),
      );
    }

    final sign = (twr ?? 0) >= 0 ? '+' : '';
    final color = (twr ?? 0) >= 0 ? AmiColors.hexGreen : AmiColors.hexRed;
    return _Panel(
      accent: color,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            l.gamesBoardYouAre(rank, board.entrantCount),
            style: AmiTypography.statBig.copyWith(color: AmiColors.textHigh),
          ),
          if (twr != null) ...[
            const SizedBox(height: AmiSpacing.xs),
            Row(
              children: [
                Text('$sign${twr.toStringAsFixed(2)}%',
                    style: AmiTypography.dataMd.copyWith(color: color)),
                const SizedBox(width: AmiSpacing.s),
                Text(l.gamesTwrLabel, style: AmiTypography.caption),
              ],
            ),
          ],
        ],
      ),
    );
  }
}

/// Field size and — disclosed at field level, not only per row — how much of
/// it is house desks.
class _FieldSummary extends StatelessWidget {
  const _FieldSummary({required this.board});
  final GameBoard board;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    return Row(
      children: [
        Text(l.gamesBoardEntrants(board.entrantCount),
            style: AmiTypography.caption),
        if (board.deskCount > 0) ...[
          const SizedBox(width: AmiSpacing.xs),
          Expanded(
            child: Text(
              l.gamesBoardDeskCount(board.deskCount),
              style: AmiTypography.caption,
            ),
          ),
        ],
      ],
    );
  }
}

class _BoardRow extends StatelessWidget {
  const _BoardRow({required this.row});
  final GameBoardRow row;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final twr = row.twrPct;
    final color = twr == null
        ? AmiColors.textLow
        : (twr >= 0 ? AmiColors.hexGreen : AmiColors.hexRed);

    return Padding(
      padding: const EdgeInsets.only(bottom: AmiSpacing.s),
      child: Material(
        color: row.isYou ? AmiColors.slate800 : Colors.transparent,
        borderRadius: BorderRadius.circular(AmiRadii.card),
        child: InkWell(
          borderRadius: BorderRadius.circular(AmiRadii.card),
          // Only a desk has anything to open — its published rule. A human
          // entrant has nothing further to show, and must not: the board
          // renders no other player's book (§6.1/§11.3).
          onTap: row.isDesk ? () => _showDeskRule(context, row) : null,
          child: Padding(
            padding: const EdgeInsets.symmetric(
              horizontal: AmiSpacing.m,
              vertical: AmiSpacing.s,
            ),
            child: Row(
              children: [
                SizedBox(
                  width: 34,
                  child: Text(
                    row.rank == null ? '—' : '${row.rank}',
                    style: AmiTypography.dataMd.copyWith(
                      color: row.rank == null
                          ? AmiColors.textLow
                          : AmiColors.textHigh,
                    ),
                  ),
                ),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          Flexible(
                            child: Text(
                              row.handle,
                              overflow: TextOverflow.ellipsis,
                              style: AmiTypography.body.copyWith(
                                color: AmiColors.textHigh,
                              ),
                            ),
                          ),
                          if (row.isDesk) ...[
                            const SizedBox(width: AmiSpacing.xs),
                            HexChip(
                              label: l.gamesBoardDeskChip,
                              color: AmiColors.hexAmber,
                              variant: HexChipVariant.tinted,
                            ),
                          ],
                          if (row.isYou) ...[
                            const SizedBox(width: AmiSpacing.xs),
                            HexChip(
                              label: l.gamesBoardYouChip,
                              color: AmiColors.hexGreen,
                              variant: HexChipVariant.tinted,
                            ),
                          ],
                        ],
                      ),
                      if (twr == null)
                        Text(l.gamesBoardNoCloseYet,
                            style: AmiTypography.caption),
                    ],
                  ),
                ),
                Text(
                  // A dash, not 0.00%. An unmeasured run and a flat run are
                  // different facts and must not draw the same.
                  twr == null
                      ? '—'
                      : '${twr >= 0 ? '+' : ''}${twr.toStringAsFixed(2)}%',
                  style: AmiTypography.dataMd.copyWith(color: color),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

void _showDeskRule(BuildContext context, GameBoardRow row) {
  final l = AppLocalizations.of(context);
  showModalBottomSheet<void>(
    context: context,
    backgroundColor: AmiColors.slate800,
    isScrollControlled: true,
    builder: (_) => SafeArea(
      child: Padding(
        padding: const EdgeInsets.all(AmiSpacing.l),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(row.handle,
                style: AmiTypography.h3.copyWith(color: AmiColors.textHigh)),
            const SizedBox(height: AmiSpacing.xs),
            Text(l.gamesDesksIntro, style: AmiTypography.caption),
            const SizedBox(height: AmiSpacing.m),
            Text(l.gamesDeskRuleTitle, style: AmiTypography.caption),
            const SizedBox(height: AmiSpacing.xs),
            // The rule comes from the server, not from app copy. A rule that
            // lived in the client would drift from the code that actually
            // picks the names, and a stale published rule is worse than none.
            Text(row.deskRule ?? '', style: AmiTypography.body),
            const SizedBox(height: AmiSpacing.l),
          ],
        ),
      ),
    ),
  );
}

class _Panel extends StatelessWidget {
  const _Panel({required this.child, required this.accent});
  final Widget child;
  final Color accent;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(AmiSpacing.m),
      decoration: BoxDecoration(
        color: AmiColors.slate800,
        borderRadius: BorderRadius.circular(AmiRadii.card),
        border: Border.all(color: accent.withValues(alpha: 0.4)),
      ),
      child: child,
    );
  }
}
