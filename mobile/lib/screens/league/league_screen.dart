/// CR011 (C3) — LeagueScreen: this week's standings + a history sheet. My row
/// is highlighted; the top-5 promotion zone tints green and the bottom-5
/// relegation zone tints red at low opacity. Reads CR010's league providers.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/league.dart';
import 'package:ami_trade/screens/league/league_common.dart';
import 'package:ami_trade/state/league_providers.dart';
import 'package:ami_trade/state/onboarding_providers.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:ami_trade/widgets/hex/hex_avatar.dart';
import 'package:ami_trade/widgets/hex/hex_chip.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

class LeagueScreen extends ConsumerWidget {
  const LeagueScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l = AppLocalizations.of(context);
    final async = ref.watch(standingsProvider);
    return Scaffold(
      backgroundColor: AmiColors.slate900,
      appBar: AppBar(
        backgroundColor: AmiColors.slate900,
        title: Text(l.leagueTitle, style: AmiTypography.labelMono),
        actions: [
          IconButton(
            tooltip: l.leagueHistoryTitle,
            icon: const Icon(Icons.history),
            onPressed: () => _showHistory(context, l),
          ),
        ],
      ),
      body: SafeArea(
        child: async.when(
          loading: () => const Center(child: CircularProgressIndicator()),
          error: (_, __) => _Centered(text: l.leagueError),
          data: (standings) {
            if (standings == null || standings.members.isEmpty) {
              return _Centered(text: l.leagueUnassigned);
            }
            final total = standings.members.length;
            return Column(
              children: [
                _Header(standings: standings, l: l),
                Expanded(
                  child: ListView.builder(
                    padding:
                        const EdgeInsets.symmetric(vertical: AmiSpacing.s),
                    itemCount: total,
                    itemBuilder: (context, i) => _StandingRow(
                      member: standings.members[i],
                      total: total,
                      you: l.leagueYou,
                    ),
                  ),
                ),
              ],
            );
          },
        ),
      ),
    );
  }

  Future<void> _showHistory(BuildContext context, AppLocalizations l) {
    return showModalBottomSheet<void>(
      context: context,
      backgroundColor: AmiColors.slate800,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(16)),
      ),
      builder: (_) => _HistorySheet(l: l),
    );
  }
}


class _Centered extends StatelessWidget {
  const _Centered({required this.text});
  final String text;

  @override
  Widget build(BuildContext context) => Center(
        child: Padding(
          padding: const EdgeInsets.all(AmiSpacing.xl),
          child: Text(
            text,
            textAlign: TextAlign.center,
            style: AmiTypography.body.copyWith(color: AmiColors.textLow),
          ),
        ),
      );
}


class _Header extends StatelessWidget {
  const _Header({required this.standings, required this.l});
  final LeagueStandings standings;
  final AppLocalizations l;

  @override
  Widget build(BuildContext context) {
    LeagueMemberRow? mine;
    for (final m in standings.members) {
      if (m.isMe) {
        mine = m;
        break;
      }
    }
    final rollsIn = leagueRollsIn(standings.endsAt);
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(AmiSpacing.m),
      decoration: const BoxDecoration(
        color: AmiColors.slate800,
        border: Border(bottom: BorderSide(color: AmiColors.slate700)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              HexChip(
                label: leagueTierLabel(standings.tier),
                color: leagueTierColor(standings.tier),
                variant: HexChipVariant.tinted,
              ),
              const Spacer(),
              if (rollsIn.isNotEmpty)
                Text(
                  '${l.leagueRollsInLabel} $rollsIn',
                  style:
                      AmiTypography.caption.copyWith(color: AmiColors.textLow),
                ),
            ],
          ),
          if (mine != null) ...[
            const SizedBox(height: AmiSpacing.s),
            Row(
              children: [
                Text(
                  '${l.leagueRankLabel} ${mine.rank} / ${standings.members.length}',
                  style: AmiTypography.dataMd.copyWith(color: AmiColors.textHigh),
                ),
                const Spacer(),
                Text(
                  '${mine.points} ${l.leaguePts}',
                  style: AmiTypography.dataMd.copyWith(color: AmiColors.hexGreen),
                ),
              ],
            ),
          ],
        ],
      ),
    );
  }
}


class _StandingRow extends StatelessWidget {
  const _StandingRow({
    required this.member,
    required this.total,
    required this.you,
  });
  final LeagueMemberRow member;
  final int total;
  final String you;

