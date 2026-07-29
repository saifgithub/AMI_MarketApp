/// CR016 (E4/D8 / C2) — HexBottomNav: the AMI signature bottom navigation.
/// Five destinations; the active one's icon sits inside a true flat-top *regular
/// hexagon* (the honeycomb-avatar geometry) filled with the purple→blue brand
/// gradient + a blue border and glow, label underneath. Inactive destinations are
/// a muted icon + label. Material semantics are preserved — same five
/// destinations, full-cell touch targets, `Semantics(button, selected)` — only
/// the visuals change. Drop-in for the stock `BottomNavigationBar` in
/// `home_shell.dart`.
///
/// DEF043: the earlier build used `CutCornerOctagonClipper` (a cut-corner *octagon*)
/// as an elongated pill, and the label kept `labelMono`'s 1.8 tracking so
/// `PORTFOLIO` wrapped to two lines. This version uses a genuine hexagon and
/// single-line labels.
library;

import 'package:ami_trade/theme/ami_theme.dart';
import 'package:flutter/material.dart';

class HexNavItem {
  const HexNavItem({required this.icon, required this.label});
  final IconData icon;
  final String label;
}

class HexBottomNav extends StatelessWidget {
  const HexBottomNav({
    super.key,
    required this.currentIndex,
    required this.onTap,
    required this.items,
  });

  final int currentIndex;
  final ValueChanged<int> onTap;
  final List<HexNavItem> items;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      height: 64,
      child: Row(
        // M1: stretch so each cell's tap target fills the full bar height
        // (no dead strips top/bottom) — width already fills via Expanded.
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          for (var i = 0; i < items.length; i++)
            Expanded(child: _Cell(
              item: items[i],
              active: i == currentIndex,
              onTap: () => onTap(i),
            )),
        ],
      ),
    );
  }
}

class _Cell extends StatelessWidget {
  const _Cell({required this.item, required this.active, required this.onTap});

  final HexNavItem item;
  final bool active;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    // Icon zone — fixed size so every tab's icon (and thus every label) sits on
    // the same baseline whether or not the hexagon is drawn behind it. The
    // hexagon is a flat-top *regular* hexagon (2 : √3 ≈ 1.155 w:h).
    const iconZone = Size(38, 33);
    final iconWidget = Icon(item.icon,
        size: 20, color: active ? Colors.white : AmiColors.textLow);

    final content = Column(
      mainAxisAlignment: MainAxisAlignment.center,
      mainAxisSize: MainAxisSize.min,
      children: [
        SizedBox.fromSize(
          size: iconZone,
          child: active
              ? CustomPaint(
                  painter: const _ActiveHexPainter(),
                  child: Center(child: iconWidget),
                )
              : Center(child: iconWidget),
        ),
        const SizedBox(height: 4),
        // FittedBox + tight tracking → the label always renders on one line
        // (DEF043: PORTFOLIO used to wrap because labelMono's 1.8 tracking
        // overflowed the cell). scaleDown only shrinks the rare too-wide label.
        FittedBox(
          fit: BoxFit.scaleDown,
          child: Text(
            item.label,
            maxLines: 1,
            softWrap: false,
            style: AmiTypography.labelMono.copyWith(
              fontSize: 9,
              letterSpacing: 0.4,
              color: active ? AmiColors.textHigh : AmiColors.textLow,
            ),
          ),
        ),
      ],
    );

    return Semantics(
      button: true,
      selected: active,
      label: item.label,
      child: GestureDetector(
        onTap: onTap,
        behavior: HitTestBehavior.opaque,
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 6),
          child: Center(child: content),
        ),
      ),
    );
  }
}

/// Paints the active tab's flat-top regular hexagon: soft purple/blue glow, a
/// purple→blue gradient fill, and a crisp hexBlue border. A [CustomPainter]
/// (not `ClipPath` + `Border.all`) so the border traces the true hex edges
/// rather than a clipped rectangle stroke.
class _ActiveHexPainter extends CustomPainter {
  const _ActiveHexPainter();

  Path _hex(Size size) {
    final double w = size.width;
    final double h = size.height;
    final double qw = w * 0.25; // where the left/right diagonals meet the top
    return Path()
      ..moveTo(qw, 0)
      ..lineTo(w - qw, 0)
      ..lineTo(w, h * 0.5)
      ..lineTo(w - qw, h)
      ..lineTo(qw, h)
      ..lineTo(0, h * 0.5)
      ..close();
  }

  @override
  void paint(Canvas canvas, Size size) {
    final path = _hex(size);
    final rect = Offset.zero & size;

    // Glow — a blurred stroke halo behind the fill.
    canvas.drawPath(
      path,
      Paint()
        ..color = AmiColors.hexBlue.withValues(alpha: 0.45)
        ..style = PaintingStyle.stroke
        ..strokeWidth = 2
        ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 6),
    );

    // Gradient fill — confident brand hexagon so the white icon reads.
    canvas.drawPath(
      path,
      Paint()
        ..shader = LinearGradient(
          colors: [
            AmiColors.hexPurple.withValues(alpha: 0.85),
            AmiColors.hexBlue.withValues(alpha: 0.85),
          ],
        ).createShader(rect),
    );

    // Crisp border along the true hex edges.
    canvas.drawPath(
      path,
      Paint()
        ..color = AmiColors.hexBlue
        ..style = PaintingStyle.stroke
        ..strokeWidth = 1.4,
    );
  }

  @override
  bool shouldRepaint(covariant _ActiveHexPainter oldDelegate) => false;
}
