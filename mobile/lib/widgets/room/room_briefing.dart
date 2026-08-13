/// CR173 slice 1 — what the live Room shows by default: four desks, not twelve
/// seats.
///
/// The complaint this answers, measured (research 01): the live Room pins
/// **12 identity marks** from frame one, before the user has been told anything.
/// This surface carries **2** — the working agent's mark on the active row, and
/// whatever a tapped-open desk reveals — and the twelve stay one tap away behind
/// WATCH THE FLOOR, forever.
///
/// **It invents nothing.** Every row, count and state comes from
/// `room_stage.dart`, which folds the six `RoomPhase`s the app already carries
/// into four rows and derives seat states through the same `seatStateFor` the
/// 12-seat roster uses. This file is presentation: it decides what a state looks
/// like, never what it is.
///
/// **The honesty rules it has to keep** (CR173 §5.9): a stage row's four states
/// are the four seat states (DEF059 — a stalled desk must not wear the
/// appearance of a running one, so `interrupted` outranks everything and says
/// so); the desk count's denominator excludes seats that can never report, so a
/// finished desk never reads as one still waiting; and every marker that carries
/// state by fill alone is wrapped in a `Semantics` label naming both the desk
/// and its state (DEF174 — the shipped roster shipped colour-and-motion-only
/// status once already).
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/room_stage.dart';
import 'package:ami_trade/state/room_providers.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:ami_trade/theme/hex_clipper.dart';
import 'package:ami_trade/widgets/room/room_transcript_rows.dart';
import 'package:flutter/material.dart';

class RoomBriefing extends StatefulWidget {
  const RoomBriefing({super.key, required this.state, this.withheldDetail});

  final RoomState state;

  /// CR098 locked chairs, keyed by agent id — rendered in seat, inside the desk
  /// the analyst belongs to. Supplied by the caller so this widget stays free of
  /// the withhold vocabulary, and so the roster and the briefing show the same
  /// chair rather than two descriptions of one absence.
  final Map<String, Widget>? withheldDetail;

  @override
  State<RoomBriefing> createState() => _RoomBriefingState();
}

class _RoomBriefingState extends State<RoomBriefing> {
  /// One desk open at a time. Opening a second while the first stays open turns
  /// a four-row surface back into the twelve-row one it replaced.
  RoomStage? _open;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final stages = stagesFromRoomState(widget.state);

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _ProgressBar(stages: stages),
        const SizedBox(height: AmiSpacing.m),
        for (final view in stages)
          _StageRow(
            view: view,
            state: widget.state,
            expanded: _open == view.stage,
            withheldDetail: widget.withheldDetail,
            onTap: () => setState(
                () => _open = _open == view.stage ? null : view.stage),
          ),
        const SizedBox(height: AmiSpacing.s),
        Text(l.roomBriefingCaption,
            style: AmiTypography.caption.copyWith(color: AmiColors.textLow)),
      ],
    );
  }
}

/// Four hex segments under one clip — DEF146's rule, which is a property of a
/// segmented control and not of the one control it was found on: cutting each
/// segment separately produces four objects with gaps, which is what "the
/// buttons are not hex design" meant.
class _ProgressBar extends StatelessWidget {
  const _ProgressBar({required this.stages});

  final List<RoomStageView> stages;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    return ClipPath(
      clipper: const FlatTopHexagonBarClipper(endInset: 6),
      child: Row(
        children: [
          for (var i = 0; i < stages.length; i++) ...[
            if (i > 0)
              Container(width: 1, height: 6, color: AmiColors.slate900),
            Expanded(
              child: Semantics(
                label: l.roomStageStatusSemantic(
                  _stageName(l, stages[i].stage),
                  _statusWord(l, stages[i].status),
                ),
                child: Container(
                  height: 6,
                  color: _stageColor(stages[i].status),
                ),
              ),
            ),
          ],
        ],
      ),
    );
  }
}

class _StageRow extends StatelessWidget {
  const _StageRow({
    required this.view,
    required this.state,
    required this.expanded,
    required this.onTap,
    this.withheldDetail,
  });

