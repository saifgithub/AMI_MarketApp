/// CR109 slice 3 — the Close (design §10.2) and the Wind-Up (§10, §6.7).
///
/// THREE-BEAT CEREMONY BUDGET, non-negotiable:
///   1. THE RESULT (`_BeatResult`) — the number: rank/basis, the signed
///      career-point delta, the curve replayed with its provenance markers
///      (`widgets/games/games_close_curve.dart`).
///   2. ONE INSIGHT (`_BeatInsight`) — chosen by priority. This slice never
///      reaches the duel verdict (slice 3b, unbuilt) or the paid agent
///      post-mortem (a later slice — see the fence below), so the priority
///      in practice is: a server-supplied near-miss line, else the
///      counterfactual pair. Design §10.4: the two counterfactual lines
///      "pair with §10.2," so both render together as ONE card — and they
///      render UNCONDITIONALLY, because implementation_plan.md's own
///      acceptance line is "a free user's Close contains rank, delta,
///      curve and both counterfactual lines," not "...reachable from a
///      panel."
///   3. THE WAY BACK IN (`_BeatReentry`) — the re-entry CTA, always the
///      FINAL beat, always present: win, lose or void (design §10.3, "the
///      arrow that is the whole game").
///
/// Everything else — the alpha_scored/alpha_display breakdown, intent vs.
/// outcome, the wildness index, the cost line, the fuller basis/forfeit/void
/// explanation — lives one tap deeper in [GamesCloseDebriefSheet].
///
/// **No upsell anywhere on this screen or in the debrief.** The paid agent
/// post-mortem is a later slice and is DELIBERATELY NOT MODELED OR STUBBED
/// here (design §10.2 fence 2: the locked card, when it ships, belongs in
/// the debrief panel one tap deeper, never inside the three beats). Not
/// building it now means there is nothing here that could be placed wrong.
/// There is also no entitlement field anywhere on [GameCloseResult] — see
/// that model's docstring — so this screen has no free/paid branch to get
/// wrong either.
///
/// **The Wind-Up.** The design names a separate "loss ceremony" for a
/// blown-up run (§10, §6.7: "losing must be a chapter, not an ending").
/// `_BeatResult` still carries dignified `state == 'forfeit'` framing (warm
/// accent, "CHAPTER CLOSED" rather than fail-screen language) for
/// forward-compatibility, but **the live backend never actually reaches it
/// through this screen**: `games_record_service.py.get_close_payload`
/// requires `entry.state in ("finished", "void")` and 409s otherwise — "a
/// forfeit has no Close," by that module's own docstring. The Wind-Up's
/// real, reachable home this slice is therefore
/// [GamesRecordScreen]'s run-history row for a forfeited entry, answered
/// inline rather than by opening this screen (see that file's `_HistoryRow`
/// — routing a forfeit here would always land on the generic error state
/// below, not on this dignified branch). This screen's forfeit branch stays
/// in place and tested regardless, so if a later revision of the close
/// payload ever does carry `state: 'forfeit'`, the client already renders
/// it correctly rather than crashing or reading it as a plain loss.
///
/// A VOID run (implementation_plan.md §6.6, "degrade loudly") never shows a
/// number that looks real — beat 1 states [GameCloseResult.voidReason]
/// plainly instead of any rank/points/curve.
///
/// Reached from [GamesRecordScreen]'s run-history rows — see that file's
/// docstring for why that is the only contractually-solid path to a
/// specific closed run this slice. Not a new top-level entry point: this
/// screen, like the rest of `screens/games/`, is only reachable from inside
/// the already-gated `/games` subtree (`features/games/games_gate.dart`).
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/games.dart';
import 'package:ami_trade/screens/games/games_entry_sheet.dart';
import 'package:ami_trade/state/games_providers.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:ami_trade/widgets/games/games_close_curve.dart';
import 'package:ami_trade/widgets/hex/glass_panel.dart';
import 'package:ami_trade/widgets/hex/hex_button.dart';
import 'package:ami_trade/widgets/hex/hex_chip.dart';
import 'package:ami_trade/widgets/hex/hex_mark.dart';
import 'package:ami_trade/widgets/sheet_insets.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

