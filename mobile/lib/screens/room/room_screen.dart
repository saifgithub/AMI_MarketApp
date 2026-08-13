/// Convene the Room — the streaming console.
///
/// **CR173 slice 1 changed what a live run looks like by default.** It used to
/// pin all 12 seats from the first frame; it now opens on a four-stage briefing
/// (`room_briefing.dart`) — analyst desk, research debate, risk review, PM
/// verdict — with desk counts on each row and the desk's members one tap away.
/// The shipped roster is not gone: `WATCH THE FLOOR` restores it, and that
/// choice persists as the third value of CR106's `RoomViewMode`, written
/// through the same single writer.
///
/// The settled screen is untouched — this CR ends exactly where CR106 begins.
library;

import 'dart:async';

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/agent.dart';
import 'package:ami_trade/models/room.dart';
import 'package:ami_trade/models/room_board.dart';
import 'package:ami_trade/models/room_board_mappers.dart';
import 'package:ami_trade/models/room_stage.dart';
import 'package:ami_trade/screens/lessons/lessons_screen.dart';
import 'package:ami_trade/screens/sim/ticker_detail_screen.dart';
import 'package:ami_trade/screens/sim/trade_ticket_sheet.dart';
import 'package:ami_trade/services/api/api_exceptions.dart';
import 'package:ami_trade/services/celebration.dart';
import 'package:ami_trade/services/share/share_service.dart';
import 'package:ami_trade/state/mandate_providers.dart';
import 'package:ami_trade/state/room_providers.dart';
import 'package:ami_trade/state/room_view_mode_provider.dart';
import 'package:ami_trade/state/sim_providers.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:ami_trade/widgets/paywall/upgrade_paywall.dart';
import 'package:ami_trade/widgets/hex/hex_avatar.dart';
import 'package:ami_trade/widgets/hex/hex_pulse_loader.dart';
import 'package:ami_trade/widgets/room/room_board.dart';
import 'package:ami_trade/widgets/room/room_briefing.dart';
import 'package:ami_trade/widgets/room/room_transcript_rows.dart';
import 'package:ami_trade/widgets/room/room_view_mode_toggle.dart';
import 'package:flutter/material.dart';
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

  /// CR106 T-MODESIDE — a mode change made FOR THIS SCREEN ONLY, by the peek
  /// sheet's `READ THE FULL DEBATE`. It deliberately does not go through
  /// `setMode`, because one curious tap on a 26pt mark must not rewrite what
  /// every future Room opens as. Null means "use the stored preference".
  RoomViewMode? _sessionMode;
  String? _jumpAgentId;

  @override
  void dispose() {
    _scrollCtrl.dispose();
    super.dispose();
  }

  void _jumpToAgent(RoomVoice voice) {
    setState(() {
      _sessionMode = RoomViewMode.transcript;
      _jumpAgentId = voice.agentId;
    });
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(roomNotifierProvider(widget.ticker));

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

    // T-LIVE: the board only exists once the run has landed. While it streams,
    // the screen is always the live wall — a comb filling in agent by agent
    // reads as a running vote count.
    final settled = state.done || state.verdict != null;
    final storedMode = ref.watch(roomViewModeProvider);
    final mode = _sessionMode ?? storedMode;
    final showBoard = settled && !mode.showsTranscript;

    return Scaffold(
      backgroundColor: AmiColors.slate900,
      body: SafeArea(
        child: Column(
          children: [
            _Header(ticker: widget.ticker, phase: state.phase),
            if (settled)
              RoomSubHeader(
                meta: _stripMeta(context, state),
                mode: mode,
                // The ONLY caller of setMode in the feature (T-MODESIDE).
                onModeChanged: _setMode,
              )
            else
              // CR173 — the same strip, the same writer, a different pair of
              // labels. T-MODESIDE extends to the third value unchanged: this
              // control and the settled one above are the only two things that
              // write the preference.
              RoomSubHeader.live(mode: mode, onModeChanged: _setMode),
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
                    if (state.liveDataNotice != null)
                      _LiveDataNoticeCard(notice: state.liveDataNotice!),
                    if (state.error != null)
                      _ErrorBanner(message: state.error!),
                    if (state.reconnecting) const _ReconnectingBanner(),
                    if (showBoard)
                      RoomBoard(
                        data: boardFromRoomState(
                          state: state,
                          ticker: widget.ticker,
                        ),
                        onVoiceTap: (voice) => showAgentPeekSheet(
                          context,
                          voice: voice,
                          onReadFullDebate: () => _jumpToAgent(voice),
                        ),
                        footer: state.verdict == null
                            ? _ConveneAgainButton(ticker: widget.ticker)
                            : _VerdictActions(
                                verdict: state.verdict!,
                                ticker: widget.ticker,
                                runId: state.runId,
                              ),
                      )
                    else ...[
                      // CR112: a settled run shows the collapsed rows with
                      // the full text reachable; a live run shows PER-AGENT
                      // STATUS + headline, never the growing prose — that is
                      // the entire point of this CR. The roster is fixed
                      // (all 12 seats, always) because there is nothing to
                      // scroll to as agents move through it.
                      if (settled)
                        RoomTranscriptRows(
                          voices: transcriptVoicesFromRoomState(state),
                          expandedAgentId: _jumpAgentId,
                          highlightAgentId: _jumpAgentId,
                          // A locked chair keeps its own row rather than
                          // collapsing to a bare `NOT HEARD`: CR098 D1's
                          // roster countdown says WHICH remedy applies, and
                          // losing it once a run finishes would re-open the
                          // exact hole the CR098 audit closed.
                          withheldDetail: {
                            for (final e in state.withheldAgents.entries)
                              e.key: _WithheldAgentChair(info: e.value),
                          },
                        )
                      else if (mode.showsLiveFloor)
                        _RoomLiveRoster(state: state)
                      else
                        // CR173 slice 1 — the default. Four desks instead of
                        // twelve seats, and the locked chairs are handed in
                        // rather than re-described, so an absent analyst reads
                        // identically on both live views.
                        RoomBriefing(
                          state: state,
                          withheldDetail: {
                            for (final e in state.withheldAgents.entries)
                              e.key: _WithheldAgentChair(info: e.value),
                          },
                        ),
                      if (settled && state.verdict != null) ...[
                        const SizedBox(height: AmiSpacing.l),
                        _VerdictCard(
                          verdict: state.verdict!,
                          ticker: widget.ticker,
                          runId: state.runId,
                        ),
                      ],
                      if (settled && state.verdict == null)
                        Padding(
                          padding: const EdgeInsets.all(AmiSpacing.l),
                          child: Text(
                              AppLocalizations.of(context).roomEndedNoVerdict,
                              style: AmiTypography.body),
                        ),
                    ],
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

  /// The one place `setMode` is called from, shared by the live and the settled
  /// strip. Clearing `_sessionMode` first is what stops a screen-local override
  /// (the peek sheet's `READ THE FULL DEBATE`) from outliving the deliberate
  /// choice that replaces it.
  void _setMode(RoomViewMode m) {
    setState(() => _sessionMode = null);
    ref.read(roomViewModeProvider.notifier).setMode(m);
  }

  /// The strip's leading half. `duration_ms` and `credit_cost` live on
  /// `RoomRun` server-side but never reach the live stream, so the Room shows
  /// what it does know: how many of the twelve spoke.
  String _stripMeta(BuildContext context, RoomState state) {
    final l = AppLocalizations.of(context);
    return l.roomTranscriptHint(state.transcript.length);
  }
}

/// The NO RESULT hero's action. The run produced nothing, so the honest offer
/// is to run it again — not a trade, and not a chart of a thesis that was never
/// reached.
class _ConveneAgainButton extends ConsumerWidget {
  const _ConveneAgainButton({required this.ticker});
  final String ticker;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l = AppLocalizations.of(context);
    return SizedBox(
      width: double.infinity,
      child: ElevatedButton.icon(
        style: ElevatedButton.styleFrom(
          backgroundColor: AmiColors.hexCyan,
          foregroundColor: AmiColors.slate900,
          padding: const EdgeInsets.symmetric(vertical: AmiSpacing.s + 2),
        ),
        icon: const Icon(Icons.refresh),
        label: Text(l.roomHeroConveneAgain),
        onPressed: () =>
            ref.read(roomNotifierProvider(ticker).notifier).start(),
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
                        color: phase == null
                            ? AmiColors.textLow
                            : AmiColors.hexGreen),
                    const SizedBox(width: 4),
                    Text(
                      phase ?? l.roomStandingBy,
                      style: AmiTypography.caption.copyWith(
                        color: phase == null
                            ? AmiColors.textLow
                            : AmiColors.hexGreen,
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

/// CR098 — a locked chair for one tenure-withheld analyst. Renders inline in
/// `state.order` at the point the `agent_withheld` event arrived (before any
/// ANALYSTS-phase agent speaks — D4), never in a floating banner that could
/// drift out of seat position.
///
/// The countdown line is deliberately ROSTER-level, not per-agent: it names
/// the roster's single nearest upcoming pull-back step, which is never "this
/// analyst returns" (pull-back is monotonic — an analyst never un-withholds
/// without an upgrade). Omitted entirely when both `nextStepAgentId` and
/// `nextStepDays` are null (nothing further scheduled to go dark) — never a
/// "null days" artifact.
class _WithheldAgentChair extends StatelessWidget {
  const _WithheldAgentChair({required this.info});

  final WithheldAgentInfo info;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final a = agentById(info.agentId);
    final nextAgentId = info.nextStepAgentId;
    final nextDays = info.nextStepDays;
    final showCountdown = nextAgentId != null && nextDays != null;
    return Padding(
      padding: const EdgeInsets.only(bottom: AmiSpacing.s),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Opacity(
            opacity: 0.35,
            child: HexAvatar(
              label: a.abbreviation,
              color: a.color,
              size: 28,
              status: HexAvatarStatus.idle,
            ),
          ),
          const SizedBox(width: AmiSpacing.s),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    const Icon(Icons.lock_outline,
                        size: 14, color: AmiColors.textLow),
                    const SizedBox(width: 6),
                    Expanded(
                      child: Text(
                        l.roomAgentWithheldChairLabel(a.displayName),
                        style: AmiTypography.body
                            .copyWith(color: AmiColors.textMed),
                      ),
                    ),
                  ],
                ),
                if (showCountdown) ...[
                  const SizedBox(height: 2),
                  Text(
                    l.roomAgentWithheldRosterNote(
                      agentById(nextAgentId).displayName,
                      nextDays,
                    ),
                    style: AmiTypography.caption
                        .copyWith(color: AmiColors.textLow),
                  ),
                ],
              ],
            ),
          ),
        ],
      ),
    );
  }
}

