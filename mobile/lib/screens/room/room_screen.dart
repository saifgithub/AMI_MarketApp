/// Convene the Room — the Matrix-style streaming console.
///
/// All 12 agents speak in phases on a single ticker. The current phase
/// banner highlights at the top; each agent's contribution streams in
/// a typewriter feed below, role-colour-coded and tagged with the agent's
/// abbreviation. The final Verdict card lands at the bottom.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/agent.dart';
import 'package:ami_trade/models/room.dart';
import 'package:ami_trade/screens/sim/trade_ticket_sheet.dart';
import 'package:ami_trade/state/room_providers.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:ami_trade/widgets/hex/hex_avatar.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

class RoomScreen extends ConsumerStatefulWidget {
  const RoomScreen({super.key, required this.ticker});

  final String ticker;

  @override
  ConsumerState<RoomScreen> createState() => _RoomScreenState();
}

class _RoomScreenState extends ConsumerState<RoomScreen> {
  final _scrollCtrl = ScrollController();

  @override
  void dispose() {
    _scrollCtrl.dispose();
    super.dispose();
  }

  void _scrollToBottom() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!_scrollCtrl.hasClients) return;
      _scrollCtrl.animateTo(
        _scrollCtrl.position.maxScrollExtent + 400,
        duration: AmiMotion.normal,
        curve: AmiMotion.easeOut,
      );
    });
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(roomNotifierProvider(widget.ticker));

    ref.listen<int>(
      roomNotifierProvider(widget.ticker).select((s) => s.transcript.length),
      (_, __) => _scrollToBottom(),
    );

    return Scaffold(
      backgroundColor: AmiColors.slate900,
      body: SafeArea(
        child: Column(
          children: [
            _Header(ticker: widget.ticker, phase: state.phase),
            Expanded(
              child: SingleChildScrollView(
                controller: _scrollCtrl,
                padding: const EdgeInsets.all(AmiSpacing.m),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    if (state.error != null)
                      _ErrorBanner(message: state.error!),
                    for (final agentId in state.order)
                      _AgentLine(
                        agentId: agentId,
                        text: state.transcript[agentId] ?? '',
                        active: state.activeAgent == agentId,
                      ),
                    if (state.verdict != null) ...[
                      const SizedBox(height: AmiSpacing.l),
                      _VerdictCard(
                        verdict: state.verdict!,
                        ticker: widget.ticker,
                        runId: state.runId,
                      ),
                    ],
                    if (state.done && state.verdict == null)
                      Padding(
                        padding: const EdgeInsets.all(AmiSpacing.l),
                        child: Text(
                            AppLocalizations.of(context).roomEndedNoVerdict,
                            style: AmiTypography.body),
                      ),
                    const SizedBox(height: AmiSpacing.xxl),
                  ],
                ),
              ),
            ),
            _Footer(state: state),
          ],
        ),
      ),
    );
  }
}


