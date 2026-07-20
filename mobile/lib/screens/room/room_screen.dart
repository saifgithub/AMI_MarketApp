/// Convene the Room — the Matrix-style streaming console.
///
/// All 12 agents speak in phases on a single ticker. The current phase
/// banner highlights at the top; each agent's contribution streams in
/// a typewriter feed below, role-colour-coded and tagged with the agent's
/// abbreviation. The final Verdict card lands at the bottom.
library;

import 'dart:async';

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/agent.dart';
import 'package:ami_trade/models/room.dart';
import 'package:ami_trade/screens/lessons/lessons_screen.dart';
import 'package:ami_trade/screens/sim/ticker_detail_screen.dart';
import 'package:ami_trade/screens/sim/trade_ticket_sheet.dart';
import 'package:ami_trade/services/api/api_exceptions.dart';
import 'package:ami_trade/services/celebration.dart';
import 'package:ami_trade/services/share/share_service.dart';
import 'package:ami_trade/state/room_providers.dart';
import 'package:ami_trade/state/sim_providers.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:ami_trade/widgets/hex/hex_avatar.dart';
import 'package:ami_trade/widgets/hex/hex_pulse_loader.dart';
import 'package:flutter/material.dart';
import 'package:flutter_markdown_plus/flutter_markdown_plus.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_tts/flutter_tts.dart';

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

    // Celebration hook (CR004 B1): the verdict landing is the payoff of a
    // 12-agent run — mark the moment it arrives with the micro tier.
    ref.listen<RoomVerdict?>(
      roomNotifierProvider(widget.ticker).select((s) => s.verdict),
      (prev, next) {
        if (prev == null && next != null) {
          Celebrate.micro(
            context,
            accent: next.isApprove
                ? AmiColors.hexGreen
                : next.isPass
                    ? AmiColors.slate500
                    : AmiColors.hexAmber,
          );
        }
      },
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
                    if (state.paywall != null)
                      _PaywallCard(
                        info: state.paywall!,
                        ticker: widget.ticker,
                      ),
                    if (state.serverError)
                      _ServerErrorCard(ticker: widget.ticker),
                    if (state.error != null)
                      _ErrorBanner(message: state.error!),
                    if (state.reconnecting) const _ReconnectingBanner(),
                    if (state.streaming && state.order.isEmpty)
                      _RoomRoster(state: state),
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
                MarkdownBody(
                  data: text,
                  shrinkWrap: true,
                  styleSheet: _agentMarkdownStyle(
                    active ? AmiColors.textHigh : AmiColors.textMed,
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


/// B3 — Room roster skeleton. Replaces the empty-body + footer-spinner wait
/// with the 12-agent lineup so convening the Room reads as a team assembling.
/// Rows derive their state from `RoomState` (no per-agent status map exists):
/// speaking = `activeAgent`, done = already in `order`, else standing by. In
/// the display window (streaming + `order` empty) every row is standing by;
/// the speaking/done branches light up automatically if the lineup is ever
/// shown mid-run (the live pulse arrives with D3).
class _RoomRoster extends StatelessWidget {
  const _RoomRoster({required this.state});
  final RoomState state;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        for (final agent in kAllAgents.sublist(0, 12))
          _RosterRow(agent: agent, state: state, standingByLabel: l.roomStandingBy),
      ],
    );
  }
}


class _RosterRow extends StatelessWidget {
  const _RosterRow({
    required this.agent,
    required this.state,
    required this.standingByLabel,
  });

  final Agent agent;
  final RoomState state;
  final String standingByLabel;

  @override
  Widget build(BuildContext context) {
    final speaking = state.activeAgent == agent.id;
    final done = !speaking && state.order.contains(agent.id);
    final lit = speaking || done;
    return Padding(
      padding: const EdgeInsets.only(bottom: AmiSpacing.s),
      child: Row(
        children: [
          Opacity(
            opacity: lit ? 1.0 : 0.35,
            child: HexAvatar(
              label: agent.abbreviation,
              color: agent.color,
              size: 28,
              // CR014/D3: the currently-streaming agent pulses (signal).
              status:
                  speaking ? HexAvatarStatus.signal : HexAvatarStatus.idle,
            ),
          ),
          const SizedBox(width: AmiSpacing.s),
          Expanded(
            child: Text(
              agent.displayName,
              style: AmiTypography.body.copyWith(
                color: lit ? AmiColors.textHigh : AmiColors.textMed,
              ),
            ),
          ),
          if (speaking)
            Container(
              width: 6,
              height: 6,
              decoration:
                  BoxDecoration(color: agent.color, shape: BoxShape.circle),
            )
          else if (done)
            const Icon(Icons.check, color: AmiColors.hexGreen, size: 16)
          else
            Text(
              standingByLabel.toUpperCase(),
              style: AmiTypography.labelMono
                  .copyWith(color: AmiColors.textLow, fontSize: 10),
            ),
        ],
      ),
    );
  }
}


