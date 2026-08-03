/// CR136 M09 — Portfolio Health card (SCREEN_DESIGNS 07a/07b): §F1 tiles, six states, gate CTA. hexBlue accent — a measurement is not a warning.
///
/// The accent is `hexBlue` in every populated state and never amber. Amber
/// means a real exclusion or an unavailable system app-wide (and red means a
/// mandate violation or a loss), so an amber Portfolio Health card would read
/// as "you have done something wrong" when all it says is "here is what your
/// book's risk measures". Amber appears in exactly two places here: the
/// mock-data refusal (the system genuinely is unavailable) and the PARTIAL
/// chip (a genuine exclusion).
///
/// Six states, first match wins, and the four non-populated ones deliberately
/// do NOT look like a result: no accent stripe, no tile grid, a dashed border.
/// SCREEN_DESIGNS 07b is explicit that an error state shaped like a result is
/// how a reader ends up quoting a number that was never measured.
///
/// Nothing here computes a metric. The client scales a value by the unit the
/// backend pinned (`kMetricValueUnit`), formats it to the dp M06 uses for the
/// same figure, and prints it.
library;

import 'dart:math' as math;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/portfolio_health.dart';
import 'package:ami_trade/screens/sim/portfolio_health_finding_screen.dart';
import 'package:ami_trade/state/mandate_providers.dart';
import 'package:ami_trade/state/portfolio_health_providers.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:ami_trade/widgets/hex/accent_card.dart';
import 'package:ami_trade/widgets/hex/hex_button.dart';
import 'package:ami_trade/widgets/hex/hex_pulse_loader.dart';
import 'package:ami_trade/widgets/empty_state.dart';
import 'package:ami_trade/widgets/paywall/upgrade_paywall.dart';
import 'package:ami_trade/widgets/portfolio_health/health_chrome.dart';
import 'package:ami_trade/widgets/portfolio_health/risk_money_bars.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

/// Which call to action the card shows. The tiles above it are NEVER gated
/// (Rev 4) — only the written Finding is.
enum HealthCtaState { generate, trial, dailyCap, upgrade }

/// Pure derivation from M07's eight-key gate dict.
///
/// The server stays the authority: a stale card racing the gate simply gets
/// 402/429 from the POST and the Finding screen shows the matching panel. The
/// client never invents access, which is why this reads the flags rather than
/// inferring anything from the plan name.
HealthCtaState deriveHealthCta(HealthGateStatus g) {
  final hasAccess = g.mode == 'open' ||
      g.planHasAccess ||
      (g.mode == 'trial' && g.trialActive);
  if (!hasAccess) return HealthCtaState.upgrade;
  if (g.dailyUsed >= g.dailyCap) return HealthCtaState.dailyCap;
  if (g.mode == 'trial' && g.trialActive && !g.planHasAccess) {
    return HealthCtaState.trial;
  }
  return HealthCtaState.generate;
}

/// Directional isolates around a numeric run, so RTL reordering cannot
/// scramble it (CR106's T-BIDI trap). `_isolateNumeric` in
/// `portfolio_screen.dart` is file-private, hence this two-line copy.
String _iso(String s) => '\u2066$s\u2069';

String _fixed(double v, int dp) => _iso(v.toStringAsFixed(dp));

String _int(int v) => _iso('$v');