class _Header extends StatelessWidget {
  const _Header({required this.ticker, required this.phase});
  final String ticker;
  final String? phase;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    return Container(
      height: 88,
      padding: const EdgeInsets.symmetric(horizontal: AmiSpacing.s),
      decoration: const BoxDecoration(
        color: AmiColors.glassChrome,
        border: Border(bottom: BorderSide(color: AmiColors.slate700)),
      ),
      child: Row(
        children: [
          IconButton(
            icon: const Icon(Icons.arrow_back, color: AmiColors.textHigh),
            onPressed: () => Navigator.of(context).pop(),
          ),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Row(
                  children: [
                    Text(l.roomHeadingPrefix,
                        style: AmiTypography.labelMono
                            .copyWith(color: AmiColors.hexBlue)),
                    const SizedBox(width: 6),
                    Text(ticker,
                        style: AmiTypography.statMid
                            .copyWith(color: AmiColors.textHigh)),
                  ],
                ),
                const SizedBox(height: 2),
                Row(
                  children: [
                    Icon(Icons.bolt,
                        size: 12,
                        color: phase == null ? AmiColors.textLow : AmiColors.hexGreen),
                    const SizedBox(width: 4),
                    Text(
                      phase ?? l.roomStandingBy,
                      style: AmiTypography.caption.copyWith(
                        color: phase == null ? AmiColors.textLow : AmiColors.hexGreen,
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}


class _AgentLine extends StatelessWidget {
  const _AgentLine({
    required this.agentId,
    required this.text,
    required this.active,
  });

  final String agentId;
  final String text;
  final bool active;

  @override
  Widget build(BuildContext context) {
    final a = agentById(agentId);
    return Padding(
      padding: const EdgeInsets.only(bottom: AmiSpacing.s),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          HexAvatar(
            label: a.abbreviation,
            color: a.color,
            size: 28,
            status: active ? HexAvatarStatus.recentCall : HexAvatarStatus.idle,
          ),
          const SizedBox(width: AmiSpacing.s),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Text(a.abbreviation,
                        style: AmiTypography.labelMono
                            .copyWith(color: a.color, fontSize: 11)),
                    if (active) ...[
                      const SizedBox(width: 6),
                      Container(
                        width: 6,
                        height: 6,
                        decoration: BoxDecoration(
                          color: a.color,
                          shape: BoxShape.circle,
                        ),
                      ),
                    ],
                  ],
                ),
                const SizedBox(height: 2),
                Text(
                  text,
                  style: AmiTypography.stream.copyWith(
                    color: active ? AmiColors.textHigh : AmiColors.textMed,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}


class _ErrorBanner extends StatelessWidget {
  const _ErrorBanner({required this.message});
  final String message;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      margin: const EdgeInsets.only(bottom: AmiSpacing.m),
      padding: const EdgeInsets.all(AmiSpacing.s),
      decoration: BoxDecoration(
        color: AmiColors.slate800,
        borderRadius: BorderRadius.circular(AmiRadii.card),
        border: Border.all(color: AmiColors.hexRed),
      ),
      child: Row(
        children: [
          const Icon(Icons.error_outline, color: AmiColors.hexRed, size: 18),
          const SizedBox(width: AmiSpacing.s),
          Expanded(child: Text(message, style: AmiTypography.body)),
        ],
      ),
    );
  }
}


class _VerdictCard extends StatelessWidget {
  const _VerdictCard({
    required this.verdict,
    required this.ticker,
    this.runId,
  });
  final RoomVerdict verdict;
  final String ticker;
  final String? runId;

  @override
  Widget build(BuildContext context) {
    final isApprove = verdict.isApprove;
    final accent = isApprove ? AmiColors.hexGreen : AmiColors.hexAmber;
    final l = AppLocalizations.of(context);
    return Container(
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
              Icon(
                isApprove ? Icons.check_circle : Icons.cancel,
                color: accent,
                size: 28,
              ),
              const SizedBox(width: AmiSpacing.s),
              Text(l.roomVerdictHeading(verdict.action),
                  style: AmiTypography.labelMono.copyWith(color: accent)),
              const Spacer(),
              if (verdict.overriddenFromLlm)
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                  decoration: BoxDecoration(
                    color: AmiColors.hexAmber.withValues(alpha: 0.15),
                    borderRadius: BorderRadius.circular(4),
                  ),
                  child: Text(l.roomSafetyFloorPill,
                      style: AmiTypography.labelMono.copyWith(
                          color: AmiColors.hexAmber, fontSize: 9)),
                ),
            ],
          ),
          const SizedBox(height: AmiSpacing.m),
          if (isApprove) ...[
            _MetricRow(label: l.roomMetricTicker, value: ticker, accent: accent),
            _MetricRow(
              label: l.roomMetricSize,
              value: verdict.sizePct == null
                  ? '—'
                  : '${verdict.sizePct!.toStringAsFixed(1)}%',
              accent: accent,
            ),
            _MetricRow(
              label: l.roomMetricEntry,
              value: verdict.entry == null ? '—' : '\$${verdict.entry!.toStringAsFixed(2)}',
              accent: accent,
            ),
            _MetricRow(
              label: l.roomMetricStop,
              value: verdict.stop == null ? '—' : '\$${verdict.stop!.toStringAsFixed(2)}',
              accent: accent,
            ),
            _MetricRow(
              label: l.roomMetricTarget,
              value: verdict.target == null ? '—' : '\$${verdict.target!.toStringAsFixed(2)}',
              accent: accent,
            ),
            _MetricRow(
              label: l.roomMetricHorizon,
              value: verdict.timeHorizonDays == null
                  ? '—'
                  : l.roomHorizonDays(verdict.timeHorizonDays!),
              accent: accent,
            ),
            const SizedBox(height: AmiSpacing.s),
          ],
          if (verdict.violations.isNotEmpty) ...[
            Text(l.roomViolations,
                style: AmiTypography.labelMono.copyWith(
                    fontSize: 11, color: AmiColors.hexAmber)),
            const SizedBox(height: 4),
            for (final v in verdict.violations)
              Padding(
                padding: const EdgeInsets.only(bottom: 2),
                child: Text('• $v', style: AmiTypography.caption),
              ),
            const SizedBox(height: AmiSpacing.s),
          ],
          Container(
            width: double.infinity,
            padding: const EdgeInsets.all(AmiSpacing.s),
            decoration: BoxDecoration(
              color: AmiColors.slate900,
              borderRadius: BorderRadius.circular(AmiRadii.card),
            ),
            child: Text(verdict.reason, style: AmiTypography.body),
          ),
          if (isApprove) ...[
            const SizedBox(height: AmiSpacing.m),
            SizedBox(
              width: double.infinity,
              child: ElevatedButton.icon(
                style: ElevatedButton.styleFrom(
                  backgroundColor: AmiColors.hexCyan,
                  foregroundColor: AmiColors.slate900,
                  padding: const EdgeInsets.symmetric(vertical: AmiSpacing.s + 2),
                ),
                icon: const Icon(Icons.add_circle_outline),
                label: Text(l.roomOpenTradeTicket),
                onPressed: () => TradeTicketSheet.show(
                  context,
                  prefill: verdict,
                  verdictRef: runId,
                  tickerPrefill: ticker,
                ),
              ),
            ),
            const SizedBox(height: AmiSpacing.xs),
            Text(
              l.roomTradeTicketCaption,
              style: AmiTypography.caption.copyWith(color: AmiColors.textLow),
              textAlign: TextAlign.center,
            ),
          ],
        ],
      ),
    );
  }
}


class _MetricRow extends StatelessWidget {
  const _MetricRow({
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
            child: Text(label,
                style: AmiTypography.labelMono
                    .copyWith(fontSize: 11, color: AmiColors.textLow)),
          ),
          Text(value,
              style: AmiTypography.statSmall.copyWith(color: accent)),
        ],
      ),
    );
  }
}