  final RoomStageView view;
  final RoomState state;
  final bool expanded;
  final VoidCallback onTap;
  final Map<String, Widget>? withheldDetail;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final accent = _stageColor(view.status);
    final live = view.status == RoomStageStatus.active;

    return Semantics(
      button: true,
      expanded: expanded,
      child: InkWell(
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.only(bottom: AmiSpacing.m),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Padding(
                padding: const EdgeInsets.only(top: 4, right: AmiSpacing.s),
                // The state marker. Labelled, because a filled dot is exactly
                // the colour-only status DEF174 was filed over.
                child: Semantics(
                  label: l.roomStageStatusSemantic(
                    _stageName(l, view.stage),
                    _statusWord(l, view.status),
                  ),
                  excludeSemantics: true,
                  child: SizedBox(
                    width: 10,
                    height: 10 * 0.8660254, // flat-top regular hexagon
                    child: ClipPath(
                      clipper: const FlatTopRegularHexagon(),
                      child: ColoredBox(color: accent),
                    ),
                  ),
                ),
              ),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      _headingFor(l, view),
                      style: AmiTypography.labelMono.copyWith(
                        fontSize: 11,
                        color: view.status == RoomStageStatus.waiting
                            ? AmiColors.textMed
                            : accent,
                      ),
                    ),
                    const SizedBox(height: 2),
                    // A desk that has not started explains itself; one that is
                    // working shows the work. Showing both at once is how the
                    // row grows back into the wall this replaced.
                    if (expanded)
                      _Members(
                        view: view,
                        state: state,
                        withheldDetail: withheldDetail,
                        full: true,
                      )
                    else if (live || view.status == RoomStageStatus.interrupted)
                      _Members(
                        view: view,
                        state: state,
                        withheldDetail: withheldDetail,
                        full: false,
                      )
                    else
                      Text(_subtitleFor(l, view.stage),
                          style: AmiTypography.caption
                              .copyWith(color: AmiColors.textLow)),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  /// `ANALYST DESK · 2/4 REPORTED`. The count appears once the desk is in play —
  /// on a desk that has not started, `0/4 REPORTED` is noise dressed as data.
  String _headingFor(AppLocalizations l, RoomStageView view) {
    final name = _stageName(l, view.stage);
    if (view.status == RoomStageStatus.waiting) return name;
    return '$name · '
        '${l.roomStageReported(view.reportedCount, view.reportableCount)}';
  }
}

/// The desk's members. Collapsed (`full: false`) this is the streamed line —
/// only the members that have actually done something. Tapped open it is the
/// whole desk, standing-by seats included, which is the answer to "who is on
/// it?" and the reason the twelve are not lost.
class _Members extends StatelessWidget {
  const _Members({
    required this.view,
    required this.state,
    required this.full,
    this.withheldDetail,
  });

  final RoomStageView view;
  final RoomState state;
  final bool full;
  final Map<String, Widget>? withheldDetail;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final seats = full ? view.seats : view.spoken.toList();
    if (seats.isEmpty) {
      return Text(_subtitleFor(l, view.stage),
          style: AmiTypography.caption.copyWith(color: AmiColors.textLow));
    }
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        for (final seat in seats)
          if (seat.seat == RoomSeatState.withheld)
            // CR098's own chair, not a re-description of it. Falls back to the
            // ordinary line if the caller supplied none, rather than dropping
            // the seat.
            withheldDetail?[seat.agentId] ??
                _SeatLine(seat: seat, state: state, full: full)
          else
            _SeatLine(seat: seat, state: state, full: full),
      ],
    );
  }
}

class _SeatLine extends StatelessWidget {
  const _SeatLine({
    required this.seat,
    required this.state,
    required this.full,
  });

  final RoomStageSeat seat;
  final RoomState state;
  final bool full;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final agent = seat.agent;
    final stance = state.agentStances[seat.agentId];
    // DEF125 — a length-stopped turn is marked in the raw text and rendered
    // with the same amber hex on the comb and the roster. A third surface
    // showing it as a clean completion would re-open that defect here.
    final truncated = seat.seat == RoomSeatState.responded &&
        hasAmiAnnotation(state.transcript[seat.agentId] ?? '');

