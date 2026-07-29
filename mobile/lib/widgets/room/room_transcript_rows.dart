/// CR106 Mode B — the collapsed transcript: one row per agent, expanding in
/// place. Shared by the live Room and the Journal replay (T-TWICE).
///
/// **Extract, never summarise.** At 390pt the row budget leaves ~220pt of gist
/// ≈ 32 Latin characters. That is a fragment, not a sentence, so every gist is
/// either a verbatim quotation, a parsed level triple, or an explicit state —
/// never a truncated sentence. The Bull and Bear prompts explicitly ask for
/// *"thesis + evidence + falsifier"*, and cutting an adversative sentence at 32
/// characters strands the negation and inverts the meaning. A line that looks
/// like a summary but is an artifact of a character count is the DEF059
/// failure class.
///
/// Ranked sources, in order:
///   1. the agent's own `headline` from the CR106 B2 envelope, when it stated
///      one (already length-capped server-side — a too-long one arrives null
///      rather than cut);
///   2. its first `**bold**` span, verbatim — `_PROSE_FORMAT` instructs agents
///      to bold key metrics, so this is the agent's own designated headline
///      number, and being a quotation it cannot be wrong;
///   3. the Trader's level triple, parsed the same way `_LEVEL_PATTERNS` does
///      server-side;
///   4. `NO RESPONSE` for an empty contribution — never a blank row;
///   5. `NOT HEARD` for a withheld analyst.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/agent.dart';
import 'package:ami_trade/models/room_board.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:ami_trade/widgets/hex/hex_avatar.dart';
import 'package:ami_trade/widgets/room/room_board.dart';
import 'package:ami_trade/widgets/sheet_insets.dart';
import 'package:flutter/material.dart';
import 'package:flutter_markdown_plus/flutter_markdown_plus.dart';

/// The runner corrected or verified this agent's arithmetic, or the turn hit
/// its length limit (DEF125) — either way the row is marked and it is the row a
/// reader should be nudged to open. A substring test, and the highest-value bit
/// in the whole transcript.
bool hasAmiAnnotation(String content) => content.contains('[AMI');

/// First `**bold**` span, verbatim.
String? firstBoldSpan(String content) {
  final m = RegExp(r'\*\*(.+?)\*\*', dotAll: true).firstMatch(content);
  final v = m?.group(1)?.trim();
  return (v == null || v.isEmpty) ? null : v;
}

/// The Trader's level triple. Mirrors `room_runner._LEVEL_PATTERNS`; a partial
/// match yields nothing, because two thirds of a setup is not a setup.
String? levelTriple(String content) {
  double? grab(String name) {
    final m = RegExp('$name[^0-9\\-]{0,12}\\\$?\\s*([0-9]+(?:\\.[0-9]+)?)',
            caseSensitive: false)
        .firstMatch(content);
    return m == null ? null : double.tryParse(m.group(1)!);
  }

  final entry = grab('entry');
  final stop = grab('stop');
  final target = grab('target');
  if (entry == null || stop == null || target == null) return null;
  return '\$${entry.toStringAsFixed(2)} → \$${target.toStringAsFixed(2)} '
      'stop \$${stop.toStringAsFixed(2)}';
}

/// The row's one-line gist, by the ranked sources above. Returns null when
/// nothing quotable exists — the caller then renders `NO RESPONSE`.
String? gistFor(RoomVoice voice) {
  if (voice.withheld) return null;
  if (voice.headline != null) return voice.headline;
  final bold = firstBoldSpan(voice.content);
  if (bold != null) return bold;
  return levelTriple(voice.content);
}

class RoomTranscriptRows extends StatefulWidget {
  const RoomTranscriptRows({
    super.key,
    required this.voices,
    this.expandedAgentId,
    this.highlightAgentId,
    this.withheldDetail = const {},
  });

  final List<RoomVoice> voices;

  /// agentId → a richer replacement for that agent's collapsed row.
  ///
  /// A withheld analyst's row would otherwise read `NOT HEARD` and stop there,
  /// which drops CR098 D1's roster countdown — the disclosure that says WHICH
  /// remedy applies (a plan upgrade, not credits) and when the next pull-back
  /// lands. That is monetisation-relevant and it is the thing the CR098 round-1
  /// audit caught going missing on a dropped connection; it must not go missing
  /// again just because the run finished. Supplied by the Room, which has the
  /// countdown; the Journal has no such data and supplies nothing, so its rows
  /// legitimately say `NOT HEARD` and no more.
  final Map<String, Widget> withheldDetail;

  /// Opened programmatically by the peek sheet's `READ THE FULL DEBATE`.
  final String? expandedAgentId;

  /// Briefly tinted so the eye lands after that jump.
  final String? highlightAgentId;

  @override
  State<RoomTranscriptRows> createState() => _RoomTranscriptRowsState();
}

class _RoomTranscriptRowsState extends State<RoomTranscriptRows> {
  final _expanded = <String>{};

  @override
  void initState() {
    super.initState();
    if (widget.expandedAgentId != null) _expanded.add(widget.expandedAgentId!);
  }

