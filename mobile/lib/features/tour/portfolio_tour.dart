/// Coach-mark step definitions for the Portfolio tab tour (3 steps).
library;

import 'package:ami_trade/features/tour/ami_tour_overlay.dart';
import 'package:ami_trade/features/tour/tour_card.dart';
import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:flutter/material.dart';

List<AmiTourStep> buildPortfolioTargets({
  required AppLocalizations l,
  required GlobalKey headerKey,
  required GlobalKey valueCardKey,
  required GlobalKey watchlistKey,
}) {
  return [
    // Step 1 — Portfolio header (explains purpose + new trade button)
    AmiTourStep(
      identify: 'portfolio_header',
      target: headerKey,
      shape: AmiTourShape.roundedRect,
      radius: 0,
      paddingFocus: 4,
      align: AmiTourAlign.bottom,
      builder: (ctx, ctrl) => TourCard(
        title: l.tourPortfolio1Title,
        body: l.tourPortfolio1Body,
        controller: ctrl,
        skipLabel: l.tourSkip,
        nextLabel: l.tourNext,
      ),
    ),

    // Step 2 — Value card (total portfolio value + P&L)
    AmiTourStep(
      identify: 'portfolio_value_card',
      target: valueCardKey,
      shape: AmiTourShape.roundedRect,
      radius: 12,
      paddingFocus: 8,
      align: AmiTourAlign.bottom,
      builder: (ctx, ctrl) => TourCard(
        title: l.tourPortfolio2Title,
        body: l.tourPortfolio2Body,
        controller: ctrl,
        skipLabel: l.tourSkip,
        nextLabel: l.tourNext,
      ),
    ),

    // Step 3 — Watchlist section
    AmiTourStep(
      identify: 'portfolio_watchlist',
      target: watchlistKey,
      shape: AmiTourShape.roundedRect,
      radius: 8,
      paddingFocus: 8,
      align: AmiTourAlign.bottom,
      builder: (ctx, ctrl) => TourCard(
        title: l.tourPortfolio3Title,
        body: l.tourPortfolio3Body,
        controller: ctrl,
        skipLabel: l.tourSkip,
        nextLabel: l.tourDone,
      ),
    ),
  ];
}
