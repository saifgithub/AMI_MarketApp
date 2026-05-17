/// Coach-mark step definitions for the Lessons tab tour (3 steps).
library;

import 'package:ami_trade/features/tour/tour_card.dart';
import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:flutter/material.dart';
import 'package:tutorial_coach_mark/tutorial_coach_mark.dart';

List<TargetFocus> buildLessonsTargets({
  required AppLocalizations l,
  required GlobalKey headerKey,
  required GlobalKey progressKey,
  required GlobalKey hexClusterKey,
}) {
  return [
    // Step 1 — Header
    TargetFocus(
      identify: 'lessons_header',
      keyTarget: headerKey,
      shape: ShapeLightFocus.RRect,
      radius: 0,
      paddingFocus: 4,
      contents: [
        TargetContent(
          align: ContentAlign.bottom,
          builder: (ctx, ctrl) => TourCard(
            title: l.tourLessons1Title,
            body: l.tourLessons1Body,
            controller: ctrl,
            skipLabel: l.tourSkip,
            nextLabel: l.tourNext,
          ),
        ),
      ],
    ),

    // Step 2 — Slim progress bar
    TargetFocus(
      identify: 'lessons_progress',
      keyTarget: progressKey,
      shape: ShapeLightFocus.RRect,
      radius: 8,
      paddingFocus: 8,
      contents: [
        TargetContent(
          align: ContentAlign.bottom,
          builder: (ctx, ctrl) => TourCard(
            title: l.tourLessons2Title,
            body: l.tourLessons2Body,
            controller: ctrl,
            skipLabel: l.tourSkip,
            nextLabel: l.tourNext,
          ),
        ),
      ],
    ),

    // Step 3 — Hex cluster
    TargetFocus(
      identify: 'lessons_hex_cluster',
      keyTarget: hexClusterKey,
      shape: ShapeLightFocus.RRect,
      radius: 12,
      paddingFocus: 12,
      contents: [
        TargetContent(
          align: ContentAlign.top,
          builder: (ctx, ctrl) => TourCard(
            title: l.tourLessons3Title,
            body: l.tourLessons3Body,
            controller: ctrl,
            skipLabel: l.tourSkip,
            nextLabel: l.tourDone,
          ),
        ),
      ],
    ),
  ];
}
