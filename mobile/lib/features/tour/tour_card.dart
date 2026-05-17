/// AMI-styled tooltip card used in every coach-mark step.
library;

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
              TextButton(
                style: TextButton.styleFrom(
                  minimumSize: Size.zero,
                  padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 4),
                  tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                ),
                onPressed: controller.skip,
                child: Text(
                  skipLabel,
                  style: AmiTypography.caption.copyWith(color: AmiColors.textLow),
                ),
              ),
              Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  if (onTryNow != null && tryNowLabel != null) ...[
                    TextButton(
                      style: TextButton.styleFrom(
                        minimumSize: Size.zero,
                        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
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
                      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
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
