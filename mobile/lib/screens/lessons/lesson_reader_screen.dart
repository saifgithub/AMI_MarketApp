/// Lesson reader — renders markdown blocks, in-line quiz, ChatWith CTA.
///
/// Plain markdown rendering is intentionally lightweight (no third-party
/// dep). We handle: H1/H2/H3 headings, paragraphs, bullet lists, simple
/// pipe tables, blockquotes, inline **bold** and *italic*. Anything more
/// exotic falls back to mono prose. Good enough for the alpha lessons.
///
/// Quiz blocks render as multiple-choice cards; the reader collects answers,
/// submits to /v1/lessons/quiz, and shows a result panel — pass / fail per
/// question + any newly unlocked agents.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/agent.dart';
import 'package:ami_trade/models/lessons.dart';
import 'package:ami_trade/screens/agent/one_on_one_screen.dart';
import 'package:ami_trade/services/celebration.dart';
import 'package:ami_trade/state/lessons_providers.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:ami_trade/widgets/hex/hex_avatar.dart';
import 'package:ami_trade/widgets/lessons/animation_block.dart';
import 'package:ami_trade/widgets/lessons/term_block.dart';
import 'package:ami_trade/widgets/lessons/term_registry.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

class LessonReaderScreen extends ConsumerStatefulWidget {
  const LessonReaderScreen({
    super.key,
    required this.lessonId,
    this.quizOnly = false,
  });

  final String lessonId;

  /// A19 — When true, the reader hides every markdown / chat_with block and
  /// jumps straight to the quizzes. Wrong-answer explanations still surface
  /// on submit (they're the teaching surface for skippers). A pass in this
  /// mode counts toward agent unlocks identically to a full read+pass.
  final bool quizOnly;

  @override
  ConsumerState<LessonReaderScreen> createState() =>
      _LessonReaderScreenState();
}


class _LessonReaderScreenState extends ConsumerState<LessonReaderScreen> {
  @override
  void initState() {
    super.initState();
    // Kick off the glossary asset load so `<Term/>` chips have data by the
    // time the lesson body finishes streaming in. Idempotent + cached.
    TermRegistry.instance.load().then((_) {
      if (mounted) setState(() {});
    });
  }

  @override
  Widget build(BuildContext context) {
    // Celebration hooks (CR004 B1): quiz pass = meso burst; an unlock in
    // the result escalates to the full-screen major takeover.
    ref.listen(lessonReaderProvider(widget.lessonId), (prev, next) {
      final result = next.result;
      if (prev?.result != null || result == null || !result.passed) return;
      if (result.unlockedAgents.isNotEmpty) {
        Celebrate.major(context, agent: agentById(result.unlockedAgents.first));
      } else {
        Celebrate.meso(context, accent: AmiColors.hexGreen);
      }
    });
    final state = ref.watch(lessonReaderProvider(widget.lessonId));
    final l = AppLocalizations.of(context);
    return Scaffold(
      backgroundColor: AmiColors.slate900,
      body: SafeArea(
        child: Column(
          children: [
            _Header(
              title: state.lesson?.meta.title ?? l.lessonReaderLoading,
              suffix: widget.quizOnly ? l.lessonReaderQuizOnlyBadge : null,
            ),
            Expanded(child: _body(context, ref, state)),
          ],
        ),
      ),
    );
  }

