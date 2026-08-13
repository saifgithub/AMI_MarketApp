/// CR106 — the Verdict Board. One widget, rendered by both the live Room and
/// the Decision Journal replay from the same [RoomBoardData] (T-TWICE).
///
/// The complaint this answers, relayed by Saiful from users: *"the long
/// technical result from convene the room \[is not\] good, most users do not
/// want to read too much."* Measured, that is 12 stacked contributions,
/// ~3,500–6,000 characters, and four to seven phone screens before the verdict
/// is even reached.
///
/// Two rules govern every graphic below, and both exist because a board makes
/// an unsupported claim **louder** than prose does:
///
///  1. **Nothing is drawn that the data does not support.** No level
///     provenance → no risk/reward ribbon, just the plain price list (T-PROV).
///     No recorded stances → one honest sentence, not eleven hexes arranged
///     into empty bands (T-SUM11). Absent is never inferred (T-BACKFILL).
///  2. **Family colour is sacred.** An Analyst hex reads cyan and a Risk hex
///     amber, always. Stance is the *band* a hex sits in, conviction is the
///     underline bar, and the label inside says who it is — because three cyan
///     analysts and two purple researchers are mutually indistinguishable
///     otherwise, and BULL vs BEAR (the pair a reader most wants to tell
///     apart) are the same purple.
///
/// Surface shape follows the shipped app, not the design-system mount: panels
/// are rounded rects (`AmiRadii.card` / `AmiRadii.sheet`), and hexagonal
/// geometry is spent on exactly three things — the agent marks, the hero's
/// outcome mark, and the BOARD|TRANSCRIPT toggle.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/agent.dart';
import 'package:ami_trade/models/room.dart';
import 'package:ami_trade/models/room_board.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:ami_trade/widgets/room/room_consensus_strip.dart';
import 'package:ami_trade/theme/hex_clipper.dart';
import 'package:flutter/material.dart';
import 'package:flutter_markdown_plus/flutter_markdown_plus.dart';
// `package:intl` also exports a `TextDirection`, with `LTR`/`RTL` constants
// that are NOT Flutter's. Hidden so the ribbon's `TextDirection.ltr` lock —
// the thing standing between "2.8 : 1" and "1 : 2.8" in Arabic — resolves to
// the framework's enum and cannot silently bind to the wrong type.
import 'package:intl/intl.dart' hide TextDirection;

/// Accent for an outcome. A **status** colour, sanctioned cross-family by the
/// design system — the PM being purple is irrelevant to it.
Color accentForOutcome(VerdictOutcome outcome) {
  switch (outcome) {
    case VerdictOutcome.approve:
      return AmiColors.hexGreen;
    case VerdictOutcome.reject:
      // Red, not amber: the design system assigns red to mandate violations,
      // and amber stays reserved for the violations list and the safety-floor
      // pill. Two different amber things on one card is one too many.
      return AmiColors.hexRed;
    case VerdictOutcome.noResult:
      return AmiColors.hexRed;
    case VerdictOutcome.pass:
    case VerdictOutcome.noVerdict:
    case VerdictOutcome.unknown:
      // PASS and NO_VERDICT share slate and are told apart by fill-vs-outline,
      // mark, heading and what else is on the card. Copied verbatim from
      // `sharia_verdict_banner.dart`: "unknown → NEUTRAL slate, deliberately…
      // amber here would read as 'this trade was risky'."
      return AmiColors.slate500;
  }
}

/// The single glyph inside the hero's hexagon. `NO_VERDICT` deliberately has
/// none — an empty outline hex *is* the statement, and any mark inside it would
/// read as a decision.
String? _markForOutcome(VerdictOutcome outcome) {
  switch (outcome) {
    case VerdictOutcome.approve:
      return '✓';
    case VerdictOutcome.pass:
      return '—';
    case VerdictOutcome.reject:
    case VerdictOutcome.noResult:
      return '✗';
    case VerdictOutcome.noVerdict:
    case VerdictOutcome.unknown:
      return null;
  }
}

/// Filled outcomes carry a 14% tint; the two "we are not asserting an outcome"
/// states are outline-only.
bool _isFilled(VerdictOutcome outcome) =>
    outcome != VerdictOutcome.noVerdict &&
    outcome != VerdictOutcome.noResult &&
    outcome != VerdictOutcome.unknown;