class PortfolioHealthCard extends ConsumerWidget {
  const PortfolioHealthCard({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l = AppLocalizations.of(context);
    final async = ref.watch(portfolioHealthProvider);

    return healthFadeIn(
      context,
      Padding(
        padding: const EdgeInsets.only(bottom: AmiSpacing.s),
        child: async.when(
          loading: () => const _HealthSkeleton(),
          error: (_, __) => _HealthNotice(
            icon: Icons.refresh,
            iconColor: AmiColors.textLow,
            body: l.portfolioHealthErrorBody,
            onTap: () => ref.invalidate(portfolioHealthProvider),
          ),
          data: (health) => _body(context, ref, l, health),
        ),
      ),
    );
  }

  Widget _body(
    BuildContext context,
    WidgetRef ref,
    AppLocalizations l,
    PortfolioHealth health,
  ) {
    if (health.status == 'refused_mock_data') {
      return _HealthNotice(
        icon: Icons.cloud_off_outlined,
        iconColor: AmiColors.hexAmber,
        title: l.portfolioHealthMockRefusalTitle,
        titleColor: AmiColors.hexAmber,
        body: l.portfolioHealthMockRefusalBody,
      );
    }
    if (health.status == 'no_holdings') {
      // No CTA: the Positions tab's own new-trader hint owns the trade call to
      // action, and two competing CTAs on one screen is the DEF151 class.
      return HealthDashedBox(
        child: AmiEmptyState(
          icon: Icons.hexagon_outlined,
          title: l.portfolioHealthEmptyTitle,
        ),
      );
    }
    if (health.status != 'ok') {
      // Anything outside the three pinned statuses — a status this build has
      // never heard of, or a body that carried none at all. Falling through to
      // the populated card would render a wire divergence in the exact visual
      // grammar of a real measurement, hexBlue stripe and all, and the reader
      // would have no way to tell "the engine measured nothing" from "this app
      // could not read what it got" (CR040).
      return _HealthNotice(
        icon: Icons.help_outline,
        iconColor: AmiColors.textLow,
        body: l.portfolioHealthUnknownStatusBody,
        onTap: () => ref.invalidate(portfolioHealthProvider),
      );
    }
    if (_allInsufficient(health)) {
      return _InsufficientState(health: health);
    }
    return _PopulatedCard(health: health);
  }

  static bool _allInsufficient(PortfolioHealth health) {
    if (health.status != 'ok') return false;
    const core = [
      'portfolio_volatility',
      'beta',
      'effective_bets',
      'risk_contribution',
    ];
    return core.every((m) => health.block(m)?.sufficient != true);
  }
}

// ── Non-populated states ────────────────────────────────────────────────────

class _HealthSkeleton extends StatelessWidget {
  const _HealthSkeleton();

  @override
  Widget build(BuildContext context) => Container(
        height: 132,
        decoration: BoxDecoration(
          color: AmiColors.slate800.withValues(alpha: 0.5),
          borderRadius: BorderRadius.circular(AmiRadii.card),
          border: Border.all(color: AmiColors.slate700),
        ),
        child: const Center(child: HexPulseLoader(size: 28)),
      );
}

/// The dashed notice used by the transport-error and refusal states. Slate for
/// a failed fetch (the request never reached a verdict), amber for the engine's
/// own refusal — the two must not look alike.
class _HealthNotice extends StatelessWidget {
  const _HealthNotice({
    required this.icon,
    required this.iconColor,
    required this.body,
    this.title,
    this.titleColor,
    this.onTap,
  });

  final IconData icon;
  final Color iconColor;
  final String body;
  final String? title;
  final Color? titleColor;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final content = HealthDashedBox(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(icon, color: iconColor, size: 20),
              const SizedBox(width: AmiSpacing.s),
              if (title != null)
                Expanded(
                  child: Text(
                    title!,
                    style: AmiTypography.labelMono.copyWith(color: titleColor),
                  ),
                ),
            ],
          ),
          const SizedBox(height: AmiSpacing.s),
          Text(body, style: AmiTypography.body),
        ],
      ),
    );
    return onTap == null
        ? content
        : InkWell(
            onTap: onTap,
            borderRadius: BorderRadius.circular(AmiRadii.card),
            child: content,
          );
  }
}

/// Status is `ok` but nothing measurable came back. Neutral slate, never amber
/// — an absence of measurement is not a warning about the user's book — and no
/// metric value at all, so the state cannot be misread as a result.
class _InsufficientState extends StatelessWidget {
  const _InsufficientState({required this.health});

