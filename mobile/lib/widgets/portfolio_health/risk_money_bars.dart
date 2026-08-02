/// CR136 M09 — risk vs money bars (solid = risk share, outlined = money share; both invested-sleeve, one scale, one origin). Pure geometry, painter-free.
///
/// The comparison only means anything if both bars are drawn on the same axis,
/// so the axis is an object rather than a convention: [RiskMoneyBarGeometry] is
/// built once from every row and both bars of every row read their offset and
/// width from that one instance. A shared scale and a shared origin are then
/// structural — there is no second place to get them wrong.
///
/// Both shares are invested-sleeve (Rev 4 F9, amendment 1). Cash is a
/// total-book quantity and is shown on its own line by the card, never as a
/// fourth bar: a total-book bar beside invested-sleeve bars would put two
/// bases on one axis, which is exactly the SHARE/LEVEL mix Rev 4 forbids.
///
/// One hue, two treatments — length encodes magnitude, fill-vs-outline encodes
/// kind. No opacity ramp and no size encoding (data_viz §2).
library;

import 'package:ami_trade/theme/ami_theme.dart';
import 'package:flutter/material.dart';

/// One holding's pair of shares, both as decimal fractions of the invested
/// sleeve. `risk` may be negative — a diversifier subtracts risk.
typedef RiskMoneyRow = ({String ticker, double risk, double money});

/// The shared axis. `axisMin` reserves the negative gutter when some holding
/// offsets risk; `axisMax` extends past 1.0 rather than clamping a bar that is
/// drawn to scale.
@immutable
class RiskMoneyBarGeometry {
  const RiskMoneyBarGeometry({required this.axisMin, required this.axisMax});

  /// `min(0.0, smallest risk share)` — never positive, so the origin is on the
  /// track.
  final double axisMin;

  /// `max(1.0, largest risk or money share)`.
  final double axisMax;

  double get span => axisMax - axisMin;

  /// Track-width fraction where zero sits.
  double get originX => -axisMin / span;

  /// True when the axis reserves a negative gutter, so the origin needs a tick
  /// to be readable as an origin rather than a left edge.
  bool get hasNegativeGutter => axisMin < 0.0;

  double widthOf(double share) => share.abs() / span;

  double leftOf(double share) =>
      share >= 0 ? originX : originX - widthOf(share);

  static RiskMoneyBarGeometry fromRows(List<RiskMoneyRow> rows) {
    var lo = 0.0;
    var hi = 1.0;
    for (final r in rows) {
      if (r.risk < lo) lo = r.risk;
      if (r.risk > hi) hi = r.risk;
      if (r.money > hi) hi = r.money;
    }
    return RiskMoneyBarGeometry(axisMin: lo, axisMax: hi);
  }
}

/// Reads `risk_contribution.extensions['per_holding']` rows into the top-N by
/// risk share. Returns an empty list when the engine published no per-holding
/// breakdown, which is the insufficient case — the card drops the whole block
/// rather than drawing an empty axis.
List<RiskMoneyRow> topRiskMoneyRows(Object? perHolding, {int take = 3}) {
  if (perHolding is! List) return const [];
  final rows = <RiskMoneyRow>[];
  for (final raw in perHolding) {
    if (raw is! Map) continue;
    final ticker = raw['ticker'];
    final risk = raw['risk_share'];
    final money = raw['invested_weight'];
    if (ticker is! String || risk is! num || money is! num) continue;
    rows.add((
      ticker: ticker,
      risk: risk.toDouble(),
      money: money.toDouble(),
    ));
  }
  rows.sort((a, b) => b.risk.compareTo(a.risk));
  return rows.take(take).toList(growable: false);
}

String _pct0(double fraction) {
  final rounded = (fraction * 100).roundToDouble();
  // `-0%` is arithmetically right and reads as a typo.
  final safe = rounded == 0.0 ? 0.0 : rounded;
  return '${safe.toStringAsFixed(0)}%';
}

/// Directional isolates around a numeric run, so RTL reordering cannot
/// scramble it (CR106's T-BIDI trap). Same two-line shape as
/// `_isolateNumeric` in `portfolio_screen.dart`, which is file-private there.
String _isolateNumeric(String s) => '\u2066$s\u2069';