String headingForOutcome(AppLocalizations l, RoomBoardData d) {
  switch (d.outcome) {
    case VerdictOutcome.approve:
      return l.roomHeroApprove;
    case VerdictOutcome.pass:
      return l.roomHeroPass;
    case VerdictOutcome.reject:
      return l.roomHeroReject;
    case VerdictOutcome.noVerdict:
      return l.roomHeroNoVerdict;
    case VerdictOutcome.noResult:
      return l.roomHeroNoResult;
    case VerdictOutcome.unknown:
      // The raw token. Unreadable, but honest — and strictly better than
      // asserting a failure that did not happen. See VerdictOutcome.unknown.
      return d.actionToken;
  }
}

class RoomBoard extends StatelessWidget {
  const RoomBoard({
    super.key,
    required this.data,
    this.onVoiceTap,
    this.footer,
  });

  final RoomBoardData data;

  /// Tapping a comb hex opens a peek sheet — a peek, not a mode switch. A 26pt
  /// mark is a small, casual target; tearing the whole surface down in
  /// response loses the board's scroll position, and comparison ("why is BEAR
  /// against?" then "what did CON say?") is the normal case.
  final void Function(RoomVoice voice)? onVoiceTap;

  /// Surface-specific actions. The Room offers a trade ticket; the Journal
  /// never does (T-STALE).
  final Widget? footer;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _HeroTile(data: data),
        // The override line sits between hero and comb and is never collapsed.
        // Without it the board contradicts itself — the comb shows 8 FOR while
        // the hero says PASS — and a graphic that looks broken takes the
        // user's trust in every other graphic with it (T-OVERRIDE).
        if (data.overriddenFromLlm) ...[
          const SizedBox(height: AmiSpacing.m),
          _MandateOverride(data: data),
        ],
        if (data.isApprove) ...[
          const SizedBox(height: AmiSpacing.m),
          _TradeGeometry(data: data),
        ],
        const SizedBox(height: AmiSpacing.m),
        // CR173 — the finding, then the evidence. A user who reads one line of
        // this board should learn the split and the objection, not have to
        // count hexes to find them.
        RoomConsensusStrip(data: data),
        const SizedBox(height: AmiSpacing.s),
        _ConsensusComb(data: data, onVoiceTap: onVoiceTap),
        if (data.withheldAnalystIds.isNotEmpty) ...[
          const SizedBox(height: AmiSpacing.m),
          _RosterGap(data: data),
        ],
        const SizedBox(height: AmiSpacing.m),
        _ReasonBlock(data: data),
        if (footer != null) ...[
          const SizedBox(height: AmiSpacing.m),
          footer!,
        ],
        // The dated caption belongs to the record, not to the geometry alone —
        // it is the last thing read before the user acts on anything here.
        if (data.isRecord && data.recordedAt != null) ...[
          const SizedBox(height: AmiSpacing.s),
          Text(
            l.journalLevelsAsOf(
              DateFormat('dd MMM yyyy').format(data.recordedAt!.toLocal())
                  .toUpperCase(),
            ),
            style: AmiTypography.labelMono
                .copyWith(fontSize: 9, color: AmiColors.textLow),
          ),
        ],
      ],
    );
  }
}

// ── hero ──────────────────────────────────────────────────────────────────

/// A hex-*marked* KPI tile, not a giant hexagon.
///
/// `hex_clipper.dart` already records why: sizing a label against a hexagon's
/// bounding box left `ISLAMIC FINANCE` 4.7pt of headroom at 1.0 text scale and
/// none at 1.15, because the usable width at the label line is only 0.724 of
/// the box. So the hexagon carries **one glyph** and the tile carries the words
/// and the number.
class _HeroTile extends StatelessWidget {
  const _HeroTile({required this.data});
  final RoomBoardData data;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final accent = accentForOutcome(data.outcome);
    final filled = _isFilled(data.outcome);
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(AmiSpacing.m),
      decoration: BoxDecoration(
        color: AmiColors.slate800,
        borderRadius: BorderRadius.circular(AmiRadii.sheet),
        border: Border.all(color: accent, width: 1.5),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              _OutcomeHex(
                mark: _markForOutcome(data.outcome),
                accent: accent,
                filled: filled,
              ),
              const SizedBox(width: AmiSpacing.m),
              Expanded(
                child: Text(
                  headingForOutcome(l, data),
                  style: AmiTypography.labelMono.copyWith(color: accent),
                ),
              ),
            ],
          ),
          const SizedBox(height: AmiSpacing.m),
          _HeroValue(data: data, accent: accent),
        ],
      ),
    );
  }
}

class _OutcomeHex extends StatelessWidget {
  const _OutcomeHex({
    required this.mark,
    required this.accent,
    required this.filled,
  });

  final String? mark;
  final Color accent;
  final bool filled;