/// CR106 T-BIDI: isolate signed/numeric runs so RTL layout cannot scramble
/// sign/digits. Per-file copy, matching this codebase's existing
/// convention (see `widgets/portfolio_equity_chart.dart`).
String _isolateNumeric(String s) => '\u2066$s\u2069';

String _pct(double v) => '${v >= 0 ? '+' : ''}${v.toStringAsFixed(2)}%';

class GamesCloseScreen extends ConsumerWidget {
  const GamesCloseScreen({super.key, required this.runId});

  final String runId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l = AppLocalizations.of(context);
    final closeAsync = ref.watch(gamesCloseProvider(runId));
    return Scaffold(
      backgroundColor: AmiColors.slate900,
      appBar: AppBar(title: Text(l.gamesCloseAppBarTitle)),
      body: SafeArea(
        child: closeAsync.when(
          loading: () => const Center(child: CircularProgressIndicator()),
          error: (e, _) => _CloseErrorState(
            onRetry: () => ref.invalidate(gamesCloseProvider(runId)),
          ),
          data: (result) => _CloseBody(result: result),
        ),
      ),
    );
  }
}

class _CloseErrorState extends StatelessWidget {
  const _CloseErrorState({required this.onRetry});
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(AmiSpacing.l),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(
              l.gamesCloseLoadError,
              style: AmiTypography.body,
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: AmiSpacing.m),
            HexButton(label: l.gamesRetry.toUpperCase(), onPressed: onRetry),
          ],
        ),
      ),
    );
  }
}

class _CloseBody extends StatelessWidget {
  const _CloseBody({required this.result});
  final GameCloseResult result;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    return SingleChildScrollView(
      padding: const EdgeInsets.all(AmiSpacing.m),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _BeatResult(result: result),
          const SizedBox(height: AmiSpacing.l),
          _BeatInsight(result: result),
          const SizedBox(height: AmiSpacing.s),
          Center(
            child: TextButton(
              onPressed: () =>
                  GamesCloseDebriefSheet.show(context, result: result),
              child: Text(
                l.gamesCloseDebriefCta.toUpperCase(),
                style: AmiTypography.labelMono
                    .copyWith(color: AmiColors.textMed, fontSize: 11),
              ),
            ),
          ),
          const SizedBox(height: AmiSpacing.m),
          _BeatReentry(result: result),
        ],
      ),
    );
  }
}

