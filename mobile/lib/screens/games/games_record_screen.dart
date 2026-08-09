/// CR109 slice 3 — the Record: identity / movement / history (design
/// §13.3: "The Record is the product's second surface").
///
/// Scope THIS slice only (implementation_plan.md §2's slice-3 DARK list:
/// "placement, the field board, titles, cosmetics"): career points (the
/// ledger's own `SUM(delta)`, rendered exactly as received — the ledger
/// clamps at write time, implementation_plan.md §4.5, so this screen must
/// NEVER re-clamp it), entered/finished/forfeited counts, run history, and
/// the PR board (works at n = 1). Titles, the duel W-L line, the skill stat
/// and returns-by-style are slice 3b/4/Stage-2 material and are not
/// rendered here — [GameRecord.title] is parsed defensively for
/// forward-compat, but the IDENTITY section only appears when the server
/// actually sends one.
///
/// A run-history row with a known `run_id` opens [GamesCloseScreen] for
/// that entry — the only contractually-solid way to reach a specific
/// closed run's Close this slice: `GET /v1/games/runs` only promises the
/// caller's *live* runs (implementation_plan.md §6), so there is no other
/// reliable path back to a finished one without guessing at fields the API
/// contract does not name.
///
/// Reached from [GamesHomeScreen]'s app-bar action — not a new top-level
/// entry point (no tab, card, settings row or gesture outside the already-
/// gated `/games` subtree); CR133 owns whatever permanent nav destination
/// this eventually gets.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/games.dart';
import 'package:ami_trade/screens/games/games_close_screen.dart';
import 'package:ami_trade/state/games_providers.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:ami_trade/widgets/hex/glass_panel.dart';
import 'package:ami_trade/widgets/hex/hex_button.dart';
import 'package:ami_trade/widgets/hex/hex_chip.dart';
import 'package:ami_trade/widgets/hex/hex_mark.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';

/// CR106 T-BIDI: isolate signed/numeric runs so RTL layout cannot scramble
/// sign/digits. Per-file copy, matching this codebase's existing
/// convention (see `widgets/portfolio_equity_chart.dart`).
String _isolateNumeric(String s) => '\u2066$s\u2069';

class GamesRecordScreen extends ConsumerWidget {
  const GamesRecordScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l = AppLocalizations.of(context);
    final recordAsync = ref.watch(gamesRecordProvider);
    return Scaffold(
      backgroundColor: AmiColors.slate900,
      appBar: AppBar(title: Text(l.gamesRecordTitle)),
      body: SafeArea(
        child: recordAsync.when(
          loading: () => const Center(child: CircularProgressIndicator()),
          error: (e, _) => _RecordErrorState(
            onRetry: () => ref.invalidate(gamesRecordProvider),
          ),
          data: (record) => _RecordBody(record: record),
        ),
      ),
    );
  }
}

class _RecordErrorState extends StatelessWidget {
  const _RecordErrorState({required this.onRetry});
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
              l.gamesRecordLoadError,
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

class _SectionHeading extends StatelessWidget {
  const _SectionHeading(this.label);
  final String label;

  @override
  Widget build(BuildContext context) => Text(
        label,
        style:
            AmiTypography.labelMono.copyWith(color: AmiColors.textLow, fontSize: 11),
      );
}

class _RecordBody extends StatelessWidget {
  const _RecordBody({required this.record});
  final GameRecord record;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    return SingleChildScrollView(
      padding: const EdgeInsets.all(AmiSpacing.m),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // IDENTITY — present-when-available only; titles are DARK this
          // slice (see this file's top docstring).
          if (record.title != null) ...[
            _SectionHeading(l.gamesRecordIdentityHeading),
            const SizedBox(height: AmiSpacing.s),
            HexChip(
              label: record.title!.toUpperCase(),
              color: AmiColors.hexPurple,
              variant: HexChipVariant.tinted,
            ),
            const SizedBox(height: AmiSpacing.l),
          ],

          _SectionHeading(l.gamesRecordMovementHeading),
          const SizedBox(height: AmiSpacing.s),
          _MovementCard(record: record),
          const SizedBox(height: AmiSpacing.m),
          const _PrBoard(),

          const SizedBox(height: AmiSpacing.l),
          _SectionHeading(l.gamesRecordHistoryHeading),
          const SizedBox(height: AmiSpacing.s),
          _HistoryCounts(record: record),
          const SizedBox(height: AmiSpacing.s),
          if (record.runHistory.isEmpty)
            Text(l.gamesRecordHistoryEmpty, style: AmiTypography.caption)
          else
            for (final entry in record.runHistory) _HistoryRow(entry: entry),
        ],
      ),
    );
  }
}

