/// CR267 WP-25 — "Changed from X to Y": the card on the Verdict Board, and the
/// one-line form on a Journal entry, saying why this Room's call differs from
/// the user's previous one on the same name.
///
/// The backend builds the explainer from stored fields (no agent writes it);
/// this file only decides how to say it. Two refusals shape the wording:
///
///  1. "The inputs were unchanged" is said only when the server says
///     `same_inputs_flip`. When it could not compare the two Rooms' inputs the
///     card says that instead — an empty list of changes is never read as
///     "nothing changed".
///  2. No answers section, and no apology, when the coded-rule answers are
///     unavailable for either Room.
///
/// Used by `RoomBoard` (live Room and Journal detail, one widget — T-TWICE) and
/// by the Journal list tile for the one-liner.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/room.dart';
import 'package:ami_trade/qa/semantics_ids.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:flutter/material.dart';

/// Short human label for a narrow-question id. An id this build does not know
/// is shown as its own words (underscores to spaces) rather than dropped.
String flipQuestionLabel(AppLocalizations l, String id) {
  switch (id) {
    case 'bear_objection_answered':
      return l.roomFlipQBearObjectionAnswered;
    case 'catalyst_in_horizon':
      return l.roomFlipQCatalystInHorizon;
    case 'terminal_vulnerability':
      return l.roomFlipQTerminalVulnerability;
    case 'event_risk_wait':
      return l.roomFlipQEventRiskWait;
    case 'thesis_material_directional':
      return l.roomFlipQThesisMaterialDirectional;
    case 'trade_proposed':
      return l.roomFlipQTradeProposed;
  }
  return id.replaceAll('_', ' ');
}

/// The sentence that stands in for the changed-inputs list when the list cannot
/// speak for itself, or `null` when the list should be shown.
String? flipInputsStatement(AppLocalizations l, FlipExplainer e) {
  if (!e.inputsCompared) return l.roomFlipNotCompared;
  if (e.sameInputsFlip) return l.roomFlipSameInputs;
  return null;
}

class RoomFlipCard extends StatelessWidget {
  const RoomFlipCard({super.key, required this.explainer});

  final FlipExplainer explainer;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final e = explainer;
    final statement = flipInputsStatement(l, e);
    final summaries = [
      for (final c in e.changedInputs)
        if (c.summary.trim().isNotEmpty) c.summary,
    ];
    return Semantics(
      identifier: RoomFlipIds.card,
      container: true,
      child: Container(
        key: const Key('roomFlipCard'),
        width: double.infinity,
        padding: const EdgeInsets.all(AmiSpacing.s),
        decoration: BoxDecoration(
          color: AmiColors.slate800,
          borderRadius: BorderRadius.circular(AmiRadii.card),
          border: Border.all(color: AmiColors.slate700),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              l.roomFlipHeading(e.previousAction, e.newAction),
              style: AmiTypography.labelMono
                  .copyWith(fontSize: 10, color: AmiColors.textLow),
            ),
            if (statement != null) ...[
              const SizedBox(height: AmiSpacing.xs),
              Text(statement,
                  key: const Key('roomFlipStatement'),
                  style: AmiTypography.caption),
            ],
            if (summaries.isNotEmpty) ...[
              const SizedBox(height: AmiSpacing.xs),
              for (final s in summaries)
                Padding(
                  padding: const EdgeInsets.only(top: 2),
                  child: Text(s, style: AmiTypography.caption),
                ),
            ],
            if (e.answersAvailable && e.changedAnswers.isNotEmpty) ...[
              const SizedBox(height: AmiSpacing.s),
              Text(
                l.roomFlipAnswersHeading,
                style: AmiTypography.labelMono
                    .copyWith(fontSize: 9, color: AmiColors.textLow),
              ),
              for (final a in e.changedAnswers)
                Padding(
                  padding: const EdgeInsets.only(top: 2),
                  child: Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Expanded(
                        child: Text(
                          flipQuestionLabel(l, a.question),
                          style: AmiTypography.caption,
                        ),
                      ),
                      const SizedBox(width: AmiSpacing.s),
                      // Composed in code, not the ARB (CR133's nav-path guard
                      // scans arrows there), and locked LTR so the two answers
                      // do not swap sides under RTL.
                      Text(
                        '${a.before} → ${a.after}',
                        style: AmiTypography.statSmall
                            .copyWith(color: AmiColors.textHigh),
                        textDirection: TextDirection.ltr,
                      ),
                    ],
                  ),
                ),
            ],
          ],
        ),
      ),
    );
  }
}

/// "Changed from X to Y: <first changed input, or the same-inputs line>" for a
/// Journal list tile. With nothing to add after the colon it is just
/// "Changed from X to Y".
class RoomFlipJournalLine extends StatelessWidget {
  const RoomFlipJournalLine({super.key, required this.explainer});

  final FlipExplainer explainer;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final e = explainer;
    final detail = flipInputsStatement(l, e) ??
        e.changedInputs
            .map((c) => c.summary.trim())
            .where((s) => s.isNotEmpty)
            .firstOrNull;
    return Semantics(
      identifier: RoomFlipIds.journalLine,
      container: true,
      child: Text(
        detail == null
            ? l.roomFlipJournalLineBare(e.previousAction, e.newAction)
            : l.roomFlipJournalLine(e.previousAction, e.newAction, detail),
        key: const Key('roomFlipJournalLine'),
        style: AmiTypography.caption.copyWith(color: AmiColors.textHigh),
        maxLines: 3,
        overflow: TextOverflow.ellipsis,
      ),
    );
  }
}