  @override
  Widget build(BuildContext context) {
    final promo = member.rank <= 5;
    // M2: the backend relegates bottom-5 only for cohorts >= 10
    // (MIN_COHORT_FOR_RELEGATION) — don't show the red tint below that.
    final releg = total >= 10 && member.rank > total - 5;
    Color? zone;
    if (member.isMe) {
      zone = AmiColors.hexBlue.withValues(alpha: 0.14);
    } else if (promo) {
      zone = AmiColors.hexGreen.withValues(alpha: 0.06);
    } else if (releg) {
      zone = AmiColors.hexRed.withValues(alpha: 0.06);
    }
    final name = member.displayName ?? member.handle;
    return Container(
      color: zone,
      padding: const EdgeInsets.symmetric(
          horizontal: AmiSpacing.m, vertical: AmiSpacing.s),
      child: Row(
        children: [
          SizedBox(
            width: 28,
            child: Text('${member.rank}',
                style:
                    AmiTypography.labelMono.copyWith(color: AmiColors.textMed)),
          ),
          HexAvatar(
            label: _initials(member.handle),
            color: member.isMe ? AmiColors.hexBlue : AmiColors.slate600,
            size: 32,
          ),
          const SizedBox(width: AmiSpacing.s),
          Expanded(
            child: Row(
              children: [
                Flexible(
                  child: Text(
                    name,
                    overflow: TextOverflow.ellipsis,
                    style: AmiTypography.body.copyWith(
                      color:
                          member.isMe ? AmiColors.textHigh : AmiColors.textMed,
                    ),
                  ),
                ),
                if (member.isMe) ...[
                  const SizedBox(width: 6),
                  Text(you,
                      style: AmiTypography.caption
                          .copyWith(color: AmiColors.hexBlue)),
                ],
              ],
            ),
          ),
          Text('${member.points}',
              style: AmiTypography.dataMd.copyWith(color: AmiColors.textHigh)),
        ],
      ),
    );
  }

  String _initials(String handle) {
    final parts =
        handle.trim().split(RegExp(r'\s+')).where((p) => p.isNotEmpty).toList();
    if (parts.isEmpty) return '—';
    if (parts.length == 1) {
      final p = parts.first;
      return (p.length >= 2 ? p.substring(0, 2) : p).toUpperCase();
    }
    return (parts[0][0] + parts[1][0]).toUpperCase();
  }
}


class _HistorySheet extends ConsumerStatefulWidget {
  const _HistorySheet({required this.l});
  final AppLocalizations l;

  @override
  ConsumerState<_HistorySheet> createState() => _HistorySheetState();
}

class _HistorySheetState extends ConsumerState<_HistorySheet> {
  late final Future<List<LeagueHistoryEntry>> _future;

  @override
  void initState() {
    super.initState();
    _future = ref.read(apiClientProvider).leagueHistory();
  }

  @override
  Widget build(BuildContext context) {
    final l = widget.l;
    return SafeArea(
      child: Padding(
        padding: const EdgeInsets.all(AmiSpacing.l),
        child: FutureBuilder<List<LeagueHistoryEntry>>(
          future: _future,
          builder: (context, snap) {
            final rows = snap.data ?? const <LeagueHistoryEntry>[];
            return Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(l.leagueHistoryTitle, style: AmiTypography.labelMono),
                const SizedBox(height: AmiSpacing.m),
                if (snap.connectionState == ConnectionState.waiting)
                  const Padding(
                    padding: EdgeInsets.all(AmiSpacing.m),
                    child: Center(child: CircularProgressIndicator()),
                  )
                else if (rows.isEmpty)
                  Text(l.leagueHistoryEmpty,
                      style: AmiTypography.body
                          .copyWith(color: AmiColors.textLow))
                else
                  for (final e in rows)
                    Padding(
                      padding: const EdgeInsets.only(bottom: AmiSpacing.s),
                      child: Row(
                        children: [
                          HexChip(
                            label: leagueTierLabel(e.tier),
                            color: leagueTierColor(e.tier),
                            variant: HexChipVariant.outlined,
                            fontSize: 10,
                          ),
                          const SizedBox(width: AmiSpacing.s),
                          Text(e.week, style: AmiTypography.caption),
                          const Spacer(),
                          Text('#${e.rankFinal}',
                              style: AmiTypography.body
                                  .copyWith(color: AmiColors.textMed)),
                          const SizedBox(width: AmiSpacing.s),
                          _OutcomeTag(outcome: e.outcome, l: l),
                        ],
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


class _OutcomeTag extends StatelessWidget {
  const _OutcomeTag({required this.outcome, required this.l});
  final String? outcome;
  final AppLocalizations l;

  @override
  Widget build(BuildContext context) {
    final (label, color) = switch (outcome) {
      'promoted' => (l.leagueOutcomePromoted, AmiColors.hexGreen),
      'relegated' => (l.leagueOutcomeRelegated, AmiColors.hexRed),
      _ => (l.leagueOutcomeStay, AmiColors.textLow),
    };
    return Text(label, style: AmiTypography.caption.copyWith(color: color));
  }
}