/// BEAT 1 — the result.
class _BeatResult extends StatelessWidget {
  const _BeatResult({required this.result});
  final GameCloseResult result;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);

    if (result.isVoid) {
      return SizedBox(
        key: const Key('games_close_beat_result'),
        width: double.infinity,
        child: GlassPanel(
          accentColor: AmiColors.hexCyan,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              HexChip(
                label: l.gamesCloseVoidChip,
                color: AmiColors.hexCyan,
                variant: HexChipVariant.tinted,
              ),
              const SizedBox(height: AmiSpacing.s),
              Text(l.gamesCloseVoidHeading, style: AmiTypography.h3),
              const SizedBox(height: AmiSpacing.xs),
              // Server-authored text (implementation_plan.md §6.6 "degrade
              // loudly") — never localized client-side, never replaced by a
              // fabricated score.
              Text(
                result.voidReason ?? l.gamesCloseVoidReasonUnknown,
                style: AmiTypography.body,
              ),
              if (result.stipendAwarded) ...[
                const SizedBox(height: AmiSpacing.s),
                Text(
                  l.gamesCloseStipendNote(result.careerPointsDelta),
                  style:
                      AmiTypography.caption.copyWith(color: AmiColors.hexGreen),
                ),
              ],
            ],
          ),
        ),
      );
    }

    final isWindUp = result.isForfeit;
    // Wind-Up: a dignified, warm accent — never red doom, never amber
    // warning. The normal Close reads as an analyst measurement (cyan).
    final accent = isWindUp ? AmiColors.hexBlue : AmiColors.hexCyan;
    final delta = result.careerPointsDelta;
    final deltaSign = delta >= 0 ? '+' : '';
    final deltaColor = delta > 0
        ? AmiColors.hexGreen
        : (delta < 0 ? AmiColors.hexRed : AmiColors.textMed);

    return SizedBox(
      key: const Key('games_close_beat_result'),
      width: double.infinity,
      child: GlassPanel(
        accentColor: accent,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                HexChip(
                  label: result.cadence.toUpperCase(),
                  color: accent,
                  variant: HexChipVariant.tinted,
                ),
                const Spacer(),
                // The thin-field basis disclosure lives WITH the number
                // (CR040 degrade-loudly), not tucked in the debrief.
                if (result.isThinField)
                  Flexible(
                    child: Text(
                      l.gamesCloseBasisThinField(result.entrantCount),
                      style: AmiTypography.caption,
                      textAlign: TextAlign.end,
                    ),
                  )
                else if (result.rank != null)
                  Flexible(
                    child: Text(
                      l.gamesCloseBasisRanked(result.rank!, result.entrantCount),
                      style: AmiTypography.caption,
                      textAlign: TextAlign.end,
                    ),
                  ),
              ],
            ),
            const SizedBox(height: AmiSpacing.m),
            Row(
              crossAxisAlignment: CrossAxisAlignment.center,
              children: [
                HexMark(
                  color: accent,
                  child: Text(
                    result.rank != null ? '#${result.rank}' : (isWindUp ? '↺' : '±'),
                    style: AmiTypography.dataMd.copyWith(color: accent),
                  ),
                ),
                const SizedBox(width: AmiSpacing.m),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        isWindUp
                            ? l.gamesCloseTitleForfeit
                            : l.gamesCloseTitleFinished,
                        style: AmiTypography.h4,
                      ),
                      Text(
                        _isolateNumeric('$deltaSign$delta'),
                        style: AmiTypography.statBig
                            .copyWith(color: deltaColor, fontSize: 34),
                      ),
                      Text(l.gamesCloseCareerPointsLabel,
                          style: AmiTypography.caption),
                    ],
                  ),
                ),
              ],
            ),
            const SizedBox(height: AmiSpacing.m),
            GamesCloseCurve(points: result.navSeries, color: accent),
          ],
        ),
      ),
    );
  }
}

/// BEAT 2 — one insight.
class _BeatInsight extends StatelessWidget {
  const _BeatInsight({required this.result});
  final GameCloseResult result;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);

    if (result.isVoid) {
      return Container(
        key: const Key('games_close_beat_insight'),
        width: double.infinity,
        padding: const EdgeInsets.all(AmiSpacing.m),
        decoration: BoxDecoration(
          color: AmiColors.slate800,
          borderRadius: BorderRadius.circular(AmiRadii.card),
          border: Border.all(color: AmiColors.slate700),
        ),
        child: Text(l.gamesCloseInsightVoidNote, style: AmiTypography.body),
      );
    }

    final headline = result.hasNearMiss
        ? l.gamesCloseNearMissLine(
            result.nearMissGapPct!.toStringAsFixed(1), result.nearMissLabel!)
        : ((result.alphaDisplay ?? 0) >= 0
            ? l.gamesCloseInsightIndexBeat
            : l.gamesCloseInsightIndexNeutral(
                _isolateNumeric(_pct(result.counterfactualIndexPct ?? 0))));

    return Container(
      key: const Key('games_close_beat_insight'),
      width: double.infinity,
      padding: const EdgeInsets.all(AmiSpacing.m),
      decoration: BoxDecoration(
        color: AmiColors.slate800,
        borderRadius: BorderRadius.circular(AmiRadii.card),
        border: Border.all(color: AmiColors.hexPurple.withValues(alpha: 0.4)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(headline,
              style: AmiTypography.body.copyWith(color: AmiColors.textHigh)),
          const SizedBox(height: AmiSpacing.s),
          // Both counterfactual lines, UNCONDITIONALLY — see this file's
          // top docstring. Neither is derived from the other, or from
          // alpha_scored/alpha_display; both render exactly as received.
          if (result.counterfactualFirstPicksPct != null)
            Text(
              l.gamesCloseCounterfactualFirstPicks(
                  _isolateNumeric(_pct(result.counterfactualFirstPicksPct!))),
              style: AmiTypography.caption,
            ),
          if (result.counterfactualIndexPct != null)
            Text(
              l.gamesCloseCounterfactualIndex(
                  _isolateNumeric(_pct(result.counterfactualIndexPct!))),
              style: AmiTypography.caption,
            ),
        ],
      ),
    );
  }
}

