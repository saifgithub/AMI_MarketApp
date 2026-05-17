import 'package:ami_trade/theme/ami_theme.dart';
import 'package:ami_trade/theme/hex_clipper.dart';
import 'package:flutter/material.dart';

/// Visual state for an agent hex on the Floor home screen.
enum HexAvatarStatus {
  /// Unlocked, no recent activity. Flat role color.
  idle,

  /// Unlocked, contributed to a Room in the last 24h. Soft glow.
  recentCall,

  /// Unlocked, flagged something today. Pulsing glow.
  signal,

  /// Unlocked, agent wants attention (coach prompt, drift alert).
  attention,

  /// Locked — user hasn't completed Earn Path or doesn't have Skip Path.
  locked,
}

/// Hex avatar for one of the 12 agents (or the Concierge).
///
/// Spec: docs/05_design/floor_home_honeycomb.md
class HexAvatar extends StatelessWidget {
  const HexAvatar({
    super.key,
    required this.label,
    required this.color,
    this.size = 96,
    this.status = HexAvatarStatus.idle,
    this.solid = true,
    this.onTap,
    this.onLongPress,
  });

  /// Short uppercase abbreviation (e.g., "FUND", "BEAR", "PM"). 2–4 chars works best.
  final String label;

  /// Role color (cyan/purple/amber/green/pink). See [agentFamilyColor].
  final Color color;

  /// Width in logical pixels. Height is derived from the regular hex aspect ratio.
  final double size;

  final HexAvatarStatus status;

  /// `true` (default): solid colour fill, white label — original Floor look.
  /// `false`: 15%-alpha tinted fill, label rendered in the role colour —
  /// matches the lessons hex cluster styling. Has no effect when the
  /// avatar is locked (locked styling always wins).
  final bool solid;

  final VoidCallback? onTap;
  final VoidCallback? onLongPress;

  bool get _isLocked => status == HexAvatarStatus.locked;
  bool get _hasGlow =>
      status == HexAvatarStatus.recentCall ||
      status == HexAvatarStatus.signal ||
      status == HexAvatarStatus.attention;

  @override
  Widget build(BuildContext context) {
    final hexHeight = size / flatTopRegularHexagonAspectRatio;
    final effectiveColor = _isLocked ? AmiColors.slate700 : color;

    // Fill / border / label colour per style. Locked always wins.
    final Color fillColor;
    final Color? borderColor;
    final Color labelColor;
    if (_isLocked) {
      fillColor = AmiColors.slate800;
      borderColor = AmiColors.slate600;
      labelColor = AmiColors.textLow;
    } else if (solid) {
      fillColor = effectiveColor;
      borderColor = effectiveColor;
      labelColor = Colors.white;
    } else {
      // Translucent — match TrackHexButton on the lessons cluster. No
      // border there, just the clip path defining the shape.
      fillColor = effectiveColor.withValues(alpha: 0.15);
      borderColor = null;
      labelColor = effectiveColor;
    }

    return GestureDetector(
      onTap: onTap,
      onLongPress: onLongPress,
      child: SizedBox(
        width: size,
        height: hexHeight,
        child: Stack(
          alignment: Alignment.center,
          clipBehavior: Clip.none,
          children: [
            // Glow underlay — drop-shadow filter so the clip-path doesn't cut it off
            if (_hasGlow)
              IgnorePointer(
                child: Container(
                  width: size * 1.2,
                  height: hexHeight * 1.2,
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    gradient: RadialGradient(
                      colors: [
                        effectiveColor.withValues(alpha: 0.35),
                        effectiveColor.withValues(alpha: 0),
                      ],
                    ),
                  ),
                ),
              ),
            // The hex itself
            ClipPath(
              clipper: const FlatTopRegularHexagon(),
              child: Container(
                width: size,
                height: hexHeight,
                decoration: BoxDecoration(
                  color: fillColor,
                  border: borderColor == null
                      ? null
                      : Border.all(color: borderColor, width: 1),
                ),
                alignment: Alignment.center,
                child: Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 4),
                  child: Text(
                    label,
                    style: AmiTypography.labelMono.copyWith(
                      fontSize: size * 0.16,
                      color: labelColor,
                    ),
                    textAlign: TextAlign.center,
                    maxLines: 1,
                    overflow: TextOverflow.clip,
                  ),
                ),
              ),
            ),
            // Lock glyph
            if (_isLocked)
              Positioned(
                top: hexHeight * 0.18,
                right: size * 0.22,
                child: const Icon(Icons.lock, size: 12, color: AmiColors.textLow),
              ),
            // Attention badge
            if (status == HexAvatarStatus.attention)
              Positioned(
                top: hexHeight * 0.15,
                right: size * 0.18,
                child: Container(
                  width: 14,
                  height: 14,
                  decoration: const BoxDecoration(
                    color: AmiColors.hexAmber,
                    shape: BoxShape.circle,
                  ),
                  alignment: Alignment.center,
                  child: const Text(
                    '!',
                    style: TextStyle(
                      fontFamily: AmiTypography.jetBrains,
                      fontSize: 10,
                      fontWeight: FontWeight.w700,
                      color: AmiColors.slate900,
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
