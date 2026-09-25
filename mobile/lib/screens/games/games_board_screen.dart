/// CR109 — the field board: where you stand against everyone else.
///
/// Saiful, playing the shipped build: *"How do I see my current standing
/// against the rest of the field in the weekly game?"* The answer was that he
/// couldn't, and underneath that, that there was no field — one human in a
/// weekly run is solitaire with a fee. Slice 3c supplies the opponents (the
/// house desks); this screen is where they become visible.
///
/// DEF420 — Saiful, on the shipped +109 build: *"This screen is not
/// aesthetically pleasing and in line with the rest of the app."* The screen
/// was wearing a bare Material `AppBar` (every other pushed page uses
/// `AmiScreenHeader`, CR232) and its empty state set "Not ranked yet" in
/// `statBig` (42pt), which wraps at small widths / large text scales — a
/// heading has no business at stat size. This pass restyles the chrome, the
/// empty state and the row into the app's existing vocabulary
/// (`AmiScreenHeader`, `AccentCard`, `HexAvatar`, `HexChip`) with zero change
/// to data or behaviour — every provider read, every `l10n` key and every
/// rule below is untouched.
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
import 'package:ami_trade/theme/ami_window_size.dart';
import 'package:ami_trade/widgets/games/games_field_strip.dart';
import 'package:ami_trade/widgets/hex/accent_card.dart';
import 'package:ami_trade/widgets/hex/ami_screen_header.dart';
import 'package:ami_trade/widgets/hex/hex_avatar.dart';
import 'package:ami_trade/widgets/hex/hex_button.dart';
import 'package:ami_trade/widgets/hex/hex_chip.dart';
import 'package:ami_trade/widgets/hex/hex_pulse_loader.dart';
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
      body: SafeArea(
        child: Column(
          children: [
            // DEF420 — the one shared header every other pushed route wears
            // (CR232/CR133). This screen was the outlier on a bare Material
            // AppBar.
            AmiScreenHeader(
              title: l.gamesBoardTitle,
              titleColor: AmiColors.hexGreen,
              showBack: true,
            ),
            Expanded(
              child: boardAsync.when(
                loading: () =>
                    const Center(child: HexPulseLoader(color: AmiColors.hexGreen)),
                error: (_, __) => Center(
                  child: Padding(
                    padding: const EdgeInsets.all(AmiSpacing.l),
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Text(l.gamesLoadError,
                            style: AmiTypography.body,
                            textAlign: TextAlign.center),
                        const SizedBox(height: AmiSpacing.m),
                        HexButton(
                          label: l.gamesRetry.toUpperCase(),
                          onPressed: () =>
                              ref.invalidate(gamesBoardProvider(runId)),
                        ),
                      ],
                    ),
                  ),
                ),
                data: (board) => AmiWindowSizeBuilder(
                  builder: (context, windowClass, widthDp) {
                    // DEF420 — Saiful: "really it should be adaptive to the
                    // different screen size surely?" Compact keeps the
                    // original single-column padding; medium/expanded widen
                    // the gutter a step (there is more room and a wall-to-
                    // wall card looks unfinished on a tablet) and the whole
                    // list is capped + centred via AmiContentWidthConstraint
                    // so a leaderboard row does not stretch into an
                    // unreadably long line.
                    final gutter = windowClass.isAtLeastMedium
                        ? AmiSpacing.l
                        : AmiSpacing.m;
                    return RefreshIndicator(
                      onRefresh: () async =>
                          ref.invalidate(gamesBoardProvider(runId)),
                      child: ListView(
                        padding: EdgeInsets.symmetric(
                          horizontal: gutter,
                          vertical: AmiSpacing.m,
                        ),
                        children: [
                          AmiContentWidthConstraint(
                            child: Column(
                              key: const Key('games_board_content_column'),
                              crossAxisAlignment: CrossAxisAlignment.stretch,
                              children: [
                                _YourStanding(board: board),
                                const SizedBox(height: AmiSpacing.m),
                                // The race, before the table. A list can
                                // only say WHO is ahead; this says BY HOW
                                // MUCH, which is the question a player
                                // actually has and the one the old screen
                                // answered nowhere.
                                GamesFieldStrip(rows: board.rows),
                                _FieldSummary(board: board),
                                _ChampionLine(board: board),
                                const SizedBox(height: AmiSpacing.m),
                                if (board.rows.isEmpty)
                                  Text(l.gamesBoardEmpty,
                                      style: AmiTypography.body)
                                else
                                  ...orderedRows(board.rows).map((r) => _BoardRow(
                                        row: r,
                                        tied: isTiedRank(board.rows, r.rank),
                                      )),
                                const SizedBox(height: AmiSpacing.m),
                                // Said out loud rather than left to be
                                // inferred: this board is stale by design
                                // between closes, and a player who does not
                                // know that reads an unchanged number as a
                                // broken feature.
                                Text(l.gamesBoardUpdatesNote,
                                    style: AmiTypography.caption),
                                const SizedBox(height: AmiSpacing.l),
                              ],
                            ),
                          ),
                        ],
                      ),
                    );
                  },
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// Is [utcInstant] within US Eastern daylight time (EDT, UTC-4)?
///
/// DEF420 MINOR-1: the previous estimate split the difference between EDT
/// (UTC-4) and EST (UTC-5) at a fixed 20:30 UTC, which is off by 30 minutes
/// every single day and, during the "wrong" half of the year, counts down to
/// a close that already happened. `mobile/pubspec.yaml` has no `timezone`
/// package (checked), so this implements the US DST rule directly rather
/// than pulling in a new dependency for one calculation: DST runs from
/// 2:00am local on the second Sunday of March to 2:00am local on the first
/// Sunday of November (the rule in effect since 2007). The comparison is
/// done in UTC throughout — DST start is 07:00 UTC (2am EST = UTC-5) and DST
/// end is 06:00 UTC (2am EDT = UTC-4) — so no local-time/UTC round trip is
/// needed for the boundary itself.
bool _isUsEasternDaylightTime(DateTime utcInstant) {
  final year = utcInstant.year;

  DateTime nthSundayOfMonthUtc(int month, int n, int hourUtc) {
    var d = DateTime.utc(year, month, 1);
    final firstSundayDay = 1 + ((7 - d.weekday) % 7);
    final day = firstSundayDay + (n - 1) * 7;
    return DateTime.utc(year, month, day, hourUtc);
  }

  // Second Sunday of March, 2:00am EST (UTC-5) = 07:00 UTC.
  final dstStart = nthSundayOfMonthUtc(3, 2, 7);
  // First Sunday of November, 2:00am EDT (UTC-4) = 06:00 UTC.
  final dstEnd = nthSundayOfMonthUtc(11, 1, 6);

  return !utcInstant.isBefore(dstStart) && utcInstant.isBefore(dstEnd);
}

/// A rough, client-only estimate of the next US equity close (4pm ET,
/// Mon–Fri), used ONLY to soften the "not ranked yet" wait with a sense of
/// scale — never as a scored fact. Deliberately ignores market holidays: the
/// board's own [GameBoardScreen] copy already says standings move "once per
/// US close," so a holiday just means this estimate undershoots by a day,
/// never that it asserts a close happened when it didn't. No backend call —
/// per DEF420's brief, this is arithmetic on the device clock only.
///
/// DEF420 MINOR-1: previously pinned "4pm ET" to a fixed 20:30 UTC
/// year-round (splitting the difference between EDT and EST), which was off
/// by 30 minutes every day and, under the "wrong" side of the DST rule,
/// could count down to a close that had already happened. This now resolves
/// 4pm ET to the correct UTC hour — 20:00 UTC during EDT, 21:00 UTC during
/// EST — via [_isUsEasternDaylightTime], checked against the CANDIDATE close
/// instant (not just "now"), since DST can change between "now" and the
/// close being computed on the two transition days.
DateTime? nextUsCloseEstimate([DateTime? from]) {
  final now = (from ?? DateTime.now()).toUtc();

  DateTime closeOn(DateTime utcDay) {
    final hourUtc = _isUsEasternDaylightTime(
      DateTime.utc(utcDay.year, utcDay.month, utcDay.day, 20),
    )
        ? 20
        : 21;
    return DateTime.utc(utcDay.year, utcDay.month, utcDay.day, hourUtc);
  }

  var close = closeOn(now);
  if (!close.isAfter(now)) {
    close = closeOn(now.add(const Duration(days: 1)));
  }
  // Skip to Monday's close if we've landed on a weekend.
  while (close.weekday == DateTime.saturday || close.weekday == DateTime.sunday) {
    close = closeOn(close.add(const Duration(days: 1)));
  }
  return close;
}

/// "2h 14m" / "1d 6h" — same coarse-on-purpose shape as the run screen's
/// countdown (`games_arc_beat.dart`'s `formatCountdown`), reimplemented here
/// rather than imported so this screen's only dependency stays the model +
/// theme layer it already has. A precise duplicate is safe: both round the
/// same way and neither is a scored figure.
String _formatWait(Duration d) {
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

/// The player's own position, or an honest statement that there isn't one yet.
class _YourStanding extends StatelessWidget {
  const _YourStanding({required this.board});
  final GameBoard board;

  /// "0.42% off 2nd", or — when you lead — how much of a cushion you hold.
  ///
  /// Computed from the row immediately above (or below, when leading) rather
  /// than from `yourRank` arithmetic, so a tie renders as the tie it is
  /// instead of an invented gap. Null whenever either side is unmeasured:
  /// an unknown gap is not a zero one, which is the same rule the duel card
  /// follows and the ninth-instance bug class this feature keeps producing.
  String? _chaseLine(AppLocalizations l) {
    final ranked = board.rows.where((r) => r.rank != null && r.twrPct != null)
        .toList()
      ..sort((a, b) => a.rank!.compareTo(b.rank!));
    final meIdx = ranked.indexWhere((r) => r.isYou);
    if (meIdx < 0) return null;
    final me = ranked[meIdx];

    if (meIdx > 0) {
      final above = ranked[meIdx - 1];
      final gap = above.twrPct! - me.twrPct!;
      if (gap <= 0) return null; // a tie — the rank already says it
      return l.gamesBoardChase(gap.toStringAsFixed(2), above.rank!);
    }
    // You lead. The interesting number is the cushion, not the gap.
    if (ranked.length < 2) return null;
    final below = ranked[1];
    final lead = me.twrPct! - below.twrPct!;
    if (lead <= 0) return null;
    return l.gamesBoardLeadBy(lead.toStringAsFixed(2));
  }

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final rank = board.yourRank;
    final twr = board.yourTwrPct;
    final chase = _chaseLine(l);

    // `rank == null` means no completed close, NOT last place. Two different
    // facts, and the one this renders must be the true one.
    if (rank == null) {
      final close = nextUsCloseEstimate();
      final wait = close?.difference(DateTime.now());
      return AccentCard(
        accent: AmiColors.slate600,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // DEF420 — a heading, not a stat. This used to be `statBig`
            // (42pt), which wraps to two lines at 375dp / 1.3x text scale;
            // "Not ranked yet" is a status, and the app's own heading scale
            // is what every other status card on the app uses for one.
            Text(l.gamesBoardNotRankedYet,
                style: AmiTypography.h3, maxLines: 1),
            const SizedBox(height: AmiSpacing.xs),
            Text(l.gamesBoardStandingsClosed, style: AmiTypography.body),
            if (wait != null && !wait.isNegative) ...[
              const SizedBox(height: AmiSpacing.s),
              Row(
                children: [
                  const Icon(Icons.schedule,
                      size: 14, color: AmiColors.textLow),
                  const SizedBox(width: AmiSpacing.xs),
                  // Flexible + ellipsis — a Row with an unbounded Text is
                  // the CR226 overflow class (see ami_screen_header.dart's
                  // own subtitle comment): at 1.3x text scale on a 375dp
                  // screen this line sat a fraction of a pixel past the
                  // AccentCard's padding before this guard was added.
                  Flexible(
                    child: Text(
                      l.gamesBoardNextCloseIn(_formatWait(wait)),
                      style: AmiTypography.caption,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
                ],
              ),
            ],
          ],
        ),
      );
    }

    final sign = (twr ?? 0) >= 0 ? '+' : '';
    final color = (twr ?? 0) >= 0 ? AmiColors.hexGreen : AmiColors.hexRed;
    return AccentCard(
      accent: color,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            l.gamesBoardYouAre(rank, board.entrantCount),
            style: AmiTypography.statMid.copyWith(color: AmiColors.textHigh),
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
          ),
          if (twr != null) ...[
            const SizedBox(height: AmiSpacing.xs),
            Row(
              children: [
                Flexible(
                  child: Text('$sign${twr.toStringAsFixed(2)}%',
                      style: AmiTypography.dataMd.copyWith(color: color),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis),
                ),
                const SizedBox(width: AmiSpacing.s),
                // DEF420 round 2 — this Row had neither child guarded, so at
                // 320–375dp / 1.3x text scale (the headline above it is
                // already wide) it overflowed by 44px. Both children now
                // shrink instead of forcing the Row past its bound; the
                // label is the one allowed to go first since the number is
                // the more load-bearing of the two.
                Flexible(
                  child: Text(l.gamesTwrLabel,
                      style: AmiTypography.caption,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis),
                ),
              ],
            ),
          ],
          // The single most actionable line on the screen, and it was
          // missing: how far off the place above. "3rd of 6" is a fact;
          // "0.42% off 2nd" is a reason to open the app tomorrow.
          if (chase != null) ...[
            const SizedBox(height: AmiSpacing.xs),
            Text(chase, style: AmiTypography.caption),
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
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: AmiSpacing.s),
      child: Row(
        children: [
          Text(
            l.gamesBoardEntrants(board.entrantCount),
            style: AmiTypography.caption,
          ),
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
      ),
    );
  }
}

/// CR109 slice 8 (§8.5) — who holds the field's title, once it has closed.
///
/// The displaced case is the one the design cares about: the board leader
/// could not hold the title, so it passed down, and saying that plainly is
/// the whole point. §8.5: *"A board that quietly promotes second place looks
/// like a bug; one that explains itself looks like a rule."*
class _ChampionLine extends StatelessWidget {
  const _ChampionLine({required this.board});
  final GameBoard board;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    if (board.state != 'closed') return const SizedBox.shrink();
    final champion = board.champion;
    // No champion on a closed field means nobody in it was eligible — a
    // leader with no title-holder. Stated, never filled in with the leader.
    if (champion == null) {
      return Text(l.gamesBoardNoChampion, style: AmiTypography.caption);
    }
    return Text(
      champion.displaced
          ? l.gamesBoardChampionDisplaced(
              champion.handle, _ordinal(champion.rank))
          : l.gamesBoardChampionTitle(champion.handle),
      style: AmiTypography.body.copyWith(color: AmiColors.hexAmber),
    );
  }

  static String _ordinal(int rank) {
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
}

/// DEF343 — is this rank shared by more than one entrant?
///
/// Competition ranking (1, 1, 3) makes a shared rank arithmetically correct
/// and visually confusing: the field screenshot showed two entrants tied at
/// +0.05%, both rank 3 of 4, with the YOU row rendered *below* its tied peer
/// and nothing saying "tied" — so the player read the listing as "I am 4th"
/// while the hero said "#3 of 4". Counted from the rows themselves, which the
/// client already has in full; nothing hidden is being re-derived here.
bool isTiedRank(List<GameBoardRow> rows, int? rank) {
  if (rank == null) return false;
  return rows.where((r) => r.rank == rank).length > 1;
}

/// The YOU row sorts FIRST inside its tie group, and nothing else moves.
///
/// The other half of DEF343: a marker alone still leaves the player reading
/// their own row last among equals. Stable within every other group, so the
/// board's order is otherwise exactly the server's.
List<GameBoardRow> orderedRows(List<GameBoardRow> rows) {
  final out = List<GameBoardRow>.from(rows);
  for (var i = 0; i < out.length; i++) {
    if (!out[i].isYou || out[i].rank == null) continue;
    var first = i;
    while (first > 0 && out[first - 1].rank == out[i].rank) {
      first--;
    }
    if (first != i) {
      final me = out.removeAt(i);
      out.insert(first, me);
    }
    break;
  }
  return out;
}

/// Short mono initials for the row's [HexAvatar] — first letter of up to two
/// "words" in the handle (`Momentum Desk` → `MD`, `careful-vector` → `C`).
/// Purely a display derivation; carries no identity meaning the row's own
/// text doesn't already state.
String _initials(String handle) {
  final parts = handle
      .trim()
      .split(RegExp(r'[\s_-]+'))
      .where((p) => p.isNotEmpty)
      .toList();
  if (parts.isEmpty) return '?';
  if (parts.length == 1) {
    return parts.first.substring(0, parts.first.length >= 2 ? 2 : 1).toUpperCase();
  }
  return (parts[0][0] + parts[1][0]).toUpperCase();
}

class _BoardRow extends StatelessWidget {
  const _BoardRow({required this.row, this.tied = false});
  final GameBoardRow row;

  /// Renders the rank as `=3` rather than `3`. `=` rather than DEF343's other
  /// suggestion `T-3`: "T" abbreviates the English "tied" and would need its
  /// own translated form in AR and MS, where a bare glyph does not. One less
  /// string to retranslate, for the same meaning.
  final bool tied;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final twr = row.twrPct;
    final color = twr == null
        ? AmiColors.textLow
        : (twr >= 0 ? AmiColors.hexGreen : AmiColors.hexRed);
    // DEF420 — the identity accent for this row's HexAvatar: desks read
    // amber (matches their DESK chip), the player's own row reads cyan
    // (matches the app's "you" accent elsewhere, e.g. the duel card), and
    // everyone else reads by their own return so a losing entrant doesn't
    // borrow the leader's green.
    final avatarColor = row.isDesk
        ? AmiColors.hexAmber
        : row.isYou
            ? AmiColors.hexCyan
            : color == AmiColors.textLow
                ? AmiColors.slate600
                : color;

    final twrText = Text(
      // A dash, not 0.00%. An unmeasured run and a flat run are
      // different facts and must not draw the same.
      twr == null ? '—' : '${twr >= 0 ? '+' : ''}${twr.toStringAsFixed(2)}%',
      style: AmiTypography.dataMd.copyWith(color: color),
      maxLines: 1,
      overflow: TextOverflow.ellipsis,
    );

    final content = Padding(
      padding: const EdgeInsets.symmetric(
        horizontal: AmiSpacing.m,
        vertical: AmiSpacing.s,
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.center,
        children: [
          SizedBox(
            width: 24,
            child: Text(
              row.rank == null
                  ? '—'
                  : (tied ? '=${row.rank}' : '${row.rank}'),
              style: AmiTypography.dataMd.copyWith(
                color:
                    row.rank == null ? AmiColors.textLow : AmiColors.textHigh,
              ),
              maxLines: 1,
              overflow: TextOverflow.clip,
            ),
          ),
          const SizedBox(width: AmiSpacing.xs),
          HexAvatar(
            // 44 — the same size the app already uses for an agent avatar in
            // a list row (brief_history_screen.dart, lesson_beat_deck.dart),
            // not a new one invented for this screen.
            label: _initials(row.handle),
            color: avatarColor,
            size: 44,
          ),
          const SizedBox(width: AmiSpacing.s),
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
                // DEF420 round 2 — the return moved off the TOP line (it used
                // to sit as a sibling after this whole Expanded, on the same
                // row as the name + chips) and onto its OWN line here. On a
                // narrow compact window at 1.3x text scale, rank + avatar +
                // name + a chip + a percentage all sharing one Row's width
                // had no slack left to give — this is the fix, not a
                // tighter squeeze of the same five things.
                //
                // Still a dash (never '0.00%') when unmeasured — twrText
                // itself renders '—' in that case — AND still the "No close
                // yet" caption underneath, exactly as before this restyle:
                // two different signals (the dash where a number would be,
                // the sentence explaining why) that were always both shown.
                twrText,
                if (twr == null)
                  Text(l.gamesBoardNoCloseYet, style: AmiTypography.caption)
                // CR109 slice 8 (§8.5) — published, not hidden.
                // "Ineligible does not mean invisible": the entrant
                // ranks, the board shows what happened, and the row
                // says out loud that this one cannot hold the title.
                // A silent exclusion is the tell §11.2 avoids.
                else if (row.titleIneligibleReason != null)
                  Text(l.gamesBoardIneligibleNote,
                      style: AmiTypography.caption),
              ],
            ),
          ),
        ],
      ),
    );

    // DEF420 — the YOU row now reads as a deliberately emphasised state
    // (a real accent wash + border) rather than the old barely-visible flat
    // `slate800` tint, matching the accent-card vocabulary used everywhere
    // else on the screen.
    if (row.isYou) {
      return Padding(
        padding: const EdgeInsets.only(bottom: AmiSpacing.s),
        child: ClipRRect(
          borderRadius: BorderRadius.circular(AmiRadii.card),
          child: Material(
            color: AmiColors.hexCyan.withValues(alpha: 0.12),
            child: Container(
              decoration: BoxDecoration(
                border: Border.all(
                  color: AmiColors.hexCyan.withValues(alpha: 0.5),
                ),
                borderRadius: BorderRadius.circular(AmiRadii.card),
              ),
              // Only a desk has anything to open — its published rule. A
              // human entrant (including the player) has nothing further to
              // show, and must not: the board renders no other player's
              // book (§6.1/§11.3).
              child: row.isDesk
                  ? InkWell(
                      borderRadius: BorderRadius.circular(AmiRadii.card),
                      onTap: () => _showDeskRule(context, row),
                      child: content,
                    )
                  : content,
            ),
          ),
        ),
      );
    }

    return Padding(
      padding: const EdgeInsets.only(bottom: AmiSpacing.s),
      child: Material(
        color: AmiColors.slate800,
        borderRadius: BorderRadius.circular(AmiRadii.card),
        child: InkWell(
          borderRadius: BorderRadius.circular(AmiRadii.card),
          // Only a desk has anything to open — its published rule. A
          // human entrant has nothing further to show, and must not: the
          // board renders no other player's book (§6.1/§11.3).
          onTap: row.isDesk ? () => _showDeskRule(context, row) : null,
          child: content,
        ),
      ),
    );
  }
}

void _showDeskRule(BuildContext context, GameBoardRow row) {
  final l = AppLocalizations.of(context);
  showModalBottomSheet<void>(
    context: context,
    useRootNavigator: false,
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