class _MovementCard extends StatelessWidget {
  const _MovementCard({required this.record});
  final GameRecord record;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    return GlassPanel(
      accentColor: AmiColors.hexCyan,
      child: Row(
        children: [
          HexMark(
            color: AmiColors.hexCyan,
            child: const Icon(Icons.bolt, color: Colors.white, size: 20),
          ),
          const SizedBox(width: AmiSpacing.m),
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // implementation_plan.md §4.5: the ledger clamps AT WRITE
              // TIME, so this is rendered exactly as received — no
              // .clamp()/math.max() on this screen, ever.
              Text(
                _isolateNumeric('${record.careerPoints}'),
                style: AmiTypography.statBig,
              ),
              Text(l.gamesRecordCareerPointsLabel, style: AmiTypography.caption),
            ],
          ),
        ],
      ),
    );
  }
}

class _PrBoard extends ConsumerWidget {
  const _PrBoard();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l = AppLocalizations.of(context);
    final prsAsync = ref.watch(gamesRecordPrsProvider);
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
          Text(
            l.gamesRecordPrHeading,
            style:
                AmiTypography.labelMono.copyWith(color: AmiColors.hexPurple, fontSize: 11),
          ),
          const SizedBox(height: AmiSpacing.s),
          prsAsync.when(
            loading: () => const Padding(
              padding: EdgeInsets.symmetric(vertical: AmiSpacing.s),
              child: Center(child: CircularProgressIndicator(strokeWidth: 2)),
            ),
            error: (e, _) => Text(l.gamesRecordLoadError, style: AmiTypography.caption),
            data: (prs) => prs.isEmpty
                ? Text(l.gamesRecordPrEmpty, style: AmiTypography.caption)
                : Column(children: [for (final pr in prs) _PrRow(pr: pr)]),
          ),
        ],
      ),
    );
  }
}

class _PrRow extends StatelessWidget {
  const _PrRow({required this.pr});
  final GamePersonalRecord pr;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final label = _prLabel(l, pr.kind) ?? pr.fallbackLabel;
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 6),
      child: Row(
        children: [
          HexMark(
            color: AmiColors.hexPurple,
            size: 32,
            child: const Icon(Icons.star, color: Colors.white, size: 14),
          ),
          const SizedBox(width: AmiSpacing.s),
          Expanded(child: Text(label, style: AmiTypography.body)),
          if (pr.value != null)
            Text(
              _isolateNumeric(
                  '${pr.value! >= 0 ? '+' : ''}${pr.value!.toStringAsFixed(2)}'),
              style: AmiTypography.dataMd,
            ),
        ],
      ),
    );
  }

  String? _prLabel(AppLocalizations l, String kind) {
    switch (kind) {
      case 'best_weekly_twr':
        return l.gamesPrBestReturn;
      case 'best_alpha':
        return l.gamesPrBestAlpha;
      case 'best_drawdown_control':
        return l.gamesPrBestDrawdown;
      case 'longest_hold':
        return l.gamesPrLongestHold;
      case 'longest_finish_streak':
        return l.gamesPrLongestStreak;
      default:
        return null;
    }
  }
}

