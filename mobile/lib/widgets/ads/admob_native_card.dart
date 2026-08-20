/// AdMob native-card chrome (CR122-MOBILE-C).
///
/// Wraps the SDK-rendered native template in the SAME `ads.md` UX contract
/// the house card honours: SPONSORED label in mono uppercase, one-tap
/// dismiss (X in the corner), amber-edged flat rectangle deliberately unlike
/// agent cards. The template itself comes through [AdMobNativeHandle] — this
/// file never imports the ad SDK (the seam is structural, see
/// `test/ads_structural_test.dart`). Disposal of the underlying platform ad
/// is owned here: on dismiss and on unmount.
library;

import 'package:ami_trade/services/ads/admob_sdk.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:ami_trade/widgets/ads/ad_badge.dart';
import 'package:flutter/material.dart';

class AdMobNativeCard extends StatefulWidget {
  const AdMobNativeCard({
    super.key,
    required this.fill,
    required this.onDismiss,
  });

  final AdMobNativeFill fill;
  final VoidCallback onDismiss;

  @override
  State<AdMobNativeCard> createState() => _AdMobNativeCardState();
}

class _AdMobNativeCardState extends State<AdMobNativeCard> {
  bool _disposed = false;

  void _disposeAd() {
    if (_disposed) return;
    _disposed = true;
    widget.fill.handle.dispose();
  }

  @override
  void dispose() {
    _disposeAd();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(AmiSpacing.s),
      decoration: BoxDecoration(
        color: AmiColors.cardBgAlt,
        borderRadius: BorderRadius.circular(AmiRadii.card),
        border: Border.all(color: AmiColors.hexAmber.withValues(alpha: 0.5)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const AdBadge(sponsored: true),
              const Spacer(),
              IconButton(
                onPressed: () {
                  _disposeAd();
                  widget.onDismiss();
                },
                icon: const Icon(Icons.close,
                    size: 18, color: AmiColors.textMed),
                padding: EdgeInsets.zero,
                constraints:
                    const BoxConstraints(minWidth: 32, minHeight: 32),
              ),
            ],
          ),
          SizedBox(
            height: widget.fill.handle.preferredHeight,
            width: double.infinity,
            child: _disposed
                ? const SizedBox.shrink()
                : widget.fill.handle.build(context),
          ),
        ],
      ),
    );
  }
}
