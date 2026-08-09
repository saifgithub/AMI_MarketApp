/// PortfolioEquityChart — NAV-over-time curve for the Portfolio screen.
///
/// CR109 slice 1. **The app cannot draw a portfolio's history today**, so
/// this is user-visible value on its own merits — it is not scaffolding
/// for a game, and nothing here is game-facing. No game surface, no new
/// nav destination, no new strings about "the game".
///
/// Reads `GET /v1/sim/portfolio/{user_id}/history` via
/// [portfolioHistoryProvider]. Follows `widgets/ticker_chart.dart`'s
/// conventions rather than inventing a second charting idiom: a
/// hand-painted line via `CustomPainter` (fl_chart 0.69.0 has no primitive
/// for per-segment dash styling either), the same card chrome, the same
/// touch-drag crosshair model.
///
/// **Degrade loudly (CR040 / CR134).** A point whose `price_source` is not
/// `live` is marked with a dashed segment AND a filled tick — pattern
/// only, never opacity or saturation. CR134's correction is explicit: "a
/// dimmed mark reads as absent, not small." A day the simulated feed
/// produced is not a fact.
///
/// A portfolio with fewer than two snapshots draws no curve and says why
/// in one line — never a blank frame, never a flat zero line.
library;

import 'dart:ui' as ui;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/sim.dart';
import 'package:ami_trade/services/api/friendly_error.dart';
import 'package:ami_trade/state/sim_providers.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';

const double _kChartHeight = 96;

/// Wraps a signed numeric run in Unicode directional isolates so RTL
/// reordering cannot scramble sign/digits — the CR106 T-BIDI trap. Kept as
/// a small per-file copy rather than a shared util, matching this
/// codebase's existing convention (see `screens/sim/portfolio_screen.dart`
/// and `widgets/portfolio_health/risk_money_bars.dart`, each with their
/// own copy).
String _isolateNumeric(String s) => '\u2066$s\u2069';

class PortfolioEquityChart extends ConsumerWidget {
  const PortfolioEquityChart({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l = AppLocalizations.of(context);
    final async = ref.watch(portfolioHistoryProvider);
    return Padding(
      padding: const EdgeInsets.only(bottom: AmiSpacing.s),
      child: async.when(
        loading: () => const _EquityCurveSkeleton(),
        error: (e, _) => _EquityCurveNotice(
          label: friendlyError(e, action: 'load your equity curve'),
          onRetry: isRetryable(e)
              ? () => ref.invalidate(portfolioHistoryProvider)
              : null,
        ),
        data: (history) => _EquityCurveCard(l: l, history: history),
      ),
    );
  }
}

class _EquityCurveSkeleton extends StatelessWidget {
  const _EquityCurveSkeleton();

  @override
  Widget build(BuildContext context) {
    return Container(
      height: _kChartHeight + AmiSpacing.m * 2 + 24,
      decoration: BoxDecoration(
        color: AmiColors.slate800.withValues(alpha: 0.5),
        borderRadius: BorderRadius.circular(AmiRadii.card),
        border: Border.all(color: AmiColors.slate700),
      ),
    );
  }
}

/// Mirrors `ticker_chart.dart`'s `_ChartNotice` shape: [onRetry] null means
/// tapping could not change the outcome, so nothing here is tappable and no
/// refresh glyph is shown (DEF151's lesson — an affordance that cannot do
/// what it depicts).
class _EquityCurveNotice extends StatelessWidget {
  const _EquityCurveNotice({required this.label, this.onRetry});

  final String label;
  final VoidCallback? onRetry;

  @override
  Widget build(BuildContext context) {
    final body = Padding(
      padding: const EdgeInsets.all(AmiSpacing.m),
      child: Row(
        children: [
          Icon(
            onRetry == null ? Icons.show_chart : Icons.refresh,
            color: AmiColors.textLow,
            size: 18,
          ),
          const SizedBox(width: AmiSpacing.s),
          Expanded(child: Text(label, style: AmiTypography.caption)),
        ],
      ),
    );
    return Container(
      decoration: BoxDecoration(
        color: AmiColors.slate800.withValues(alpha: 0.5),
        borderRadius: BorderRadius.circular(AmiRadii.card),
        border: Border.all(color: AmiColors.slate700),
      ),
      child: onRetry == null
          ? body
          : InkWell(
              onTap: onRetry,
              borderRadius: BorderRadius.circular(AmiRadii.card),
              child: body,
            ),
    );
  }
}

class _EquityCurveCard extends StatefulWidget {
  const _EquityCurveCard({required this.l, required this.history});

  final AppLocalizations l;
  final SimPortfolioHistory history;

  @override
  State<_EquityCurveCard> createState() => _EquityCurveCardState();
}

class _EquityCurveCardState extends State<_EquityCurveCard> {
  // Local-coordinate X of the user's finger during a touch-drag; null when
  // no drag is active. Same crosshair model as ticker_chart.dart.
  double? _dragX;

