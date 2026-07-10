/// AnimationBlock — renders `<Animation name="..." />` inside a lesson.
///
/// Looks the name up in `AnimationRegistry` (CR013 / D-061: coded Flutter
/// animations, no Lottie). A registered name builds its parameterised
/// `AmiAnimation`; an unknown name renders `AmiHexPlaceholder` so a lesson that
/// references a not-yet-built animation still ships.
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
    final builder = AnimationRegistry.builderFor(name);
    if (builder == null) {
      return AmiHexPlaceholder(name: name);
    }
    return builder(context);
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
