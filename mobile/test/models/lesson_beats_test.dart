/// CR174 §3 — the block-list → beat-deck fold.
///
/// The interesting failures are all silent ones: a deck that quietly reorders a
/// lesson, an interaction that arms in English and vanishes in Arabic, an empty
/// card where a heading was, or a play card that never gets inserted because the
/// lesson's shape was one section shorter than the author assumed.
library;

import 'package:ami_trade/models/lesson_beats.dart';
import 'package:ami_trade/models/lessons.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:ami_trade/widgets/lessons/anim/balance_scale_painter.dart';
import 'package:ami_trade/widgets/lessons/interactive_registry.dart';
import 'package:ami_trade/widgets/lessons/lesson_play.dart';
import 'package:flutter_test/flutter_test.dart';

const _meta = LessonMeta(
  id: 'x',
  title: 'X',
  durationMin: 5,
  level: 1,
  track: 'risk_portfolio',
  topic: 't',
  prerequisites: [],
  tags: [],
  agentCallouts: [],
);

const _q1 = QuizQuestion(id: 'q1', question: 'Q one?', options: ['a', 'b']);
const _q2 = QuizQuestion(id: 'q2', question: 'Q two?', options: ['a', 'b']);

/// The shape every pilot lesson actually has, verified against
/// `content/lessons/014_position_sizing_basics.en.mdx`: an H1 + intro, an
/// `<Animation>`, two prose sections, a `<ChatWith>`, an empty `## Quiz`
/// heading, two `<Quiz>` blocks, then two more prose sections.
Lesson _lesson({String heading1 = 'Example', String heading2 = 'The trap'}) =>
    Lesson(
      meta: _meta,
      quizzes: const [_q1, _q2],
      blocks: [
        const LessonBlock(
          kind: LessonBlockKind.markdown,
          markdown: '# X\n\nIntro paragraph one.',
        ),
        const LessonBlock(
            kind: LessonBlockKind.animation, animationName: 'position_size_calc'),
        LessonBlock(
          kind: LessonBlockKind.markdown,
          markdown: '## $heading1\n\nWorked example.\n\nSecond paragraph.\n\n'
              '## $heading2\n\nThe mistake.',
        ),
        const LessonBlock(
            kind: LessonBlockKind.chatWith, chatWithAgent: 'portfolio_manager'),
        const LessonBlock(kind: LessonBlockKind.markdown, markdown: '## Quiz'),
        const LessonBlock(kind: LessonBlockKind.quiz, quiz: _q1),
        const LessonBlock(kind: LessonBlockKind.quiz, quiz: _q2),
        const LessonBlock(
          kind: LessonBlockKind.markdown,
          markdown: '## Try it\n\nGo and do it.\n\n## Takeaway\n\nThe close.',
        ),
      ],
    );

final _play = LessonPlay(
  accent: AmiColors.hexCyan,
  controlLabel: 'STOP',
  min: 0,
  max: 10,
  step: 1,
  initial: 5,
  formatValue: (v) => v.toStringAsFixed(0),
  build: (v, caps) => LessonPlayFrame(
    painter: (t, th) => BalanceScalePainter(
      t: t,
      theme: th,
      leftLabel: 'L',
      leftValue: v,
      rightLabel: 'R',
      rightValue: 10 - v,
    ),
    readouts: const [PlayReadout('V', 'x')],
  ),
);

