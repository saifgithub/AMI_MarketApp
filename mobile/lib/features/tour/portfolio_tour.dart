/// Coach-mark step definitions for the Portfolio tab tour (3 steps).
library;

import 'package:ami_trade/features/tour/tour_card.dart';
import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:flutter/material.dart';
import 'package:tutorial_coach_mark/tutorial_coach_mark.dart';

List<TargetFocus> buildPortfolioTargets({
  required AppLocalizations l,
  required GlobalKey headerKey,
  required GlobalKey valueCardKey,
  required GlobalKey watchlistKey,
}) {
  return [
    // Step 1 — Portfolio header (explains purpose + new trade button)
    TargetFocus(
      identify: 'portfolio_header',
      keyTarget: headerKey,
      shape: ShapeLightFocus.RRect,
      radius: 0,
      paddingFocus: 4,
      contents: [
        TargetContent(
          align: ContentAlign.bottom,
          builder: (ctx, ctrl) => TourCard(
            title: l.tourPortfolio1Title,
            body: l.tourPortfolio1Body,
            controller: ctrl,
            skipLabel: l.tourSkip,
            nextLabel: l.tourNext,
          ),
        ),
      ],
    ),

    // Step 2 — Value card (total portfolio value + P&L)
    TargetFocus(
      identify: 'portfolio_value_card',
      keyTarget: valueCardKey,
      shape: ShapeLightFocus.RRect,
      radius: 12,
      paddingFocus: 8,
      contents: [
        TargetContent(
          align: ContentAlign.bottom,
          builder: (ctx, ctrl) => TourCard(
            title: l.tourPortfolio2Title,
            body: l.tourPortfolio2Body,
            controller: ctrl,
            skipLabel: l.tourSkip,
            nextLabel: l.tourNext,
          ),
        ),
      ],
    ),

    // Step 3 — Watchlist section
    TargetFocus(
      identify: 'portfolio_watchlist',
      keyTarget: watchlistKey,
      shape: ShapeLightFocus.RRect,
      radius: 8,
      paddingFocus: 8,
      contents: [
        TargetContent(
          align: ContentAlign.bottom,
          builder: (ctx, ctrl) => TourCard(
            title: l.tourPortfolio3Title,
            body: l.tourPortfolio3Body,
            controller: ctrl,
            skipLabel: l.tourSkip,
            nextLabel: l.tourDone,
          ),
        ),
      ],
    ),
  ];
}