class _Footer extends StatelessWidget {
  const _Footer({required this.state});
  final RoomState state;

  @override
  Widget build(BuildContext context) {
    if (state.streaming) {
      return Container(
        padding: const EdgeInsets.all(AmiSpacing.m),
        decoration: const BoxDecoration(
          color: AmiColors.slate900,
          border: Border(top: BorderSide(color: AmiColors.slate700)),
        ),
        child: Row(
          children: [
            const SizedBox(
              width: 14,
              height: 14,
              child: CircularProgressIndicator(
                strokeWidth: 2, color: AmiColors.hexGreen,
              ),
            ),
            const SizedBox(width: AmiSpacing.s),
            Text(
              '${AppLocalizations.of(context).roomDeliberating} ${state.phase ?? ""}'
                  .trim(),
              style: AmiTypography.caption,
            ),
          ],
        ),
      );
    }
    if (state.done) {
      return Container(
        padding: const EdgeInsets.all(AmiSpacing.m),
        decoration: const BoxDecoration(
          color: AmiColors.slate900,
          border: Border(top: BorderSide(color: AmiColors.slate700)),
        ),
        child: Row(
          children: [
            const Icon(Icons.check, color: AmiColors.hexGreen, size: 16),
            const SizedBox(width: AmiSpacing.s),
            Text(AppLocalizations.of(context).roomSavedToJournal,
                style: AmiTypography.caption),
            const Spacer(),
            TextButton(
              onPressed: () => Navigator.of(context).pop(),
              child: Text(AppLocalizations.of(context).roomClose),
            ),
          ],
        ),
      );
    }
    return const SizedBox.shrink();
  }
}