  static const double _size = 56;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: _size,
      height: _size / flatTopRegularHexagonAspectRatio,
      child: CustomPaint(
        painter: _HexOutlinePainter(accent: accent, filled: filled),
        child: Center(
          child: mark == null
              ? null
              : Text(
                  mark!,
                  style: AmiTypography.statMid
                      .copyWith(color: accent, fontSize: 22),
                ),
        ),
      ),
    );
  }
}

/// A flat-top hexagon: canvas interior, accent border, optional accent tint.
///
/// The interior is the CANVAS, never a saturated accent fill — which is the
/// whole reason the comb's labels are legible where `HexAvatar`'s are not
/// (DEF142). Measured WCAG 2.1 on `slate900`: cyan 7.35 · amber 8.31 · green
/// 7.04 · pink 5.06 · purple 4.22, so every family clears
/// [amiCanvasContrastFloor] — the project's own accent-as-type floor, set by
/// the dimmest shipped token, which is `hexPurple` itself.
///
/// A solid family fill cannot be made to work here: white measures 2.15–4.23
/// across the five, `slate900` is a wash on purple at 4.22 vs white's 4.23, and
/// `textHigh` on purple is **3.85** — worse than white. There is no ink that
/// clears 4.5:1 on a saturated `hexPurple`, so the fill is what changes.
class _HexOutlinePainter extends CustomPainter {
  const _HexOutlinePainter({
    required this.accent,
    required this.filled,
    this.borderAlpha = 1.0,
  });

  final Color accent;

  /// Adds a 14% accent tint over the canvas interior. Cosmetic weight only —
  /// the label's contrast is computed against the canvas either way, because
  /// a 14% tint moves it by less than the floor's margin.
  final bool filled;

  final double borderAlpha;

  @override
  void paint(Canvas canvas, Size size) {
    final path = const FlatTopRegularHexagon().getClip(size);
    canvas.drawPath(path, Paint()..color = AmiColors.slate900);
    if (filled) {
      canvas.drawPath(path, Paint()..color = accent.withValues(alpha: 0.14));
    }
    canvas.drawPath(
      path,
      Paint()
        ..color = accent.withValues(alpha: borderAlpha)
        ..style = PaintingStyle.stroke
        ..strokeWidth = 1.5,
    );
  }

  @override
  bool shouldRepaint(covariant _HexOutlinePainter old) =>
      old.accent != accent ||
      old.filled != filled ||
      old.borderAlpha != borderAlpha;
}

class _HeroValue extends StatelessWidget {
  const _HeroValue({required this.data, required this.accent});
  final RoomBoardData data;
  final Color accent;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    if (data.isApprove) {
      final size = data.sizePct;
      return Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // `FittedBox` on the NUMBER only — never on a mono label, which
          // breaks its letter-spacing rhythm.
          FittedBox(
            fit: BoxFit.scaleDown,
            alignment: AlignmentDirectional.centerStart,
            child: Text(
              size == null ? '—' : '${size.toStringAsFixed(1)}%',
              style: AmiTypography.statBig.copyWith(color: accent),
            ),
          ),
          const SizedBox(height: 2),
          // T-UNIT: a bare "3.0%" beside APPROVE reads as an expected return.
          // The unit line is not decoration.
          Text(
            [
              l.roomHeroUnitPortfolio,
              if (data.horizonDays != null)
                l.roomHeroUnitHorizon(data.horizonDays!),
            ].join(' · '),
            style: AmiTypography.labelMono
                .copyWith(fontSize: 9, color: AmiColors.textLow),
          ),
        ],
      );
    }
    final String value;
    switch (data.outcome) {
      case VerdictOutcome.pass:
        // Words, not "0%". Zero is a size; no position is not a size.
        value = l.roomHeroNoPosition;
        break;
      case VerdictOutcome.reject:
        value = l.roomHeroBlockedCount(data.violations.length);
        break;
      case VerdictOutcome.noVerdict:
        value = l.roomHeroNotIssued;
        break;
      case VerdictOutcome.noResult:
      case VerdictOutcome.unknown:
        value = l.roomHeroNoResultValue;
        break;
      case VerdictOutcome.approve:
        value = '';
        break;
    }
    return FittedBox(
      fit: BoxFit.scaleDown,
      alignment: AlignmentDirectional.centerStart,
      child: Text(
        value,
        style: AmiTypography.statMid.copyWith(color: accent),
      ),
    );
  }
}

// ── mandate override ──────────────────────────────────────────────────────

