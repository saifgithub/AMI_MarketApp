/// TickerChart — adaptive candlestick / line chart for the TickerDetail screen.
///
/// Bundle 2 of the TickerDetail surface (AT:R41). The grilling pass in
/// AT:R40 locked: 6 period chips (1D/1W/1M/3M/1Y/5Y, default 1M),
/// candlestick for short ranges (1D/1W/1M), line for long ranges
/// (3M/1Y/5Y), volume bars always rendered as a sub-chart, crosshair
/// on touch-drag, 220pt portrait height. Used in both portrait
/// (`onExpand` non-null → expand button visible) and landscape
/// fullscreen (`onExpand` null → no expand button).
///
/// fl_chart 0.69.0 has no CandlestickChart widget, so the candles are
/// painted by a custom CustomPainter. The line variant also uses a
/// custom painter — keeps the touch model uniform (one top-level
/// GestureDetector drives the crosshair across price + volume).
library;

import 'dart:ui' as ui;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/sim.dart';
import 'package:ami_trade/state/ticker_history_provider.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:ami_trade/theme/hex_clipper.dart';
import 'package:ami_trade/widgets/hex/hex_pulse_loader.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';

const List<String> _kPeriods = ['1D', '1W', '1M', '3M', '1Y', '5Y'];
const String _kDefaultPeriod = '1M';

// Candlestick body width as a fraction of the per-candle slot.
const double _kCandleBodyFraction = 0.7;

enum _ChartType { candlestick, line }

_ChartType _chartTypeFor(String period) {
  switch (period.toUpperCase()) {
    case '1D':
    case '1W':
    case '1M':
      return _ChartType.candlestick;
    default:
      return _ChartType.line;
  }
}

class TickerChart extends ConsumerStatefulWidget {
  const TickerChart({
    super.key,
    required this.ticker,
    required this.height,
    this.onExpand,
  });

  final String ticker;
  final double height;

  /// Non-null in portrait (shows the expand IconButton at top-right).
  /// Null in the fullscreen route (already fullscreen — no expand).
  final VoidCallback? onExpand;

  @override
  ConsumerState<TickerChart> createState() => _TickerChartState();
}

class _TickerChartState extends ConsumerState<TickerChart> {
  String _period = _kDefaultPeriod;
  // Local-coordinate X of the user's finger during a touch-drag; null
  // when no drag is active. Drives the crosshair line and the readout
  // label in both painters.
  double? _dragX;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final key = TickerHistoryKey(widget.ticker, _period.toLowerCase());
    final async = ref.watch(tickerHistoryProvider(key));

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        _PeriodSelector(
          period: _period,
          onChanged: (p) => setState(() {
            _period = p;
            _dragX = null;
          }),
        ),
        const SizedBox(height: AmiSpacing.xs),
        SizedBox(
          height: widget.height,
          child: Stack(
            children: [
              async.when(
                loading: () => const _ChartSkeleton(),
                error: (_, __) => _ChartError(
                  label: l.tickerDetailChartUnavailable,
                  onRetry: () => ref.invalidate(tickerHistoryProvider(key)),
                ),
                data: (history) {
                  if (history.candles.isEmpty) {
                    return _ChartError(
                      label: l.tickerDetailChartUnavailable,
                      onRetry: () => ref.invalidate(tickerHistoryProvider(key)),
                    );
                  }
                  return _ChartBody(
                    history: history,
                    chartType: _chartTypeFor(_period),
                    dragX: _dragX,
                    onDragUpdate: (x) => setState(() => _dragX = x),
                    onDragEnd: () => setState(() => _dragX = null),
                  );
                },
              ),
              if (widget.onExpand != null)
                Positioned(
                  top: 4,
                  right: 4,
                  child: Tooltip(
                    message: l.tickerDetailChartExpand,
                    child: IconButton(
                      iconSize: 18,
                      padding: const EdgeInsets.all(6),
                      constraints: const BoxConstraints(),
                      icon: const Icon(
                        Icons.fullscreen,
                        color: AmiColors.textMed,
                      ),
                      onPressed: widget.onExpand,
                    ),
                  ),
                ),
            ],
          ),
        ),
      ],
    );
  }
}

