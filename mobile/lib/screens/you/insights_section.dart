/// CR178 — INSIGHTS, the rendering half.
///
/// AMI's product claim is that it makes you a better decision-maker, and until
/// this screen nothing in the app told you what your decisions look like. The
/// Journal is a log; this is what makes the log educational.
///
/// Every figure here aggregates journal rows **already written** — no new
/// table, no migration, no new endpoint. What it will not do is render a figure
/// it cannot derive: three panels the design wanted are absent rather than
/// zeroed, and each card withholds itself below a threshold rather than drawing
/// a `1/1` bar that reads 100%. See [buildInsights] for both rules and why.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/agent.dart';
import 'package:ami_trade/screens/you/insights_data.dart';
import 'package:ami_trade/screens/you/insights_providers.dart';
import 'package:ami_trade/services/api/friendly_error.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

class InsightsSection extends ConsumerWidget {
  const InsightsSection({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final async = ref.watch(insightsProvider);
    return async.when(
      loading: () => const Center(child: CircularProgressIndicator()),
      // DEF148 — the caught object never reaches the user directly; what it
      // would render is a stack trace and an MDN link.
      error: (e, _) => Padding(
        padding: const EdgeInsets.all(AmiSpacing.l),
        child: Center(
          child: Text(friendlyError(e, action: 'read your decisions'),
              style: AmiTypography.body),
        ),
      ),
      data: (data) => _Body(data: data),
    );
  }
}

class _Body extends StatelessWidget {
  const _Body({required this.data});
  final InsightsData data;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    if (data.isEmpty) return _Empty(l: l);

    // The window label, once, at the top and on every card. Once at the top is
    // not enough: cards scroll (this segment is the deepest surface in the app)
    // and a reader who lands mid-list would take an aggregate for all-time.
    final window = data.windowIsCapped
        ? l.insightsWindowCapped(kInsightsWindow)
        : l.insightsWindowAll(data.entryCount);

    return ListView(
      padding: const EdgeInsets.all(AmiSpacing.m),
      children: [
        if (data.trades != null) ...[
          _TradesCardView(card: data.trades!, window: window),
          const SizedBox(height: AmiSpacing.m),
        ],
        if (data.verdicts != null) ...[
          _VerdictCardView(card: data.verdicts!, window: window),
          const SizedBox(height: AmiSpacing.m),
        ],
        if (data.analysts.isNotEmpty) ...[
          _AnalystsCardView(counts: data.analysts, window: window),
          const SizedBox(height: AmiSpacing.m),
        ],
        if (data.mandate != null) ...[
          _MandateCardView(card: data.mandate!, window: window),
          const SizedBox(height: AmiSpacing.m),
        ],
        if (data.challenges != null) ...[
          _ChallengeCardView(card: data.challenges!, window: window),
          const SizedBox(height: AmiSpacing.m),
        ],
        const SizedBox(height: AmiSpacing.xxl),
      ],
    );
  }
}

class _Empty extends StatelessWidget {
  const _Empty({required this.l});
  final AppLocalizations l;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(AmiSpacing.l),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(l.insightsEmptyHeading,
                style: AmiTypography.labelMono
                    .copyWith(color: AmiColors.textMed)),
            const SizedBox(height: AmiSpacing.s),
            Text(l.insightsEmptyBody,
                textAlign: TextAlign.center,
                style: AmiTypography.caption
                    .copyWith(color: AmiColors.textLow)),
          ],
        ),
      ),
    );
  }
}

// ── shared chrome ────────────────────────────────────────────────────────

class _Card extends StatelessWidget {
  const _Card({
    required this.title,
    required this.window,
    required this.children,
    this.note,
    this.caveat,
  });

  final String title;
  final String window;
  final List<Widget> children;

  /// What the card means. Rendered in body type — it is content.
  final String? note;

  /// What the card is NOT, or what it left out. Rendered dimmer and last,
  /// but never omitted: a caveat that only appears when someone remembers to
  /// look for it is not a caveat.
  final String? caveat;

  @override
  Widget build(BuildContext context) {
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
          Text(title,
              style: AmiTypography.labelMono.copyWith(color: AmiColors.hexBlue)),
          const SizedBox(height: 2),
          Text(window,
              style: AmiTypography.caption.copyWith(color: AmiColors.textLow)),
          const SizedBox(height: AmiSpacing.m),
          ...children,
          if (note != null) ...[
            const SizedBox(height: AmiSpacing.m),
            Text(note!, style: AmiTypography.caption),
          ],
          if (caveat != null) ...[
            const SizedBox(height: AmiSpacing.s),
            Text(caveat!,
                style:
                    AmiTypography.caption.copyWith(color: AmiColors.textLow)),
          ],
        ],
      ),
    );
  }
}