  @override
  Widget build(BuildContext context) {
    final l = widget.l;
    // The wire contract does not promise point order; sort defensively
    // rather than trust it, same posture as the History tab's own sort of
    // closed trades by date.
    final points = List<SimPortfolioHistoryPoint>.of(widget.history.points)
      ..sort((a, b) => a.asOfDate.compareTo(b.asOfDate));
    final hasCurve = points.length >= 2;
    final anySimulated = points.any((p) => !p.isLive);
    final twr = widget.history.twrPct;
    final twrColor = twr >= 0 ? AmiColors.hexGreen : AmiColors.hexRed;

    return Container(
      padding: const EdgeInsets.all(AmiSpacing.m),
      decoration: BoxDecoration(
        color: AmiColors.slate800,
        borderRadius: BorderRadius.circular(AmiRadii.card),
        border: Border.all(color: AmiColors.slate700),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Wrap, not Row+Spacer: at narrow widths or a larger text scale a
          // fixed Row here throws a RenderFlex overflow (measured: 59–110px
          // at 1.0–1.15 scale on a 390pt surface). Wrap drops the trailing
          // group to its own line instead of overflowing — the same
          // overflow-safe pattern `_ClosedTradeSummary` already uses below
          // in this file for its own row of stat labels.
          Wrap(
            crossAxisAlignment: WrapCrossAlignment.center,
            spacing: AmiSpacing.s,
            runSpacing: 4,
            children: [
              Text(
                l.portfolioEquityCurveHeading,
                style: AmiTypography.labelMono
                    .copyWith(color: AmiColors.hexCyan),
              ),
              if (hasCurve)
                Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Text(
                      l.portfolioEquityCurveWindowReturn,
                      style: AmiTypography.caption.copyWith(fontSize: 10),
                    ),
                    const SizedBox(width: 4),
                    Text(
                      _isolateNumeric(
                        '${twr >= 0 ? '+' : ''}${twr.toStringAsFixed(2)}%',
                      ),
                      style: AmiTypography.labelMono
                          .copyWith(fontSize: 11, color: twrColor),
                    ),
                  ],
                ),
            ],
          ),
          const SizedBox(height: AmiSpacing.s),
          if (!hasCurve)
            Row(
              children: [
                const Icon(Icons.show_chart,
                    color: AmiColors.textLow, size: 16),
                const SizedBox(width: AmiSpacing.s),
                Expanded(
                  child: Text(
                    l.portfolioEquityCurveEmpty,
                    style: AmiTypography.caption,
                  ),
                ),
              ],
            )
          else ...[
            GestureDetector(
              behavior: HitTestBehavior.opaque,
              onHorizontalDragStart: (d) =>
                  setState(() => _dragX = d.localPosition.dx),
              onHorizontalDragUpdate: (d) =>
                  setState(() => _dragX = d.localPosition.dx),
              onHorizontalDragEnd: (_) => setState(() => _dragX = null),
              onHorizontalDragCancel: () => setState(() => _dragX = null),
              onTapDown: (d) => setState(() => _dragX = d.localPosition.dx),
              onTapUp: (_) => setState(() => _dragX = null),
              onTapCancel: () => setState(() => _dragX = null),
              child: SizedBox(
                height: _kChartHeight,
                width: double.infinity,
                child: CustomPaint(
                  painter:
                      _EquityCurvePainter(points: points, dragX: _dragX),
                ),
              ),
            ),
            if (anySimulated) ...[
              const SizedBox(height: AmiSpacing.xs),
              Text(
                l.portfolioEquityCurveSimulatedNote,
                style:
                    AmiTypography.caption.copyWith(color: AmiColors.textLow),
              ),
            ],
          ],
        ],
      ),
    );
  }
}

// ── Painter ─────────────────────────────────────────────────────────────

double _yForNav(double nav, double minNav, double maxNav, double height) {
  if (maxNav <= minNav) return height / 2;
  return height - ((nav - minNav) / (maxNav - minNav)) * height;
}

double _xForIndex(int i, int count, double width) {
  if (count <= 1) return width / 2;
  return (i / (count - 1)) * width;
}

/// Manual dash stepper — no `path_drawing` dependency in this project, and
/// this is the one primitive that needs it. Walks from [from] to [to] in
/// fixed dash/gap increments.
void _drawDashedLine(
  Canvas canvas,
  Offset from,
  Offset to,
  Paint paint, {
  double dashLength = 4,
  double gapLength = 3,
}) {
  final total = (to - from).distance;
  if (total == 0) return;
  final direction = (to - from) / total;
  var covered = 0.0;
  var start = from;
  while (covered < total) {
    final reachedEnd = covered + dashLength >= total;
    final dashEnd = reachedEnd ? to : start + direction * dashLength;
    canvas.drawLine(start, dashEnd, paint);
    covered += dashLength + gapLength;
    start = dashEnd + direction * gapLength;
  }
}

class _EquityCurvePainter extends CustomPainter {
  _EquityCurvePainter({required this.points, required this.dragX});

  final List<SimPortfolioHistoryPoint> points;
  final double? dragX;