class _MandateOverride extends StatelessWidget {
  const _MandateOverride({required this.data});
  final RoomBoardData data;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(AmiSpacing.s),
      decoration: BoxDecoration(
        color: AmiColors.slate800,
        borderRadius: BorderRadius.circular(AmiRadii.card),
        border: Border.all(color: AmiColors.hexAmber),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            l.roomOverrideHeading,
            style: AmiTypography.labelMono
                .copyWith(fontSize: 10, color: AmiColors.hexAmber),
          ),
          // Violations render inline and NEVER behind an expander.
          for (final v in data.violations) ...[
            const SizedBox(height: 4),
            Text('• $v', style: AmiTypography.caption),
          ],
        ],
      ),
    );
  }
}

// ── trade geometry: the ribbon, or the plain list ─────────────────────────

class _TradeGeometry extends StatelessWidget {
  const _TradeGeometry({required this.data});
  final RoomBoardData data;

  @override
  Widget build(BuildContext context) {
    return data.showsRibbon ? _RiskRewardRibbon(data: data) : _LevelList(data: data);
  }
}

/// The fallback whenever provenance is missing or the levels do not form a
/// coherent long setup. Not a lesser version of the ribbon — a different,
/// weaker claim, stated as such.
class _LevelList extends StatelessWidget {
  const _LevelList({required this.data});
  final RoomBoardData data;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final accent = accentForOutcome(data.outcome);
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(AmiSpacing.s),
      decoration: BoxDecoration(
        color: AmiColors.slate800,
        borderRadius: BorderRadius.circular(AmiRadii.card),
        border: Border.all(color: AmiColors.slate700),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (data.levelProvenance == null)
            Padding(
              padding: const EdgeInsets.only(bottom: AmiSpacing.xs),
              child: Text(
                l.roomGeometryNoProvenance,
                style: AmiTypography.labelMono
                    .copyWith(fontSize: 9, color: AmiColors.textLow),
              ),
            ),
          BoardMetricRow(
            label: l.roomMetricEntry,
            value: _money(data.entry),
            accent: accent,
          ),
          BoardMetricRow(
            label: l.roomMetricStop,
            value: _money(data.stop),
            accent: accent,
          ),
          BoardMetricRow(
            label: l.roomMetricTarget,
            value: _money(data.target),
            accent: accent,
          ),
          if (data.horizonDays != null)
            BoardMetricRow(
              label: l.roomMetricHorizon,
              value: l.roomHorizonDays(data.horizonDays!),
              accent: accent,
            ),
        ],
      ),
    );
  }
}

String _money(double? v) => v == null ? '—' : '\$${v.toStringAsFixed(2)}';

class BoardMetricRow extends StatelessWidget {
  const BoardMetricRow({
    super.key,
    required this.label,
    required this.value,
    required this.accent,
  });

  final String label;
  final String value;
  final Color accent;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 2),
      child: Row(
        children: [
          SizedBox(
            width: 72,
            child: Text(
              label,
              style: AmiTypography.labelMono
                  .copyWith(fontSize: 11, color: AmiColors.textLow),
            ),
          ),
          Text(value, style: AmiTypography.statSmall.copyWith(color: accent)),
        ],
      ),
    );
  }
}

class _RiskRewardRibbon extends StatelessWidget {
  const _RiskRewardRibbon({required this.data});
  final RoomBoardData data;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final rr = data.riskReward;
    final derived = data.derivedLevelKeys;
    final derivedLabel = derived
        .map((k) => switch (k) {
              'entry' => l.roomMetricEntry,
              'stop' => l.roomMetricStop,
              _ => l.roomMetricTarget,
            })
        .join(' · ');
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(AmiSpacing.s),
      decoration: BoxDecoration(
        color: AmiColors.slate800,
        borderRadius: BorderRadius.circular(AmiRadii.card),
        border: Border.all(color: AmiColors.slate700),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Text(
                  l.roomRibbonHeading,
                  style: AmiTypography.labelMono
                      .copyWith(fontSize: 10, color: AmiColors.textLow),
                ),
              ),
              Text(
                rr == null ? '—' : '${rr.toStringAsFixed(1)} : 1',
                style: AmiTypography.dataMd
                    .copyWith(color: AmiColors.textHigh),
                // T-BIDI: a numeric magnitude run inverts under RTL. Confirmed
                // in the prototype — "2.8 : 1" rendered as "1 : 2.8", which is
                // a WRONG NUMBER, not a layout nit.
                textDirection: TextDirection.ltr,
              ),
            ],
          ),
          const SizedBox(height: AmiSpacing.s),
          // The whole track is locked LTR for the same reason: it is a numeric
          // magnitude axis, and the design system already rules that numbers
          // stay LTR inside RTL text.
          Directionality(
            textDirection: TextDirection.ltr,
            child: _RibbonTrack(data: data),
          ),
          if (derived.isNotEmpty) ...[
            const SizedBox(height: AmiSpacing.s),
            Text(
              // Hollow-vs-filled says "a different KIND of thing", not
              // "danger" — so no amber and no ⚠ here. `⬢`/`⬡` is the brand's
              // own sanctioned pair for exactly this distinction.
              '⬡ ${l.roomRibbonDerived(derivedLabel.toUpperCase())}',
              style: AmiTypography.labelMono
                  .copyWith(fontSize: 9, color: AmiColors.textLow),
            ),
          ],
        ],
      ),
    );
  }
}