/// One labelled proportional bar.
///
/// [total] is passed in rather than derived per row so every bar in a card
/// shares a denominator — bars normalised to their own maximum look like
/// percentages and are not.
class _Bar extends StatelessWidget {
  const _Bar({
    required this.label,
    required this.value,
    required this.total,
    required this.color,
  });

  final String label;
  final int value;
  final int total;
  final Color color;

  @override
  Widget build(BuildContext context) {
    final fraction = total == 0 ? 0.0 : value / total;
    return Padding(
      padding: const EdgeInsets.only(bottom: AmiSpacing.s),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(child: Text(label, style: AmiTypography.body)),
              Text('$value',
                  style: AmiTypography.labelMono.copyWith(color: color)),
            ],
          ),
          const SizedBox(height: 4),
          // The bar axis stays LTR under RTL — a proportion read right-to-left
          // is a different proportion.
          Directionality(
            textDirection: TextDirection.ltr,
            child: ClipRRect(
              borderRadius: BorderRadius.circular(2),
              child: LinearProgressIndicator(
                value: fraction,
                minHeight: 6,
                backgroundColor: AmiColors.slate700,
                valueColor: AlwaysStoppedAnimation<Color>(color),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

// ── card 1 — how your trades ended ───────────────────────────────────────

class _TradesCardView extends StatelessWidget {
  const _TradesCardView({required this.card, required this.window});
  final TradesCard card;
  final String window;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    String label(TradeEnding e) => switch (e) {
          TradeEnding.won => l.insightsTradesWon,
          TradeEnding.lost => l.insightsTradesLost,
          TradeEnding.manual => l.insightsTradesManual,
        };
    Color colour(TradeEnding e) => switch (e) {
          TradeEnding.won => AmiColors.hexGreen,
          TradeEnding.lost => AmiColors.hexRed,
          // Amber, not red: overriding your own plan is not a loss, it is a
          // habit worth noticing.
          TradeEnding.manual => AmiColors.hexAmber,
        };

    return _Card(
      title: l.insightsTradesTitle,
      window: window,
      note: l.insightsTradesNote,
      caveat: card.unclassified > 0
          ? l.insightsTradesUnclassified(card.unclassified)
          : null,
      children: [
        // Fixed order, not map order: the reading is won → lost → manual, and
        // a card whose rows move between builds is a card nobody trusts.
        for (final e in TradeEnding.values)
          if ((card.counts[e] ?? 0) > 0)
            _Bar(
              label: label(e),
              value: card.counts[e]!,
              total: card.total,
              color: colour(e),
            ),
      ],
    );
  }
}

// ── card 2 — what your PM decided ────────────────────────────────────────

class _VerdictCardView extends StatelessWidget {
  const _VerdictCardView({required this.card, required this.window});
  final VerdictCard card;
  final String window;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    String label(VerdictOutcome v) => switch (v) {
          VerdictOutcome.approve => l.insightsVerdictApprove,
          VerdictOutcome.modify => l.insightsVerdictModify,
          VerdictOutcome.reject => l.insightsVerdictReject,
          VerdictOutcome.pass => l.insightsVerdictPass,
          VerdictOutcome.noVerdict => l.insightsVerdictNoVerdict,
        };
    Color colour(VerdictOutcome v) => switch (v) {
          VerdictOutcome.approve => AmiColors.hexGreen,
          VerdictOutcome.modify => AmiColors.hexCyan,
          VerdictOutcome.reject => AmiColors.hexRed,
          VerdictOutcome.pass => AmiColors.textMed,
          // Grey, deliberately not red: NO_VERDICT is not a rejection, and
          // colour is the fastest way to say otherwise.
          VerdictOutcome.noVerdict => AmiColors.textLow,
        };

    final showsNoVerdict =
        (card.counts[VerdictOutcome.noVerdict] ?? 0) > 0;

    return _Card(
      title: l.insightsVerdictTitle,
      window: window,
      note: showsNoVerdict ? l.insightsVerdictNoVerdictNote : null,
      caveat: card.noVerdictRecorded > 0
          ? l.insightsVerdictUnrecorded(card.noVerdictRecorded)
          : null,
      children: [
        for (final v in VerdictOutcome.values)
          if ((card.counts[v] ?? 0) > 0)
            _Bar(
              label: label(v),
              value: card.counts[v]!,
              total: card.ruled,
              color: colour(v),
            ),
      ],
    );
  }
}

// ── card 3 — analysts you sought out ─────────────────────────────────────

class _AnalystsCardView extends StatelessWidget {
  const _AnalystsCardView({required this.counts, required this.window});
  final List<AnalystCount> counts;
  final String window;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final total = counts.fold<int>(0, (a, c) => a + c.count);
    return _Card(
      title: l.insightsAnalystsTitle,
      window: window,
      caveat: l.insightsAnalystsNote,
      children: [
        for (final c in counts)
          _Bar(
            label: _agentName(c.agentId),
            value: c.count,
            total: total,
            // `Agent.color` is a FAMILY colour, not a per-member one — four
            // analysts sharing one cyan is correct, and is the point.
            color: _agentColour(c.agentId),
          ),
      ],
    );
  }
}

Agent? _agent(String id) {
  for (final a in kAllAgents) {
    if (a.id == id) return a;
  }
  return null;
}

/// An agent this build does not know renders under its wire id rather than
/// under a guessed name — the DEF210 rule.
String _agentName(String id) => _agent(id)?.displayName ?? id;

Color _agentColour(String id) => _agent(id)?.color ?? AmiColors.textMed;

// ── card 4 — how your mandate has moved ──────────────────────────────────

class _MandateCardView extends StatelessWidget {
  const _MandateCardView({required this.card, required this.window});
  final MandateCard card;
  final String window;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    return _Card(
      title: l.insightsMandateTitle,
      window: window,
      children: [
        Text(l.insightsMandateEdits(card.editCount),
            style: AmiTypography.labelMono.copyWith(color: AmiColors.hexPurple)),
        const SizedBox(height: AmiSpacing.s),
        if (card.moves.isEmpty)
          Text(l.insightsMandateNoMoves, style: AmiTypography.caption)
        else
          for (final m in card.moves)
            Padding(
              padding: const EdgeInsets.only(bottom: 6),
              child: Row(
                children: [
                  Expanded(
                    child: Text(_limitLabel(m.field),
                        style: AmiTypography.body),
                  ),
                  Text(
                    '${_num(m.from)} → ${_num(m.to)}',
                    style: AmiTypography.labelMono.copyWith(
                      color: m.loosened
                          ? AmiColors.hexAmber
                          : AmiColors.hexGreen,
                    ),
                  ),
                  const SizedBox(width: AmiSpacing.s),
                  Text(
                    m.loosened
                        ? l.insightsMandateLoosened
                        : l.insightsMandateTightened,
                    style: AmiTypography.caption.copyWith(
                      color: m.loosened
                          ? AmiColors.hexAmber
                          : AmiColors.textLow,
                    ),
                  ),
                ],
              ),
            ),
      ],
    );
  }
}

