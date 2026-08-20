/// Lesson reader — the lesson body, its in-line quiz and the ChatWith CTA, in
/// whichever of CR174's two modes the learner is in.
///
/// **Book mode is the shipped reader, unchanged.** Its block list, its markdown
/// renderer and its batch submit are all exactly what they were; CR174 moved
/// three widgets into `widgets/lessons/` so the beat deck could reuse them
/// rather than fork them, and changed nothing they render.
///
/// **Interactive mode replaces only the body.** The header, the meta bar, the
/// prerequisites row and the quiz round trip are shared. The toggle appears
/// only for a lesson the interactive registry covers — CR040's degrade-loudly
/// clause says an empty interactive mode is worse than no toggle, and CR038
/// says an authoring convention would not be a control, so the registry itself
/// is the gate.
///
/// Quiz blocks render as multiple-choice cards in both modes; the reader
/// collects answers, submits to /v1/lessons/quiz, and shows a result panel —
/// pass / fail per question + any newly unlocked agents.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/agent.dart';
import 'package:ami_trade/models/lesson_beats.dart';
import 'package:ami_trade/models/lessons.dart';
import 'package:ami_trade/screens/agent/one_on_one_screen.dart';
import 'package:ami_trade/screens/lessons/lesson_beat_deck.dart';
import 'package:ami_trade/services/celebration.dart';
import 'package:ami_trade/services/telemetry/telemetry_emitter.dart';
import 'package:ami_trade/state/lesson_view_mode_provider.dart';
import 'package:ami_trade/state/lessons_providers.dart';
import 'package:ami_trade/state/mandate_providers.dart';
import 'package:ami_trade/state/telemetry_providers.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:ami_trade/widgets/hex/ami_segment_bar.dart';
import 'package:ami_trade/widgets/hex/hex_avatar.dart';
import 'package:ami_trade/widgets/lessons/animation_block.dart';
import 'package:ami_trade/widgets/lessons/interactive_registry.dart';
import 'package:ami_trade/widgets/lessons/lesson_markdown.dart';
import 'package:ami_trade/widgets/lessons/lesson_play.dart';
import 'package:ami_trade/widgets/lessons/lesson_quiz_card.dart';
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
    // CR181 — depth segment: opening the reader counts on arrival, whether
    // or not the lesson behind it loads. Fire-and-forget.
    ref.read(telemetryProvider).record(TelemetryEvents.lessonOpen);
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
              // DEF148: the error path clears `loading` without ever giving
              // the screen a title, so a failed load left the bar reading
              // "Loading…" above a wall of stack text about a request that
              // had already finished failing.
              title: state.lesson?.meta.title ??
                  (state.error != null
                      ? l.lessonReaderUnavailableTitle
                      : l.lessonReaderLoading),
              suffix: widget.quizOnly ? l.lessonReaderQuizOnlyBadge : null,
            ),
            if (_offersInteractive(state)) _modeToggle(l),
            Expanded(child: _body(context, ref, state)),
          ],
        ),
      ),
    );
  }

  /// The toggle's only gate.
  ///
  /// A19's quiz-only entry is excluded deliberately: it is already a filtered
  /// mode entered from context, and offering a second mode dial inside it would
  /// stack two answers to "which parts of this lesson am I seeing".
  bool _offersInteractive(LessonReaderState state) =>
      !widget.quizOnly &&
      state.lesson != null &&
      InteractiveRegistry.has(widget.lessonId);

  LessonViewMode _mode() => resolveLessonViewMode(
        chosen: ref.watch(lessonViewModeProvider),
        learningStyle: ref.watch(mandateNotifierProvider).mandate?.learningStyle,
      );

  Widget _modeToggle(AppLocalizations l) {
    final mode = _mode();
    return AmiSegmentBar(
      segments: [
        AmiSegment(label: l.lessonModeBook, semanticsId: 'lesson_mode_book'),
        AmiSegment(
            label: l.lessonModeInteractive,
            semanticsId: 'lesson_mode_interactive'),
      ],
      selected: mode == LessonViewMode.book ? 0 : 1,
      onSelect: (i) => ref.read(lessonViewModeProvider.notifier).setMode(
            i == 0 ? LessonViewMode.book : LessonViewMode.interactive,
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

    if (_offersInteractive(state) && _mode() == LessonViewMode.interactive) {
      final mandate = ref.watch(mandateNotifierProvider).mandate;
      final notifier = ref.read(lessonReaderProvider(widget.lessonId).notifier);
      return LessonBeatDeck(
        cards: cardsFor(lesson, InteractiveRegistry.forLesson(widget.lessonId)),
        state: state,
        // Null mandate → `LessonPlayCaps.unknown`, and every model that would
        // have drawn a ceiling draws none. A cap we cannot read is not a cap we
        // may invent (CR040).
        caps: mandate == null
            ? LessonPlayCaps.unknown
            : LessonPlayCaps(
                singleNameCapPct: mandate.singleNameCapPct,
                maxDrawdownPct: mandate.maxDrawdownPct,
                maxOpenRiskPct: mandate.maxOpenRiskPct,
              ),
        onSelect: notifier.selectAnswer,
        onSubmit: notifier.submit,
        onRetry: notifier.retry,
        onDone: () => Navigator.of(context).pop(),
      );
    }

    final visibleBlocks = widget.quizOnly
        ? lesson.blocks.where((b) => b.kind == LessonBlockKind.quiz).toList()
        : lesson.blocks;

    return ListView(
      padding: const EdgeInsets.all(AmiSpacing.m),
      children: [
        _LessonMetaBar(meta: lesson.meta),
        _PrerequisitesRow(prerequisites: lesson.meta.prerequisites),
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
          LessonResultPanel(
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
          // CR044 — the group-scoped code ("TECH 12"); level tier trails the
          // duration meta line below.
          child: Text(meta.codeLabel,
              style: AmiTypography.labelMono.copyWith(
                  fontSize: 11, color: AmiColors.hexCyan)),
        ),
        const SizedBox(width: AmiSpacing.s),
        // The track used to be interpolated here straight from the API, so this
        // line showed users a raw `risk_portfolio`. The code carries the track
        // now, legibly, so the duplicate is gone rather than relabelled.
        Text(
          '${AppLocalizations.of(context).lessonsDurationMin(meta.durationMin)} · L${meta.level}',
          style: AmiTypography.caption,
        ),
        const Spacer(),
        for (final id in meta.agentCallouts)
          Padding(
            padding: const EdgeInsetsDirectional.only(start: 4),
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
        return LessonMarkdown(text: block.markdown ?? '');
      case LessonBlockKind.quiz:
        return LessonQuizCard(
          question: block.quiz!,
          selected: state.selectedAnswers[block.quiz!.id],
          locked: state.result != null,
          revealResult: state.result != null,
          // DEF294 — the reveal's answer key comes from the graded response, not
          // from the question, which no longer carries one.
          result: state.result?.forQuestion(block.quiz!.id),
          onSelect: (idx) => onSelect(block.quiz!.id, idx),
        );
      case LessonBlockKind.animation:
        return AnimationBlock(name: block.animationName ?? 'unknown');
      case LessonBlockKind.term:
        return Padding(
          padding: const EdgeInsets.symmetric(vertical: 2),
          child: Align(
            alignment: AlignmentDirectional.centerStart,
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


/// CR053 — the lesson's `prerequisites` (already parsed into `LessonMeta`,
/// never surfaced before). Renders nothing when the list is empty. Each
/// prereq is a tappable chip (code + title) that deep-links into that
/// lesson's reader; an id absent from the catalogue degrades to plain text
/// (CR040), never a dead tap.
class _PrerequisitesRow extends ConsumerWidget {
  const _PrerequisitesRow({required this.prerequisites});
  final List<String> prerequisites;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    if (prerequisites.isEmpty) return const SizedBox.shrink();
    final catalogue = ref.watch(lessonsNotifierProvider).catalogue;
    final l = AppLocalizations.of(context);
    return Padding(
      padding: const EdgeInsets.only(top: AmiSpacing.s),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            l.lessonReaderPrerequisites,
            style: AmiTypography.labelMono
                .copyWith(color: AmiColors.textLow, fontSize: 11),
          ),
          const SizedBox(height: 4),
          Wrap(
            spacing: 6,
            runSpacing: 6,
            children: [
              for (final id in prerequisites)
                _PrerequisiteChip(
                  lessonId: id,
                  meta: findLessonMetaById(catalogue, id),
                ),
            ],
          ),
        ],
      ),
    );
  }
}

class _PrerequisiteChip extends StatelessWidget {
  const _PrerequisiteChip({required this.lessonId, required this.meta});
  final String lessonId;
  final LessonMeta? meta;

  @override
  Widget build(BuildContext context) {
    if (meta == null) {
      return Text(lessonId, style: AmiTypography.caption);
    }
    final m = meta!;
    return GestureDetector(
      onTap: () => Navigator.of(context).push(MaterialPageRoute<void>(
        builder: (_) => LessonReaderScreen(lessonId: m.id),
      )),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
        decoration: BoxDecoration(
          color: AmiColors.slate800,
          borderRadius: BorderRadius.circular(4),
          border: Border.all(color: AmiColors.hexCyan),
        ),
        child: Text(
          '${m.codeLabel} · ${m.title}',
          style: AmiTypography.caption.copyWith(color: AmiColors.hexCyan),
        ),
      ),
    );
  }
}