  final PortfolioHealth health;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final cause = health.block('portfolio_volatility')?.insufficientCause;
    final coveredPct = health.investedValue > 0
        ? 100.0 * health.coveredInvestedValue / health.investedValue
        : 0.0;

    String body;
    switch (cause) {
      case kCauseShortWindow:
        body = l.portfolioHealthInsufficientBody(
          _int(health.block('portfolio_volatility')?.nObservations ?? 0),
        );
      case kCauseDroppedWeight:
        body = l.portfolioHealthInsufficientDroppedBody(
          _fixed(coveredPct, 0),
        );
      default:
        // zero_variance, feed_unavailable, or a cause added later. The two
        // above are the only ones SCREEN_DESIGNS pinned copy for; naming the
        // wrong cause would be worse than naming none, and leaving the state
        // with no explanation at all is the hole CR040 exists to close.
        // Recorded deviation: this key is not in M09 §3.7's table.
        body = l.portfolioHealthInsufficientGenericBody;
    }

    return HealthDashedBox(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Text(
                // Deliberately not `dataMd`: that style is the metric-value
                // register, and a test asserts this state renders no value in
                // it. A glyph wearing the value style would make that guard
                // vacuous.
                '⬡',
                style: AmiTypography.h4.copyWith(color: AmiColors.textLow),
              ),
              const SizedBox(width: AmiSpacing.s),
              Expanded(
                child: Text(
                  l.portfolioHealthInsufficientTitle,
                  style: AmiTypography.labelMono
                      .copyWith(color: AmiColors.textMed),
                ),
              ),
            ],
          ),
          const SizedBox(height: AmiSpacing.s),
          Text(body, style: AmiTypography.body),
        ],
      ),
    );
  }
}

// ── The populated card ──────────────────────────────────────────────────────

class _PopulatedCard extends ConsumerWidget {
  const _PopulatedCard({required this.health});

  final PortfolioHealth health;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l = AppLocalizations.of(context);
    final tiles = _tiles(l);
    final notes = _notes(l);
    final riskBlock = health.block('risk_contribution');
    final rows = riskBlock?.sufficient == true
        ? topRiskMoneyRows(riskBlock!.extensions['per_holding'])
        : const <RiskMoneyRow>[];
    // Defence in depth against a 0/0 axis: in practice an empty invested
    // sleeve arrives as `no_holdings`, which never reaches this widget.
    final showBars = rows.isNotEmpty && health.coveredInvestedValue > 0;
    // Keyed on the DISPLAYED figure, not the raw one. A risk share of −0.004
    // is genuinely negative but prints as "0%", and a caveat explaining a
    // negative number with no negative number on screen to point at explains
    // nothing. The bar's geometry still uses the true value.
    final anyNegative = rows.any((r) => (r.risk * 100).round() < 0);