/// CR112 — the live roster. Replaces both the old pre-order skeleton (B3) and
/// the growing per-agent prose feed. Fixed at all 12 seats from the first
/// frame — there is nowhere to scroll to, so unlike the feed it replaces this
/// never needs `_scrollToBottom`. Each seat renders STATUS
/// (waiting / thinking / responded / interrupted), and on `responded` the
/// agent's own one-line headline — never the growing prose (bug 583602ee:
/// CR106 fixed the destination, this fixes the journey).
class _RoomLiveRoster extends StatelessWidget {
  const _RoomLiveRoster({required this.state});
  final RoomState state;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        for (final agent in kAllAgents.sublist(0, 12))
          state.withheldAgents[agent.id] != null
              ? _WithheldAgentChair(info: state.withheldAgents[agent.id]!)
              : _AgentStatusRow(agent: agent, state: state, l: l),
      ],
    );
  }
}

/// One roster seat. No per-agent status map exists — every state is derived
/// from `RoomState` alone, by [seatStateFor] in `room_stage.dart`.
///
/// **The derivation moved out of this widget in CR173 and that is the point.**
/// The four-stage briefing renders the same twelve states on a different
/// surface, and §5.9 requires the two to agree exactly. Two copies of this
/// reasoning agreeing today is not the same as one copy that cannot disagree
/// (DEF098) — so there is one function, and both surfaces call it.
class _AgentStatusRow extends StatelessWidget {
  const _AgentStatusRow({
    required this.agent,
    required this.state,
    required this.l,
  });