  Widget _body(BuildContext context, WidgetRef ref, LessonReaderState state) {
    if (state.loading) {
      return const Center(child: CircularProgressIndicator());
    }
    if (state.error != null) {
      return Padding(
        padding: const EdgeInsets.all(AmiSpacing.l),
        child: Center(child: Text(state.error!, style: AmiTypography.body)),
      );
    }
    final lesson = state.lesson;
    if (lesson == null) return const SizedBox.shrink();

    final visibleBlocks = widget.quizOnly
        ? lesson.blocks.where((b) => b.kind == LessonBlockKind.quiz).toList()
        : lesson.blocks;

    return ListView(
      padding: const EdgeInsets.all(AmiSpacing.m),
      children: [
        _LessonMetaBar(meta: lesson.meta),
        if (widget.quizOnly) ...[
          const SizedBox(height: AmiSpacing.m),
          _QuizOnlyBanner(quizCount: visibleBlocks.length),
        ],
        const SizedBox(height: AmiSpacing.l),
        for (final block in visibleBlocks) ...[
          _BlockView(
            block: block,
            state: state,
            onSelect: (questionId, idx) => ref
                .read(lessonReaderProvider(widget.lessonId).notifier)
                .selectAnswer(questionId, idx),
          ),
          const SizedBox(height: AmiSpacing.m),
        ],
        const SizedBox(height: AmiSpacing.l),
        if (state.result == null)
          ElevatedButton(
            style: ElevatedButton.styleFrom(
              backgroundColor: AmiColors.hexGreen,
              foregroundColor: AmiColors.slate900,
              padding: const EdgeInsets.symmetric(vertical: AmiSpacing.m),
            ),
            onPressed: ref
                    .read(lessonReaderProvider(widget.lessonId).notifier)
                    .allAnswered
                ? () => ref
                    .read(lessonReaderProvider(widget.lessonId).notifier)
                    .submit()
                : null,
            child: Text(state.submitting
                ? AppLocalizations.of(context).lessonReaderChecking
                : AppLocalizations.of(context).lessonReaderSubmitQuiz),
          )
        else
          _ResultPanel(
            result: state.result!,
            onRetry: () => ref
                .read(lessonReaderProvider(widget.lessonId).notifier)
                .retry(),
            onDone: () => Navigator.of(context).pop(),
          ),
        const SizedBox(height: AmiSpacing.xxl),
      ],
    );
  }
}


class _Header extends StatelessWidget {
  const _Header({required this.title, this.suffix});
  final String title;
  final String? suffix;

  @override
  Widget build(BuildContext context) {
    return Container(
      height: 64,
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
            child: Text(title,
                style: AmiTypography.h4,
                maxLines: 1, overflow: TextOverflow.ellipsis),
          ),
          if (suffix != null)
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
              decoration: BoxDecoration(
                color: AmiColors.slate800,
                borderRadius: BorderRadius.circular(4),
                border: Border.all(color: AmiColors.hexAmber),
              ),
              child: Text(
                suffix!,
                style: AmiTypography.labelMono.copyWith(
                  color: AmiColors.hexAmber, fontSize: 11,
                ),
              ),
            ),
          const SizedBox(width: AmiSpacing.s),
        ],
      ),
    );
  }
}


class _QuizOnlyBanner extends StatelessWidget {
  const _QuizOnlyBanner({required this.quizCount});
  final int quizCount;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    return Container(
      padding: const EdgeInsets.all(AmiSpacing.m),
      decoration: BoxDecoration(
        color: AmiColors.slate800,
        borderRadius: BorderRadius.circular(AmiRadii.card),
        border: Border.all(color: AmiColors.hexAmber),
      ),
      child: Row(
        children: [
          const Icon(Icons.bolt, color: AmiColors.hexAmber),
          const SizedBox(width: AmiSpacing.s),
          Expanded(
            child: Text(
              quizCount == 1
                  ? l.lessonReaderQuizOnlyBannerOne
                  : l.lessonReaderQuizOnlyBannerMany(quizCount),
              style: AmiTypography.caption,
            ),
          ),
        ],
      ),
    );
  }
}


