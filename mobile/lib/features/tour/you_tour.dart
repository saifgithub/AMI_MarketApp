/// CR180 — coach-mark steps for the `YOU` tab (4 steps).
///
/// `YOU` is the one tab with nothing behind it that the user has seen before:
/// its two familiar halves arrived from somewhere else and its third did not
/// exist. So the tour teaches the things a user cannot infer by looking:
/// that this tab is segmented at all, that the mandate lives inside SETTINGS
/// rather than behind a gear, what the JOURNAL is *for*, and what INSIGHTS is
/// for.
///
/// CR190 added the JOURNAL step. The Journal's own 3-step tour only fires
/// once the user taps into the segment — a learner who never taps it was
/// never told it exists, or why. This step is the telling, and its frame is
/// deliberate (Saiful, bug a345042c): the Journal is where you record
/// reasoning and learn from outcomes — a learning tool, not a signal feed.
/// Steps follow the segment bar's left-to-right order: SETTINGS, JOURNAL,
/// INSIGHTS.
library;

import 'package:ami_trade/features/tour/ami_tour_overlay.dart';
import 'package:ami_trade/features/tour/tour_card.dart';
import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:flutter/material.dart';

List<AmiTourStep> buildYouTargets({
  required AppLocalizations l,
  required GlobalKey segmentBarKey,
  required GlobalKey settingsSegmentKey,
  required GlobalKey journalSegmentKey,
  required GlobalKey insightsSegmentKey,
}) {
  return [
    AmiTourStep(
      identify: 'you_segments',
      target: segmentBarKey,
      shape: AmiTourShape.roundedRect,
      radius: 4,
      paddingFocus: 6,
      align: AmiTourAlign.bottom,
      builder: (ctx, ctrl) => TourCard(
        title: l.tourYou1Title,
        body: l.tourYou1Body,
        controller: ctrl,
        skipLabel: l.tourSkip,
        nextLabel: l.tourNext,
      ),
    ),
    AmiTourStep(
      identify: 'you_settings',
      target: settingsSegmentKey,
      shape: AmiTourShape.roundedRect,
      radius: 4,
      paddingFocus: 6,
      align: AmiTourAlign.bottom,
      builder: (ctx, ctrl) => TourCard(
        title: l.tourYou2Title,
        body: l.tourYou2Body,
        controller: ctrl,
        skipLabel: l.tourSkip,
        nextLabel: l.tourNext,
      ),
    ),
    AmiTourStep(
      identify: 'you_journal',
      target: journalSegmentKey,
      shape: AmiTourShape.roundedRect,
      radius: 4,
      paddingFocus: 6,
      align: AmiTourAlign.bottom,
      builder: (ctx, ctrl) => TourCard(
        title: l.tourYouJournalTitle,
        body: l.tourYouJournalBody,
        controller: ctrl,
        skipLabel: l.tourSkip,
        nextLabel: l.tourNext,
      ),
    ),
    AmiTourStep(
      identify: 'you_insights',
      target: insightsSegmentKey,
      shape: AmiTourShape.roundedRect,
      radius: 4,
      paddingFocus: 6,
      align: AmiTourAlign.bottom,
      builder: (ctx, ctrl) => TourCard(
        title: l.tourYou3Title,
        body: l.tourYou3Body,
        controller: ctrl,
        skipLabel: l.tourSkip,
        nextLabel: l.tourDone,
      ),
    ),
  ];
}
