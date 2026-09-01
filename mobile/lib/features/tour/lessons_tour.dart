/// Coach-mark step definitions for the Lessons tab tour (3 steps).
library;

import 'package:ami_trade/features/tour/ami_tour_overlay.dart';
import 'package:ami_trade/features/tour/tour_card.dart';
import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:flutter/material.dart';

List<AmiTourStep> buildLessonsTargets({
  required AppLocalizations l,
  required GlobalKey headerKey,
  required GlobalKey progressKey,
  required GlobalKey hexClusterKey,
}) {
  return [
    // Step 1 — Header
    AmiTourStep(
      identify: 'lessons_header',
      target: headerKey,
      shape: AmiTourShape.roundedRect,
      radius: 0,
      paddingFocus: 4,
      align: AmiTourAlign.bottom,
      builder: (ctx, ctrl) => TourCard(
        title: l.tourLessons1Title,
        body: l.tourLessons1Body,
        controller: ctrl,
        skipLabel: l.tourSkip,
        nextLabel: l.tourNext,
      ),
    ),

    // Step 2 — Slim progress bar
    AmiTourStep(
      identify: 'lessons_progress',
      target: progressKey,
      shape: AmiTourShape.roundedRect,
      radius: 8,
      paddingFocus: 8,
      align: AmiTourAlign.bottom,
      builder: (ctx, ctrl) => TourCard(
        title: l.tourLessons2Title,
        body: l.tourLessons2Body,
        controller: ctrl,
        skipLabel: l.tourSkip,
        nextLabel: l.tourNext,
      ),
    ),

    // Step 3 — Hex cluster. Cluster sits in the upper-middle of the screen,
    // so position the tooltip BELOW it (the area beneath is empty space).
    AmiTourStep(
      identify: 'lessons_hex_cluster',
      target: hexClusterKey,
      shape: AmiTourShape.roundedRect,
      radius: 12,
      paddingFocus: 12,
      align: AmiTourAlign.bottom,
      builder: (ctx, ctrl) => TourCard(
        title: l.tourLessons3Title,
        body: l.tourLessons3Body,
        controller: ctrl,
        skipLabel: l.tourSkip,
        nextLabel: l.tourDone,
      ),
    ),
  ];
}
