/// Celebration layer (CR004 B1) — the app's three reward tiers.
///
/// micro  — light haptic + 250ms accent flash over the calling widget's
///          panel. Challenge correct, Room verdict lands, watchlist add.
/// meso   — medium haptic + [HexBurstOverlay] radiating from the calling
///          widget. Lesson quiz pass, streak milestone, league promotion.
/// major  — full-screen [AgentUnlockedScreen] takeover. Agent unlock only.
///
/// Every success moment routes through here so reward language stays
/// consistent (precision, not carnival — one controller, short curves).
library;

import 'dart:math' as math;

import 'package:ami_trade/models/agent.dart';
import 'package:ami_trade/screens/agent/agent_unlocked_screen.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:ami_trade/theme/hex_clipper.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

abstract final class Celebrate {
  /// Light haptic + brief accent flash over the calling widget's bounds.
  /// Call with the context of the card/panel that earned the moment.
  static void micro(BuildContext context, {Color accent = AmiColors.hexGreen}) {
    HapticFeedback.lightImpact();
    final overlay = Overlay.maybeOf(context);
    final box = context.findRenderObject() as RenderBox?;
    if (overlay == null || box == null || !box.hasSize) return;
    final origin = box.localToGlobal(Offset.zero);
    late final OverlayEntry entry;
    entry = OverlayEntry(
      builder: (_) => _FlashOverlay(
        rect: origin & box.size,
        accent: accent,
        onDone: () => entry.remove(),
      ),
    );
    overlay.insert(entry);
  }

  /// Heavy haptic + full-screen [AgentUnlockedScreen] takeover.
  /// Reserved for agent unlocks — the app's biggest earned moment.
  static void major(BuildContext context, {required Agent agent}) {
    HapticFeedback.heavyImpact();
    Navigator.of(context).push(
      MaterialPageRoute(
        fullscreenDialog: true,
        builder: (_) => AgentUnlockedScreen(agent: agent),
      ),
    );
  }

  /// Medium haptic + hex-shard burst radiating from the calling widget.
  static void meso(BuildContext context, {Color accent = AmiColors.hexBlue}) {
    HapticFeedback.mediumImpact();
    final overlay = Overlay.maybeOf(context);
    final box = context.findRenderObject() as RenderBox?;
    if (overlay == null || box == null || !box.hasSize) return;
    final center = box.localToGlobal(box.size.center(Offset.zero));
    late final OverlayEntry entry;
    entry = OverlayEntry(
      builder: (_) => HexBurstOverlay(
        origin: center,
        accent: accent,
        onDone: () => entry.remove(),
      ),
    );
    overlay.insert(entry);
  }
}

/// 250ms accent wash over one panel — the micro tier's visual.
class _FlashOverlay extends StatefulWidget {
  const _FlashOverlay({
    required this.rect,
    required this.accent,
    required this.onDone,
  });

  final Rect rect;
  final Color accent;
  final VoidCallback onDone;

  @override
  State<_FlashOverlay> createState() => _FlashOverlayState();
}

class _FlashOverlayState extends State<_FlashOverlay>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 250),
  )
    ..addStatusListener((s) {
      if (s == AnimationStatus.completed) widget.onDone();
    })
    ..forward();

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Positioned.fromRect(
      rect: widget.rect,
      child: IgnorePointer(
        child: AnimatedBuilder(
          animation: _controller,
          builder: (_, __) => Container(
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(AmiRadii.card),
              color: widget.accent.withValues(
                alpha: 0.20 * (1 - _controller.value),
              ),
              border: Border.all(
                color: widget.accent.withValues(
                  alpha: 0.6 * (1 - _controller.value),
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}

/// 10–14 small hexes radiating from [origin], 600ms easeOutCubic, fade to 0.
/// The meso tier's visual — inserted as a full-screen ignore-pointer layer.
class HexBurstOverlay extends StatefulWidget {
  const HexBurstOverlay({
    super.key,
    required this.origin,
    required this.accent,
    required this.onDone,
  });

  final Offset origin;
  final Color accent;
  final VoidCallback onDone;

  @override
  State<HexBurstOverlay> createState() => _HexBurstOverlayState();
}

class _HexBurstOverlayState extends State<HexBurstOverlay>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 600),
  )
    ..addStatusListener((s) {
      if (s == AnimationStatus.completed) widget.onDone();
    })
    ..forward();

  late final List<_Shard> _shards = _makeShards();

  List<_Shard> _makeShards() {
    final rng = math.Random(widget.origin.dx.toInt() ^ widget.origin.dy.toInt());
    final count = 10 + rng.nextInt(5); // 10–14
    final palette = [
      widget.accent,
      AmiColors.hexCyan,
      AmiColors.hexPurple,
      AmiColors.hexGreen,
      AmiColors.hexAmber,
    ];
    return List.generate(count, (i) {
      final angle = (i / count) * 2 * math.pi + rng.nextDouble() * 0.5;
      return _Shard(
        angle: angle,
        distance: 60 + rng.nextDouble() * 70,
        size: 6 + rng.nextDouble() * 8,
        color: palette[rng.nextInt(palette.length)],
        spin: (rng.nextDouble() - 0.5) * 2 * math.pi,
      );
    });
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Positioned.fill(
      child: IgnorePointer(
        child: AnimatedBuilder(
          animation: _controller,
          builder: (_, __) => CustomPaint(
            painter: _HexBurstPainter(
              t: Curves.easeOutCubic.transform(_controller.value),
              origin: widget.origin,
              shards: _shards,
            ),
          ),
        ),
      ),
    );
  }
}

class _Shard {
  const _Shard({
    required this.angle,
    required this.distance,
    required this.size,
    required this.color,
    required this.spin,
  });

  final double angle;
  final double distance;
  final double size;
  final Color color;
  final double spin;
}

class _HexBurstPainter extends CustomPainter {
  const _HexBurstPainter({
    required this.t,
    required this.origin,
    required this.shards,
  });

  final double t;
  final Offset origin;
  final List<_Shard> shards;

  @override
  void paint(Canvas canvas, Size size) {
    const clipper = FlatTopRegularHexagon();
    final opacity = (1 - t).clamp(0.0, 1.0);
    for (final shard in shards) {
      final pos = origin +
          Offset(math.cos(shard.angle), math.sin(shard.angle)) *
              (shard.distance * t);
      final paint = Paint()
        ..color = shard.color.withValues(alpha: opacity);
      canvas.save();
      canvas.translate(pos.dx, pos.dy);
      canvas.rotate(shard.spin * t);
      canvas.translate(-shard.size / 2, -shard.size / 2);
      canvas.drawPath(
        clipper.getClip(Size(shard.size, shard.size)), paint,
      );
      canvas.restore();
    }
  }

  @override
  bool shouldRepaint(covariant _HexBurstPainter old) => old.t != t;
}