/// Markdown styling for agent stream text. Inherits the screen-wide
/// stream typography so bold / bullets / inline code stay visually
/// consistent with the surrounding monospace-paced reading flow.
MarkdownStyleSheet _agentMarkdownStyle(Color color) {
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


/// CR047 "The Winzip" — the soft credit wall, rendered as a warm countdown
/// instead of a dead paywall. Under the winzip funnel the server has already
/// re-granted one Room; this card just runs down the cooldown, speaks AMI's
/// "your Room is available now" line when it lands, and lets the user convene
/// again — with a Training nudge to fill the wait. Falls back to a plain
/// "out of credits, resets on the reset date" card when the wall is the hard
/// monthly one (GTM_FUNNEL=none).
class _PaywallCard extends ConsumerStatefulWidget {
  const _PaywallCard({required this.info, required this.ticker});

  final InsufficientCreditsException info;
  final String ticker;

  @override
  ConsumerState<_PaywallCard> createState() => _PaywallCardState();
}

class _PaywallCardState extends ConsumerState<_PaywallCard> {
  Timer? _tick;
  bool _announced = false;

  bool get _isWinzip =>
      widget.info.isWinzip && widget.info.cooldownUntil != null;

  Duration get _remaining {
    final until = widget.info.cooldownUntil;
    if (until == null) return Duration.zero;
    final d = until.difference(DateTime.now());
    return d.isNegative ? Duration.zero : d;
  }

  bool get _ready => _isWinzip && _remaining == Duration.zero;

  @override
  void initState() {
    super.initState();
    if (_isWinzip && _remaining > Duration.zero) {
      _tick = Timer.periodic(const Duration(seconds: 1), (_) {
        if (!mounted) return;
        setState(() {});
        if (_ready) {
          _tick?.cancel();
          _announceReady(AppLocalizations.of(context).roomWinzipVoiceLine);
        }
      });
    } else if (_isWinzip) {
      // Cooldown already elapsed by the time we render — no chime, just ready.
      _announced = true;
    }
  }

  @override
  void dispose() {
    _tick?.cancel();
    super.dispose();
  }

  Future<void> _announceReady(String line) async {
    if (_announced) return;
    _announced = true;
    // The voice is a delight, never load-bearing — swallow any TTS failure so
    // a device without a usable voice engine still shows the Convene button.
    try {
      final tts = FlutterTts();
      await tts.setLanguage('en-US');
      await tts.setSpeechRate(0.5);
      await _preferFemaleVoice(tts);
      await tts.speak(line);
    } catch (_) {}
  }

  Future<void> _preferFemaleVoice(FlutterTts tts) async {
    try {
      final voices = (await tts.getVoices) as List?;
      if (voices == null) return;
      const preferred = {
        'samantha', 'karen', 'moira', 'tessa', 'fiona', 'serena', 'aria',
      };
      for (final v in voices) {
        final m = Map<String, dynamic>.from(v as Map);
        final name = (m['name'] as String? ?? '').toLowerCase();
        final locale = (m['locale'] as String? ?? '').toLowerCase();
        if (locale.startsWith('en') &&
            (preferred.any(name.contains) || name.contains('female'))) {
          await tts.setVoice({
            'name': m['name'].toString(),
            'locale': m['locale'].toString(),
          });
          return;
        }
      }
    } catch (_) {}
  }

  String _fmt(Duration d) {
    final m = d.inMinutes.remainder(60).toString().padLeft(2, '0');
    final s = d.inSeconds.remainder(60).toString().padLeft(2, '0');
    return '$m:$s';
  }

  String _resetDateStr() {
    final r = widget.info.resetsAt;
    if (r == null) return 'the 1st';
    return '${r.year}-${r.month.toString().padLeft(2, '0')}-'
        '${r.day.toString().padLeft(2, '0')}';
  }

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    const accent = AmiColors.hexAmber;
    final title = _isWinzip ? l.roomWinzipTitle : l.roomPaywallTitle;
    final body = _isWinzip
        ? (_ready ? l.roomWinzipReady : l.roomWinzipBody(_fmt(_remaining)))
        : l.roomPaywallBody(_resetDateStr());

    return Container(
      width: double.infinity,
      margin: const EdgeInsets.only(bottom: AmiSpacing.m),
      padding: const EdgeInsets.all(AmiSpacing.m),
      decoration: BoxDecoration(
        color: AmiColors.slate800,
        borderRadius: BorderRadius.circular(AmiRadii.card),
        border: Border.all(color: accent),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(
                _ready ? Icons.check_circle_outline : Icons.hourglass_bottom,
                color: accent,
                size: 18,
              ),
              const SizedBox(width: AmiSpacing.s),
              Expanded(
                child: Text(
                  title,
                  style: AmiTypography.labelMono.copyWith(color: accent),
                ),
              ),
            ],
          ),
          const SizedBox(height: AmiSpacing.s),
          Text(body, style: AmiTypography.body),
          if (_isWinzip && !_ready) ...[
            const SizedBox(height: AmiSpacing.m),
            Center(
              child: Text(
                _fmt(_remaining),
                style: AmiTypography.statBig.copyWith(color: accent),
              ),
            ),
          ],
          const SizedBox(height: AmiSpacing.m),
          if (_ready)
            SizedBox(
              width: double.infinity,
              child: ElevatedButton.icon(
                style: ElevatedButton.styleFrom(
                  backgroundColor: AmiColors.hexCyan,
                  foregroundColor: AmiColors.slate900,
                  padding:
                      const EdgeInsets.symmetric(vertical: AmiSpacing.s + 2),
                ),
                icon: const Icon(Icons.groups_2_outlined),
                label: Text(l.roomWinzipConvene),
                onPressed: () => ref
                    .read(roomNotifierProvider(widget.ticker).notifier)
                    .start(),
              ),
            ),
          SizedBox(
            width: double.infinity,
            child: TextButton.icon(
              style: TextButton.styleFrom(foregroundColor: accent),
              icon: const Icon(Icons.school_outlined, size: 18),
              label: Text(l.roomWinzipReviewTraining),
              onPressed: () => Navigator.of(context).push(
                MaterialPageRoute<void>(builder: (_) => const LessonsScreen()),
              ),
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


/// DEF073: friendly card shown when a Room convene hits a 5xx (502/503/504).
/// Reassures the user it's transient and offers a one-tap Retry (re-runs the
/// convene), instead of surfacing a raw status code.
class _ServerErrorCard extends ConsumerWidget {
  const _ServerErrorCard({required this.ticker});
  final String ticker;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l = AppLocalizations.of(context);
    const accent = AmiColors.hexRed;
    return Container(
      width: double.infinity,
      margin: const EdgeInsets.only(bottom: AmiSpacing.m),
      padding: const EdgeInsets.all(AmiSpacing.m),
      decoration: BoxDecoration(
        color: AmiColors.slate800,
        borderRadius: BorderRadius.circular(AmiRadii.card),
        border: Border.all(color: accent),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(Icons.cloud_off_outlined, color: accent, size: 18),
              const SizedBox(width: AmiSpacing.s),
              Expanded(
                child: Text(
                  l.roomServerErrorTitle,
                  style: AmiTypography.labelMono.copyWith(color: accent),
                ),
              ),
            ],
          ),
          const SizedBox(height: AmiSpacing.s),
          Text(l.roomServerErrorBody, style: AmiTypography.body),
          const SizedBox(height: AmiSpacing.m),
          SizedBox(
            width: double.infinity,
            child: ElevatedButton.icon(
              style: ElevatedButton.styleFrom(
                backgroundColor: AmiColors.hexCyan,
                foregroundColor: AmiColors.slate900,
                padding: const EdgeInsets.symmetric(vertical: AmiSpacing.s + 2),
              ),
              icon: const Icon(Icons.refresh),
              label: Text(l.roomRetry),
              onPressed: () =>
                  ref.read(roomNotifierProvider(ticker).notifier).start(),
            ),
          ),
        ],
      ),
    );
  }
}


