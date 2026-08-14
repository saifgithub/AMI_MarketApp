/// CR174 §3 — the beat deck: the same lesson, one objective at a time.
///
/// The measured before-state is a ~620-word scroll with no pictures, nothing to
/// do until the 50% mark, and no feedback until a batch submit at the end. The
/// deck answers the middle two directly — one card at a time, and the model
/// card sits at index 1 — and leaves grading exactly where it was.
///
/// **What this screen does not do, on purpose:**
///
///  - It does not re-author the corpus. Every word comes from the same
///    `LessonBlock` list book mode renders, sliced by [cardsFor]. Tightening
///    prose per card is the education lane's job.
///  - It does not grade. The quiz cards collect selections and the last card
///    submits them together, through the same notifier book mode calls. An
///    instant client-side reveal on a question that moves an agent-unlock gate
///    is the DEF042 shape, and CR174's formative/scored rule exists to keep the
///    two apart.
///  - It does not auto-advance. Nothing on this screen moves without the
///    learner moving it (CR173's carousel finding: a surface that advances on
///    its own is read as broken, and the reader loses their place in a lesson).
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/agent.dart';
import 'package:ami_trade/models/lesson_beats.dart';
import 'package:ami_trade/screens/agent/one_on_one_screen.dart';
import 'package:ami_trade/state/lessons_providers.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:ami_trade/widgets/hex/hex_avatar.dart';
import 'package:ami_trade/widgets/lessons/animation_block.dart';
import 'package:ami_trade/widgets/lessons/lesson_markdown.dart';
import 'package:ami_trade/widgets/lessons/lesson_parameter_play.dart';
import 'package:ami_trade/widgets/lessons/lesson_play.dart';
import 'package:ami_trade/widgets/lessons/lesson_quiz_card.dart';
import 'package:flutter/material.dart';

class LessonBeatDeck extends StatefulWidget {
  const LessonBeatDeck({
    super.key,
    required this.cards,
    required this.state,
    required this.caps,
    required this.onSelect,
    required this.onSubmit,
    required this.onRetry,
    required this.onDone,
  });

  final List<LessonCard> cards;
  final LessonReaderState state;
  final LessonPlayCaps caps;
  final void Function(String questionId, int index) onSelect;
  final VoidCallback onSubmit;
  final VoidCallback onRetry;
  final VoidCallback onDone;

  @override
  State<LessonBeatDeck> createState() => _LessonBeatDeckState();
}

class _LessonBeatDeckState extends State<LessonBeatDeck> {
  final _controller = PageController();
  int _index = 0;

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  void _go(int to) {
    if (to < 0 || to >= widget.cards.length) return;
    _controller.animateToPage(to,
        duration: AmiMotion.normal, curve: AmiMotion.easeOut);
  }

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final total = widget.cards.length;
    if (total == 0) return const SizedBox.shrink();
    final index = _index.clamp(0, total - 1);

    return Column(
      children: [
        _Progress(index: index, total: total),
        Expanded(
          child: PageView.builder(
            controller: _controller,
            itemCount: total,
            onPageChanged: (i) => setState(() => _index = i),
            itemBuilder: (_, i) => SingleChildScrollView(
              padding: const EdgeInsets.fromLTRB(
                  AmiSpacing.m, AmiSpacing.m, AmiSpacing.m, AmiSpacing.l),
              child: _CardView(
                card: widget.cards[i],
                state: widget.state,
                caps: widget.caps,
                onSelect: widget.onSelect,
                onSubmit: widget.onSubmit,
                onRetry: widget.onRetry,
                onDone: widget.onDone,
              ),
            ),
          ),
        ),
        Container(
          padding: const EdgeInsets.symmetric(
              horizontal: AmiSpacing.s, vertical: 4),
          decoration: const BoxDecoration(
            color: AmiColors.glassChrome,
            border: Border(top: BorderSide(color: AmiColors.slate700)),
          ),
          child: Row(
            children: [
              IconButton(
                tooltip: l.lessonDeckBack,
                icon: const Icon(Icons.chevron_left),
                color: index == 0 ? AmiColors.slate600 : AmiColors.textHigh,
                onPressed: index == 0 ? null : () => _go(index - 1),
              ),
              Expanded(
                child: Directionality(
                  textDirection: TextDirection.ltr,
                  child: Text(
                    '${index + 1} / $total',
                    textAlign: TextAlign.center,
                    style: AmiTypography.labelMono
                        .copyWith(fontSize: 11, color: AmiColors.textMed),
                  ),
                ),
              ),
              IconButton(
                tooltip: l.lessonDeckNext,
                icon: const Icon(Icons.chevron_right),
                color: index == total - 1
                    ? AmiColors.slate600
                    : AmiColors.textHigh,
                onPressed:
                    index == total - 1 ? null : () => _go(index + 1),
              ),
            ],
          ),
        ),
      ],
    );
  }
}

class _Progress extends StatelessWidget {
  const _Progress({required this.index, required this.total});
  final int index;
  final int total;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      height: 3,
      child: LinearProgressIndicator(
        value: total == 0 ? 0 : (index + 1) / total,
        backgroundColor: AmiColors.slate800,
        valueColor:
            const AlwaysStoppedAnimation<Color>(AmiColors.hexBlue),
      ),
    );
  }
}

class _CardView extends StatelessWidget {
  const _CardView({
    required this.card,
    required this.state,
    required this.caps,
    required this.onSelect,
    required this.onSubmit,
    required this.onRetry,
    required this.onDone,
  });