/// BEAT 3 — the way back in. Always the final beat, win/lose/void alike.
class _BeatReentry extends ConsumerWidget {
  const _BeatReentry({required this.result});
  final GameCloseResult result;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l = AppLocalizations.of(context);
    final cadencesAsync = ref.watch(gamesCadencesProvider);
    return SizedBox(
      key: const Key('games_close_beat_reentry'),
      width: double.infinity,
      child: GlassPanel(
        // Execution-family accent — this is the CTA, not a read (design
        // rule: colour by agent family, never a hard-coded CTA hue; hexGreen
        // is the same accent every other trade/entry CTA in this feature
        // already uses).
        accentColor: AmiColors.hexGreen,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(l.gamesCloseReentryHeading, style: AmiTypography.h4),
            const SizedBox(height: AmiSpacing.s),
            cadencesAsync.when(
              loading: () => const SizedBox(
                height: 20,
                child: Center(child: CircularProgressIndicator(strokeWidth: 2)),
              ),
              error: (e, _) =>
                  Text(l.gamesLoadError, style: AmiTypography.caption),
              data: (cadences) {
                var target = GameCadenceInfo(cadence: result.cadence);
                for (final c in cadences) {
                  if (c.cadence == result.cadence) {
                    target = c;
                    break;
                  }
                }
                final entrants = target.nextField?.entrantCount ?? 0;
                return Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    if (entrants > 0)
                      Padding(
                        padding: const EdgeInsets.only(bottom: AmiSpacing.s),
                        child: Text(
                          l.gamesFieldEntrantCount(entrants),
                          style: AmiTypography.caption,
                        ),
                      ),
                    SizedBox(
                      width: double.infinity,
                      child: HexButton(
                        label: l.gamesCloseReentryCta.toUpperCase(),
                        color: AmiColors.hexGreen,
                        onPressed: target.alreadyHolds
                            ? null
                            : () =>
                                GamesEntrySheet.show(context, cadence: result.cadence),
                      ),
                    ),
                  ],
                );
              },
            ),
          ],
        ),
      ),
    );
  }
}

/// The debrief panel — one tap deeper than the three beats (design §10.2).
/// Everything the Close's ceremony budget doesn't have room for: the
/// alpha_scored/alpha_display breakdown, intent vs. outcome, the wildness
/// index, the cost line, and the fuller thin-field/forfeit/void
/// explanation.
///
/// **No paid-tier content lives here.** The post-mortem is a later slice —
/// see this file's top docstring for why it is deliberately not modeled or
/// stubbed, here or anywhere in this CR.
class GamesCloseDebriefSheet extends StatelessWidget {
  const GamesCloseDebriefSheet({super.key, required this.result});
  final GameCloseResult result;

