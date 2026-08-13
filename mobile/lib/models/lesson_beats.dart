/// CR174 §3 — the fold from a lesson's block list to a beat deck. Pure.
///
/// **The deck is a re-cut of the shipped corpus, not a rewrite of it.** Every
/// word on every card comes from the same `LessonBlock` list book mode renders,
/// which is the distinction that answers CR174's own R1 risk: the rejected
/// CR173 concept F duplicated *every surface*, forever, in three locales. This
/// duplicates one body renderer over one source, so a lesson is authored once
/// and translated per-`id` once. Tightening the prose per card is the education
/// lane's job (CR174 §8, authoring-prompt v4); slicing it is this file's.
///
/// Four properties are load-bearing:
///
///  1. **Document order is preserved.** A deck that reorders a lesson teaches a
///     different lesson, and the reader has no way to tell. Same constraint as
///     CR173's contiguous phase→stage fold, for the same reason.
///  2. **Sections are counted, never matched by name.** `## The trap` is
///     `## الفخ` in Arabic. Anchoring an interaction to heading text would arm
///     it in English and drop it silently in the two locales that ship at v1.0,
///     which is the worst kind of failure — invisible, and only to the users we
///     built the feature for.
///  3. **A heading is a kicker, not a card.** Emitting `## Quiz` as its own
///     card produces an empty beat, which is the placeholder box CR040 forbids.
///  4. **The `<Animation>` is dropped when a play replaces it.** Showing both
///     is the original complaint restated: the decorative visual sitting next to
///     the one that actually carries the lesson.
library;

import 'package:ami_trade/models/lessons.dart';
import 'package:ami_trade/widgets/lessons/interactive_registry.dart';
import 'package:ami_trade/widgets/lessons/lesson_play.dart';
import 'package:flutter/foundation.dart';

enum LessonCardKind {
  /// Prose, straight from the lesson body.
  prose,

  /// Prose the learner commits to seeing before it is shown.
  reveal,

  /// The parameter-bound model.
  play,

  /// A registered `<Animation>` on a lesson with no play of its own.
  animation,

  /// One graded question. Answers still submit as a batch to the server.
  quiz,

  /// The `<ChatWith>` hand-off.
  chat,

  /// The last card: submit the graded answers, then the result panel.
  check,
}

@immutable
class LessonCard {
  const LessonCard({
    required this.kind,
    required this.sectionIndex,
    this.kicker,
    this.markdown = '',
    this.quiz,
    this.animationName,
    this.chatWithAgent,
    this.play,
  });

  final LessonCardKind kind;

  /// `-1` for everything before the first `## ` heading.
  final int sectionIndex;

  /// The section heading, verbatim and already translated, shown above the
  /// first card of its section.
  final String? kicker;

  final String markdown;
  final QuizQuestion? quiz;
  final String? animationName;
  final String? chatWithAgent;
  final LessonPlay? play;

  bool get isInteraction =>
      kind == LessonCardKind.play ||
      kind == LessonCardKind.reveal ||
      kind == LessonCardKind.quiz;
}

/// Words in a card's prose, for the CR's before/after measurement. Counts the
/// text the reader sees, so inline `{{term:…}}` / `{{lesson:…}}` tokens collapse
/// to the one word they render as.
int lessonWordCount(String markdown) {
  final cleaned = markdown
      .replaceAll(RegExp(r'\{\{(?:term|lesson):[a-zA-Z0-9_]+\}\}'), 'x')
      .replaceAll(RegExp(r'[*`>|#-]'), ' ');
  return cleaned.split(RegExp(r'\s+')).where((w) => w.isNotEmpty).length;
}

/// The deck for [lesson]. [spec] is `null` for any lesson interactive mode does
/// not cover — and the caller should not be here at all in that case, because
/// [InteractiveRegistry.has] gates the toggle.
List<LessonCard> cardsFor(Lesson lesson, LessonInteractive? spec) {
  final cards = <LessonCard>[];
  var section = -1;
  String? kicker;
  var playInserted = spec == null;

  void insertPlayIfDue(int nowEntering, {bool force = false}) {
    if (playInserted) return;
    if (!force && nowEntering <= spec!.afterSection) return;
    cards.add(LessonCard(
      kind: LessonCardKind.play,
      sectionIndex: spec!.afterSection,
      play: spec.play,
    ));
    playInserted = true;
  }

  void emitProse(String text) {
    final body = text.trim();
    if (body.isEmpty) return;
    insertPlayIfDue(section);
    final reveal = spec?.revealSections.contains(section) ?? false;
    cards.add(LessonCard(
      kind: reveal ? LessonCardKind.reveal : LessonCardKind.prose,
      sectionIndex: section,
      kicker: kicker,
      markdown: body,
    ));
    kicker = null;
  }

  for (final block in lesson.blocks) {
    switch (block.kind) {
      case LessonBlockKind.markdown:
        final buffer = StringBuffer();
        for (final raw in (block.markdown ?? '').split('\n')) {
          final line = raw.trimRight();
          if (line.startsWith('# ')) {
            // The lesson title. It is already the screen's header; repeating it
            // spends the first card saying nothing.
            emitProse(buffer.toString());
            buffer.clear();
            continue;
          }
          if (line.startsWith('## ')) {
            emitProse(buffer.toString());
            buffer.clear();
            section += 1;
            kicker = line.substring(3).trim();
            continue;
          }
          if (line.trim().isEmpty) {
            emitProse(buffer.toString());
            buffer.clear();
            continue;
          }
          if (buffer.isNotEmpty) buffer.write('\n');
          buffer.write(line);
        }
        emitProse(buffer.toString());
      case LessonBlockKind.animation:
        // Dropped when a play stands in its place — property 4 above.
        if (spec != null) continue;
        insertPlayIfDue(section);
        cards.add(LessonCard(
          kind: LessonCardKind.animation,
          sectionIndex: section,
          kicker: kicker,
          animationName: block.animationName ?? 'unknown',
        ));
        kicker = null;
      case LessonBlockKind.quiz:
        insertPlayIfDue(section);
        cards.add(LessonCard(
          kind: LessonCardKind.quiz,
          sectionIndex: section,
          kicker: kicker,
          quiz: block.quiz,
        ));
        kicker = null;
      case LessonBlockKind.chatWith:
        insertPlayIfDue(section);
        cards.add(LessonCard(
          kind: LessonCardKind.chat,
          sectionIndex: section,
          kicker: kicker,
          chatWithAgent: block.chatWithAgent ?? 'concierge',
        ));
        kicker = null;
      case LessonBlockKind.term:
        // `<Term/>` is inline-tokenised server-side before block extraction, so
        // a standalone term block carries no prose of its own to show.
        continue;
    }
  }

  // `afterSection` is hand-authored per lesson. A number larger than the lesson
  // has sections would otherwise drop the only thing interactive mode exists
  // for — silently, and on that one lesson, which is the hardest kind of gap to
  // notice. Append rather than lose it.
  insertPlayIfDue(section + 1, force: true);

  if (lesson.quizzes.isNotEmpty) {
    cards.add(LessonCard(
      kind: LessonCardKind.check,
      sectionIndex: section,
    ));
  }
  return cards;
}