void main() {
  test('the H1 is dropped — it is already the screen title', () {
    final cards = cardsFor(_lesson(), null);
    expect(cards.map((c) => c.markdown).join(), isNot(contains('# X')));
    expect(cards.first.markdown, 'Intro paragraph one.');
  });

  test('a heading is a kicker on the next card, never a card of its own', () {
    final cards = cardsFor(_lesson(), null);
    // `## Quiz` has no prose beneath it. Emitting it would produce the empty
    // placeholder card CR040 forbids; it has to ride on the first quiz.
    expect(cards.where((c) => c.markdown.trim().isEmpty && c.kind == LessonCardKind.prose),
        isEmpty);
    final firstQuiz = cards.firstWhere((c) => c.kind == LessonCardKind.quiz);
    expect(firstQuiz.kicker, 'Quiz');
  });

  test('document order is preserved', () {
    final cards = cardsFor(_lesson(), null);
    final kinds = cards.map((c) => c.kind).toList();
    expect(
      kinds,
      const [
        LessonCardKind.prose, // intro
        LessonCardKind.animation,
        LessonCardKind.prose, // Example p1
        LessonCardKind.prose, // Example p2
        LessonCardKind.prose, // The trap
        LessonCardKind.chat,
        LessonCardKind.quiz,
        LessonCardKind.quiz,
        LessonCardKind.prose, // Try it
        LessonCardKind.prose, // Takeaway
        LessonCardKind.check,
      ],
      reason: 'a deck that reorders a lesson teaches a different lesson, and '
          'the reader has no way to tell it happened',
    );
  });

  test('sections are counted, not matched by heading text', () {
    // The same lesson under Arabic headings must fold identically — this is
    // the whole reason the registry anchors on an index. A text match would
    // arm the interaction in English and silently drop it in the two locales
    // that ship at v1.0.
    final en = cardsFor(_lesson(), null);
    final ar = cardsFor(_lesson(heading1: 'مثال', heading2: 'الفخ'), null);
    expect(ar.map((c) => c.kind).toList(), en.map((c) => c.kind).toList());
    expect(ar.map((c) => c.sectionIndex).toList(),
        en.map((c) => c.sectionIndex).toList());
  });

  test('the play lands at card index 1, and the animation it replaces goes',
      () {
    final cards = cardsFor(
        _lesson(), LessonInteractive(play: _play, revealSections: const {1}));
    expect(cards[1].kind, LessonCardKind.play,
        reason: 'acceptance #2 — the measured before-state is a first '
            'interaction at the 50% mark of the body');
    expect(cards.where((c) => c.kind == LessonCardKind.animation), isEmpty,
        reason: 'the decorative visual sitting beside the one that carries '
            'the lesson is the original complaint restated');
  });

  test('only the declared section is hidden behind a reveal', () {
    final cards = cardsFor(
        _lesson(), LessonInteractive(play: _play, revealSections: const {1}));
    final reveals = cards.where((c) => c.kind == LessonCardKind.reveal);
    expect(reveals, hasLength(1));
    expect(reveals.single.sectionIndex, 1);
    expect(reveals.single.markdown, 'The mistake.');
  });

  test('a play anchored past the last section still gets inserted', () {
    // Not hypothetical: `afterSection` is hand-authored per lesson, and a
    // number one larger than the lesson has sections would otherwise drop the
    // only thing interactive mode exists for — silently, on that lesson alone.
    final cards = cardsFor(
        _lesson(), LessonInteractive(play: _play, afterSection: 99));
    expect(cards.where((c) => c.kind == LessonCardKind.play), hasLength(1));
  });

  test('a lesson with no quiz gets no check card', () {
    final cards = cardsFor(
      Lesson(meta: _meta, quizzes: const [], blocks: [
        const LessonBlock(
            kind: LessonBlockKind.markdown, markdown: '# X\n\nOnly prose.'),
      ]),
      null,
    );
    expect(cards.where((c) => c.kind == LessonCardKind.check), isEmpty);
  });

  test('the word counter reads what the reader sees', () {
    // Inline `{{term:…}}` tokens render as one word, so counting the raw token
    // would inflate the per-card figure acceptance #2 is measured against.
    expect(lessonWordCount('Open the {{term:ami_mandate}} editor now.'), 5);
    expect(lessonWordCount('**Bold** and *italic* words'), 4);
  });

  group('the registry is anchored to lessons that exist in the shape it '
      'assumes', () {
    for (final id in InteractiveRegistry.registeredLessonIds) {
      test(id, () {
        final spec = InteractiveRegistry.forLesson(id)!;
        expect(spec.afterSection, greaterThanOrEqualTo(-1));
        expect(spec.play.min, lessThan(spec.play.max));
        expect(spec.play.initial,
            inInclusiveRange(spec.play.min, spec.play.max),
            reason: 'the control opens on the lesson\'s own worked example; '
                'an initial outside the range silently clamps to an edge');
        expect(spec.play.divisions, greaterThan(1));
        for (final s in spec.revealSections) {
          expect(s, greaterThanOrEqualTo(0));
        }
      });
    }
  });
}