  final Agent agent;
  final RoomState state;
  final AppLocalizations l;

  @override
  Widget build(BuildContext context) {
    final stance = state.agentStances[agent.id];
    final seat = seatStateFor(state, agent.id);
    final responded = seat == RoomSeatState.responded;
    final thinking = seat == RoomSeatState.thinking;
    final interrupted = seat == RoomSeatState.interrupted;
    final lit = responded || thinking || interrupted;
    // DEF125: a length-stopped turn is marked `[AMI …]` in the raw text; the
    // settled comb (`room_transcript_rows.dart`) marks it with the same
    // amber hex, reused here (acceptance 6) so a truncated turn never reads
    // as a clean completion on either surface.
    final truncated =
        responded && hasAmiAnnotation(state.transcript[agent.id] ?? '');

    // DEF174 — thinking (and, via the icon-only `responded` check, the
    // completed state too) was colour + motion only: a screen reader was
    // told nothing while the hex avatar pulsed. `roomAgentStatusSemantic`
    // names both the agent and its status so the same information sighted
    // users read off the dot/icon/text reaches the accessibility tree.
    final statusWord = interrupted
        ? l.roomAgentInterrupted
        : thinking
            ? l.roomAgentThinking
            : responded
                ? l.roomAgentResponded
                : l.roomStandingBy;
    final statusSemanticLabel =
        l.roomAgentStatusSemantic(agent.displayName, statusWord);

    return Padding(
      padding: const EdgeInsets.only(bottom: AmiSpacing.s),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Opacity(
                opacity: lit ? 1.0 : 0.35,
                child: HexAvatar(
                  label: agent.abbreviation,
                  color: agent.color,
                  size: 28,
                  // CR014/D3: the currently-speaking agent pulses (signal).
                  status:
                      thinking ? HexAvatarStatus.signal : HexAvatarStatus.idle,
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
              if (truncated) ...[
                Semantics(
                  label: l.roomAgentTruncatedMark,
                  child: const Text('⬢',
                      style:
                          TextStyle(fontSize: 11, color: AmiColors.hexAmber)),
                ),
                const SizedBox(width: 4),
              ],
              // DEF174 — the trailing indicator (a colour-changing dot for
              // `thinking`, a bare check icon for `responded`) carried no
              // text a screen reader could read; `waiting`/`interrupted`
              // already had visible text, but folding all four into one
              // Semantics node means the next new state can't reopen this
              // gap by accident. `excludeSemantics` replaces whatever each
              // branch's own child semantics would say (nothing, for the
              // dot and the icon) with the one label naming the agent and
              // its state — scoped to just this indicator so the agent-name
              // Text above and the headline below stay independently
              // readable.
              Semantics(
                label: statusSemanticLabel,
                excludeSemantics: true,
                child: interrupted
                    ? Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          const Icon(Icons.error_outline,
                              color: AmiColors.hexRed, size: 16),
                          const SizedBox(width: 4),
                          Text(
                            l.roomAgentInterrupted,
                            style: AmiTypography.labelMono.copyWith(
                                color: AmiColors.hexRed, fontSize: 10),
                          ),
                        ],
                      )
                    : thinking
                        ? Container(
                            width: 6,
                            height: 6,
                            decoration: BoxDecoration(
                                color: agent.color, shape: BoxShape.circle),
                          )
                        : responded
                            ? const Icon(Icons.check,
                                color: AmiColors.hexGreen, size: 16)
                            : Text(
                                l.roomStandingBy.toUpperCase(),
                                style: AmiTypography.labelMono.copyWith(
                                    color: AmiColors.textLow, fontSize: 10),
                              ),
              ),
            ],
          ),
          if (stance != null && stance.recorded) _headline(stance),
        ],
      ),
    );
  }

  /// CR112 acceptance 9 — the three `recorded`/`headline` states, each a
  /// DIFFERENT widget so none can be mistaken for another:
  ///   (a) `recorded == false` — this run carries no stances at all. Never
  ///       reaches here (guarded by the caller) — no headline row at all.
  ///   (b) `recorded == true`, `headline == null` — the agent finished and
  ///       stated no view. Reuses the Verdict Board's own `NOT STATED`
  ///       gutter label (`roomCombNotStated`) so the same fact reads
  ///       identically on both surfaces — never neutral, never a blank that
  ///       could pass for a rendering bug.
  ///   (c) `recorded == true`, `headline` present — the headline itself.
  Widget _headline(AgentStance stance) {
    final headline = stance.headline;
    return Padding(
      padding: const EdgeInsets.only(left: 36, top: 2),
      child: headline == null
          ? Text(
              l.roomCombNotStated,
              style: AmiTypography.labelMono
                  .copyWith(fontSize: 10, color: AmiColors.textLow),
            )
          : Text(
              headline,
              style: AmiTypography.body.copyWith(color: AmiColors.textMed),
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
            ),
    );
  }
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
        'samantha',
        'karen',
        'moira',
        'tessa',
        'fiona',
        'serena',
        'aria',
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
    // CR047 Winzip cooldown path is unchanged (soft, self-resetting wall);
    // CR084 turns the hard monthly wall into a live RC paywall.
    return _isWinzip ? _buildWinzip(context, l) : _buildHardWall(context, l);
  }

  /// CR047 "The Winzip" cooldown countdown — untouched by CR084.
  Widget _buildWinzip(BuildContext context, AppLocalizations l) {
    const accent = AmiColors.hexAmber;
    final body =
        _ready ? l.roomWinzipReady : l.roomWinzipBody(_fmt(_remaining));
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
                  l.roomWinzipTitle,
                  style: AmiTypography.labelMono.copyWith(color: accent),
                ),
              ),
            ],
          ),
          const SizedBox(height: AmiSpacing.s),
          Text(body, style: AmiTypography.body),
          if (!_ready) ...[
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

  /// CR084 hard-wall paywall: the "out of credits" framing followed by the live
  /// RC offering (or the degrade card when the store isn't wired yet, DEF100).
  /// A completed purchase refreshes entitlement from the backend, then clears
  /// the wall and re-convenes.
  Widget _buildHardWall(BuildContext context, AppLocalizations l) {
    const accent = AmiColors.hexAmber;
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
              const Icon(Icons.lock_outline, color: accent, size: 18),
              const SizedBox(width: AmiSpacing.s),
              Expanded(
                child: Text(
                  l.roomPaywallTitle,
                  style: AmiTypography.labelMono.copyWith(color: accent),
                ),
              ),
            ],
          ),
          const SizedBox(height: AmiSpacing.s),
          Text(l.roomPaywallBody(_resetDateStr()), style: AmiTypography.body),
          const SizedBox(height: AmiSpacing.m),
          UpgradePaywall(
            resetDateLabel: _resetDateStr(),
            onPurchased: () =>
                ref.read(roomNotifierProvider(widget.ticker).notifier).start(),
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

/// CR090: renders the structural live-data disclosure (`live_data_notice`),
/// one per run. Now four states, four distinct renderings (D3, extended by
/// CR098 D1) — this is the entire point of the CR:
///   - `live`: confirms real data was used and what it cost.
///   - `withheld_paid`: the data exists but wasn't paid for — explicit
///     "needs credits" copy + an upgrade-for-credits CTA.
///   - `withheld_tenure` (CR098 D1): the data exists but the analyst is off
///     the roster on account age — a DIFFERENT remedy (plan upgrade, not
///     credits) needs its OWN copy + its own CTA. Routing this to the
///     credits CTA is the DEF059-class inversion this state exists to catch:
///     buying credits will not bring the analyst back.
///   - `unavailable`: nobody has this data right now — said plainly, with
///     NO CTA and no upsell (upselling something we can't deliver is the
///     DEF059 inversion this CR exists to prevent).
/// Absence of a notice renders nothing (D4) — the caller only mounts this
/// when `state.liveDataNotice != null`.
class _LiveDataNoticeCard extends ConsumerWidget {
  const _LiveDataNoticeCard({required this.notice});

  final RoomLiveDataNotice notice;

  bool get _newsWithheld => notice.news == 'withheld_paid';
  bool get _socialWithheld => notice.social == 'withheld_paid';
  bool get _anyWithheld => _newsWithheld || _socialWithheld;
  bool get _newsTenure => notice.news == 'withheld_tenure';
  bool get _socialTenure => notice.social == 'withheld_tenure';
  bool get _anyTenure => _newsTenure || _socialTenure;
  bool get _anyLive => notice.news == 'live' || notice.social == 'live';

  String _resetDateStr(WidgetRef ref) {
    final r = ref.read(mandateNotifierProvider).mandate?.creditsResetAt;
    if (r == null) return 'the 1st';
    return '${r.year}-${r.month.toString().padLeft(2, '0')}-'
        '${r.day.toString().padLeft(2, '0')}';
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l = AppLocalizations.of(context);
    // D3/D1: withheld_paid and withheld_tenure each carry an honest upsell
    // (different remedies, different CTAs below) so they take priority in
    // framing over unavailable; unavailable-only never gets a CTA.
    // withheld_tenure gets its own accent (purple, not amber) so the card
    // never LOOKS like the credits-withheld state even before reading it.
    final accent = _anyWithheld
        ? AmiColors.hexAmber
        : _anyTenure
            ? AmiColors.hexPurple
            : AmiColors.slate500;
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
              Icon(Icons.rss_feed, color: accent, size: 18),
              const SizedBox(width: AmiSpacing.s),
              Expanded(
                child: Text(
                  l.roomLiveDataNoticeTitle,
                  style: AmiTypography.labelMono.copyWith(color: accent),
                ),
              ),
            ],
          ),
          const SizedBox(height: AmiSpacing.s),
          Text(_stateLine(l, 'News', notice.news), style: AmiTypography.body),
          Text(_stateLine(l, 'Social', notice.social),
              style: AmiTypography.body),
          if (_anyLive) ...[
            const SizedBox(height: AmiSpacing.xs),
            Text(
              l.roomLiveDataSurchargeCharged(notice.surchargeCharged),
              style: AmiTypography.body.copyWith(color: AmiColors.slate600),
            ),
          ],
          if (_anyWithheld) ...[
            const SizedBox(height: AmiSpacing.m),
            SizedBox(
              width: double.infinity,
              child: ElevatedButton(
                style: ElevatedButton.styleFrom(
                  backgroundColor: AmiColors.hexAmber,
                  foregroundColor: AmiColors.slate900,
                  padding:
                      const EdgeInsets.symmetric(vertical: AmiSpacing.s + 2),
                ),
                onPressed: () => showUpgradeSheet(
                  context,
                  resetDateLabel: _resetDateStr(ref),
                ),
                child: Text(l.roomLiveDataUpgradeCta),
              ),
            ),
          ],
          // CR098 (D1): withheld_tenure's OWN CTA — deliberately never the
          // credits button above. A tenure withhold is fixed by a plan
          // upgrade; buying credits does nothing for it, so pointing this
          // state at the credits CTA is the exact DEF059-class inversion
          // this state exists to catch.
          if (_anyTenure) ...[
            const SizedBox(height: AmiSpacing.m),
            SizedBox(
              width: double.infinity,
              child: ElevatedButton(
                style: ElevatedButton.styleFrom(
                  backgroundColor: AmiColors.hexPurple,
                  foregroundColor: AmiColors.slate900,
                  padding:
                      const EdgeInsets.symmetric(vertical: AmiSpacing.s + 2),
                ),
                onPressed: () => showUpgradeSheet(
                  context,
                  resetDateLabel: _resetDateStr(ref),
                ),
                child: Text(l.roomLiveDataTenureUpgradeCta),
              ),
            ),
          ],
        ],
      ),
    );
  }

  String _stateLine(AppLocalizations l, String feedLabel, String state) {
    switch (state) {
      case 'live':
        return l.roomLiveDataFeedLive(feedLabel);
      case 'withheld_paid':
        return l.roomLiveDataFeedWithheld(feedLabel);
      case 'withheld_tenure':
        return l.roomLiveDataFeedTenure(feedLabel);
      case 'unavailable':
      default:
        return l.roomLiveDataFeedUnavailable(feedLabel);
    }
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

/// The wire enum is rendered raw for every action that is already a readable
/// English word. `NO_VERDICT` is not — and an unrecognised future value is
/// still rendered rather than crashing the card (acceptance #9): the enum grew
/// once and will grow again, and a token the user does not recognise beats a
/// blank screen.
String _actionLabel(AppLocalizations l, String action) =>
    action == 'NO_VERDICT' ? l.roomVerdictActionNoVerdict : action;

/// `agentById` falls back to the Concierge for an unknown id, which in a
/// disclosure would name the WRONG analyst as absent — a confident lie. Here an
/// id we cannot resolve renders as itself instead.
String _analystLabel(String id) {
  for (final a in kAllAgents) {
    if (a.id == id) return a.displayName;
  }
  return id;
}

/// The analyst whose absence forced the refusal. `NO_VERDICT` is by
/// construction the Market-withheld state (Amendment 2), so prefer Market when
/// it is in the list; fall back to whatever was withheld rather than asserting
/// a name the payload does not support.
String _blockingAnalystId(RoomVerdict v) {
  const market = 'market_analyst';
  if (v.opinionsNotIncluded.contains(market)) return market;
  return v.opinionsNotIncluded.isEmpty ? market : v.opinionsNotIncluded.first;
}

String _verdictResetDateStr(WidgetRef ref) {
  final r = ref.read(mandateNotifierProvider).mandate?.creditsResetAt;
  if (r == null) return 'the 1st';
  return '${r.year}-${r.month.toString().padLeft(2, '0')}-'
      '${r.day.toString().padLeft(2, '0')}';
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
    final isNoVerdict = verdict.isNoVerdict;
    // PASS ("no strong opinion, sit out") is neither an APPROVE nor a
    // mandate REJECT — give it its own neutral treatment so it doesn't
    // read as a rejection (DEF056: PASS is now a real, distinct outcome).
    // NO_VERDICT (CR098 Amendment 2) is the same argument one step further:
    // the PM refused to price a trade without a market read. That is
    // professional discipline, not a turn-down, and the amber reject accent
    // states the opposite.
    final neutral = isPass || isNoVerdict;
    final accent = isApprove
        ? AmiColors.hexGreen
        : neutral
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
        : trades.where((t) => t.verdictRef == runId).firstOrNull;
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
                    : isNoVerdict
                        ? Icons.pause_circle_outline
                        : isPass
                            ? Icons.remove_circle_outline
                            : Icons.cancel,
                color: accent,
                size: 28,
              ),
              const SizedBox(width: AmiSpacing.s),
              Text(l.roomVerdictHeading(_actionLabel(l, verdict.action)),
                  style: AmiTypography.labelMono.copyWith(color: accent)),
              const Spacer(),
              if (verdict.overriddenFromLlm)
                Container(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                  decoration: BoxDecoration(
                    color: AmiColors.hexAmber.withValues(alpha: 0.15),
                    borderRadius: BorderRadius.circular(4),
                  ),
                  child: Text(l.roomSafetyFloorPill,
                      style: AmiTypography.labelMono
                          .copyWith(color: AmiColors.hexAmber, fontSize: 9)),
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
                  stanceLabel:
                      l.roomVerdictHeading(_actionLabel(l, verdict.action)),
                  outcome: outcomeFromAction(verdict.action),
                  reason: verdict.reason,
                ),
              ),
            ],
          ),
          const SizedBox(height: AmiSpacing.m),
          if (isApprove) ...[
            _MetricRow(
                label: l.roomMetricTicker, value: ticker, accent: accent),
            _MetricRow(
              label: l.roomMetricSize,
              value: verdict.sizePct == null
                  ? '—'
                  : '${verdict.sizePct!.toStringAsFixed(1)}%',
              accent: accent,
            ),
            _MetricRow(
              label: l.roomMetricEntry,
              value: verdict.entry == null
                  ? '—'
                  : '\$${verdict.entry!.toStringAsFixed(2)}',
              accent: accent,
            ),
            _MetricRow(
              label: l.roomMetricStop,
              value: verdict.stop == null
                  ? '—'
                  : '\$${verdict.stop!.toStringAsFixed(2)}',
              accent: accent,
            ),
            _MetricRow(
              label: l.roomMetricTarget,
              value: verdict.target == null
                  ? '—'
                  : '\$${verdict.target!.toStringAsFixed(2)}',
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
                style: AmiTypography.labelMono
                    .copyWith(fontSize: 11, color: AmiColors.hexAmber)),
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
          // CR098 D3 — the closing disclosure, on EVERY action. An APPROVE
          // reached without Social must still say Social was not in the room;
          // gating this on NO_VERDICT would drop it for the common case, which
          // is the honesty the whole CR exists for. D4: empty list renders
          // nothing at all — no heading, no divider — so an ordinary
          // full-roster run is byte-identical to today's card.
          if (verdict.opinionsNotIncluded.isNotEmpty) ...[
            const SizedBox(height: AmiSpacing.s),
            Text(l.roomVerdictOpinionsHeading,
                style: AmiTypography.labelMono
                    .copyWith(fontSize: 11, color: AmiColors.textLow)),
            const SizedBox(height: 4),
            Text(l.roomVerdictOpinionsNote,
                style:
                    AmiTypography.caption.copyWith(color: AmiColors.textMed)),
            const SizedBox(height: 4),
            for (final id in verdict.opinionsNotIncluded)
              Padding(
                padding: const EdgeInsets.only(bottom: 2),
                child: Text('• ${_analystLabel(id)}',
                    style: AmiTypography.caption),
              ),
          ],
          // CR098 D2 — app chrome, deliberately outside the PM's voice and
          // visually separated from it by the divider above. The PM declines on
          // professional grounds and never sells; the remedy lives here.
          if (isNoVerdict) ...[
            const SizedBox(height: AmiSpacing.m),
            const Divider(height: 1, color: AmiColors.slate700),
            const SizedBox(height: AmiSpacing.s),
            SizedBox(
              width: double.infinity,
              child: OutlinedButton(
                style: OutlinedButton.styleFrom(
                  foregroundColor: AmiColors.hexCyan,
                  side: const BorderSide(color: AmiColors.hexCyan),
                  padding:
                      const EdgeInsets.symmetric(vertical: AmiSpacing.s + 2),
                ),
                onPressed: () => showUpgradeSheet(
                  context,
                  resetDateLabel: _verdictResetDateStr(ref),
                ),
                child: Text(
                  l.roomVerdictIncludeAnalystCta(
                      _analystLabel(_blockingAnalystId(verdict))),
                ),
              ),
            ),
          ],
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
                    const Icon(Icons.check_circle,
                        color: AmiColors.hexGreen, size: 20),
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
                    padding:
                        const EdgeInsets.symmetric(vertical: AmiSpacing.s + 2),
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

/// The board's action footer on the LIVE Room: share, the trade ticket when
/// there is a trade to place, the NO_VERDICT upgrade CTA, and SEE CHART.
///
/// The Journal deliberately gets a different footer — a June entry's `$118.20`
/// is not a live price, and a one-tap ticket against it invites a trade at a
/// stale level (T-STALE).
class _VerdictActions extends ConsumerWidget {
  const _VerdictActions({
    required this.verdict,
    required this.ticker,
    this.runId,
  });

  final RoomVerdict verdict;
  final String ticker;
  final String? runId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l = AppLocalizations.of(context);
    final outcome = outcomeFromAction(verdict.action);
    final trades = ref.watch(simNotifierProvider).trades;
    final existingTrade = runId == null
        ? null
        : trades.where((t) => t.verdictRef == runId).firstOrNull;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        if (verdict.isApprove)
          if (existingTrade != null)
            Container(
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
                  const Icon(Icons.check_circle,
                      color: AmiColors.hexGreen, size: 20),
                  const SizedBox(width: AmiSpacing.s),
                  Text(
                    '${existingTrade.side.toUpperCase()} '
                    '${existingTrade.quantity.toStringAsFixed(0)} '
                    '${existingTrade.ticker} @ '
                    '\$${existingTrade.entryPrice.toStringAsFixed(2)}',
                    style: AmiTypography.labelMono.copyWith(
                      color: AmiColors.hexGreen,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                ],
              ),
            )
          else
            ElevatedButton.icon(
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
        // CR098 D2 — app chrome, deliberately outside the PM's voice. The PM
        // declines on professional grounds and never sells.
        if (verdict.isNoVerdict) ...[
          const SizedBox(height: AmiSpacing.s),
          OutlinedButton(
            style: OutlinedButton.styleFrom(
              foregroundColor: AmiColors.hexCyan,
              side: const BorderSide(color: AmiColors.hexCyan),
              padding: const EdgeInsets.symmetric(vertical: AmiSpacing.s + 2),
            ),
            onPressed: () => showUpgradeSheet(
              context,
              resetDateLabel: _verdictResetDateStr(ref),
            ),
            child: Text(
              l.roomVerdictIncludeAnalystCta(
                  _analystLabel(_blockingAnalystId(verdict))),
            ),
          ),
        ],
        const SizedBox(height: AmiSpacing.s),
        OutlinedButton.icon(
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
        const SizedBox(height: AmiSpacing.s),
        TextButton.icon(
          style: TextButton.styleFrom(foregroundColor: AmiColors.textMed),
          icon: const Icon(Icons.ios_share, size: 18),
          label: Text(l.shareTooltip),
          onPressed: () => ShareService.shareVerdict(
            context,
            ticker: ticker,
            stanceLabel: l.roomVerdictHeading(_actionLabel(l, verdict.action)),
            outcome: outcome,
            reason: verdict.reason,
          ),
        ),
      ],
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
          Text(value, style: AmiTypography.statSmall.copyWith(color: accent)),
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
