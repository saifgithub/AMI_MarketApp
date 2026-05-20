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

  /// Unlocked, agent wants attention (brief prompt, drift alert).
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
            // The hex itself — matches the lessons-landing hex cluster
            // treatment: 15%-alpha role-color fill + role-color label, not
            // fully-saturated white-on-color. Border carries the full role
            // color so the hex still reads at a glance. (Bug 11fde6f6.)
            ClipPath(
              clipper: const FlatTopRegularHexagon(),
              child: Container(
                width: size,
                height: hexHeight,
                decoration: BoxDecoration(
                  color: _isLocked
                      ? AmiColors.slate800
                      : effectiveColor.withValues(alpha: 0.15),
                  border: Border.all(
                    color: _isLocked ? AmiColors.slate600 : effectiveColor,
                    width: 1,
                  ),
                ),
                alignment: Alignment.center,
                child: Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 4),
                  child: Text(
                    label,
                    style: AmiTypography.labelMono.copyWith(
                      fontSize: size * 0.16,
                      color: _isLocked ? AmiColors.textLow : effectiveColor,
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