class _RibbonTrack extends StatelessWidget {
  const _RibbonTrack({required this.data});
  final RoomBoardData data;

  bool _derived(String key) =>
      data.sourceFor(key) == LevelSource.amiDefault ||
      data.sourceFor(key) == LevelSource.trader;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final f = data.entryFraction;
    return LayoutBuilder(builder: (context, c) {
      final w = c.maxWidth;
      return Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Entry rides ABOVE the track; stop and target sit below it.
          // Splitting the rows is not cosmetic: on one line the three labels
          // collide whenever entry falls within ~22% of either end — which is
          // exactly what a tight stop looks like.
          SizedBox(
            height: 30,
            child: Stack(
              children: [
                Positioned(
                  left: (w * f - 40).clamp(0.0, w - 80),
                  width: 80,
                  child: Column(
                    children: [
                      Text(
                        _money(data.entry),
                        textAlign: TextAlign.center,
                        style: AmiTypography.statSmall
                            .copyWith(color: AmiColors.textHigh),
                      ),
                      Text(
                        l.roomMetricEntry,
                        textAlign: TextAlign.center,
                        style: AmiTypography.labelMono.copyWith(
                            fontSize: 8, color: AmiColors.textLow),
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 2),
          ClipPath(
            clipper: const CutCornerOctagonClipper(cornerCut: 4),
            child: SizedBox(
              height: 8,
              child: Row(
                children: [
                  Expanded(
                    flex: (f * 1000).round().clamp(1, 999),
                    child: _RibbonSegment(
                      color: AmiColors.hexRed,
                      dashed: _derived('stop'),
                    ),
                  ),
                  Expanded(
                    flex: ((1 - f) * 1000).round().clamp(1, 999),
                    child: _RibbonSegment(
                      color: AmiColors.hexGreen,
                      dashed: _derived('target'),
                    ),
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 2),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              _RibbonEnd(
                price: _money(data.stop),
                label: l.roomMetricStop,
                hollow: _derived('stop'),
                align: CrossAxisAlignment.start,
              ),
              _RibbonEnd(
                price: _money(data.target),
                label: l.roomMetricTarget,
                hollow: _derived('target'),
                align: CrossAxisAlignment.end,
              ),
            ],
          ),
        ],
      );
    });
  }
}

class _RibbonSegment extends StatelessWidget {
  const _RibbonSegment({required this.color, required this.dashed});
  final Color color;
  final bool dashed;

  @override
  Widget build(BuildContext context) {
    // A level AMI supplied gets a lighter, broken-looking fill; one a person
    // stated is solid. Same hue either way — provenance is not severity.
    return Container(
      color: color.withValues(alpha: dashed ? 0.18 : 0.45),
    );
  }
}

class _RibbonEnd extends StatelessWidget {
  const _RibbonEnd({
    required this.price,
    required this.label,
    required this.hollow,
    required this.align,
  });

  final String price;
  final String label;
  final bool hollow;
  final CrossAxisAlignment align;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: align,
      children: [
        Text(
          price,
          style: AmiTypography.statSmall.copyWith(
            color: hollow ? AmiColors.textMed : AmiColors.textHigh,
          ),
        ),
        Text(
          '${hollow ? '⬡ ' : ''}$label',
          style: AmiTypography.labelMono
              .copyWith(fontSize: 8, color: AmiColors.textLow),
        ),
      ],
    );
  }
}

// ── consensus comb ────────────────────────────────────────────────────────

class _ConsensusComb extends StatelessWidget {
  const _ConsensusComb({required this.data, this.onVoiceTap});
  final RoomBoardData data;
  final void Function(RoomVoice voice)? onVoiceTap;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(AmiSpacing.s),
      decoration: BoxDecoration(
        color: AmiColors.slate800,
        borderRadius: BorderRadius.circular(AmiRadii.card),
        border: Border.all(color: AmiColors.slate700),
      ),
      child: data.stancesRecorded ? _bands(context, l) : _notRecorded(l),
    );
  }

  /// One honest sentence, not three empty bands and eleven hexes in a gutter.
  /// Empty bands would read as "nobody had a view"; this says what actually
  /// happened, which is that we did not record it. Never reconstructed
  /// afterwards from the prose — that would be a guess about a past decision
  /// wearing the authority of a record (T-BACKFILL).
  Widget _notRecorded(AppLocalizations l) => Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            l.roomCombNotRecorded,
            style: AmiTypography.labelMono
                .copyWith(fontSize: 10, color: AmiColors.textLow),
          ),
          const SizedBox(height: 4),
          Text(l.roomCombNotRecordedBody, style: AmiTypography.caption),
        ],
      );

  Widget _bands(BuildContext context, AppLocalizations l) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Expanded(
              child: Text(
                l.roomCombVoices(data.voices.length),
                style: AmiTypography.labelMono
                    .copyWith(fontSize: 10, color: AmiColors.textLow),
              ),
            ),
            Text(
              // Counted over stated positions only, so this does NOT always
              // equal the total — which is the point (T-SUM11).
              l.roomCombStated(data.statedCount),
              style: AmiTypography.labelMono
                  .copyWith(fontSize: 10, color: AmiColors.textLow),
            ),
          ],
        ),
        _Band(
          label: l.roomCombFor,
          voices: data.voicesFor,
          onVoiceTap: onVoiceTap,
        ),
        _Band(
          label: l.roomCombNeutral,
          voices: data.voicesNeutral,
          onVoiceTap: onVoiceTap,
        ),
        _Band(
          label: l.roomCombAgainst,
          voices: data.voicesAgainst,
          onVoiceTap: onVoiceTap,
        ),
        if (data.voicesNotStated.isNotEmpty)
          _Band(
            label: l.roomCombNotStated,
            voices: data.voicesNotStated,
            onVoiceTap: onVoiceTap,
            gutter: true,
          ),
      ],
    );
  }
}

