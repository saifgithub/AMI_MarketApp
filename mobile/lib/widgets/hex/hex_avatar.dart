import 'package:ami_trade/theme/ami_theme.dart';
import 'package:ami_trade/theme/hex_clipper.dart';
import 'package:flutter/material.dart';

/// Visual state for an agent hex on the Floor home screen.
enum HexAvatarStatus {
  /// Unlocked, no recent activity. Flat role color.
  idle,

  /// Unlocked, contributed to a Room in the last 24h. Soft (static) glow.
  recentCall,

  /// Unlocked, flagged something today. Pulsing glow (CR014/D3).
  signal,

  /// Unlocked, agent wants attention (brief prompt, drift alert). Stronger
  /// amber-tinted pulse + "!" badge (CR014/D3).
  attention,

  /// Locked — user hasn't completed Earn Path or doesn't have Skip Path.
  locked,
}

/// Hex avatar for one of the 12 agents (or the Concierge).
///
/// Spec: docs/initial_specs/05_design/floor_home_honeycomb.md. The `signal` and
/// `attention` states drive a low-frequency (2200ms) glow pulse — "precision,
/// not carnival"; `recentCall` stays a static soft glow.
class HexAvatar extends StatefulWidget {
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

  @override
  State<HexAvatar> createState() => _HexAvatarState();
}

class _HexAvatarState extends State<HexAvatar>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 2200),
  );

  bool get _isLocked => widget.status == HexAvatarStatus.locked;
  bool get _hasGlow =>
      widget.status == HexAvatarStatus.recentCall ||
      widget.status == HexAvatarStatus.signal ||
      widget.status == HexAvatarStatus.attention;
  bool get _shouldPulse =>
      widget.status == HexAvatarStatus.signal ||
      widget.status == HexAvatarStatus.attention;

  @override
  void initState() {
    super.initState();
    _syncPulse();
  }

  @override
  void didUpdateWidget(covariant HexAvatar old) {
    super.didUpdateWidget(old);
    if (old.status != widget.status) _syncPulse();
  }

  void _syncPulse() {
    if (_shouldPulse) {
      if (!_controller.isAnimating) _controller.repeat(reverse: true);
    } else {
      _controller
        ..stop()
        ..value = 0;
    }
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final hexHeight = widget.size / flatTopRegularHexagonAspectRatio;
    final effectiveColor = _isLocked ? AmiColors.slate700 : widget.color;
    final attention = widget.status == HexAvatarStatus.attention;
    final glowColor = attention ? AmiColors.hexAmber : effectiveColor;

    return GestureDetector(
      onTap: widget.onTap,
      onLongPress: widget.onLongPress,
      child: SizedBox(
        width: widget.size,
        height: hexHeight,
        child: Stack(
          alignment: Alignment.center,
          clipBehavior: Clip.none,
          children: [
            // Glow underlay. Pulses for signal/attention, static for recentCall.
            if (_hasGlow)
              _shouldPulse
                  ? AnimatedBuilder(
                      animation: _controller,
                      builder: (_, __) {
                        final t = Curves.easeInOut.transform(_controller.value);
                        final lowA = attention ? 0.3 : 0.2;
                        final highA = attention ? 0.66 : 0.48;
                        return _glow(
                          glowColor,
                          lowA + (highA - lowA) * t,
                          1.0 + 0.12 * t,
                          hexHeight,
                        );
                      },
                    )
                  : _glow(glowColor, 0.35, 1.0, hexHeight),
            // The hex itself
            ClipPath(
              clipper: const FlatTopRegularHexagon(),
              child: Container(
                width: widget.size,
                height: hexHeight,
                decoration: BoxDecoration(
                  color: _isLocked ? AmiColors.slate800 : effectiveColor,
                  border: Border.all(
                    color: _isLocked ? AmiColors.slate600 : effectiveColor,
                    width: 1,
                  ),
                ),
                alignment: Alignment.center,
                child: Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 4),
                  child: Text(
                    widget.label,
                    style: AmiTypography.labelMono.copyWith(
                      fontSize: widget.size * 0.16,
                      color: _isLocked ? AmiColors.textLow : Colors.white,
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
                right: widget.size * 0.22,
                child: const Icon(Icons.lock, size: 12, color: AmiColors.textLow),
              ),
            // Attention badge
            if (attention)
              Positioned(
                top: hexHeight * 0.15,
                right: widget.size * 0.18,
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

  Widget _glow(Color color, double alpha, double scale, double hexHeight) {
    return IgnorePointer(
      child: Container(
        width: widget.size * 1.2 * scale,
        height: hexHeight * 1.2 * scale,
        decoration: BoxDecoration(
          shape: BoxShape.circle,
          gradient: RadialGradient(
            colors: [
              color.withValues(alpha: alpha),
              color.withValues(alpha: 0),
            ],
          ),
        ),
      ),
    );
  }
}