    return AccentCard(
      accent: AmiColors.hexBlue,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(l.portfolioHealthTitle, style: AmiTypography.h4),
          const SizedBox(height: AmiSpacing.xs),
          Text(
            l.portfolioHealthWindowSubtitle,
            style: AmiTypography.labelMono
                .copyWith(fontSize: 9, color: AmiColors.textLow),
          ),
          if (health.partial) ...[
            const SizedBox(height: AmiSpacing.s),
            _PartialNote(health: health),
          ],
          if (tiles.isNotEmpty) ...[
            const SizedBox(height: AmiSpacing.m),
            _TileGrid(tiles: tiles),
          ],
          const SizedBox(height: AmiSpacing.s),
          _ConcentrationTile(health: health),
          for (final note in notes) ...[
            const SizedBox(height: AmiSpacing.s),
            Text(note, style: AmiTypography.caption),
          ],
          if (showBars) ...[
            const SizedBox(height: AmiSpacing.m),
            _BarsSection(rows: rows, anyNegative: anyNegative),
          ],
          const SizedBox(height: AmiSpacing.s),
          Text(
            l.portfolioHealthCashLine(_fixed(health.cashFraction * 100, 0)),
            style: AmiTypography.caption,
          ),
          const SizedBox(height: AmiSpacing.m),
          _GateCta(gate: health.gate),
        ],
      ),
    );
  }

  List<_TileSpec> _tiles(AppLocalizations l) {
    final out = <_TileSpec>[];

    final vol = health.block('portfolio_volatility');
    if (vol?.sufficient == true) {
      out.add(_TileSpec(
        label: l.portfolioHealthTileVolatility,
        value: _fixed(vol!.valuePercent!, 1),
        unit: l.portfolioHealthTileVolatilityUnit,
        note: health.benchmarkVolAnn == null
            ? null
            : l.portfolioHealthTileVolatilityBenchmark(
                _fixed(health.benchmarkVolAnn! * 100, 1),
              ),
      ));
    }

    final beta = health.block('beta');
    if (beta?.sufficient == true) {
      final r2 = (beta!.extensions['r_squared'] as num?)?.toDouble();
      out.add(_TileSpec(
        label: l.portfolioHealthTileBeta,
        // A ratio: no percent sign, here or in its unit line.
        value: _fixed(beta.value!, 2),
        unit: l.portfolioHealthTileBetaUnit,
        note: beta.lowExplanatoryPower == true && r2 != null
            ? l.portfolioHealthBetaLowR2(_fixed(r2 * 100, 0))
            : null,
      ));
    }

    final bets = health.block('effective_bets');
    if (bets?.sufficient == true) {
      out.add(_TileSpec(
        label: l.portfolioHealthTileBets,
        value: _fixed(bets!.value!, 1),
        unit: l.portfolioHealthTileBetsUnit(_int(health.holdingsCount)),
      ));
    }

    // Tier 2. Keyed on block PRESENCE: until M07/M03 wire the realised blocks
    // through, its absence is a silent absent tile — never a dash, which would
    // read as a measured nothing (Rev 4 §F1: "Tier 2, when sufficient").
    final mdd = health.block('realised_max_drawdown');
    if (mdd != null && mdd.sufficient) {
      out.add(_TileSpec(
        label: l.portfolioHealthTileMdd,
        // Already a percentage on the wire (M03 §3.5) — never scaled again.
        value: '${_fixed(mdd.valuePercent!, 1)}%',
        unit: l.portfolioHealthTileMddUnit(_int(mdd.windowDays)),
      ));
    }

    return out;
  }

  /// Notes that stand in for a tile that is not there. Each names AMI's own
  /// limit rather than the user's book (Rev 4 F20).
  ///
  /// Every branch is keyed on the block being INSUFFICIENT, never on a
  /// particular cause; a cause only ever chooses which note, never whether
  /// there is one. That inversion is the fix for M04's audit r1 MAJOR M1: the
  /// beta branch used to fire only on `benchmark_misaligned`, so a SPY feed
  /// outage — the ordinary Yahoo rate-limit case — deleted the beta tile and
  /// put nothing in its place, leaving a card that still read as a complete
  /// measurement. Closed by construction here, so cause number seven cannot
  /// reopen it.
  List<String> _notes(AppLocalizations l) {
    final out = <String>[];

    final vol = health.block('portfolio_volatility');
    if (vol != null && !vol.sufficient) {
      out.add(l.portfolioHealthVolUnavailableNote);
    }

    final bets = health.block('effective_bets');
    if (bets != null && !bets.sufficient) {
      out.add(bets.insufficientCause == kCauseTOverN
          ? l.portfolioHealthTnNote(
              _int(bets.nObservations),
              _int(health.riskyHoldingsCount),
            )
          : l.portfolioHealthBetsUnavailableNote);
    }

    final beta = health.block('beta');
    if (beta != null && !beta.sufficient) {
      out.add(beta.insufficientCause == kCauseBenchmarkMisaligned
          ? l.portfolioHealthBenchmarkNote
          : l.portfolioHealthBetaUnavailableNote);
    }

    // `risk_contribution` gates the risk-vs-money bars — the largest element on
    // the card — and had no branch here at all until audit r2 MINOR m2: on any
    // share-basis cause other than `t_over_n` the bars vanished and the only
    // note on screen spoke to effective bets, so nothing told the reader that
    // risk attribution had not been measured.
    final risk = health.block('risk_contribution');
    if (risk != null && !risk.sufficient) {
      out.add(risk.insufficientCause == kCauseTOverN
          ? l.portfolioHealthTnNote(
              _int(risk.nObservations),
              _int(health.riskyHoldingsCount),
            )
          : l.portfolioHealthRiskUnavailableNote);
    }

    final mdd = health.block('realised_max_drawdown');
    if (mdd != null && !mdd.sufficient) {
      out.add(l.portfolioHealthMddNote(_int(mdd.nObservations)));
    }

    // `effective_bets` and `risk_contribution` are fed from one variable in the
    // engine (`portfolio_health.py:377`), so they go insufficient together with
    // the same cause — and on `t_over_n` they share one note, whose copy already
    // covers both the bets tile and the bars. Deduping here is what lets every
    // branch above stay keyed on insufficiency alone: the alternative is a
    // branch that asks what some OTHER block's cause was, which is the exact
    // coupling this fix exists to remove. Set preserves insertion order.
    return out.toSet().toList();
  }
}

