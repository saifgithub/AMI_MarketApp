/// CR013 (E3/D1) — shared helpers for the lesson animation primitives:
/// normalized→canvas mapping (y-up), partial-polyline reveal, and mono label
/// drawing. Keeps the seven painters small and consistent.
library;

import 'dart:ui' as ui;

import 'package:flutter/material.dart';

/// Insets applied inside the canvas so strokes/labels don't clip the edges.
const EdgeInsets kAnimPad = EdgeInsets.fromLTRB(20, 22, 20, 26);

/// Map a normalized point (x,y ∈ [0,1], y measured **up** from the bottom) into
/// canvas pixels for [size], respecting [pad].
Offset mapNorm(Offset n, Size size, [EdgeInsets pad = kAnimPad]) {
  final w = size.width - pad.horizontal;
  final h = size.height - pad.vertical;
  return Offset(pad.left + n.dx * w, size.height - pad.bottom - n.dy * h);
}

/// Build a polyline path through canvas-space points.
Path polyline(List<Offset> pts) {
  final p = Path();
  if (pts.isEmpty) return p;
  p.moveTo(pts.first.dx, pts.first.dy);
  for (var i = 1; i < pts.length; i++) {
    p.lineTo(pts[i].dx, pts[i].dy);
  }
  return p;
}

/// Return the polyline through [pts] revealed only up to fraction [t] (0→1) of
/// its total length — the "drawing" effect. Also returns the current head.
({Path path, Offset head}) revealPolyline(List<Offset> pts, double t) {
  final path = Path();
  if (pts.isEmpty) return (path: path, head: Offset.zero);
  if (pts.length == 1 || t <= 0) {
    path.moveTo(pts.first.dx, pts.first.dy);
    return (path: path, head: pts.first);
  }
  var total = 0.0;
  for (var i = 1; i < pts.length; i++) {
    total += (pts[i] - pts[i - 1]).distance;
  }
  final target = total * t.clamp(0.0, 1.0);
  path.moveTo(pts.first.dx, pts.first.dy);
  var walked = 0.0;
  var head = pts.first;
  for (var i = 1; i < pts.length; i++) {
    final seg = (pts[i] - pts[i - 1]).distance;
    if (walked + seg <= target || seg == 0) {
      path.lineTo(pts[i].dx, pts[i].dy);
      walked += seg;
      head = pts[i];
    } else {
      final f = (target - walked) / seg;
      head = Offset.lerp(pts[i - 1], pts[i], f)!;
      path.lineTo(head.dx, head.dy);
      break;
    }
  }
  return (path: path, head: head);
}

/// Draw a `labelMono`-style text anchored at [at] with [align] alignment.
void drawLabel(
  Canvas canvas,
  String text,
  Offset at, {
  required TextStyle style,
  Alignment align = Alignment.center,
  double maxWidth = 220,
}) {
  final tp = TextPainter(
    text: TextSpan(text: text, style: style),
    textDirection: ui.TextDirection.ltr,
    textAlign: TextAlign.center,
  )..layout(maxWidth: maxWidth);
  final dx = at.dx - tp.width * (align.x + 1) / 2;
  final dy = at.dy - tp.height * (align.y + 1) / 2;
  tp.paint(canvas, Offset(dx, dy));
}

/// Ease helper: remap a sub-window [a,b] of `t` to [0,1] (for staged reveals).
double stageT(double t, double a, double b) =>
    ((t - a) / (b - a)).clamp(0.0, 1.0);