class _Band extends StatelessWidget {
  const _Band({
    required this.label,
    required this.voices,
    this.onVoiceTap,
    this.gutter = false,
  });

  final String label;
  final List<RoomVoice> voices;
  final void Function(RoomVoice voice)? onVoiceTap;

  /// The gutter is a separate area below the bands, never a fourth lane — the
  /// agents in it did not take a position, and a lane would imply they did.
  final bool gutter;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(top: AmiSpacing.s),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Text(
                label,
                style: AmiTypography.labelMono.copyWith(
                  fontSize: 9,
                  color: gutter ? AmiColors.textLow : AmiColors.textMed,
                ),
              ),
              const SizedBox(width: 6),
              Text(
                '${voices.length}',
                style: AmiTypography.labelMono
                    .copyWith(fontSize: 9, color: AmiColors.textLow),
              ),
            ],
          ),
          const SizedBox(height: 3),
          if (voices.isEmpty)
            const SizedBox(height: 4)
          else
            // Wraps rather than clips, so a large text scale costs height and
            // never legibility.
            Wrap(
              spacing: 4,
              runSpacing: 4,
              children: [
                for (final v in voices)
                  CombHex(voice: v, onTap: onVoiceTap, hollow: gutter),
              ],
            ),
        ],
      ),
    );
  }
}

/// One agent in the comb: family hue, its own label inside, conviction as an
/// underline bar beneath.
///
/// Saiful, 2026-07-28: *"we will need to be able to identify the agents in the
/// voices… since the groups share the icon colours."* Correct, and it is the
/// one thing colour cannot fix — family colour is shared **by design**.
class CombHex extends StatelessWidget {
  const CombHex({
    super.key,
    required this.voice,
    this.onTap,
    this.hollow = false,
  });

  final RoomVoice voice;
  final void Function(RoomVoice voice)? onTap;
  final bool hollow;

  static const double _w = 26;