// ── Period selector ─────────────────────────────────────────────────────


/// C3 (CR015/D7) — elongated-hex period toggle. Active cell = solid hexBlue +
/// glow; inactive = slate800 with a slate700 hex border.
class _PeriodSelector extends StatelessWidget {
  const _PeriodSelector({required this.period, required this.onChanged});

  final String period;
  final ValueChanged<String> onChanged;

  @override
  Widget build(BuildContext context) {
    return Wrap(
      spacing: 6,
      runSpacing: 6,
      children: [
        for (final p in _kPeriods)
          _PeriodCell(
            label: p,
            active: p == period,
            onTap: () => onChanged(p),
          ),
      ],
    );
  }
}

class _PeriodCell extends StatelessWidget {
  const _PeriodCell({
    required this.label,
    required this.active,
    required this.onTap,
  });

  final String label;
  final bool active;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    Widget cell = ClipPath(
      clipper: const FlatTopHexagonClipper(cornerCut: 8),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 7),
        decoration: BoxDecoration(
          color: active ? AmiColors.hexBlue : AmiColors.slate800,
          border: Border.all(
            color: active ? AmiColors.hexBlue : AmiColors.slate700,
            width: 1,
          ),
        ),
        child: Text(
          label,
          style: AmiTypography.labelMono.copyWith(
            fontSize: 11,
            color: active ? AmiColors.slate900 : AmiColors.textMed,
          ),
        ),
      ),
    );
    if (active) {
      cell = DecoratedBox(
        decoration: const BoxDecoration(boxShadow: AmiShadow.glowBlue),
        child: cell,
      );
    }
    return Semantics(
      button: true,
      selected: active,
      label: label,
      child: GestureDetector(
        onTap: onTap,
        behavior: HitTestBehavior.opaque,
        child: cell,
      ),
    );
  }
}

// ── Loading / error states ──────────────────────────────────────────────


class _ChartSkeleton extends StatelessWidget {
  const _ChartSkeleton();

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        color: AmiColors.slate800.withValues(alpha: 0.5),
        borderRadius: BorderRadius.circular(AmiRadii.card),
        border: Border.all(color: AmiColors.slate700),
      ),
      child: const Center(child: HexPulseLoader(size: 28)),
    );
  }
}


class _ChartError extends StatelessWidget {
  const _ChartError({required this.label, required this.onRetry});

  final String label;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        color: AmiColors.slate800.withValues(alpha: 0.5),
        borderRadius: BorderRadius.circular(AmiRadii.card),
        border: Border.all(color: AmiColors.slate700),
      ),
      child: InkWell(
        onTap: onRetry,
        borderRadius: BorderRadius.circular(AmiRadii.card),
        child: Center(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Icon(Icons.refresh, color: AmiColors.textLow, size: 24),
              const SizedBox(height: AmiSpacing.xs),
              Text(
                label,
                style: AmiTypography.caption,
                textAlign: TextAlign.center,
              ),
            ],
          ),
        ),
      ),
    );
  }
}

// ── Chart body — price + volume stack ───────────────────────────────────


class _ChartBody extends StatelessWidget {
  const _ChartBody({
    required this.history,
    required this.chartType,
    required this.dragX,
    required this.onDragUpdate,
    required this.onDragEnd,
  });

