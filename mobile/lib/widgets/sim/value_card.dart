/// CR234 — the value-card SHELL, extracted from what was `_ValueCard`
/// (`portfolio_screen.dart`) so AMI's own TOTAL VALUE card and Alpaca's
/// linked-account card render from ONE component.
///
/// Saiful, from a TestFlight screenshot: the Alpaca account card used the
/// same border/card treatment as AMI's but not the same typography or
/// layout discipline — its BUYING PWR value wrapped onto two lines
/// ("$362,137.5" / "7") where AMI's own TOTAL VALUE never wraps. *"The
/// alpaca section needs to be done along the same design as the rest."*
///
/// [ValueCard] owns: the title row (label + trailing pill/badge slot), a
/// headline WIDGET slot (so AMI's animated count-up plugs in unchanged),
/// and a column of stat rows below it, all built with the SAME
/// width-safety rule (`Flexible`+`ellipsis`, never a bare `Text` in a
/// `Row`) that `portfolio_screen.dart`'s own P&L/cash row already
/// established — the wrap defect happened because the Alpaca card skipped
/// that rule, not because the rule doesn't exist. `portfolio_screen.dart`'s
/// `_ValueCard` and `widgets/alpaca/alpaca_account_card.dart`'s
/// `AlpacaAccountCard` both build on this now.
library;

import 'package:ami_trade/theme/ami_theme.dart';
import 'package:flutter/material.dart';

/// One label/value pair rendered as a row beneath the headline — e.g.
/// AMI's "CASH $x" or Alpaca's "BUYING PWR $x". Each side is wrapped in
/// `Flexible`+`ellipsis` by [ValueCard] itself so a long-enough number
/// clips instead of wrapping, whatever width the card is given.
class ValueCardStat {
  const ValueCardStat({
    required this.label,
    required this.value,
    this.valueColor,
  });

  final String label;
  final String value;
  final Color? valueColor;
}

/// How [ValueCard] arranges its `stats` row.
///
/// `inline` is `_ValueCard`'s original AMI shape — "CASH $x" and a second
/// stat share one text line, en dash-free, right-aligned pair. `columns` is
/// the pre-existing Alpaca account summary's shape (label above, value
/// below, each stat its own equal-width column) — kept as a distinct mode
/// rather than forced into `inline`'s shape, since Alpaca's account card
/// has three stats (CASH/PORTFOLIO/BUYING PWR) where AMI's has two, and
/// three short stacked columns read better at that count than three
/// same-line label/value pairs would.
enum ValueCardStatsLayout { inline, columns }

class ValueCard extends StatelessWidget {
  const ValueCard({
    super.key,
    required this.title,
    required this.titleColor,
    required this.headline,
    this.trailing,
    this.stats = const [],
    this.statsLayout = ValueCardStatsLayout.inline,
    this.extra = const [],
  });

  final String title;
  final Color titleColor;

  /// The big headline number, as a WIDGET rather than a plain string — so
  /// AMI's own `TweenAnimationBuilder` count-up (CR014/D3) plugs in
  /// unchanged (this shell imposes no animation of its own; a card whose
  /// value can jump discontinuously between unrelated accounts, as
  /// Alpaca's does on unlink/relink, may reasonably skip it). The caller
  /// also decides whether to wrap its own `Text` in a `FittedBox` — AMI's
  /// pre-CR234 headline never did and must not start now (unchanged
  /// rendering); Alpaca's account card does, since a fresh paper account's
  /// buying power ($362,137.57 in Saiful's own screenshot) is exactly the
  /// value that used to wrap onto two lines.
  final Widget headline;

  /// The title row's trailing slot — AMI's `_QuoteSourcePill`
  /// (LIVE/MOCK), or an [AlpacaBadge]. Optional; omitted entirely when null
  /// rather than reserving empty space for it.
  final Widget? trailing;

  /// Stat rows directly under the headline — each stat's value is
  /// `Flexible`+`ellipsis`, the one guard the pre-CR234 Alpaca card skipped.
  final List<ValueCardStat> stats;

  final ValueCardStatsLayout statsLayout;

  /// Anything else the caller needs below the stats (AMI's committed/
  /// available and drawdown lines) — passed through as-is since those are
  /// specific enough to each side that generalising them here would just
  /// be `_ValueCard`'s original bespoke code moved rather than shared.
  final List<Widget> extra;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(AmiSpacing.m),
      decoration: BoxDecoration(
        color: AmiColors.slate800,
        borderRadius: BorderRadius.circular(AmiRadii.sheet),
        border: Border.all(color: AmiColors.slate700),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Flexible(
                child: Text(
                  title,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: AmiTypography.labelMono.copyWith(color: titleColor),
                ),
              ),
              const Spacer(),
              if (trailing != null) trailing!,
            ],
          ),
          const SizedBox(height: AmiSpacing.xs),
          headline,
          if (stats.isNotEmpty) ...[
            const SizedBox(height: AmiSpacing.s),
            statsLayout == ValueCardStatsLayout.inline
                ? _InlineStatsRow(stats: stats)
                : _ColumnStatsRow(stats: stats),
          ],
          ...extra,
        ],
      ),
    );
  }
}

/// AMI's original CASH-row shape: label/value pairs sharing one text line,
/// each value `Flexible`+`ellipsis`.
class _InlineStatsRow extends StatelessWidget {
  const _InlineStatsRow({required this.stats});
  final List<ValueCardStat> stats;

  @override
  Widget build(BuildContext context) {
    final children = <Widget>[];
    for (var i = 0; i < stats.length; i++) {
      final s = stats[i];
      if (i > 0) children.add(const SizedBox(width: AmiSpacing.s));
      children.add(Text(s.label,
          style: AmiTypography.labelMono.copyWith(fontSize: 10)));
      children.add(const SizedBox(width: 6));
      // Flexible+ellipsis, never a bare Text — this is the one guard the
      // pre-CR234 Alpaca card skipped, and BUYING PWR wrapping onto two
      // lines was the direct result.
      children.add(Flexible(
        child: Text(
          s.value,
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
          textAlign: i == 0 ? TextAlign.start : TextAlign.end,
          style: AmiTypography.statSmall.copyWith(color: s.valueColor),
        ),
      ));
    }
    return Row(children: children);
  }
}

/// The pre-existing Alpaca account summary's shape: each stat its own
/// equal-width column, label above (dim caption) and value below
/// (labelMono) — unchanged from `_AlpacaStat`'s original layout, just with
/// the `Flexible`+`ellipsis` guard it was missing added onto the value.
class _ColumnStatsRow extends StatelessWidget {
  const _ColumnStatsRow({required this.stats});
  final List<ValueCardStat> stats;

  @override
  Widget build(BuildContext context) {
    final children = <Widget>[];
    for (var i = 0; i < stats.length; i++) {
      if (i > 0) children.add(const SizedBox(width: AmiSpacing.m));
      final s = stats[i];
      children.add(Expanded(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(s.label,
                style:
                    AmiTypography.caption.copyWith(color: AmiColors.slate500)),
            Text(
              s.value,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: AmiTypography.labelMono
                  .copyWith(color: s.valueColor ?? AmiColors.textHigh),
            ),
          ],
        ),
      ));
    }
    return Row(children: children);
  }
}