String _num(num v) => v == v.roundToDouble() ? v.toInt().toString() : '$v';

/// Wire field → a name a user recognises. Unknown fields fall back to the wire
/// spelling rather than to a pretty guess.
String _limitLabel(String field) => switch (field) {
      'risk_score' => 'Risk score',
      'max_drawdown_pct' => 'Max drawdown',
      'sector_cap_pct' => 'Sector cap',
      'single_name_cap_pct' => 'Single-name cap',
      'max_open_positions' => 'Max open positions',
      'max_trades_per_day' => 'Max trades/day',
      'max_trades_per_week' => 'Max trades/week',
      'max_open_risk_pct' => 'Max open risk',
      'post_loss_cooldown_hours' => 'Post-loss cooldown',
      _ => field,
    };

// ── card 5 — daily challenge by type ─────────────────────────────────────

class _ChallengeCardView extends StatelessWidget {
  const _ChallengeCardView({required this.card, required this.window});
  final ChallengeCard card;
  final String window;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    return _Card(
      title: l.insightsChallengeTitle,
      window: window,
      caveat: [
        l.insightsChallengeUnweighted,
        if (card.omittedTypes > 0) l.insightsChallengeOmitted(card.omittedTypes),
      ].join('\n'),
      children: [
        for (final r in card.rows)
          Padding(
            padding: const EdgeInsets.only(bottom: AmiSpacing.s),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Expanded(
                      child: Text(_challengeLabel(r.type),
                          style: AmiTypography.body),
                    ),
                    Text(l.insightsChallengeRow(r.correct, r.attempts),
                        style: AmiTypography.labelMono
                            .copyWith(color: AmiColors.hexCyan)),
                  ],
                ),
                const SizedBox(height: 4),
                Directionality(
                  textDirection: TextDirection.ltr,
                  child: ClipRRect(
                    borderRadius: BorderRadius.circular(2),
                    child: LinearProgressIndicator(
                      value: r.correct / r.attempts,
                      minHeight: 6,
                      backgroundColor: AmiColors.slate700,
                      valueColor: const AlwaysStoppedAnimation<Color>(
                          AmiColors.hexCyan),
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

String _challengeLabel(String type) =>
    type.replaceAll('_', ' ').split(' ').map((w) {
      if (w.isEmpty) return w;
      return w[0].toUpperCase() + w.substring(1);
    }).join(' ');