class _PartialNote extends StatelessWidget {
  const _PartialNote({required this.health});

  final PortfolioHealth health;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final tickers = health.droppedHoldings
        .map((d) => d['ticker'])
        .whereType<String>()
        .toList(growable: false);
    final covered = health.investedValue > 0
        ? 100.0 * health.coveredInvestedValue / health.investedValue
        : 0.0;

    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Container(
          padding: const EdgeInsets.symmetric(
            horizontal: AmiSpacing.xs,
            vertical: 2,
          ),
          decoration: BoxDecoration(
            border: Border.all(color: AmiColors.hexAmber),
            borderRadius: BorderRadius.circular(AmiRadii.sm),
          ),
          child: Text(
            l.portfolioHealthPartialChip,
            style: AmiTypography.labelMono
                .copyWith(fontSize: 9, color: AmiColors.hexAmber),
          ),
        ),
        const SizedBox(width: AmiSpacing.s),
        Expanded(
          child: Text(
            l.portfolioHealthPartialNote(
              _iso(tickers.join(', ')),
              _fixed(covered, 0),
            ),
            style: AmiTypography.caption,
          ),
        ),
      ],
    );
  }
}

class _TileSpec {
  const _TileSpec({
    required this.label,
    required this.value,
    required this.unit,
    this.note,
    this.chip,
  });

  final String label;
  final String value;
  final String unit;
  final String? note;
  final String? chip;
}

class _TileGrid extends StatelessWidget {
  const _TileGrid({required this.tiles});

  final List<_TileSpec> tiles;

  @override
  Widget build(BuildContext context) {
    final rows = <Widget>[];
    for (var i = 0; i < tiles.length; i += 2) {
      final left = tiles[i];
      final right = i + 1 < tiles.length ? tiles[i + 1] : null;
      if (rows.isNotEmpty) rows.add(const SizedBox(height: AmiSpacing.s));
      // `IntrinsicHeight` so a pair of tiles matches height even when one
      // carries a note the other does not — a stretched Row inside a scroll
      // view is otherwise handed an unbounded height and fails to lay out.
      rows.add(IntrinsicHeight(
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Expanded(child: _Tile(spec: left)),
            const SizedBox(width: AmiSpacing.s),
            Expanded(
              child: right == null
                  ? const SizedBox.shrink()
                  : _Tile(spec: right),
            ),
          ],
        ),
      ));
    }
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: rows);
  }
}

class _Tile extends StatelessWidget {
  const _Tile({required this.spec});

  final _TileSpec spec;