  @override
  void paint(Canvas canvas, Size size) {
    if (points.length < 2) return;

    final minNav = points.map((p) => p.nav).reduce((a, b) => a < b ? a : b);
    final maxNav = points.map((p) => p.nav).reduce((a, b) => a > b ? a : b);

    final offsets = [
      for (var i = 0; i < points.length; i++)
        Offset(
          _xForIndex(i, points.length, size.width),
          _yForNav(points[i].nav, minNav, maxNav, size.height),
        ),
    ];

    _paintFill(canvas, size, offsets);
    _paintLine(canvas, offsets);
    _paintProvenanceTicks(canvas, offsets);

    if (dragX != null) {
      _paintCrosshair(canvas, size, offsets);
    }
  }

  void _paintFill(Canvas canvas, Size size, List<Offset> offsets) {
    final fillPath = Path()..moveTo(offsets.first.dx, size.height);
    for (final o in offsets) {
      fillPath.lineTo(o.dx, o.dy);
    }
    fillPath.lineTo(offsets.last.dx, size.height);
    fillPath.close();
    canvas.drawPath(
      fillPath,
      Paint()
        ..shader = LinearGradient(
          begin: Alignment.topCenter,
          end: Alignment.bottomCenter,
          colors: [
            AmiColors.hexCyan.withValues(alpha: 0.25),
            AmiColors.hexCyan.withValues(alpha: 0.02),
          ],
        ).createShader(Rect.fromLTWH(0, 0, size.width, size.height)),
    );
  }

  /// The line, segment by segment. CR040/CR134: a segment touching a
  /// non-live point is dashed, never dimmed — same color, same opacity,
  /// whether the segment is solid or dashed. Encoding provenance by
  /// darkening or desaturating the mark is exactly what CR134 rules out:
  /// "a dimmed mark reads as absent, not small."
  void _paintLine(Canvas canvas, List<Offset> offsets) {
    final linePaint = Paint()
      ..color = AmiColors.hexCyan
      ..strokeWidth = 1.8
      ..style = PaintingStyle.stroke
      ..strokeJoin = StrokeJoin.round
      ..strokeCap = StrokeCap.round;
    for (var i = 0; i < offsets.length - 1; i++) {
      final segmentLive = points[i].isLive && points[i + 1].isLive;
      if (segmentLive) {
        canvas.drawLine(offsets[i], offsets[i + 1], linePaint);
      } else {
        _drawDashedLine(canvas, offsets[i], offsets[i + 1], linePaint);
      }
    }
  }

  /// A second, independent provenance signal — a filled tick at every
  /// non-live point, full color and full opacity. Belt-and-braces for the
  /// case a single simulated day sits mid-run between two live segments,
  /// where the dashing on its own two short segments is easy to miss.
  void _paintProvenanceTicks(Canvas canvas, List<Offset> offsets) {
    final tickPaint = Paint()
      ..color = AmiColors.hexCyan
      ..style = PaintingStyle.fill;
    for (var i = 0; i < points.length; i++) {
      if (!points[i].isLive) {
        canvas.drawCircle(offsets[i], 2.6, tickPaint);
      }
    }
  }

  void _paintCrosshair(Canvas canvas, Size size, List<Offset> offsets) {
    final x = dragX!.clamp(0.0, size.width);
    canvas.drawLine(
      Offset(x, 0),
      Offset(x, size.height),
      Paint()
        ..color = AmiColors.textMed.withValues(alpha: 0.6)
        ..strokeWidth = 1,
    );

    final i = _nearestIndex(x, offsets);
    final p = points[i];
    final readout =
        '${DateFormat('MMM d').format(p.asOfDate)} · \$${p.nav.toStringAsFixed(2)}';
    final tp = TextPainter(
      text: TextSpan(
        text: readout,
        style: const TextStyle(
          color: AmiColors.textHigh,
          fontSize: 10,
          fontFeatures: [FontFeature.tabularFigures()],
        ),
      ),
      textDirection: ui.TextDirection.ltr,
    )..layout();

    const padding = 4.0;
    final boxW = tp.width + padding * 2;
    final boxH = tp.height + padding * 2;
    final left = x + boxW + 6 > size.width ? x - boxW - 6 : x + 6;
    final rect = Rect.fromLTWH(
      left.clamp(0.0, size.width - boxW),
      4,
      boxW,
      boxH,
    );
    canvas.drawRRect(
      RRect.fromRectAndRadius(rect, const Radius.circular(4)),
      Paint()..color = AmiColors.slate900.withValues(alpha: 0.85),
    );
    tp.paint(canvas, rect.topLeft + const Offset(padding, padding));
  }

  int _nearestIndex(double x, List<Offset> offsets) {
    var best = 0;
    var bestDist = double.infinity;
    for (var i = 0; i < offsets.length; i++) {
      final d = (offsets[i].dx - x).abs();
      if (d < bestDist) {
        bestDist = d;
        best = i;
      }
    }
    return best;
  }

  @override
  bool shouldRepaint(covariant _EquityCurvePainter old) =>
      old.points != points || old.dragX != dragX;
}