  @override
  Widget build(BuildContext context) {
    final agent = agentById(voice.agentId);
    final label = combLabelFor(voice.agentId);
    return Semantics(
      label: agent.displayName,
      button: onTap != null,
      child: GestureDetector(
        onTap: onTap == null ? null : () => onTap!(voice),
        // A 26pt mark is below the 44pt touch target floor, so the hit area is
        // expanded behind it rather than the mark being grown.
        behavior: HitTestBehavior.opaque,
        child: SizedBox(
          width: 44,
          height: 44,
          child: Center(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                SizedBox(
                  width: _w,
                  height: _w / flatTopRegularHexagonAspectRatio,
                  child: CustomPaint(
                    painter: _HexOutlinePainter(
                      accent: agent.color,
                      filled: !hollow,
                      // The gutter and the roster gap are told apart by a
                      // lighter border, not by a different ink — legibility is
                      // not the channel that carries "did not state a view".
                      borderAlpha: hollow ? 0.5 : 1.0,
                    ),
                    child: Center(
                      child: Text(
                        label,
                        // The family colour, on the canvas. `HexAvatar` sets
                        // `Colors.white` on the saturated fill instead, which
                        // measures 2.15:1 on amber and 2.54:1 on green — below
                        // even the 3:1 large-text floor (DEF142). The comb does
                        // not inherit that.
                        style: AmiTypography.labelMono.copyWith(
                          fontSize: label.length >= 4 ? 7.5 : 9,
                          letterSpacing: 0.2,
                          color: agent.color,
                        ),
                      ),
                    ),
                  ),
                ),
                const SizedBox(height: 3),
                _ConvictionBar(conviction: voice.conviction, color: agent.color),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

/// Conviction as a 22×3pt bar whose FILLED LENGTH encodes it.
///
/// A hexagonal ring was the first design and is the better pure meter, but it
/// cost 9pt of diameter — exactly the room a legible label needs. Given
/// "how strongly" versus "who", **who wins**: an unidentifiable hex is not
/// worth a finer magnitude read.
class _ConvictionBar extends StatelessWidget {
  const _ConvictionBar({required this.conviction, required this.color});
  final String? conviction;
  final Color color;

  @override
  Widget build(BuildContext context) {
    // Unknown conviction renders NO bar and NO track. An empty track would
    // read as "low", which is a claim we are not entitled to make.
    if (conviction == null) return const SizedBox(height: 3, width: 22);
    final fraction = switch (conviction) {
      'high' => 1.0,
      'medium' => 0.62,
      _ => 0.3,
    };
    return SizedBox(
      width: 22,
      height: 3,
      child: Align(
        alignment: AlignmentDirectional.centerStart,
        child: FractionallySizedBox(
          widthFactor: fraction,
          child: Container(color: color),
        ),
      ),
    );
  }
}

/// Four-character comb labels. Only two differ from the shipped
/// `abbreviation` — `RES-M → RES` and `TRADE → TRD` — a truncation, not a
/// second naming scheme.
String combLabelFor(String agentId) {
  switch (agentId) {
    case 'research_manager':
      return 'RES';
    case 'trader':
      return 'TRD';
    default:
      final abbr = agentById(agentId).abbreviation;
      return abbr.length <= 4 ? abbr : abbr.substring(0, 4);
  }
}

/// The comb's label ink for a family: the family colour itself, read against
/// the canvas.
///
/// This is a one-line function on purpose — it is the seam the DEF142 contrast
/// pin measures, so that a future change of treatment has to go through
/// something a test can hold onto. See [_HexOutlinePainter] for why a solid
/// family fill (and therefore any single global ink) cannot work.
Color combInkFor(Color familyColour) => familyColour;

// ── roster gap ────────────────────────────────────────────────────────────

/// CR098's withheld analysts, as their own hexes: family colour, dashed
/// outline, no fill. Deliberately NOT `slate700` — that token means
/// *locked / unearned*, which is a different thing from *was not in the room*.
class _RosterGap extends StatelessWidget {
  const _RosterGap({required this.data});
  final RoomBoardData data;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(AmiSpacing.s),
      decoration: BoxDecoration(
        color: AmiColors.slate800,
        borderRadius: BorderRadius.circular(AmiRadii.card),
        border: Border.all(color: AmiColors.slate700),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Text(
                  l.roomRosterGap,
                  style: AmiTypography.labelMono
                      .copyWith(fontSize: 10, color: AmiColors.textLow),
                ),
              ),
              Text(
                l.roomRosterGapCount(data.withheldAnalystIds.length),
                style: AmiTypography.labelMono
                    .copyWith(fontSize: 10, color: AmiColors.textLow),
              ),
            ],
          ),
          const SizedBox(height: AmiSpacing.xs),
          Wrap(
            spacing: 4,
            runSpacing: 4,
            children: [
              for (final id in data.withheldAnalystIds)
                CombHex(
                  voice: RoomVoice(agentId: id, content: '', withheld: true),
                  hollow: true,
                ),
            ],
          ),
          const SizedBox(height: AmiSpacing.xs),
          for (final id in data.withheldAnalystIds)
            Text(
              '• ${analystDisplayName(id)}',
              style: AmiTypography.caption,
            ),
        ],
      ),
    );
  }
}