class _HistoryCounts extends StatelessWidget {
  const _HistoryCounts({required this.record});
  final GameRecord record;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    return Row(
      children: [
        _CountStat(label: l.gamesRecordEnteredLabel, value: record.enteredCount),
        const SizedBox(width: AmiSpacing.l),
        _CountStat(label: l.gamesRecordFinishedLabel, value: record.finishedCount),
        const SizedBox(width: AmiSpacing.l),
        _CountStat(label: l.gamesRecordForfeitedLabel, value: record.forfeitCount),
      ],
    );
  }
}

class _CountStat extends StatelessWidget {
  const _CountStat({required this.label, required this.value});
  final String label;
  final int value;

  @override
  Widget build(BuildContext context) => Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('$value', style: AmiTypography.statMid),
          Text(label, style: AmiTypography.caption),
        ],
      );
}

class _HistoryRow extends StatelessWidget {
  const _HistoryRow({required this.entry});
  final GameRecordRunHistoryEntry entry;

  /// A forfeited entry never has a Close. `games_record_service.py`'s
  /// `get_close_payload` requires `entry.state in ("finished", "void")` and
  /// 409s otherwise — by that module's own docstring, "a forfeit has no
  /// Close." Routing a forfeit row to [GamesCloseScreen] would therefore
  /// always land on the generic error state instead of anything dignified,
  /// so this row answers inline instead (the Wind-Up's actual reachable
  /// home this slice) rather than opening a screen guaranteed to fail.
  bool get _isForfeit => entry.state == 'forfeit';

  bool get _canOpenClose =>
      !_isForfeit && entry.runId != null && entry.runId!.isNotEmpty;

  @override
  Widget build(BuildContext context) {
    final delta = entry.careerPointsDelta;
    final deltaColor = delta > 0
        ? AmiColors.hexGreen
        : (delta < 0 ? AmiColors.hexRed : AmiColors.textMed);
    final tappable = _canOpenClose || _isForfeit;

    final row = Padding(
      padding: const EdgeInsets.symmetric(vertical: 6),
      child: Row(
        children: [
          HexChip(
            label: entry.cadence.toUpperCase(),
            color: _stateColor(entry.state),
            variant: HexChipVariant.outlined,
          ),
          const SizedBox(width: AmiSpacing.s),
          Expanded(
            child: Text(
              entry.closedAt != null
                  ? DateFormat('MMM d').format(entry.closedAt!)
                  : entry.state.toUpperCase(),
              style: AmiTypography.bodySm,
            ),
          ),
          Text(
            _isolateNumeric('${delta >= 0 ? '+' : ''}$delta'),
            style: AmiTypography.dataMd.copyWith(color: deltaColor),
          ),
          if (tappable) ...[
            const SizedBox(width: AmiSpacing.xs),
            const Icon(Icons.chevron_right, size: 16, color: AmiColors.textLow),
          ],
        ],
      ),
    );

    if (!tappable) return row;
    return InkWell(
      onTap: () => _isForfeit
          ? _showWindUpNote(context)
          : Navigator.of(context).push(
              MaterialPageRoute(
                  builder: (_) => GamesCloseScreen(runId: entry.runId!)),
            ),
      child: row,
    );
  }

  /// The Wind-Up, inline — "a chapter, not a fail screen" (design §10,
  /// §6.7), built entirely from data this row already has rather than a
  /// round trip that would 409.
  void _showWindUpNote(BuildContext context) {
    final l = AppLocalizations.of(context);
    showDialog<void>(
      context: context,
      builder: (_) => Dialog(
        backgroundColor: AmiColors.slate800,
        child: Padding(
          padding: const EdgeInsets.all(AmiSpacing.m),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(l.gamesCloseTitleForfeit, style: AmiTypography.h4),
              const SizedBox(height: AmiSpacing.s),
              Text(l.gamesDebriefForfeitNote, style: AmiTypography.body),
            ],
          ),
        ),
      ),
    );
  }

  Color _stateColor(String state) {
    switch (state) {
      case 'forfeit':
        return AmiColors.hexBlue;
      case 'void':
        return AmiColors.hexCyan;
      default:
        return AmiColors.hexGreen;
    }
  }
}