  @override
  Widget build(BuildContext context) => Container(
        padding: const EdgeInsets.all(AmiSpacing.s),
        decoration: BoxDecoration(
          color: AmiColors.slate900,
          borderRadius: BorderRadius.circular(AmiRadii.card),
          border: Border.all(color: AmiColors.slate700),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              spec.label,
              style: AmiTypography.labelMono
                  .copyWith(fontSize: 9, color: AmiColors.textMed),
            ),
            const SizedBox(height: AmiSpacing.xs),
            Text(spec.value, style: AmiTypography.dataMd),
            // Never a bare percentage: the unit line is what makes the number
            // mean something, so it is not optional chrome.
            Text(spec.unit, style: AmiTypography.caption),
            if (spec.chip != null) ...[
              const SizedBox(height: AmiSpacing.xs),
              Text(
                spec.chip!,
                style: AmiTypography.labelMono
                    .copyWith(fontSize: 8, color: AmiColors.textLow),
              ),
            ],
            if (spec.note != null) ...[
              const SizedBox(height: AmiSpacing.xs),
              Text(spec.note!, style: AmiTypography.caption),
            ],
          ],
        ),
      );
}

/// Full width, and never insufficient: counting weights needs no price history,
/// so this tile is present whenever the book is.
class _ConcentrationTile extends StatelessWidget {
  const _ConcentrationTile({required this.health});

  final PortfolioHealth health;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final block = health.block('weight_concentration');
    if (block == null) return const SizedBox.shrink();
    final effectiveN = (block.extensions['effective_n'] as num?)?.toDouble();
    if (effectiveN == null) return const SizedBox.shrink();
    final count = (block.extensions['holdings_count'] as num?)?.toInt() ??
        health.holdingsCount;

    return _Tile(
      spec: _TileSpec(
        label: l.portfolioHealthTileConcentration,
        value: _fixed(effectiveN, 1),
        unit: l.portfolioHealthTileConcentrationUnit(_int(count)),
        chip: block.containsEtfs ? l.portfolioHealthEtfChip : null,
      ),
    );
  }
}

/// The signature bars, collapsed by default.
///
/// Fully expanded the card measured 803pt at 390×844 — a whole screen added to
/// the Positions tab, which CR120 §9 budgets at ≤3 screens for the heavy
/// profile. Collapsing the breakdown keeps the §F1 tiles, the cash line and the
/// CTA on first sight and puts the bars one tap away; the measurement, not a
/// preference, is why (Saiful's call, 2026-08-03).
///
/// The mandatory caption lives inside the same expanded block as the bars, so
/// there is no state in which a bar is drawn without the sentence that says
/// what basis it is on.
class _BarsSection extends StatefulWidget {
  const _BarsSection({required this.rows, required this.anyNegative});

  final List<RiskMoneyRow> rows;
  final bool anyNegative;

  @override
  State<_BarsSection> createState() => _BarsSectionState();
}

class _BarsSectionState extends State<_BarsSection> {
  bool _open = false;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        InkWell(
          onTap: () => setState(() => _open = !_open),
          child: Padding(
            padding: const EdgeInsets.symmetric(vertical: AmiSpacing.xs),
            child: Row(
              children: [
                Text(
                  l.portfolioHealthBarsHeading,
                  style: AmiTypography.labelMono,
                ),
                const SizedBox(width: AmiSpacing.xs),
                Icon(
                  _open ? Icons.expand_less : Icons.expand_more,
                  size: 16,
                  color: AmiColors.textLow,
                ),
              ],
            ),
          ),
        ),
        if (_open) ...[
          const SizedBox(height: AmiSpacing.s),
          RiskMoneyBars(
            rows: widget.rows,
            axisMaxLabelStyle: AmiTypography.caption,
            legend: const _BarLegend(),
          ),
          const SizedBox(height: AmiSpacing.xs),
          Text(l.portfolioHealthBarsCaption, style: AmiTypography.caption),
          if (widget.anyNegative) ...[
            const SizedBox(height: AmiSpacing.xs),
            Text(
              l.portfolioHealthBarsNegativeNote,
              style: AmiTypography.caption,
            ),
          ],
        ],
      ],
    );
  }
}