class _LessonMetaBar extends StatelessWidget {
  const _LessonMetaBar({required this.meta});
  final LessonMeta meta;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
          decoration: BoxDecoration(
            color: AmiColors.slate800,
            borderRadius: BorderRadius.circular(4),
            border: Border.all(color: AmiColors.slate700),
          ),
          child: Text('L${meta.level}',
              style: AmiTypography.labelMono.copyWith(fontSize: 11)),
        ),
        const SizedBox(width: AmiSpacing.s),
        Text(
          AppLocalizations.of(context)
              .lessonReaderMetaDurationTrack(meta.durationMin, meta.track),
          style: AmiTypography.caption,
        ),
        const Spacer(),
        for (final id in meta.agentCallouts)
          Padding(
            padding: const EdgeInsets.only(left: 4),
            child: HexAvatar(
              label: agentById(id).abbreviation,
              color: agentById(id).color,
              size: 28,
            ),
          ),
      ],
    );
  }
}


class _BlockView extends StatelessWidget {
  const _BlockView({
    required this.block,
    required this.state,
    required this.onSelect,
  });

  final LessonBlock block;
  final LessonReaderState state;
  final void Function(String questionId, int idx) onSelect;

  @override
  Widget build(BuildContext context) {
    switch (block.kind) {
      case LessonBlockKind.markdown:
        return _MarkdownView(text: block.markdown ?? '');
      case LessonBlockKind.quiz:
        return _QuizCard(
          question: block.quiz!,
          selected: state.selectedAnswers[block.quiz!.id],
          locked: state.result != null,
          revealResult: state.result != null,
          onSelect: (idx) => onSelect(block.quiz!.id, idx),
        );
      case LessonBlockKind.animation:
        return AnimationBlock(name: block.animationName ?? 'unknown');
      case LessonBlockKind.term:
        return Padding(
          padding: const EdgeInsets.symmetric(vertical: 2),
          child: Align(
            alignment: Alignment.centerLeft,
            child: TermBlock(termId: block.termId ?? ''),
          ),
        );
      case LessonBlockKind.chatWith:
        final id = block.chatWithAgent ?? 'concierge';
        final a = agentById(id);
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
                          style: AmiTypography.labelMono.copyWith(color: a.color)),
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
}


/// Lightweight markdown renderer. Handles H1/H2/H3, paragraphs, bullets,
/// pipe tables (very simply), blockquotes, **bold** and *italic*.
class _MarkdownView extends StatelessWidget {
  const _MarkdownView({required this.text});
  final String text;

  @override
  Widget build(BuildContext context) {
    final lines = text.split('\n');
    final widgets = <Widget>[];
    final paraBuffer = StringBuffer();
    final listBuffer = <String>[];
    final tableBuffer = <String>[];

    void flushPara() {
      if (paraBuffer.isEmpty) return;
      widgets.add(_inline(paraBuffer.toString().trim(), AmiTypography.body));
      widgets.add(const SizedBox(height: 10));
      paraBuffer.clear();
    }

    void flushList() {
      if (listBuffer.isEmpty) return;
      for (final item in listBuffer) {
        widgets.add(
          Padding(
            padding: const EdgeInsets.only(left: 8, bottom: 4),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('• ', style: AmiTypography.body.copyWith(color: AmiColors.hexBlue)),
                Expanded(child: _inline(item, AmiTypography.body)),
              ],
            ),
          ),
        );
      }
      widgets.add(const SizedBox(height: 8));
      listBuffer.clear();
    }

