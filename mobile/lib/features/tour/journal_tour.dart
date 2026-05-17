/// Coach-mark step definitions for the Journal tab tour (3 steps).
library;

import 'package:ami_trade/features/tour/tour_card.dart';
import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:flutter/material.dart';
import 'package:tutorial_coach_mark/tutorial_coach_mark.dart';

List<TargetFocus> buildJournalTargets({
  required AppLocalizations l,
  required GlobalKey filterRowKey,
  required GlobalKey searchKey,
  required GlobalKey listKey,
}) {
  return [
    // Step 1 — Filter chips
    TargetFocus(
      identify: 'journal_filter_row',
      keyTarget: filterRowKey,
      shape: ShapeLightFocus.RRect,
      radius: 8,
      paddingFocus: 6,
      contents: [
        TargetContent(
          align: ContentAlign.bottom,
          builder: (ctx, ctrl) => TourCard(
            title: l.tourJournal1Title,
            body: l.tourJournal1Body,
            controller: ctrl,
            skipLabel: l.tourSkip,
            nextLabel: l.tourNext,
          ),
        ),
      ],
    ),

    // Step 2 — Search bar
    TargetFocus(
      identify: 'journal_search',
      keyTarget: searchKey,
      shape: ShapeLightFocus.RRect,
      radius: 8,
      paddingFocus: 6,
      contents: [
        TargetContent(
          align: ContentAlign.bottom,
          builder: (ctx, ctrl) => TourCard(
            title: l.tourJournal2Title,
            body: l.tourJournal2Body,
            controller: ctrl,
            skipLabel: l.tourSkip,
            nextLabel: l.tourNext,
          ),
        ),
      ],
    ),

    // Step 3 — Entry list area
    TargetFocus(
      identify: 'journal_list',
      keyTarget: listKey,
      shape: ShapeLightFocus.RRect,
      radius: 8,
      paddingFocus: 8,
      contents: [
        TargetContent(
          align: ContentAlign.top,
          builder: (ctx, ctrl) => TourCard(
            title: l.tourJournal3Title,
            body: l.tourJournal3Body,
            controller: ctrl,
            skipLabel: l.tourSkip,
            nextLabel: l.tourDone,
          ),
        ),
      ],
    ),
  ];
}
