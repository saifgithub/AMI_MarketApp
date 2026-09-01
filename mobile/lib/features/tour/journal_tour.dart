/// Coach-mark step definitions for the Journal tab tour (3 steps).
library;

import 'package:ami_trade/features/tour/ami_tour_overlay.dart';
import 'package:ami_trade/features/tour/tour_card.dart';
import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:flutter/material.dart';

List<AmiTourStep> buildJournalTargets({
  required AppLocalizations l,
  required GlobalKey filterRowKey,
  required GlobalKey searchKey,
  required GlobalKey listKey,
}) {
  return [
    // Step 1 — Filter chips
    AmiTourStep(
      identify: 'journal_filter_row',
      target: filterRowKey,
      shape: AmiTourShape.roundedRect,
      radius: 8,
      paddingFocus: 6,
      align: AmiTourAlign.bottom,
      builder: (ctx, ctrl) => TourCard(
        title: l.tourJournal1Title,
        body: l.tourJournal1Body,
        controller: ctrl,
        skipLabel: l.tourSkip,
        nextLabel: l.tourNext,
      ),
    ),

    // Step 2 — Search bar
    AmiTourStep(
      identify: 'journal_search',
      target: searchKey,
      shape: AmiTourShape.roundedRect,
      radius: 8,
      paddingFocus: 6,
      align: AmiTourAlign.bottom,
      builder: (ctx, ctrl) => TourCard(
        title: l.tourJournal2Title,
        body: l.tourJournal2Body,
        controller: ctrl,
        skipLabel: l.tourSkip,
        nextLabel: l.tourNext,
      ),
    ),

    // Step 3 — Entry list area. The target fills most of the screen, so
    // AmiTourAlign.top would push the card off the top edge. Pin it with
    // `absoluteTop` instead, near the top of the list.
    AmiTourStep(
      identify: 'journal_list',
      target: listKey,
      shape: AmiTourShape.roundedRect,
      radius: 8,
      paddingFocus: 4,
      align: AmiTourAlign.bottom,
      absoluteTop: 180,
      builder: (ctx, ctrl) => TourCard(
        title: l.tourJournal3Title,
        body: l.tourJournal3Body,
        controller: ctrl,
        skipLabel: l.tourSkip,
        nextLabel: l.tourDone,
      ),
    ),
  ];
}