    void flushTable() {
      if (tableBuffer.isEmpty) return;
      // Strip alignment row (e.g. |---|---|)
      final rows = tableBuffer
          .where((r) => !RegExp(r'^\s*\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)*\|?\s*$').hasMatch(r))
          .toList();
      if (rows.isEmpty) {
        tableBuffer.clear();
        return;
      }
      final parsed = rows.map((r) {
        var s = r.trim();
        if (s.startsWith('|')) s = s.substring(1);
        if (s.endsWith('|')) s = s.substring(0, s.length - 1);
        return s.split('|').map((c) => c.trim()).toList();
      }).toList();
      widgets.add(
        Container(
          width: double.infinity,
          margin: const EdgeInsets.only(bottom: 12),
          padding: const EdgeInsets.all(AmiSpacing.s),
          decoration: BoxDecoration(
            color: AmiColors.slate800,
            borderRadius: BorderRadius.circular(AmiRadii.card),
            border: Border.all(color: AmiColors.slate700),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              for (int i = 0; i < parsed.length; i++)
                Padding(
                  padding: const EdgeInsets.symmetric(vertical: 3),
                  child: Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      for (final cell in parsed[i])
                        Expanded(
                          child: _inline(
                            cell,
                            i == 0
                                ? AmiTypography.labelMono
                                    .copyWith(color: AmiColors.hexBlue)
                                : AmiTypography.body,
                          ),
                        ),
                    ],
                  ),
                ),
            ],
          ),
        ),
      );
      tableBuffer.clear();
    }

    for (final raw in lines) {
      final l = raw.trimRight();
      if (l.contains('|') && (l.trim().startsWith('|') || l.contains('| '))) {
        flushPara();
        flushList();
        tableBuffer.add(l);
        continue;
      } else if (tableBuffer.isNotEmpty) {
        flushTable();
      }

      if (l.startsWith('# ')) {
        flushPara();
        flushList();
        widgets.add(Padding(
          padding: const EdgeInsets.only(top: 4, bottom: 8),
          child: Text(l.substring(2), style: AmiTypography.h2),
        ));
      } else if (l.startsWith('## ')) {
        flushPara();
        flushList();
        widgets.add(Padding(
          padding: const EdgeInsets.only(top: 8, bottom: 6),
          child: Text(l.substring(3), style: AmiTypography.h3),
        ));
      } else if (l.startsWith('### ')) {
        flushPara();
        flushList();
        widgets.add(Padding(
          padding: const EdgeInsets.only(top: 6, bottom: 4),
          child: Text(l.substring(4), style: AmiTypography.h4),
        ));
      } else if (l.startsWith('- ') || l.startsWith('* ')) {
        flushPara();
        listBuffer.add(l.substring(2));
      } else if (RegExp(r'^\d+\.\s').hasMatch(l)) {
        flushPara();
        listBuffer.add(l.replaceFirst(RegExp(r'^\d+\.\s'), ''));
      } else if (l.startsWith('> ')) {
        flushPara();
        flushList();
        widgets.add(Container(
          margin: const EdgeInsets.symmetric(vertical: 6),
          padding: const EdgeInsets.fromLTRB(12, 8, 12, 8),
          decoration: const BoxDecoration(
            border: Border(left: BorderSide(color: AmiColors.hexBlue, width: 3)),
          ),
          child: _inline(l.substring(2), AmiTypography.body.copyWith(
            fontStyle: FontStyle.italic, color: AmiColors.textMed,
          )),
        ));
      } else if (l.trim().isEmpty) {
        flushPara();
        flushList();
      } else {
        if (paraBuffer.isNotEmpty) paraBuffer.write(' ');
        paraBuffer.write(l);
      }
    }
    flushPara();
    flushList();
    flushTable();

    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: widgets);
  }

  /// Tokenise **bold**, *italic*, `code`, and `{{term:id}}` inline.
  /// Term tokens render as a tappable inline chip via WidgetSpan.
  Widget _inline(String src, TextStyle base) {
    final spans = <InlineSpan>[];
    final pattern = RegExp(
      r'(\*\*[^*]+\*\*|\*[^*]+\*|`[^`]+`|\{\{term:[a-zA-Z0-9_]+\}\})',
    );
    int cursor = 0;
    for (final m in pattern.allMatches(src)) {
      if (m.start > cursor) {
        spans.add(TextSpan(text: src.substring(cursor, m.start), style: base));
      }
      final tok = m.group(0)!;
      if (tok.startsWith('{{term:')) {
        final id = tok.substring(7, tok.length - 2);
        spans.add(WidgetSpan(
          alignment: PlaceholderAlignment.middle,
          child: _InlineTermChip(termId: id, baseStyle: base),
        ));
      } else if (tok.startsWith('**')) {
        spans.add(TextSpan(
          text: tok.substring(2, tok.length - 2),
          style: base.copyWith(fontWeight: FontWeight.w700),
        ));
      } else if (tok.startsWith('*')) {
        spans.add(TextSpan(
          text: tok.substring(1, tok.length - 1),
          style: base.copyWith(fontStyle: FontStyle.italic),
        ));
      } else if (tok.startsWith('`')) {
        spans.add(TextSpan(
          text: tok.substring(1, tok.length - 1),
          style: base.copyWith(fontFamily: AmiTypography.jetBrains),
        ));
      }
      cursor = m.end;
    }
    if (cursor < src.length) {
      spans.add(TextSpan(text: src.substring(cursor), style: base));
    }
    return Text.rich(TextSpan(children: spans));
  }
}


