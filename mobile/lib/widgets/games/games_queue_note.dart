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
