/// CR173 — one line above the comb: how close the call was, and who objected.
///
/// It sits *before* the eleven hexes deliberately. The comb is the evidence;
/// this is the finding. A user who reads nothing else on the board should still
/// learn that their team split 6–3 and that the Bear Researcher was the one who
/// argued the other way — which is the KIMI lane's whole point, and the reason
/// this strip is the team as evidence rather than the team as people.
///
/// Every honesty rule lives in `room_consensus.dart`; this file only decides
/// what the answer looks like. When that model returns null there is nothing to
/// draw, and drawing nothing is correct — the comb below already says why.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/agent.dart';
import 'package:ami_trade/models/room_board.dart';
import 'package:ami_trade/models/room_consensus.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:flutter/material.dart';

class RoomConsensusStrip extends StatelessWidget {
  const RoomConsensusStrip({super.key, required this.data});

  final RoomBoardData data;

  @override
  Widget build(BuildContext context) {
    final c = consensusFor(data);
    if (c == null) return const SizedBox.shrink();
    final l = AppLocalizations.of(context);

    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(AmiSpacing.s),
      decoration: BoxDecoration(
        color: AmiColors.slate900,
        borderRadius: BorderRadius.circular(AmiRadii.card),
        border: Border.all(color: AmiColors.slate700),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Text(l.roomConsensusHeading,
                  style: AmiTypography.labelMono
                      .copyWith(fontSize: 10, color: AmiColors.textLow)),
              const SizedBox(width: AmiSpacing.s),
              Text(
                // `6–3`, not `6 of 11`: the split is the point, and a total
                // that always sums to eleven says nothing (T-SUM11).
                '${c.withCall}–${c.againstCall}',
                style: AmiTypography.labelMono.copyWith(
                  fontSize: 13,
                  color: c.unanimous ? AmiColors.hexGreen : AmiColors.textHigh,
                ),
              ),
              if (c.neutral > 0) ...[
                const SizedBox(width: AmiSpacing.s),
                Text(l.roomConsensusNeutral(c.neutral),
                    style: AmiTypography.caption
                        .copyWith(fontSize: 10, color: AmiColors.textLow)),
              ],
            ],
          ),
          const SizedBox(height: 4),
          _dissentLine(l, c),
        ],
      ),
    );
  }

  Widget _dissentLine(AppLocalizations l, RoomConsensus c) {
    // Three states, three renderings — and the third is not a blank.
    if (!c.dissentApplies) {
      return Text(l.roomConsensusNoCall,
          style: AmiTypography.caption.copyWith(color: AmiColors.textLow));
    }
    final d = c.dissenter;
    if (d == null) {
      return Text(l.roomConsensusUnanimous(c.stated),
          style: AmiTypography.caption.copyWith(color: AmiColors.textMed));
    }
    final agent = agentById(d.agentId);
    return RichText(
      maxLines: 3,
      overflow: TextOverflow.ellipsis,
      text: TextSpan(
        style: AmiTypography.caption.copyWith(color: AmiColors.textMed),
        children: [
          TextSpan(
            text: l.roomConsensusDissents(agent.displayName),
            style: AmiTypography.caption
                .copyWith(color: agent.color, fontWeight: FontWeight.w600),
          ),
          // The dissenter's own headline, when they left one. Without it the
          // line names an objection and withholds it, which is worse than not
          // naming one — so the name only appears with something behind it.
          TextSpan(text: ' ${d.headline ?? l.roomCombNotStated}'),
        ],
      ),
    );
  }
}
