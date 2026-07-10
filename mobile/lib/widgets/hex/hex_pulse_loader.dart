/// CR014 (E3/D2) — HexPulseLoader: the app-wide loading motif. A single hex
/// outline breathing scale 0.92↔1.08 with a glow fading 0.3↔0.7 over 1600ms
/// (easeInOut, repeat). Replaces the bare `CircularProgressIndicator` at the
/// auth gate, the Room deliberation footer, and chart loading states.
library;

import 'dart:math' as math;

import 'package:ami_trade/theme/ami_theme.dart';
import 'package:flutter/material.dart';

class HexPulseLoader extends StatefulWidget {
  const HexPulseLoader({super.key, this.size = 48, this.color = AmiColors.hexCyan});

  final double size;
  final Color color;

  @override
  State<HexPulseLoader> createState() => _HexPulseLoaderState();
}

class _HexPulseLoaderState extends State<HexPulseLoader>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 1600),
  )..repeat(reverse: true);

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Center(
      child: SizedBox(
        width: widget.size,
        height: widget.size,
        child: AnimatedBuilder(
          animation: _controller,
          builder: (_, __) {
            final t = Curves.easeInOut.transform(_controller.value);
            return CustomPaint(
              painter: _HexPulsePainter(
                color: widget.color,
                scale: 0.92 + 0.16 * t,
                glow: 0.3 + 0.4 * t,
              ),
            );
          },
        ),
      ),
    );
  }
}

class _HexPulsePainter extends CustomPainter {
  const _HexPulsePainter({
    required this.color,
    required this.scale,
    required this.glow,
  });

  final Color color;
  final double scale;
  final double glow;

  Path _hex(Offset c, double r) {
    final p = Path();
    for (var i = 0; i < 6; i++) {
      final a = math.pi / 6 + math.pi / 3 * i;
      final pt = Offset(c.dx + r * math.cos(a), c.dy + r * math.sin(a));
      i == 0 ? p.moveTo(pt.dx, pt.dy) : p.lineTo(pt.dx, pt.dy);
    }
    return p..close();
  }

  @override
  void paint(Canvas canvas, Size size) {
    final c = Offset(size.width / 2, size.height / 2);
    final r = size.width / 2 * 0.8 * scale;
    final path = _hex(c, r);
    // Glow underlay.
    canvas.drawPath(
      path,
      Paint()
        ..color = color.withValues(alpha: glow)
        ..style = PaintingStyle.stroke
        ..strokeWidth = 3
        ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 6),
    );
    // Crisp outline.
    canvas.drawPath(
      path,
      Paint()
        ..color = color
        ..style = PaintingStyle.stroke
        ..strokeWidth = 2.5
        ..strokeJoin = StrokeJoin.round,
    );
  }

  @override
  bool shouldRepaint(covariant _HexPulsePainter old) =>
      old.scale != scale || old.glow != glow || old.color != color;
}