/// Compact inline term chip — same tap target as TermBlock but sized to
/// flow inline with surrounding prose (no padding around the chip itself
/// so line height stays consistent with the paragraph).
class _InlineTermChip extends StatelessWidget {
  const _InlineTermChip({required this.termId, required this.baseStyle});
  final String termId;
  final TextStyle baseStyle;

  @override
  Widget build(BuildContext context) {
    final entry = TermRegistry.instance.get(termId);
    if (entry == null) {
      // Unknown id → render the prettified id inline as bold text.
      return Text(
        TermBlock.fallbackLabel(termId),
        style: baseStyle.copyWith(fontWeight: FontWeight.w700),
      );
    }
    return GestureDetector(
      onTap: () => showTermSheet(context, termId),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 0),
        decoration: BoxDecoration(
          border: Border(
            bottom: BorderSide(color: AmiColors.hexBlue, width: 1),
          ),
        ),
        child: Text(
          entry.term,
          style: baseStyle.copyWith(
            color: AmiColors.hexBlue,
            fontWeight: FontWeight.w600,
          ),
        ),
      ),
    );
  }
}


class _QuizCard extends StatelessWidget {
  const _QuizCard({
    required this.question,
    required this.onSelect,
    required this.selected,
    required this.locked,
    required this.revealResult,
  });

  final QuizQuestion question;
  final int? selected;
  final bool locked;
  final bool revealResult;
  final ValueChanged<int> onSelect;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(AmiSpacing.m),
      decoration: BoxDecoration(
        color: AmiColors.slate800,
        borderRadius: BorderRadius.circular(AmiRadii.card),
        border: Border.all(color: AmiColors.hexGreen),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(AppLocalizations.of(context).lessonReaderQuiz,
              style: AmiTypography.labelMono.copyWith(color: AmiColors.hexGreen)),
          const SizedBox(height: AmiSpacing.s),
          Text(question.question, style: AmiTypography.body),
          const SizedBox(height: AmiSpacing.s),
          for (int i = 0; i < question.options.length; i++)
            Padding(
              padding: const EdgeInsets.only(bottom: 6),
              child: InkWell(
                onTap: locked ? null : () => onSelect(i),
                borderRadius: BorderRadius.circular(AmiRadii.card),
                child: Container(
                  padding: const EdgeInsets.all(AmiSpacing.s),
                  decoration: BoxDecoration(
                    color: _bg(i),
                    borderRadius: BorderRadius.circular(AmiRadii.card),
                    border: Border.all(color: _border(i)),
                  ),
                  child: Row(
                    children: [
                      Icon(_icon(i), color: _border(i), size: 18),
                      const SizedBox(width: AmiSpacing.s),
                      Expanded(child: Text(question.options[i],
                          style: AmiTypography.body)),
                    ],
                  ),
                ),
              ),
            ),
          if (revealResult && question.explanation != null)
            Padding(
              padding: const EdgeInsets.only(top: 6),
              child: Container(
                padding: const EdgeInsets.all(AmiSpacing.s),
                decoration: BoxDecoration(
                  color: AmiColors.slate900,
                  borderRadius: BorderRadius.circular(AmiRadii.card),
                ),
                child: Text(question.explanation!, style: AmiTypography.caption),
              ),
            ),
        ],
      ),
    );
  }

  Color _bg(int i) {
    if (revealResult) {
      if (i == question.answerIndex) return AmiColors.hexGreen.withValues(alpha: 0.15);
      if (i == selected && i != question.answerIndex) {
        return AmiColors.hexRed.withValues(alpha: 0.15);
      }
    }
    if (selected == i) return AmiColors.slate900;
    return AmiColors.slate900;
  }

  Color _border(int i) {
    if (revealResult) {
      if (i == question.answerIndex) return AmiColors.hexGreen;
      if (i == selected && i != question.answerIndex) return AmiColors.hexRed;
    }
    if (selected == i) return AmiColors.hexBlue;
    return AmiColors.slate700;
  }

  IconData _icon(int i) {
    if (revealResult) {
      if (i == question.answerIndex) return Icons.check_circle;
      if (i == selected && i != question.answerIndex) return Icons.cancel;
      return Icons.radio_button_unchecked;
    }
    return selected == i
        ? Icons.radio_button_checked
        : Icons.radio_button_unchecked;
  }
}