  final LessonCard card;
  final LessonReaderState state;
  final LessonPlayCaps caps;
  final void Function(String questionId, int index) onSelect;
  final VoidCallback onSubmit;
  final VoidCallback onRetry;
  final VoidCallback onDone;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        if (card.kicker != null) ...[
          Text(
            card.kicker!.toUpperCase(),
            style: AmiTypography.labelMono
                .copyWith(fontSize: 11, color: AmiColors.hexCyan),
          ),
          const SizedBox(height: AmiSpacing.s),
        ],
        switch (card.kind) {
          LessonCardKind.prose => LessonMarkdown(text: card.markdown),
          LessonCardKind.reveal => _RevealCard(markdown: card.markdown),
          LessonCardKind.play => LessonParameterPlay(
              play: card.play!,
              caps: caps,
            ),
          LessonCardKind.animation =>
            AnimationBlock(name: card.animationName ?? 'unknown'),
          LessonCardKind.quiz => LessonQuizCard(
              question: card.quiz!,
              selected: state.selectedAnswers[card.quiz!.id],
              locked: state.result != null,
              revealResult: state.result != null,
              // DEF294 — same single source as the book reader's card.
              result: state.result?.forQuestion(card.quiz!.id),
              onSelect: (i) => onSelect(card.quiz!.id, i),
            ),
          LessonCardKind.chat => _ChatCard(agentId: card.chatWithAgent!),
          LessonCardKind.check => _CheckCard(
              state: state,
              label: l.lessonDeckCheckHeading,
              onSubmit: onSubmit,
              onRetry: onRetry,
              onDone: onDone,
            ),
        },
      ],
    );
  }
}

/// Commit-then-reveal. The lesson's `## The trap` section is written as a
/// mistake the reader is meant to make first; showing it open is the one way to
/// guarantee they do not.
///
/// Formative and client-side: nothing is scored, nothing is posted, and the
/// text was already in the payload the reader downloaded. Revealing it early
/// costs the learner the beat, not the app the answer.
class _RevealCard extends StatefulWidget {
  const _RevealCard({required this.markdown});
  final String markdown;

  @override
  State<_RevealCard> createState() => _RevealCardState();
}

class _RevealCardState extends State<_RevealCard> {
  bool _shown = false;

  @override
  Widget build(BuildContext context) {
    if (_shown) return LessonMarkdown(text: widget.markdown);
    final l = AppLocalizations.of(context);
    return InkWell(
      onTap: () => setState(() => _shown = true),
      child: Container(
        width: double.infinity,
        padding: const EdgeInsets.symmetric(
            horizontal: AmiSpacing.m, vertical: AmiSpacing.xl),
        decoration: BoxDecoration(
          color: AmiColors.slate800,
          borderRadius: BorderRadius.circular(AmiRadii.card),
          border: Border.all(color: AmiColors.hexAmber),
        ),
        child: Column(
          children: [
            const Icon(Icons.visibility_off,
                color: AmiColors.hexAmber, size: 28),
            const SizedBox(height: AmiSpacing.s),
            Text(
              l.lessonRevealTap,
              style: AmiTypography.labelMono
                  .copyWith(fontSize: 11, color: AmiColors.hexAmber),
            ),
          ],
        ),
      ),
    );
  }
}

class _ChatCard extends StatelessWidget {
  const _ChatCard({required this.agentId});
  final String agentId;

  @override
  Widget build(BuildContext context) {
    final a = agentById(agentId);
    return InkWell(
      onTap: () => Navigator.of(context).push(MaterialPageRoute<void>(
        builder: (_) => OneOnOneScreen(agent: a),
      )),
      child: Container(
        padding: const EdgeInsets.all(AmiSpacing.m),
        decoration: BoxDecoration(
          color: AmiColors.slate800,
          borderRadius: BorderRadius.circular(AmiRadii.card),
          border: Border.all(color: a.color),
        ),
        child: Row(
          children: [
            HexAvatar(label: a.abbreviation, color: a.color, size: 44),
            const SizedBox(width: AmiSpacing.s),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    AppLocalizations.of(context)
                        .lessonReaderChatWith(a.displayName.toUpperCase()),
                    style:
                        AmiTypography.labelMono.copyWith(color: a.color),
                  ),
                  const SizedBox(height: 2),
                  Text(a.tagline, style: AmiTypography.caption),
                ],
              ),
            ),
            Icon(Icons.chevron_right, color: a.color),
          ],
        ),
      ),
    );
  }
}

/// The deck's last card. Same submit, same notifier, same server round trip as
/// book mode — only the placement changed.
class _CheckCard extends StatelessWidget {
  const _CheckCard({
    required this.state,
    required this.label,
    required this.onSubmit,
    required this.onRetry,
    required this.onDone,
  });

  final LessonReaderState state;
  final String label;
  final VoidCallback onSubmit;
  final VoidCallback onRetry;
  final VoidCallback onDone;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    if (state.result != null) {
      return LessonResultPanel(
        result: state.result!,
        onRetry: onRetry,
        onDone: onDone,
      );
    }
    final answered = state.lesson?.quizzes
            .every((q) => state.selectedAnswers.containsKey(q.id)) ??
        false;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(label,
            style: AmiTypography.labelMono
                .copyWith(fontSize: 11, color: AmiColors.hexGreen)),
        const SizedBox(height: AmiSpacing.m),
        SizedBox(
          width: double.infinity,
          child: ElevatedButton(
            style: ElevatedButton.styleFrom(
              backgroundColor: AmiColors.hexGreen,
              foregroundColor: AmiColors.slate900,
              padding: const EdgeInsets.symmetric(vertical: AmiSpacing.m),
            ),
            onPressed: answered ? onSubmit : null,
            child: Text(state.submitting
                ? l.lessonReaderChecking
                : l.lessonReaderSubmitQuiz),
          ),
        ),
      ],
    );
  }
}