class RiskMoneyBars extends StatelessWidget {
  const RiskMoneyBars({
    super.key,
    required this.rows,
    required this.legend,
    required this.axisMaxLabelStyle,
  });

  final List<RiskMoneyRow> rows;

  /// Rendered under the tracks by the card, which owns all copy.
  final Widget legend;

  /// Kept as a parameter so the card's caption/legend typography stays in one
  /// place; the bars own geometry, not the type scale.
  final TextStyle axisMaxLabelStyle;

  @override
  Widget build(BuildContext context) {
    final geometry = RiskMoneyBarGeometry.fromRows(rows);
    // A magnitude axis does not mirror (data_viz §5). The wrap lives here
    // rather than at the call site so the invariant travels with the widget.
    return Directionality(
      textDirection: TextDirection.ltr,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          for (final row in rows) ...[
            _BarRow(row: row, geometry: geometry),
            const SizedBox(height: AmiSpacing.s),
          ],
          _AxisLabels(geometry: geometry, style: axisMaxLabelStyle),
          const SizedBox(height: AmiSpacing.xs),
          legend,
        ],
      ),
    );
  }
}

class _BarRow extends StatelessWidget {
  const _BarRow({required this.row, required this.geometry});

  final RiskMoneyRow row;
  final RiskMoneyBarGeometry geometry;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Text(row.ticker, style: AmiTypography.labelMono),
            // The mark is labelled (data_viz §4.4) and this text is also the
            // accessibility surface — the bars themselves are excluded, since
            // a screen reader cannot read a rectangle.
            Text(
              _isolateNumeric('${_pct0(row.risk)} / ${_pct0(row.money)}'),
              style: AmiTypography.statSmall,
            ),
          ],
        ),
        const SizedBox(height: AmiSpacing.xs),
        ExcludeSemantics(
          child: Column(
            children: [
              _Bar(share: row.risk, geometry: geometry, solid: true),
              const SizedBox(height: 3),
              _Bar(share: row.money, geometry: geometry, solid: false),
            ],
          ),
        ),
      ],
    );
  }
}

class _Bar extends StatelessWidget {
  const _Bar({
    required this.share,
    required this.geometry,
    required this.solid,
  });

  final double share;
  final RiskMoneyBarGeometry geometry;
  final bool solid;

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        final w = constraints.maxWidth;
        return SizedBox(
          height: 6,
          width: w,
          child: Stack(
            children: [
              if (geometry.hasNegativeGutter)
                Positioned(
                  left: geometry.originX * w,
                  top: 0,
                  bottom: 0,
                  child: Container(width: 1, color: AmiColors.slate600),
                ),
              Padding(
                padding: EdgeInsets.only(left: geometry.leftOf(share) * w),
                child: SizedBox(
                  width: geometry.widthOf(share) * w,
                  height: 6,
                  child: ClipRRect(
                    borderRadius: BorderRadius.circular(3),
                    child: Container(
                      decoration: BoxDecoration(
                        color: solid ? AmiColors.hexBlue : Colors.transparent,
                        border: solid
                            ? null
                            : Border.all(color: AmiColors.hexBlue, width: 1),
                        borderRadius: BorderRadius.circular(3),
                      ),
                    ),
                  ),
                ),
              ),
            ],
          ),
        );
      },
    );
  }
}

class _AxisLabels extends StatelessWidget {
  const _AxisLabels({required this.geometry, required this.style});

  final RiskMoneyBarGeometry geometry;
  final TextStyle style;

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        final w = constraints.maxWidth;
        return SizedBox(
          height: 14,
          width: w,
          child: Stack(
            children: [
              Positioned(
                left: geometry.originX * w,
                top: 0,
                child: Text(_isolateNumeric('0'), style: style),
              ),
              Positioned(
                right: 0,
                top: 0,
                // The real maximum, never a clamped 100% — a bar drawn to
                // scale past the round number has to be readable as such.
                child: Text(
                  _isolateNumeric(_pct0(geometry.axisMax)),
                  style: style,
                ),
              ),
            ],
          ),
        );
      },
    );
  }
}
