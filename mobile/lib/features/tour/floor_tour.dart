/// CR173 §5.10 — the Floor tour, 5 stops down to 3.
///
/// The old tour had one stop per thing on the screen: the Concierge hex, an
/// unlocked agent, a locked agent, the challenge, CONVENE. Two of those five no
/// longer exist on this surface, and the count itself was a symptom — a landing
/// screen that needs five explanations is a screen that does not explain
/// itself.
///
/// Three stops, each teaching something a user genuinely cannot infer by
/// looking: that the header **swipes** (a carousel that looks like a card does
/// not get swiped — the same Friedman finding the peek slice answers), that one
/// box takes **both** a ticker and a question, and that the firm row leads to
/// twelve people rather than a settings list.
///
/// **No `Try it now` on CONVENE any more.** The old step 5 offered to open the
/// convene sheet mid-tour; the omnibox's own CTA is now one tap from where the
/// coach mark sits, and an action that fires a real Room run out of a
/// walkthrough spends a credit the user did not decide to spend.
library;

import 'package:ami_trade/features/tour/ami_tour_overlay.dart';
import 'package:ami_trade/features/tour/tour_card.dart';
import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:flutter/material.dart';

List<AmiTourStep> buildFloorTargets({
  required AppLocalizations l,
  required GlobalKey carouselKey,
  required GlobalKey omniboxKey,
  required GlobalKey firmKey,
}) {
  return [
    AmiTourStep(
      identify: 'floor_carousel',
      target: carouselKey,
      shape: AmiTourShape.roundedRect,
      radius: 12,
      paddingFocus: 8,
      align: AmiTourAlign.bottom,
      builder: (ctx, ctrl) => TourCard(
        title: l.tourFloor1Title,
        body: l.tourFloor1Body,
        controller: ctrl,
        skipLabel: l.tourSkip,
        nextLabel: l.tourNext,
      ),
    ),
    AmiTourStep(
      identify: 'floor_omnibox',
      target: omniboxKey,
      shape: AmiTourShape.roundedRect,
      radius: 8,
      paddingFocus: 6,
      align: AmiTourAlign.bottom,
      builder: (ctx, ctrl) => TourCard(
        title: l.tourFloor2Title,
        body: l.tourFloor2Body,
        controller: ctrl,
        skipLabel: l.tourSkip,
        nextLabel: l.tourNext,
      ),
    ),
    AmiTourStep(
      identify: 'floor_firm',
      target: firmKey,
      shape: AmiTourShape.roundedRect,
      radius: 8,
      paddingFocus: 6,
      align: AmiTourAlign.top,
      builder: (ctx, ctrl) => TourCard(
        title: l.tourFloor3Title,
        body: l.tourFloor3Body,
        controller: ctrl,
        skipLabel: l.tourSkip,
        nextLabel: l.tourDone,
      ),
    ),
  ];
}
