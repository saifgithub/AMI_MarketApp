/// AMI-styled tooltip card used in every coach-mark step.
library;

import 'package:ami_trade/qa/semantics_ids.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:flutter/material.dart';
import 'package:tutorial_coach_mark/tutorial_coach_mark.dart';

class TourCard extends StatelessWidget {
  const TourCard({
    super.key,
    required this.title,
    required this.body,
    required this.controller,
    required this.skipLabel,
    required this.nextLabel,
    this.tryNowLabel,
    this.onTryNow,
  });

  final String title;
  final String body;
  final TutorialCoachMarkController controller;
  final String skipLabel;
  final String nextLabel;

  /// Non-null only for the Convene step — shows a secondary "Try it now" CTA.
  final String? tryNowLabel;

  /// Called when the user taps "Try it now". The tour is closed first.
  final VoidCallback? onTryNow;

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      padding: const EdgeInsets.fromLTRB(20, 16, 20, 12),
      decoration: BoxDecoration(
        color: AmiColors.slate800,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AmiColors.slate600),
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            title,
            style: AmiTypography.labelMono.copyWith(color: AmiColors.hexCyan),
          ),
          const SizedBox(height: 6),
          Text(body, style: AmiTypography.body),
          const SizedBox(height: 14),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              // DEF375: the UAT harness dismisses tours by this id. One card
              // serves all five tours, so this is the only place it is needed.
              //
              // `MergeSemantics` is load-bearing, not decoration. Without it a
              // bare `Semantics(identifier:)` around a `TextButton` produces TWO
              // nodes: the identifier lands on a parent with `tap=false,
              // isButton=false`, and the real button node underneath carries no
              // identifier at all. Measured in the rendered semantics tree, not
              // reasoned about. On iOS the addressable element is the button, so
              // `ami.tour.skip` resolved to nothing on device and three rounds of
              // harness work chased a control that was never addressable.
              // Merging collapses both into one element that has the identifier,
              // the label and the tap action — the shape `hex_bottom_nav.dart`
              // and `ami_segment_bar.dart` already get by wrapping a bare
              // GestureDetector.
              MergeSemantics(
                child: Semantics(
                  identifier: TourIds.skip,
                  child: TextButton(
                    style: TextButton.styleFrom(
                      minimumSize: Size.zero,
                      padding: const EdgeInsets.symmetric(
                          horizontal: 4, vertical: 4),
                      tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                    ),
                    onPressed: controller.skip,
                    child: Text(
                      skipLabel,
                      style: AmiTypography.caption
                          .copyWith(color: AmiColors.textLow),
                    ),
                  ),
                ),
              ),
              Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  if (onTryNow != null && tryNowLabel != null) ...[
                    TextButton(
                      style: TextButton.styleFrom(
                        minimumSize: Size.zero,
                        padding: const EdgeInsets.symmetric(
                            horizontal: 8, vertical: 4),
                        tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                      ),
                      onPressed: () {
                        controller.skip();
                        onTryNow!();
                      },
                      child: Text(
                        tryNowLabel!,
                        style: AmiTypography.labelMono
                            .copyWith(color: AmiColors.hexGreen),
                      ),
                    ),
                    const SizedBox(width: 4),
                  ],
                  TextButton(
                    style: TextButton.styleFrom(
                      minimumSize: Size.zero,
                      padding: const EdgeInsets.symmetric(
                          horizontal: 8, vertical: 4),
                      tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                    ),
                    onPressed: controller.next,
                    child: Text(
                      nextLabel,
                      style: AmiTypography.labelMono
                          .copyWith(color: AmiColors.hexCyan),
                    ),
                  ),
                ],
              ),
            ],
          ),
        ],
      ),
    );
  }
}
