/// CR234 — the position-card SHELL, extracted from what was `_HoldingCard`
/// (`portfolio_screen.dart`, CR188 slice 3) so AMI's own holdings and
/// Alpaca's linked positions render from ONE component rather than two
/// copies that can drift.
///
/// Saiful, from a TestFlight screenshot: Alpaca's positions rendered as bare
/// text rows ("ASML  x10 $17,220  -$28") — no card, no chevron, no %
/// change — while AMI's own positions were full cards (big ticker,
/// "21 sh · $210.48", STOP chip, coloured % change, chevron to detail).
/// *"The alpaca section needs to be done along the same design as the
/// rest."* The fix is this file: [PositionCard] is the exact visual shell
/// both now share, dense-collapsed / expandable-in-place per CR188's own
/// brief ("small enough to show a lot of tiles, and make them expandable to
/// see details").
///
/// [PositionCard] knows nothing about `SimHolding` or Alpaca's own models —
/// every field is a primitive or a widget slot, so it has no reason to ever
/// fork per data source again. `portfolio_screen.dart`'s `_HoldingCard`
/// builds on this for AMI holdings; `AlpacaPositionCard`
/// (`widgets/alpaca/alpaca_position_card.dart`) builds on it for Alpaca's.
library;

import 'package:ami_trade/theme/ami_theme.dart';
import 'package:ami_trade/widgets/hex/hex_chip.dart';
import 'package:flutter/material.dart';

/// One position, collapsed to a single scannable row with an optional
/// expandable detail section below it. Stateful only for the open/closed
/// toggle — every displayed fact is a constructor parameter.
class PositionCard extends StatefulWidget {
  const PositionCard({
    super.key,
    required this.ticker,
    required this.subtitle,
    required this.pctChange,
    this.stopLabel,
    this.badge,
    this.detailBuilder,
    this.onTap,
  });

  /// The loud element (CR120 §6 defect 6 — ticker is what a list is scanned
  /// by), fixed-width so a long symbol still aligns with the row above/below
  /// it. Callers pass the raw ticker; this widget owns no truncation logic
  /// beyond what `_HoldingCard` already used (a 66dp box), since neither AMI
  /// nor Alpaca symbols run long enough to need `FittedBox` the way the
  /// watchlist's wider `statMid` treatment does.
  final String ticker;

  /// The one-line fact under the ticker — AMI's "21 sh · \$210.48", or
  /// Alpaca's own quantity/avg-cost equivalent. A single pre-formatted
  /// string rather than separate qty/price fields: the two sources format
  /// this differently enough (AMI always has an avg cost; Alpaca's position
  /// response also reports its own average entry price under a different
  /// field name) that owning the formatting here would just move the fork
  /// inside this file instead of removing it.
  final String subtitle;

  /// Signed percent (already computed, e.g. `+5.3` or `-2.1`) — this widget
  /// only decides the colour (green/red) and the isolate-wrapped rendering,
  /// never the number itself.
  final double pctChange;

  /// The stop chip's label text (e.g. "STOP \$190.00"), or null to omit the
  /// chip entirely — "no stop" is a fact about the position (unprotected),
  /// not a rendering error, matching `_HoldingCard`'s original behaviour.
  final String? stopLabel;

  /// An optional identity badge (e.g. [AlpacaBadge]) rendered before the %
  /// change — present on an Alpaca-sourced card, absent on an AMI one (AMI
  /// needs no badge; the whole Positions tab is AMI's home turf).
  final Widget? badge;

  /// Builds the expanded detail section's children, given the row's own
  /// open/close state getter is not needed by the builder — it is only
  /// ever invoked while open. Null means this card never expands (no
  /// chevron, no tap-to-open) — reserved for a future read-only use; every
  /// caller today passes one.
  final List<Widget> Function(BuildContext context)? detailBuilder;

  /// Fires on tap in addition to the built-in expand/collapse — reserved
  /// for a future caller that wants a different primary action (e.g.
  /// navigate straight to detail rather than expand in place). Null means
  /// tapping only toggles expansion, `_HoldingCard`'s original behaviour.
  final VoidCallback? onTap;

  @override
  State<PositionCard> createState() => _PositionCardState();
}

class _PositionCardState extends State<PositionCard> {
  bool _open = false;

  @override
  Widget build(BuildContext context) {
    final accent = widget.pctChange >= 0 ? AmiColors.hexGreen : AmiColors.hexRed;
    final canExpand = widget.detailBuilder != null;

    return Padding(
      padding: const EdgeInsets.only(bottom: 6),
      child: InkWell(
        onTap: () {
          widget.onTap?.call();
          if (canExpand) setState(() => _open = !_open);
        },
        borderRadius: BorderRadius.circular(AmiRadii.card),
        child: Container(
          padding: const EdgeInsets.symmetric(
            horizontal: AmiSpacing.m,
            vertical: AmiSpacing.s,
          ),
          decoration: BoxDecoration(
            color: AmiColors.slate800,
            borderRadius: BorderRadius.circular(AmiRadii.card),
            border: Border.all(
              color: _open
                  ? AmiColors.hexCyan.withValues(alpha: 0.45)
                  : AmiColors.slate700,
            ),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  SizedBox(
                    width: 66,
                    child: Text(widget.ticker,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: AmiTypography.statMid
                            .copyWith(color: AmiColors.textHigh)),
                  ),
                  Expanded(
                    child: Text(
                      widget.subtitle,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: AmiTypography.caption,
                    ),
                  ),
                  const SizedBox(width: 4),
                  // The trailing cluster (badge, stop chip, %, chevron) is a
                  // lot of content for a 320dp phone when a card carries
                  // BOTH a badge and a stop chip (an Alpaca position with a
                  // bracket stop, which AMI's own cards never combined
                  // pre-CR234). FittedBox scales the whole cluster down
                  // together rather than truncating any one piece or
                  // overflowing — the same "shrink, never wrap/overflow"
                  // rule `ValueCard`'s headline uses.
                  Flexible(
                    child: FittedBox(
                      fit: BoxFit.scaleDown,
                      alignment: AlignmentDirectional.centerEnd,
                      child: Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          if (widget.badge != null) ...[
                            widget.badge!,
                            const SizedBox(width: AmiSpacing.s),
                          ],
                          if (widget.stopLabel != null) ...[
                            HexChip(
                              label: widget.stopLabel!,
                              color: AmiColors.hexAmber,
                              variant: HexChipVariant.tinted,
                              fontSize: 10,
                            ),
                            const SizedBox(width: AmiSpacing.s),
                          ],
                          Text(
                            _isolateNumeric(
                              '${widget.pctChange >= 0 ? '+' : ''}'
                              '${widget.pctChange.toStringAsFixed(1)}%',
                            ),
                            style: AmiTypography.labelMono
                                .copyWith(color: accent, fontSize: 12),
                          ),
                          if (canExpand)
                            Icon(_open ? Icons.expand_more : Icons.chevron_right,
                                color: AmiColors.textLow, size: 18),
                        ],
                      ),
                    ),
                  ),
                ],
              ),
              if (_open && canExpand) ...widget.detailBuilder!(context),
            ],
          ),
        ),
      ),
    );
  }
}

/// Wraps a numeric run in Unicode directional isolates so RTL reordering
/// cannot scramble it — the same guard `portfolio_screen.dart`'s own
/// `_isolateNumeric` applies; duplicated as a private top-level function
/// here (rather than imported) because that one is file-private in
/// `portfolio_screen.dart` and this widget must not depend on that screen.
String _isolateNumeric(String s) => '\u2066$s\u2069';