  static Future<void> show(
    BuildContext context, {
    required GameCloseResult result,
  }) {
    return showModalBottomSheet<void>(
      context: context,
      backgroundColor: AmiColors.slate800,
      isScrollControlled: true,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(16)),
      ),
      builder: (_) => GamesCloseDebriefSheet(result: result),
    );
  }

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    return Padding(
      padding: EdgeInsets.fromLTRB(
        AmiSpacing.l,
        AmiSpacing.l,
        AmiSpacing.l,
        AmiSpacing.l + sheetBottomInset(MediaQuery.of(context)),
      ),
      child: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(l.gamesDebriefHeading, style: AmiTypography.h3),
            const SizedBox(height: AmiSpacing.m),

            if (result.isThinField)
              _row(l.gamesDebriefBasisLabel,
                  l.gamesCloseBasisThinField(result.entrantCount))
            else if (result.rank != null)
              _row(
                l.gamesDebriefBasisLabel,
                l.gamesCloseBasisRanked(result.rank!, result.entrantCount),
              ),

            if (!result.isVoid &&
                (result.alphaScored != null ||
                    result.alphaDisplay != null)) ...[
              const Divider(color: AmiColors.slate700, height: AmiSpacing.l),
              // alpha_scored and alpha_display each render from their own
              // wire field — see models/games.dart's GameCloseResult
              // docstring: neither is ever computed from the other here.
              if (result.alphaScored != null)
                _row(l.gamesDebriefAlphaScoredLabel,
                    _isolateNumeric(_pct(result.alphaScored!))),
              if (result.alphaDisplay != null)
                _row(l.gamesDebriefAlphaDisplayLabel,
                    _isolateNumeric(_pct(result.alphaDisplay!))),
            ],

            if (result.intent != null || result.wildnessIndex != null) ...[
              const Divider(color: AmiColors.slate700, height: AmiSpacing.l),
              if (result.intent != null)
                _row(l.gamesDebriefIntentLabel, _intentLabel(l, result.intent!)),
              if (result.wildnessIndex != null)
                _row(l.gamesDebriefWildnessLabel,
                    result.wildnessIndex!.toStringAsFixed(2)),
            ],

            const Divider(color: AmiColors.slate700, height: AmiSpacing.l),
            // The cost line — colour-neutral by design rule (CR134 §21: "no
            // amber warning colours on... the cost line"). Plain data rows,
            // no accent at all.
            _row(l.gamesDebriefFeesLabel,
                '\$${(result.feesPaid ?? 0).toStringAsFixed(2)}'),
            _row(l.gamesDebriefTradeCountLabel, '${result.tradeCount}'),

            if (result.isForfeit) ...[
              const SizedBox(height: AmiSpacing.m),
              Text(l.gamesDebriefForfeitNote, style: AmiTypography.caption),
            ],
            if (result.isVoid) ...[
              const SizedBox(height: AmiSpacing.m),
              Text(l.gamesDebriefVoidExplainer, style: AmiTypography.caption),
            ],
          ],
        ),
      ),
    );
  }

  // Both sides Expanded (not just the label): the basis row's value can be
  // a full sentence ("Field of 3. Scored against..."), not just a short
  // figure like "+1.10%" — an unconstrained Text there overflowed the row
  // outright rather than wrapping.
  Widget _row(String label, String value) => Padding(
        padding: const EdgeInsets.symmetric(vertical: 4),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Expanded(
              flex: 2,
              child: Text(label, style: AmiTypography.caption),
            ),
            const SizedBox(width: AmiSpacing.s),
            Expanded(
              flex: 3,
              child: Text(
                value,
                style: AmiTypography.dataMd,
                textAlign: TextAlign.end,
              ),
            ),
          ],
        ),
      );

  String _intentLabel(AppLocalizations l, String intent) {
    switch (intent) {
      case 'wild':
        return l.gamesIntentWild;
      case 'thesis':
        return l.gamesIntentThesis;
      case 'disciplined':
        return l.gamesIntentDisciplined;
      default:
        return intent;
    }
  }
}