  final SimHistory history;
  final _ChartType chartType;
  final double? dragX;
  final ValueChanged<double> onDragUpdate;
  final VoidCallback onDragEnd;

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      behavior: HitTestBehavior.opaque,
      onHorizontalDragStart: (d) => onDragUpdate(d.localPosition.dx),
      onHorizontalDragUpdate: (d) => onDragUpdate(d.localPosition.dx),
      onHorizontalDragEnd: (_) => onDragEnd(),
      onHorizontalDragCancel: onDragEnd,
      onTapDown: (d) => onDragUpdate(d.localPosition.dx),
      onTapUp: (_) => onDragEnd(),
      onTapCancel: onDragEnd,
      child: Container(
        decoration: BoxDecoration(
          color: AmiColors.slate800.withValues(alpha: 0.5),
          borderRadius: BorderRadius.circular(AmiRadii.card),
          border: Border.all(color: AmiColors.slate700),
        ),
        clipBehavior: Clip.antiAlias,
        child: LayoutBuilder(
          builder: (context, constraints) {
            // Volume takes the bottom 1/4 of available height.
            final priceH = constraints.maxHeight * 0.75;
            final volumeH = constraints.maxHeight - priceH;
            return Column(
              children: [
                SizedBox(
                  height: priceH,
                  width: constraints.maxWidth,
                  child: CustomPaint(
                    painter: _PricePainter(
                      candles: history.candles,
                      chartType: chartType,
                      dragX: dragX,
                    ),
                  ),
                ),
                SizedBox(
                  height: volumeH,
                  width: constraints.maxWidth,
                  child: CustomPaint(
                    painter: _VolumePainter(
                      candles: history.candles,
                      chartType: chartType,
                      dragX: dragX,
                    ),
                  ),
                ),
              ],
            );
          },
        ),
      ),
    );
  }
}

// ── Painters ────────────────────────────────────────────────────────────


/// Map a price into the painter's y coordinate.
double _yFor(double price, double minPrice, double maxPrice, double height) {
  if (maxPrice <= minPrice) return height / 2;
  return height - ((price - minPrice) / (maxPrice - minPrice)) * height;
}

/// Index of the candle closest to the user's finger.
int _nearestIndex(double dragX, int count, double width) {
  if (count == 0) return 0;
  final slot = width / count;
  final i = (dragX / slot).floor();
  return i.clamp(0, count - 1);
}


class _PricePainter extends CustomPainter {
  _PricePainter({
    required this.candles,
    required this.chartType,
    required this.dragX,
  });

  final List<SimCandle> candles;
  final _ChartType chartType;
  final double? dragX;

  @override
  void paint(Canvas canvas, Size size) {
    if (candles.isEmpty) return;

    final minPrice = candles.map((c) => c.l).reduce((a, b) => a < b ? a : b);
    final maxPrice = candles.map((c) => c.h).reduce((a, b) => a > b ? a : b);

    if (chartType == _ChartType.candlestick) {
      _paintCandles(canvas, size, minPrice, maxPrice);
    } else {
      _paintLine(canvas, size, minPrice, maxPrice);
    }

    if (dragX != null) {
      _paintCrosshair(canvas, size, minPrice, maxPrice);
    }
  }

  void _paintCandles(Canvas canvas, Size size, double minPrice, double maxPrice) {
    final slot = size.width / candles.length;
    final bodyWidth = slot * _kCandleBodyFraction;
    final wickPaint = Paint()
      ..color = AmiColors.textLow
      ..strokeWidth = 1;

    for (var i = 0; i < candles.length; i++) {
      final c = candles[i];
      final centerX = slot * i + slot / 2;
      final highY = _yFor(c.h, minPrice, maxPrice, size.height);
      final lowY = _yFor(c.l, minPrice, maxPrice, size.height);
      final openY = _yFor(c.o, minPrice, maxPrice, size.height);
      final closeY = _yFor(c.c, minPrice, maxPrice, size.height);

      canvas.drawLine(
        Offset(centerX, highY),
        Offset(centerX, lowY),
        wickPaint,
      );

      final up = c.c >= c.o;
      final bodyPaint = Paint()
        ..color = up ? AmiColors.hexGreen : AmiColors.hexRed
        ..style = PaintingStyle.fill;
      // Body must be at least 1px tall so flat-tick candles are visible.
      final top = openY < closeY ? openY : closeY;
      final bottom = openY < closeY ? closeY : openY;
      final h = (bottom - top).clamp(1.0, size.height);
      canvas.drawRect(
        Rect.fromLTWH(centerX - bodyWidth / 2, top, bodyWidth, h),
        bodyPaint,
      );
    }
  }