  @override
  void didUpdateWidget(RoomTranscriptRows old) {
    super.didUpdateWidget(old);
    final id = widget.expandedAgentId;
    if (id != null && id != old.expandedAgentId) {
      setState(() => _expanded.add(id));
    }
  }

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final byPhase = <RoomPhase, List<RoomVoice>>{};
    for (final v in widget.voices) {
      final phase = kAgentPhase[v.agentId] ?? RoomPhase.analysts;
      byPhase.putIfAbsent(phase, () => []).add(v);
    }
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          l.roomTranscriptHint(widget.voices.length),
          style: AmiTypography.labelMono
              .copyWith(fontSize: 9, color: AmiColors.textLow),
        ),
        for (final phase in RoomPhase.values)
          if (byPhase[phase]?.isNotEmpty ?? false) ...[
            const SizedBox(height: AmiSpacing.m),
            Text(
              phaseLabel(l, phase),
              style: AmiTypography.labelMono
                  .copyWith(fontSize: 10, color: AmiColors.hexBlue),
            ),
            const SizedBox(height: AmiSpacing.xs),
            for (final v in byPhase[phase]!)
              widget.withheldDetail[v.agentId] ??
                  TranscriptRow(
                    voice: v,
                    expanded: _expanded.contains(v.agentId),
                    highlighted: widget.highlightAgentId == v.agentId,
                    onToggle: v.withheld || v.content.isEmpty
                        ? null
                        : () => setState(() {
                              if (!_expanded.remove(v.agentId)) {
                                _expanded.add(v.agentId);
                              }
                            }),
                  ),
          ],
      ],
    );
  }
}

String phaseLabel(AppLocalizations l, RoomPhase phase) {
  switch (phase) {
    case RoomPhase.analysts:
      return l.roomPhaseAnalysts;
    case RoomPhase.researchers:
      return l.roomPhaseResearchers;
    case RoomPhase.synthesis:
      return l.roomPhaseSynthesis;
    case RoomPhase.execution:
      return l.roomPhaseExecution;
    case RoomPhase.risk:
      return l.roomPhaseRisk;
    case RoomPhase.verdict:
      return l.roomPhaseVerdict;
  }
}

class TranscriptRow extends StatelessWidget {
  const TranscriptRow({
    super.key,
    required this.voice,
    required this.expanded,
    this.highlighted = false,
    this.onToggle,
  });

  final RoomVoice voice;
  final bool expanded;
  final bool highlighted;
  final VoidCallback? onToggle;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final agent = agentById(voice.agentId);
    final gist = gistFor(voice);
    final marked = !voice.withheld && hasAmiAnnotation(voice.content);
    return AnimatedContainer(
      duration: AmiMotion.normal,
      curve: AmiMotion.easeOut,
      margin: const EdgeInsets.only(bottom: 2),
      padding: const EdgeInsets.symmetric(vertical: 4, horizontal: 4),
      decoration: BoxDecoration(
        color: highlighted
            ? AmiColors.hexBlue.withValues(alpha: 0.12)
            : Colors.transparent,
        borderRadius: BorderRadius.circular(AmiRadii.card),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          InkWell(
            onTap: onToggle,
            borderRadius: BorderRadius.circular(AmiRadii.card),
            child: Row(
              children: [
                Opacity(
                  opacity: voice.withheld ? 0.35 : 1.0,
                  child: HexAvatar(
                    // The avatar hex carries NO text here: `RES-M` does not fit
                    // in a 28pt hex, and the abbreviation is printed beside it
                    // where it is actually legible (DEF142).
                    label: '',
                    color: agent.color,
                    size: 28,
                    status: HexAvatarStatus.idle,
                  ),
                ),
                const SizedBox(width: AmiSpacing.s),
                SizedBox(
                  width: 46,
                  child: Text(
                    agent.abbreviation,
                    style: AmiTypography.labelMono
                        .copyWith(color: agent.color, fontSize: 10),
                  ),
                ),
                const SizedBox(width: AmiSpacing.s),
                Expanded(
                  child: Text(
                    voice.withheld
                        ? l.roomRowNotHeard
                        : (gist ?? (voice.content.isEmpty
                            ? l.roomRowNoResponse
                            : l.roomRowNoResponse)),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: gist != null
                        ? AmiTypography.statSmall
                            .copyWith(color: AmiColors.textMed)
                        : AmiTypography.labelMono
                            .copyWith(fontSize: 9, color: AmiColors.textLow),
                  ),
                ),
                if (marked) ...[
                  const SizedBox(width: 4),
                  Text('⬢',
                      style: TextStyle(
                          fontSize: 11, color: AmiColors.hexAmber)),
                ],
                const SizedBox(width: 4),
                Icon(
                  onToggle == null
                      ? Icons.remove
                      : (expanded ? Icons.expand_less : Icons.expand_more),
                  size: 16,
                  color: AmiColors.textLow,
                ),
              ],
            ),
          ),
          if (expanded && voice.content.isNotEmpty)
            Padding(
              padding: const EdgeInsets.only(
                  left: 36, top: AmiSpacing.xs, bottom: AmiSpacing.xs),
              child: MarkdownBody(
                data: voice.content,
                shrinkWrap: true,
                styleSheet: agentMarkdownStyle(AmiColors.textMed),
              ),
            ),
        ],
      ),
    );
  }
}