class _ReconnectingBanner extends StatelessWidget {
  const _ReconnectingBanner();

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      margin: const EdgeInsets.only(bottom: AmiSpacing.m),
      padding: const EdgeInsets.all(AmiSpacing.s),
      decoration: BoxDecoration(
        color: AmiColors.slate800,
        borderRadius: BorderRadius.circular(AmiRadii.card),
        border: Border.all(color: AmiColors.hexAmber),
      ),
      child: Row(
        children: [
          const SizedBox(
            width: 14,
            height: 14,
            child: CircularProgressIndicator(
              strokeWidth: 2,
              valueColor: AlwaysStoppedAnimation(AmiColors.hexAmber),
            ),
          ),
          const SizedBox(width: AmiSpacing.s),
          Expanded(
            child: Text(
              'Connection lost. The room is still running — waiting for the verdict to land.',
              style: AmiTypography.body,
            ),
          ),
        ],
      ),
    );
  }
}


class _VerdictCard extends ConsumerWidget {
  const _VerdictCard({
    required this.verdict,
    required this.ticker,
    this.runId,
  });
  final RoomVerdict verdict;
  final String ticker;
  final String? runId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final isApprove = verdict.isApprove;
    final isPass = verdict.isPass;
    // PASS ("no strong opinion, sit out") is neither an APPROVE nor a
    // mandate REJECT — give it its own neutral treatment so it doesn't
    // read as a rejection (DEF056: PASS is now a real, distinct outcome).
    final accent = isApprove
        ? AmiColors.hexGreen
        : isPass
            ? AmiColors.slate500
            : AmiColors.hexAmber;
    final l = AppLocalizations.of(context);
    // Detect a sim trade already placed against this verdict (bug 9b3a6c2f).
    // Watching sim trades lets the verdict card flip the Buy button into a
    // "✓ Trade placed" pill the moment the trade lands — eliminates the
    // "did anything happen?" confusion that drove repeat-tap duplicates.
    final trades = ref.watch(simNotifierProvider).trades;
    final existingTrade = runId == null
        ? null
        : trades
            .where((t) => t.verdictRef == runId)
            .firstOrNull;
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
                isApprove
                    ? Icons.check_circle
                    : isPass
                        ? Icons.remove_circle_outline
                        : Icons.cancel,
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
              IconButton(
                tooltip: l.shareTooltip,
                icon: const Icon(Icons.ios_share, size: 20),
                color: AmiColors.textMed,
                visualDensity: VisualDensity.compact,
                padding: EdgeInsets.zero,
                constraints: const BoxConstraints(),
                onPressed: () => ShareService.shareVerdict(
                  context,
                  ticker: ticker,
                  stanceLabel: l.roomVerdictHeading(verdict.action),
                  isApprove: isApprove,
                  isPass: isPass,
                  reason: verdict.reason,
                ),
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
            if (existingTrade != null)
              // Trade already placed for this verdict — replace the Buy CTA
              // with a clear confirmation pill so the user doesn't second-
              // guess whether the trade landed (bug 9b3a6c2f).
              Container(
                width: double.infinity,
                padding: const EdgeInsets.symmetric(
                  vertical: AmiSpacing.s + 4,
                  horizontal: AmiSpacing.m,
                ),
                decoration: BoxDecoration(
                  color: AmiColors.hexGreen.withValues(alpha: 0.12),
                  borderRadius: BorderRadius.circular(AmiRadii.card),
                  border: Border.all(color: AmiColors.hexGreen, width: 1.5),
                ),
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    const Icon(Icons.check_circle, color: AmiColors.hexGreen, size: 20),
                    const SizedBox(width: AmiSpacing.s),
                    Text(
                      '${existingTrade.side.toUpperCase()} ${existingTrade.quantity.toStringAsFixed(0)} '
                      '${existingTrade.ticker} @ \$${existingTrade.entryPrice.toStringAsFixed(2)}',
                      style: AmiTypography.labelMono.copyWith(
                        color: AmiColors.hexGreen,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                  ],
                ),
              )
            else
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
              existingTrade != null
                  ? 'Trade placed · view it in the Journal'
                  : l.roomTradeTicketCaption,
              style: AmiTypography.caption.copyWith(color: AmiColors.textLow),
              textAlign: TextAlign.center,
            ),
          ],
          // SEE CHART — secondary action; shown in ALL verdict states
          // (approve+no-trade, approve+traded, reject). Lets the user
          // pivot from the deliberation moment into the TickerDetail
          // research surface (chart, news, earnings — Bundles 2-5).
          const SizedBox(height: AmiSpacing.s),
          SizedBox(
            width: double.infinity,
            child: OutlinedButton.icon(
              style: OutlinedButton.styleFrom(
                foregroundColor: AmiColors.hexCyan,
                side: const BorderSide(color: AmiColors.hexCyan),
                padding: const EdgeInsets.symmetric(vertical: AmiSpacing.s + 2),
              ),
              icon: const Icon(Icons.show_chart),
              label: Text(l.roomVerdictSeeChart),
              onPressed: () => Navigator.of(context).push(
                MaterialPageRoute<void>(
                  builder: (_) => TickerDetailScreen(ticker: ticker),
                ),
              ),
            ),
          ),
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
    // B3: while the roster skeleton owns the wait (streaming, nothing spoken
    // yet), the footer spinner is redundant — the lineup is the activity cue.
    if (state.streaming && state.order.isEmpty) {
      return const SizedBox.shrink();
    }
    if (state.streaming) {
      return Container(
        padding: const EdgeInsets.all(AmiSpacing.m),
        decoration: const BoxDecoration(
          color: AmiColors.slate900,
          border: Border(top: BorderSide(color: AmiColors.slate700)),
        ),
        child: Row(
          children: [
            const HexPulseLoader(size: 16, color: AmiColors.hexGreen),
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