    final String line;
    switch (seat.seat) {
      case RoomSeatState.responded:
        line = stance?.recorded == true
            ? (stance?.headline ?? l.roomCombNotStated)
            : l.roomAgentResponded;
      case RoomSeatState.thinking:
        line = l.roomStageWorking(agent.displayName);
      case RoomSeatState.interrupted:
        line = l.roomAgentInterrupted;
      case RoomSeatState.waiting:
        line = l.roomStandingBy.toUpperCase();
      case RoomSeatState.withheld:
        line = l.roomStandingBy.toUpperCase();
    }

    final colour = switch (seat.seat) {
      RoomSeatState.responded => AmiColors.textMed,
      RoomSeatState.thinking => AmiColors.textHigh,
      RoomSeatState.interrupted => AmiColors.hexRed,
      _ => AmiColors.textLow,
    };

    return Padding(
      padding: const EdgeInsets.only(bottom: 2),
      child: Semantics(
        label: l.roomAgentStatusSemantic(
            agent.displayName, _seatWord(l, seat.seat)),
        child: RichText(
          maxLines: full ? 3 : 2,
          overflow: TextOverflow.ellipsis,
          text: TextSpan(
            style: AmiTypography.caption.copyWith(color: colour),
            children: [
              // Collapsed the line is tight, so the desk's member is named by
              // its abbreviation; opened, by the name a user would say out loud.
              TextSpan(
                text: full ? agent.displayName : agent.abbreviation,
                style: AmiTypography.caption.copyWith(
                    color: agent.color, fontWeight: FontWeight.w600),
              ),
              const TextSpan(text: ' — '),
              TextSpan(text: line),
              if (truncated)
                const TextSpan(
                  text: ' ⬢',
                  style: TextStyle(color: AmiColors.hexAmber, fontSize: 10),
                ),
            ],
          ),
        ),
      ),
    );
  }
}

Color _stageColor(RoomStageStatus status) => switch (status) {
      RoomStageStatus.done => AmiColors.hexGreen,
      RoomStageStatus.active => AmiColors.hexCyan,
      RoomStageStatus.interrupted => AmiColors.hexRed,
      RoomStageStatus.waiting => AmiColors.slate700,
    };

String _stageName(AppLocalizations l, RoomStage stage) => switch (stage) {
      RoomStage.analystDesk => l.roomStageAnalystDesk,
      RoomStage.researchDebate => l.roomStageResearchDebate,
      RoomStage.riskReview => l.roomStageRiskReview,
      RoomStage.pmVerdict => l.roomStagePmVerdict,
    };

String _subtitleFor(AppLocalizations l, RoomStage stage) => switch (stage) {
      RoomStage.analystDesk => l.roomStageAnalystDeskSubtitle,
      RoomStage.researchDebate => l.roomStageResearchDebateSubtitle,
      RoomStage.riskReview => l.roomStageRiskReviewSubtitle,
      RoomStage.pmVerdict => l.roomStagePmVerdictSubtitle,
    };

/// The stage words and the seat words are the SAME four strings, which is what
/// "seat states map 1:1 onto stage-row states" means in practice (§5.9). Two
/// vocabularies for one fact is how a row comes to disagree with the desk
/// inside it.
String _statusWord(AppLocalizations l, RoomStageStatus status) =>
    switch (status) {
      RoomStageStatus.waiting => l.roomStandingBy,
      RoomStageStatus.active => l.roomAgentThinking,
      RoomStageStatus.done => l.roomAgentResponded,
      RoomStageStatus.interrupted => l.roomAgentInterrupted,
    };

String _seatWord(AppLocalizations l, RoomSeatState seat) => switch (seat) {
      RoomSeatState.waiting => l.roomStandingBy,
      RoomSeatState.thinking => l.roomAgentThinking,
      RoomSeatState.responded => l.roomAgentResponded,
      RoomSeatState.interrupted => l.roomAgentInterrupted,
      RoomSeatState.withheld => l.roomStandingBy,
    };
