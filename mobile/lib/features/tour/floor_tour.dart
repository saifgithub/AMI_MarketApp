/// Coach-mark step definitions for the Floor tab tour (5 steps).
library;

import 'package:ami_trade/features/tour/tour_card.dart';
import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:flutter/material.dart';
import 'package:tutorial_coach_mark/tutorial_coach_mark.dart';

List<TargetFocus> buildFloorTargets({
  required AppLocalizations l,
  required GlobalKey conciergeKey,
  required GlobalKey agentKey0,
  required GlobalKey agentKey4,
  required GlobalKey challengeKey,
  required GlobalKey conveneKey,
  required VoidCallback onTryConvene,
}) {
  final targets = <TargetFocus>[
    // Step 1 — Concierge
    TargetFocus(
      identify: 'floor_concierge',
      keyTarget: conciergeKey,
      shape: ShapeLightFocus.Circle,
      paddingFocus: 12,
      contents: [
        TargetContent(
          align: ContentAlign.bottom,
          builder: (ctx, ctrl) => TourCard(
            title: l.tourFloor1Title,
            body: l.tourFloor1Body,
            controller: ctrl,
            skipLabel: l.tourSkip,
            nextLabel: l.tourNext,
          ),
        ),
      ],
    ),

    // Step 2 — First agent tile (Fundamentals Analyst)
    TargetFocus(
      identify: 'floor_agent0',
      keyTarget: agentKey0,
      shape: ShapeLightFocus.Circle,
      paddingFocus: 16,
      contents: [
        TargetContent(
          align: ContentAlign.bottom,
          builder: (ctx, ctrl) => TourCard(
            title: l.tourFloor2Title,
            body: l.tourFloor2Body,
            controller: ctrl,
            skipLabel: l.tourSkip,
            nextLabel: l.tourNext,
          ),
        ),
      ],
    ),

    // Step 3 — Another agent tile (explains lock state)
    TargetFocus(
      identify: 'floor_agent4',
      keyTarget: agentKey4,
      shape: ShapeLightFocus.Circle,
      paddingFocus: 16,
      contents: [
        TargetContent(
          align: ContentAlign.bottom,
          builder: (ctx, ctrl) => TourCard(
            title: l.tourFloor3Title,
            body: l.tourFloor3Body,
            controller: ctrl,
            skipLabel: l.tourSkip,
            nextLabel: l.tourNext,
          ),
        ),
      ],
    ),
  ];

  // Step 4 — Daily challenge (conditional: only if the challenge card rendered)
  final challengeRO = challengeKey.currentContext?.findRenderObject();
  if (challengeRO != null) {
    final challengeBox = challengeRO as RenderBox?;
    if (challengeBox != null && challengeBox.size.height > 0) {
      targets.add(
        TargetFocus(
          identify: 'floor_challenge',
          keyTarget: challengeKey,
          shape: ShapeLightFocus.RRect,
          radius: 12,
          paddingFocus: 8,
          contents: [
            TargetContent(
              align: ContentAlign.top,
              builder: (ctx, ctrl) => TourCard(
                title: l.tourFloor4Title,
                body: l.tourFloor4Body,
                controller: ctrl,
                skipLabel: l.tourSkip,
                nextLabel: l.tourNext,
              ),
            ),
          ],
        ),
      );
    }
  }

  // Step 5 — Convene the Room (always last; has "Try it now" CTA)
  targets.add(
    TargetFocus(
      identify: 'floor_convene',
      keyTarget: conveneKey,
      shape: ShapeLightFocus.Circle,
      paddingFocus: 12,
      color: AmiColors.hexGreen.withValues(alpha: 0.15),
      contents: [
        TargetContent(
          align: ContentAlign.top,
          builder: (ctx, ctrl) => TourCard(
            title: l.tourFloor5Title,
            body: l.tourFloor5Body,
            controller: ctrl,
            skipLabel: l.tourSkip,
            nextLabel: l.tourDone,
            tryNowLabel: l.tourConveneTryNow,
            onTryNow: onTryConvene,
          ),
        ),
      ],
    ),
  );

  return targets;
}