/// Tapping a comb hex → a peek, not a mode switch.
///
/// The destination Saiful asked for (*"switch to transcript and to the agent's
/// exploded transcript"*) is right, but making it the *tap* is not: it loses
/// the board's scroll position for a casual tap on a 26pt mark, and comparison
/// is the normal case — four peeks beats four round trips through the toggle.
/// So the sheet carries that destination as an explicit action instead.
Future<void> showAgentPeekSheet(
  BuildContext context, {
  required RoomVoice voice,
  VoidCallback? onReadFullDebate,
}) {
  final l = AppLocalizations.of(context);
  final agent = agentById(voice.agentId);
  return showModalBottomSheet<void>(
    context: context,
    backgroundColor: AmiColors.slate800,
    isScrollControlled: true,
    shape: const RoundedRectangleBorder(
      borderRadius:
          BorderRadius.vertical(top: Radius.circular(AmiRadii.sheet)),
    ),
    builder: (ctx) {
      final mq = MediaQuery.of(ctx);
      return ConstrainedBox(
        // DEF075 sheet discipline: scrollable body, capped height, bottom
        // padding from `sheetBottomInset` — the guard CR080 flagged
        // `convene_sheet.dart` for missing.
        constraints: BoxConstraints(maxHeight: mq.size.height * 0.72),
        child: SingleChildScrollView(
          padding: EdgeInsets.fromLTRB(
            AmiSpacing.m,
            AmiSpacing.m,
            AmiSpacing.m,
            sheetBottomInset(mq),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisSize: MainAxisSize.min,
            children: [
              Row(
                children: [
                  HexAvatar(
                    label: '',
                    color: agent.color,
                    size: 32,
                    status: HexAvatarStatus.idle,
                  ),
                  const SizedBox(width: AmiSpacing.s),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(agent.displayName,
                            style: AmiTypography.h4),
                        Text(
                          phaseLabel(
                              l, kAgentPhase[voice.agentId] ?? RoomPhase.analysts),
                          style: AmiTypography.labelMono.copyWith(
                              fontSize: 9, color: AmiColors.textLow),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
              if (voice.stance != null) ...[
                const SizedBox(height: AmiSpacing.s),
                Wrap(
                  spacing: 6,
                  children: [
                    _Chip(
                      label: l.roomSheetStance,
                      value: _stanceLabel(l, voice.stance!),
                      color: agent.color,
                    ),
                    if (voice.conviction != null)
                      _Chip(
                        label: l.roomSheetConviction,
                        value: _convictionLabel(l, voice.conviction!),
                        color: agent.color,
                      ),
                  ],
                ),
              ],
              const SizedBox(height: AmiSpacing.m),
              if (voice.withheld || voice.content.isEmpty)
                Text(
                  voice.withheld ? l.roomRowNotHeard : l.roomRowNoResponse,
                  style: AmiTypography.body,
                )
              else
                MarkdownBody(
                  data: voice.content,
                  shrinkWrap: true,
                  styleSheet: agentMarkdownStyle(AmiColors.textMed),
                ),
              // A withheld or empty agent gets NO jump action — a trip to a row
              // that reads NOT HEARD is a wasted one.
              if (!voice.withheld &&
                  voice.content.isNotEmpty &&
                  onReadFullDebate != null) ...[
                const SizedBox(height: AmiSpacing.m),
                SizedBox(
                  width: double.infinity,
                  child: OutlinedButton(
                    style: OutlinedButton.styleFrom(
                      foregroundColor: AmiColors.hexCyan,
                      side: const BorderSide(color: AmiColors.hexCyan),
                    ),
                    onPressed: () {
                      Navigator.of(ctx).pop();
                      onReadFullDebate();
                    },
                    child: Text('${l.roomSheetReadFullDebate} →'),
                  ),
                ),
              ],
            ],
          ),
        ),
      );
    },
  );
}

String _stanceLabel(AppLocalizations l, String stance) => switch (stance) {
      'for' => l.roomStanceFor,
      'against' => l.roomStanceAgainst,
      _ => l.roomStanceNeutral,
    };

String _convictionLabel(AppLocalizations l, String c) => switch (c) {
      'high' => l.roomConvictionHigh,
      'medium' => l.roomConvictionMedium,
      _ => l.roomConvictionLow,
    };

class _Chip extends StatelessWidget {
  const _Chip({required this.label, required this.value, required this.color});
  final String label;
  final String value;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(AmiRadii.sm),
        border: Border.all(color: color.withValues(alpha: 0.5)),
      ),
      child: Text(
        '$label $value',
        style: AmiTypography.labelMono.copyWith(fontSize: 9, color: color),
      ),
    );
  }
}