/// `agentById` falls back to the Concierge for an unknown id, which in a
/// disclosure would name the WRONG analyst as absent — a confident lie. An id
/// we cannot resolve renders as itself.
String analystDisplayName(String id) {
  for (final a in kAllAgents) {
    if (a.id == id) return a.displayName;
  }
  return id;
}

// ── reason ────────────────────────────────────────────────────────────────

/// APPROVE clamps the reasoning behind a `WHY` expander; **PASS and NO_VERDICT
/// render it unclamped.** The rule: the board's prose budget is inversely
/// proportional to its numeric content. A PASS board has almost no numbers, and
/// "the room split and the PM declined" is the most informative thing on it.
///
/// CR127 — titled `PORTFOLIO MANAGER`, because this prose IS the PM's, and it
/// used to arrive with no attribution at all: unheaded body text after eleven
/// clearly-labelled analyst hexes, reading as the board's own narration rather
/// than as the twelfth agent's. Naming it is what makes the comb's old
/// `THE PM DECIDES — THIS IS NOT A VOTE` caption redundant — the PM is now a
/// visible card of its own after the eleven, so the comb no longer has to
/// disclaim being a tally. Follows `_ConsensusComb`/`_RosterGap`'s header
/// idiom, in the PM's family purple rather than their neutral `textLow`, since
/// this header identifies an agent where theirs name a section.
class _ReasonBlock extends StatefulWidget {
  const _ReasonBlock({required this.data});
  final RoomBoardData data;

  @override
  State<_ReasonBlock> createState() => _ReasonBlockState();
}

class _ReasonBlockState extends State<_ReasonBlock> {
  bool _expanded = false;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final clamp = widget.data.isApprove && !_expanded;
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(AmiSpacing.s),
      decoration: BoxDecoration(
        color: AmiColors.slate900,
        borderRadius: BorderRadius.circular(AmiRadii.card),
        border: Border.all(color: AmiColors.slate700),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Hidden when there is no reason text — a titled, empty PM card
          // would assert the PM said something on a run where it said
          // nothing (T-BACKFILL: absent is never inferred).
          if (widget.data.reason.trim().isNotEmpty) ...[
            Text(
              l.roomPmCardHeading,
              style: AmiTypography.labelMono.copyWith(
                fontSize: 10,
                letterSpacing: 0.4,
                // Family colour as identity. Purple-as-type on this canvas is
                // the pattern `_HexOutlinePainter` already documents —
                // hexPurple at 4.22 is itself the project's accent-as-type
                // floor, measured on slate900, which is this card's fill.
                color: agentById('portfolio_manager').color,
              ),
            ),
            const SizedBox(height: AmiSpacing.xs),
          ],
          Text(
            widget.data.reason,
            style: AmiTypography.body,
            maxLines: clamp ? 2 : null,
            overflow: clamp ? TextOverflow.ellipsis : null,
          ),
          if (widget.data.isApprove)
            Align(
              alignment: AlignmentDirectional.centerEnd,
              child: TextButton(
                style: TextButton.styleFrom(
                  foregroundColor: AmiColors.hexCyan,
                  visualDensity: VisualDensity.compact,
                ),
                onPressed: () => setState(() => _expanded = !_expanded),
                child: Text(
                  '${l.roomWhyExpand} ${_expanded ? '↑' : '→'}',
                  style: AmiTypography.labelMono
                      .copyWith(fontSize: 10, color: AmiColors.hexCyan),
                ),
              ),
            ),
        ],
      ),
    );
  }
}

/// Markdown styling shared by the transcript rows and the peek sheet, so the
/// same contribution reads identically wherever it is opened.
MarkdownStyleSheet agentMarkdownStyle(Color color) {
  final base = AmiTypography.stream.copyWith(color: color);
  return MarkdownStyleSheet(
    p: base,
    listBullet: base,
    strong: base.copyWith(fontWeight: FontWeight.w700),
    em: base.copyWith(fontStyle: FontStyle.italic),
    code: base.copyWith(
      fontFamily: 'JetBrainsMono',
      backgroundColor: AmiColors.slate800,
    ),
    blockSpacing: 6,
    h1: base.copyWith(fontWeight: FontWeight.w600, fontSize: 16),
    h2: base.copyWith(fontWeight: FontWeight.w600, fontSize: 15),
    h3: base.copyWith(fontWeight: FontWeight.w600, fontSize: 14),
  );
}
