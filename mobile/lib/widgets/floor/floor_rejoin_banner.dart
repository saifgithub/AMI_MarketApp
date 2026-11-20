/// DEF506 — the Floor's "your Room is still running" banner.
///
/// Shown only while the user has a Room in flight (`activeRoomProvider`). It
/// does not take the user anywhere on its own: opening the app on the Floor and
/// letting the user choose to go back is Saiful's ruling (2026-11-20), against
/// an auto-jump into the Room.
///
/// Amber like the Room's own reconnect/reattach banners, so "a run is live"
/// reads the same wherever it surfaces.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/qa/semantics_ids.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:flutter/material.dart';

class FloorRejoinBanner extends StatelessWidget {
  const FloorRejoinBanner({
    super.key,
    required this.ticker,
    required this.onRejoin,
  });

  final String ticker;
  final VoidCallback onRejoin;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    return Semantics(
      identifier: FloorIds.rejoinBanner,
      container: true,
      explicitChildNodes: true,
      child: Container(
        width: double.infinity,
        margin: const EdgeInsets.only(bottom: AmiSpacing.m),
        padding: const EdgeInsets.symmetric(
            horizontal: AmiSpacing.s, vertical: AmiSpacing.xs),
        decoration: BoxDecoration(
          color: AmiColors.slate800,
          borderRadius: BorderRadius.circular(AmiRadii.card),
          border: Border.all(color: AmiColors.hexAmber),
        ),
        child: Row(
          children: [
            const SizedBox(
              width: 14,
              height: 14,
              child: CircularProgressIndicator(
                strokeWidth: 2,
                valueColor: AlwaysStoppedAnimation(AmiColors.hexAmber),
              ),
            ),
            const SizedBox(width: AmiSpacing.s),
            Expanded(
              child: Text(
                l.floorRejoinBanner(ticker),
                style: AmiTypography.body,
              ),
            ),
            const SizedBox(width: AmiSpacing.xs),
            // MergeSemantics: see tour_card.dart (DEF375) — without it the
            // identifier and the button land on two different nodes.
            MergeSemantics(
              child: Semantics(
                identifier: FloorIds.rejoinCta,
                child: TextButton(
                  onPressed: onRejoin,
                  child: Text(
                    l.floorRejoinCta,
                    style: AmiTypography.labelMono
                        .copyWith(color: AmiColors.hexAmber),
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
