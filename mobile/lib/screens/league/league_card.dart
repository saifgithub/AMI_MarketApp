/// CR011 (C3) — Floor LeagueCard: tier chip + rank + points-this-week + a
/// "rolls in Nd Nh" countdown, tapping into the LeagueScreen. Unassigned state
/// nudges toward the first league. Reads CR010's league providers; hides itself
/// until `leagueMe` loads.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/screens/league/league_common.dart';
import 'package:ami_trade/screens/league/league_screen.dart';
import 'package:ami_trade/state/league_providers.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:ami_trade/widgets/hex/accent_card.dart';
import 'package:ami_trade/widgets/hex/hex_chip.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

class LeagueCard extends ConsumerWidget {
  const LeagueCard({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l = AppLocalizations.of(context);
    final me = ref.watch(leagueMeProvider).valueOrNull;
    if (me == null) return const SizedBox.shrink();
    final standings = ref.watch(standingsProvider).valueOrNull;
    final tierColor = leagueTierColor(me.tier);
    final assigned = me.rank != null && standings != null;
    final rollsIn = standings == null ? '' : leagueRollsIn(standings.endsAt);

    return AccentCard(
      accent: tierColor,
      onTap: () => Navigator.of(context).push(
        MaterialPageRoute<void>(builder: (_) => const LeagueScreen()),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(Icons.emoji_events_outlined,
                  color: AmiColors.hexAmber, size: 16),
              const SizedBox(width: 6),
              Text(l.leagueCardHeading,
                  style: AmiTypography.labelMono
                      .copyWith(color: AmiColors.hexAmber)),
              const Spacer(),
              HexChip(
                label: leagueTierLabel(me.tier),
                color: tierColor,
                variant: HexChipVariant.tinted,
              ),
            ],
          ),
          const SizedBox(height: AmiSpacing.s),
          if (assigned) ...[
            Row(
              children: [
                Text(
                  '${l.leagueRankLabel} ${me.rank} / ${standings.members.length}',
                  style:
                      AmiTypography.body.copyWith(fontWeight: FontWeight.w700),
                ),
                const Spacer(),
                Text('${me.pointsThisWeek} ${l.leaguePts}',
                    style:
                        AmiTypography.body.copyWith(color: AmiColors.hexGreen)),
              ],
            ),
            if (rollsIn.isNotEmpty) ...[
              const SizedBox(height: 4),
              Text('${l.leagueRollsInLabel} $rollsIn',
                  style:
                      AmiTypography.caption.copyWith(color: AmiColors.textLow)),
            ],
          ] else
            Text(l.leagueUnassigned,
                style:
                    AmiTypography.caption.copyWith(color: AmiColors.textLow)),
        ],
      ),
    );
  }
}