class _ResultPanel extends StatelessWidget {
  const _ResultPanel({
    required this.result,
    required this.onRetry,
    required this.onDone,
  });

  final QuizResult result;
  final VoidCallback onRetry;
  final VoidCallback onDone;

  @override
  Widget build(BuildContext context) {
    final passed = result.passed;
    final l = AppLocalizations.of(context);
    return Container(
      padding: const EdgeInsets.all(AmiSpacing.m),
      decoration: BoxDecoration(
        color: AmiColors.slate800,
        borderRadius: BorderRadius.circular(AmiRadii.card),
        border: Border.all(
          color: passed ? AmiColors.hexGreen : AmiColors.hexAmber,
          width: 1.5,
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(
                passed ? Icons.celebration : Icons.replay,
                color: passed ? AmiColors.hexGreen : AmiColors.hexAmber,
                size: 28,
              ),
              const SizedBox(width: AmiSpacing.s),
              Text(passed ? l.lessonReaderPassed : l.lessonReaderNotQuite,
                  style: AmiTypography.labelMono.copyWith(
                      color: passed ? AmiColors.hexGreen : AmiColors.hexAmber)),
            ],
          ),
          const SizedBox(height: AmiSpacing.s),
          Text(l.lessonReaderCorrectOf(result.correct, result.total),
              style: AmiTypography.statMid),
          if (result.unlockedAgents.isNotEmpty) ...[
            const SizedBox(height: AmiSpacing.m),
            Text(l.lessonReaderAgentUnlocked,
                style: AmiTypography.labelMono.copyWith(color: AmiColors.hexAmber)),
            const SizedBox(height: AmiSpacing.s),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                for (final id in result.unlockedAgents)
                  Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      HexAvatar(
                        label: agentById(id).abbreviation,
                        color: agentById(id).color,
                        size: 48,
                      ),
                      const SizedBox(width: 6),
                      Text(agentById(id).displayName,
                          style: AmiTypography.body),
                    ],
                  ),
              ],
            ),
          ],
          const SizedBox(height: AmiSpacing.m),
          Row(
            children: [
              if (!passed)
                Expanded(
                  child: OutlinedButton(
                    style: OutlinedButton.styleFrom(
                      foregroundColor: AmiColors.hexAmber,
                      side: const BorderSide(color: AmiColors.hexAmber),
                    ),
                    onPressed: onRetry,
                    child: Text(l.lessonReaderTryAgain),
                  ),
                ),
              if (!passed) const SizedBox(width: AmiSpacing.s),
              Expanded(
                child: ElevatedButton(
                  style: ElevatedButton.styleFrom(
                    backgroundColor: AmiColors.hexGreen,
                    foregroundColor: AmiColors.slate900,
                  ),
                  onPressed: onDone,
                  child: Text(passed ? l.lessonReaderDone : l.lessonReaderBackToLessons),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}
