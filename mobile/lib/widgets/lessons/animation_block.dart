/// AnimationBlock — renders `<Animation name="..." />` inside a lesson.
///
/// Looks the name up in `AnimationRegistry`. If a Lottie asset is bundled,
/// this widget would play it (Lottie playback is deliberately deferred —
/// pubspec doesn't carry the `lottie` dependency yet). When the asset is
/// missing, it renders `AmiHexPlaceholder` so the lesson surface still
/// ships content authors can reference by name today.
library;

import 'package:ami_trade/theme/ami_theme.dart';
import 'package:ami_trade/widgets/lessons/animation_registry.dart';
import 'package:flutter/material.dart';

class AnimationBlock extends StatelessWidget {
  const AnimationBlock({super.key, required this.name});

  /// The registry key from the lesson MDX (`<Animation name="..." />`).
  final String name;

  @override
  Widget build(BuildContext context) {
    final asset = AnimationRegistry.assetFor(name);
    if (asset == null) {
      return AmiHexPlaceholder(name: name);
    }
    // Asset registered but no Lottie runtime is wired yet. The placeholder
    // path still applies; once the `lottie` package is added the body of
    // this branch becomes `Lottie.asset(asset, ...)`.
    return AmiHexPlaceholder(name: name, hasAsset: true);
  }
}

/// AmiHexPlaceholder — flat-topped hex tile used wherever an animation is
/// expected but the runtime asset isn't bundled. Renders the registry key
/// in the centre so authors can spot missing animations during walkthroughs.
class AmiHexPlaceholder extends StatelessWidget {
  const AmiHexPlaceholder({
    super.key,
    required this.name,
    this.hasAsset = false,
  });

  final String name;
  final bool hasAsset;

  @override
  Widget build(BuildContext context) {
    final accent = hasAsset ? AmiColors.hexBlue : AmiColors.slate700;
    return Container(
      height: 180,
      decoration: BoxDecoration(
        color: AmiColors.slate800,
        borderRadius: BorderRadius.circular(AmiRadii.card),
        border: Border.all(color: accent),
      ),
      child: Stack(
        children: [
          Center(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Icon(
                  hasAsset ? Icons.play_circle_outline : Icons.hexagon_outlined,
                  size: 48,
                  color: accent,
                ),
                const SizedBox(height: AmiSpacing.s),
                Text(
                  name.toUpperCase(),
                  style: AmiTypography.labelMono.copyWith(color: AmiColors.textHigh),
                ),
                const SizedBox(height: 2),
                Text(
                  hasAsset ? 'animation' : 'placeholder',
                  style: AmiTypography.caption.copyWith(color: AmiColors.textLow),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