  void _paintLine(Canvas canvas, Size size, double minPrice, double maxPrice) {
    final slot = size.width / candles.length;
    final path = Path();
    final fillPath = Path();

    for (var i = 0; i < candles.length; i++) {
      final x = slot * i + slot / 2;
      final y = _yFor(candles[i].c, minPrice, maxPrice, size.height);
      if (i == 0) {
        path.moveTo(x, y);
        fillPath.moveTo(x, size.height);
        fillPath.lineTo(x, y);
      } else {
        path.lineTo(x, y);
        fillPath.lineTo(x, y);
      }
    }
    // Close fill path back down to the baseline.
    final last = slot * (candles.length - 1) + slot / 2;
    fillPath.lineTo(last, size.height);
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
    canvas.drawPath(
      path,
      Paint()
        ..color = AmiColors.hexCyan
        ..strokeWidth = 1.8
        ..style = PaintingStyle.stroke
        ..strokeJoin = StrokeJoin.round
        ..strokeCap = StrokeCap.round,
    );
  }

  void _paintCrosshair(Canvas canvas, Size size, double minPrice, double maxPrice) {
    final x = dragX!.clamp(0.0, size.width);
    final crosshairPaint = Paint()
      ..color = AmiColors.textMed.withValues(alpha: 0.6)
      ..strokeWidth = 1;
    canvas.drawLine(
      Offset(x, 0),
      Offset(x, size.height),
      crosshairPaint,
    );

    final i = _nearestIndex(x, candles.length, size.width);
    final c = candles[i];
    final readout = '${DateFormat('MMM d').format(c.dateTime.toLocal())} · '
        '\$${c.c.toStringAsFixed(2)}';
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

    // Pin the readout to the top, offset toward whichever side has room.
    final padding = 4.0;
    final boxW = tp.width + padding * 2;
    final boxH = tp.height + padding * 2;
    final left = x + boxW + 6 > size.width
        ? x - boxW - 6
        : x + 6;
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
    tp.paint(canvas, rect.topLeft + Offset(padding, padding));
  }

  @override
  bool shouldRepaint(covariant _PricePainter old) =>
      old.candles != candles ||
      old.chartType != chartType ||
      old.dragX != dragX;
}


class _VolumePainter extends CustomPainter {
  _VolumePainter({
    required this.candles,
    required this.chartType,
    required this.dragX,
  });

  final List<SimCandle> candles;
  final _ChartType chartType;
  final double? dragX;

  @override
  void paint(Canvas canvas, Size size) {
    if (candles.isEmpty) return;

    final maxV = candles.map((c) => c.v).reduce((a, b) => a > b ? a : b);
    if (maxV <= 0) return;

    final slot = size.width / candles.length;
    final barWidth = slot * _kCandleBodyFraction;

    for (var i = 0; i < candles.length; i++) {
      final c = candles[i];
      final centerX = slot * i + slot / 2;
      final h = (c.v / maxV) * size.height;
      Color color;
      if (chartType == _ChartType.candlestick) {
        color = (c.c >= c.o ? AmiColors.hexGreen : AmiColors.hexRed)
            .withValues(alpha: 0.55);
      } else {
        color = AmiColors.slate500.withValues(alpha: 0.6);
      }
      canvas.drawRect(
        Rect.fromLTWH(
          centerX - barWidth / 2,
          size.height - h,
          barWidth,
          h,
        ),
        Paint()..color = color,
      );
    }

    if (dragX != null) {
      final x = dragX!.clamp(0.0, size.width);
      canvas.drawLine(
        Offset(x, 0),
        Offset(x, size.height),
        Paint()
          ..color = AmiColors.textMed.withValues(alpha: 0.6)
          ..strokeWidth = 1,
      );
    }
  }

  @override
  bool shouldRepaint(covariant _VolumePainter old) =>
      old.candles != candles ||
      old.chartType != chartType ||
      old.dragX != dragX;
}


