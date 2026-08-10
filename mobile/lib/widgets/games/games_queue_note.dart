/// CR109 slice 2 — queue-first framing (design §5.1, §13.3; Amendment D "TKT").
///
/// US regular market hours are evening in the Gulf and past midnight in
/// Malaysia, so for AMI Trade's target markets an out-of-hours order is the
/// NORMAL path, not an edge case — CR109.md §5.1: "queue-first is the
/// primary flow, not the fallback." The ticket, the run card and the
/// confirm result all reuse this one note so the "plan tonight, fills at
/// the open" framing reads the same everywhere it appears.
///
/// Colour-neutral by design: a queued order is not a problem to flag, so
/// this never renders amber/red — that would relitigate the exact framing
/// it exists to establish.
///
/// **Two forms, same words.** [GamesQueueNote] is the full paragraph;
/// [GamesQueueInfoIcon] is a tappable ⓘ that shows it on demand. Saiful, on
/// build 76: *"The note about the trade only happening when the US market
/// opens does not need to be displayed all the time."* He is right — three
/// lines of standing copy is how a rule becomes wallpaper, and it was
/// printing TWICE on one ticket (top, and again on the confirm card). The
/// icon keeps it one tap away rather than deleting it, because for a first-
/// time player it is the single most surprising thing the game does.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:flutter/material.dart';

class GamesQueueNote extends StatelessWidget {
  const GamesQueueNote({super.key});

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Icon(Icons.schedule, color: AmiColors.textLow, size: 14),
        const SizedBox(width: AmiSpacing.xs),
        Expanded(
          child: Text(l.gamesQueueFirstNote, style: AmiTypography.caption),
        ),
      ],
    );
  }
}

/// The same note, on demand.
///
/// Sits beside a heading rather than under it, so it costs one line of
/// nothing instead of three lines of paragraph. Tapping opens a dialog with
/// the identical string — one source of copy, two presentations, so the two
/// can never drift apart.
class GamesQueueInfoIcon extends StatelessWidget {
  const GamesQueueInfoIcon({super.key});

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    return Semantics(
      button: true,
      label: l.gamesQueueInfoTooltip,
      child: InkWell(
        onTap: () => showDialog<void>(
          context: context,
          builder: (ctx) => AlertDialog(
            backgroundColor: AmiColors.slate800,
            title: Text(l.gamesQueueInfoTitle, style: AmiTypography.h4),
            content: Text(l.gamesQueueFirstNote, style: AmiTypography.body),
            actions: [
              TextButton(
                onPressed: () => Navigator.of(ctx).pop(),
                child: Text(l.gamesQueueInfoDismiss),
              ),
            ],
          ),
        ),
        borderRadius: BorderRadius.circular(14),
        child: const Padding(
          padding: EdgeInsets.all(4),
          child: Icon(
            Icons.info_outline,
            color: AmiColors.textLow,
            size: 16,
          ),
        ),
      ),
    );
  }
}