class _BarLegend extends StatelessWidget {
  const _BarLegend();

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    return Row(
      children: [
        _swatch(solid: true),
        const SizedBox(width: AmiSpacing.xs),
        Text(l.portfolioHealthLegendRisk, style: AmiTypography.caption),
        const SizedBox(width: AmiSpacing.m),
        _swatch(solid: false),
        const SizedBox(width: AmiSpacing.xs),
        Text(l.portfolioHealthLegendMoney, style: AmiTypography.caption),
      ],
    );
  }

  Widget _swatch({required bool solid}) => Container(
        width: 14,
        height: 6,
        decoration: BoxDecoration(
          color: solid ? AmiColors.hexBlue : Colors.transparent,
          border: solid ? null : Border.all(color: AmiColors.hexBlue, width: 1),
          borderRadius: BorderRadius.circular(3),
        ),
      );
}

// ── Gate CTA ────────────────────────────────────────────────────────────────

class _GateCta extends ConsumerWidget {
  const _GateCta({required this.gate});

  final HealthGateStatus gate;

  String _resetDateStr(WidgetRef ref) {
    final r = ref.read(mandateNotifierProvider).mandate?.creditsResetAt;
    if (r == null) return 'the 1st';
    return '${r.year}-${r.month.toString().padLeft(2, '0')}-'
        '${r.day.toString().padLeft(2, '0')}';
  }

  Future<void> _openFinding(BuildContext context, WidgetRef ref) async {
    await Navigator.of(context).push(MaterialPageRoute<void>(
      builder: (_) => const PortfolioHealthFindingScreen(),
    ));
    // The Finding just spent budget (or replayed today's, which did not) — the
    // card's own gate numbers are stale either way.
    ref.invalidate(portfolioHealthProvider);
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l = AppLocalizations.of(context);
    switch (deriveHealthCta(gate)) {
      case HealthCtaState.generate:
        return SizedBox(
          width: double.infinity,
          child: HexButton(
            label: l.portfolioHealthCtaFinding,
            color: AmiColors.hexBlue,
            onPressed: () => _openFinding(context, ref),
          ),
        );

      case HealthCtaState.trial:
        return Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            SizedBox(
              width: double.infinity,
              child: HexButton(
                label: l.portfolioHealthCtaFinding,
                color: AmiColors.hexBlue,
                onPressed: () => _openFinding(context, ref),
              ),
            ),
            const SizedBox(height: AmiSpacing.xs),
            Text(
              // Both numbers: the trial ends on whichever runs out first, so
              // either one alone can mislead.
              l.portfolioHealthTrialChip(
                _int(math.max(0, gate.trialFindingsBudget - gate.trialFindingsUsed)),
                _int(gate.trialFindingsBudget),
                _int(gate.trialDaysLeft),
              ),
              style: AmiTypography.caption,
            ),
          ],
        );

      case HealthCtaState.dailyCap:
        return Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            SizedBox(
              width: double.infinity,
              child: HexButton(
                label: l.portfolioHealthCtaFinding,
                color: AmiColors.hexBlue,
                onPressed: null,
              ),
            ),
            const SizedBox(height: AmiSpacing.xs),
            Text(
              l.portfolioHealthDailyCapNote(
                _int(gate.dailyUsed),
                _int(gate.dailyCap),
              ),
              style: AmiTypography.caption,
            ),
          ],
        );

      case HealthCtaState.upgrade:
        return Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(l.portfolioHealthUpgradeBody, style: AmiTypography.caption),
            const SizedBox(height: AmiSpacing.xs),
            SizedBox(
              width: double.infinity,
              child: HexButton(
                label: l.portfolioHealthUpgradeCta,
                color: AmiColors.hexBlue,
                variant: HexButtonVariant.outlined,
                onPressed: () => showUpgradeSheet(
                  context,
                  resetDateLabel: _resetDateStr(ref),
                  onPurchased: () => ref.invalidate(portfolioHealthProvider),
                ),
              ),
            ),
          ],
        );
    }
  }
}

