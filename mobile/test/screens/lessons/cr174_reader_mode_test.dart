/// CR174 — the mode dial, the deck, and the RTL gate.
///
/// The three things worth failing a build over:
///
///  - **#8 RTL is a gate, not a follow-up.** A Material `Slider` mirrors under
///    `dir=rtl`; a `CustomPaint` canvas does not, and should not (time axes stay
///    left-to-right in Arabic financial practice). Ship both defaults and the
///    drag inverts silently in Arabic only — the learner drags toward "tighter
///    stop" and the stop loosens. Nothing in English would ever show it.
///  - **CR040 degrade loudly.** A lesson with no interactive assets must not
///    offer an empty interactive mode. The registry is the gate, so the check is
///    "no entry ⇒ no toggle", not "no entry ⇒ a placeholder".
///  - **DEF042's posture on graded answers.** Interactive mode's instant loop
///    belongs to interactions that unlock nothing. A quiz card in the deck still
///    reveals nothing until the server answers.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/lesson_beats.dart';
import 'package:ami_trade/models/lessons.dart';
import 'package:ami_trade/models/mandate.dart';
import 'package:ami_trade/screens/lessons/lesson_beat_deck.dart';
import 'package:ami_trade/screens/lessons/lesson_reader_screen.dart';
import 'package:ami_trade/state/lesson_view_mode_provider.dart';
import 'package:ami_trade/state/lessons_providers.dart';
import 'package:ami_trade/state/mandate_providers.dart';
import 'package:ami_trade/widgets/hex/ami_segment_bar.dart';
import 'package:ami_trade/widgets/lessons/interactive_registry.dart';
import 'package:ami_trade/widgets/lessons/lesson_parameter_play.dart';
import 'package:ami_trade/widgets/lessons/lesson_play.dart';
import 'package:ami_trade/widgets/lessons/lesson_quiz_card.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

const _covered = '014_position_sizing_basics';
const _uncovered = '999_not_in_the_registry';

const _quiz = QuizQuestion(
  id: 'q1',
  question: 'How many shares?',
  options: ['9 shares', '50 shares'],
  answerIndex: 0,
);

LessonMeta _meta(String id) => LessonMeta(
      id: id,
      title: 'Position sizing basics',
      durationMin: 5,
      level: 1,
      track: 'risk_portfolio',
      topic: 'position_sizing',
      prerequisites: const [],
      tags: const [],
      agentCallouts: const [],
    );

Lesson _lesson(String id) => Lesson(
      meta: _meta(id),
      quizzes: const [_quiz],
      blocks: const [
        LessonBlock(
          kind: LessonBlockKind.markdown,
          markdown: '# Position sizing basics\n\nAccount risk in, shares out.',
        ),
        LessonBlock(
            kind: LessonBlockKind.animation, animationName: 'position_size_calc'),
        LessonBlock(
          kind: LessonBlockKind.markdown,
          markdown: '## Example\n\nStop at 459 gives nine shares.\n\n'
              '## The trap\n\nSizing by what feels like a real position.',
        ),
        LessonBlock(kind: LessonBlockKind.markdown, markdown: '## Quiz'),
        LessonBlock(kind: LessonBlockKind.quiz, quiz: _quiz),
      ],
    );

class _FixedReader extends LessonReaderNotifier {
  _FixedReader(super.ref, super.lessonId, LessonReaderState fixed) {
    state = fixed;
  }
}

class _FixedMandate extends MandateNotifier {
  _FixedMandate(super.ref, MandateState fixed) {
    state = fixed;
  }
}

class _FixedLessons extends LessonsNotifier {
  _FixedLessons(super.ref);
}

UserMandate _mandate(String learningStyle) => UserMandate(
      userId: 'u',
      version: 1,
      displayName: 'Trader',
      locale: 'en',
      timezone: 'UTC',
      primaryGoal: 'long_term_wealth',
      horizon: 'long',
      path: 'long_horizon',
      riskScore: 3,
      riskComponents: RiskComponents.fromJson(const {}),
      maxDrawdownPct: 30,
      learningStyle: learningStyle,
      compliance: const ComplianceFlags(),
      plan: 'trial_trader',
      creditBalance: 75,
    );

Future<void> _pumpReader(
  WidgetTester t, {
  required String lessonId,
  String learningStyle = 'quick',
  LessonViewMode? chosen,
}) async {
  await t.binding.setSurfaceSize(const Size(390, 800));
  addTearDown(() => t.binding.setSurfaceSize(null));

  await t.pumpWidget(ProviderScope(
    overrides: [
      lessonReaderProvider(lessonId).overrideWith((ref) => _FixedReader(
            ref,
            lessonId,
            LessonReaderState(lesson: _lesson(lessonId), loading: false),
          )),
      mandateNotifierProvider.overrideWith(
          (ref) => _FixedMandate(ref, MandateState(mandate: _mandate(learningStyle)))),
      lessonsNotifierProvider.overrideWith((ref) => _FixedLessons(ref)),
      lessonViewModeProvider.overrideWith(
          (ref) => LessonViewModeNotifier.withoutHydration(chosen)),
    ],
    child: MaterialApp(
      localizationsDelegates: AppLocalizations.localizationsDelegates,
      supportedLocales: AppLocalizations.supportedLocales,
      home: LessonReaderScreen(lessonId: lessonId),
    ),
  ));
  await t.pump();
}

/// The play from the real registry, so the RTL check runs against a shipped
/// model rather than a fixture that could be built the safe way by accident.
LessonPlay get _realPlay =>
    InteractiveRegistry.forLesson(_covered)!.play;

Future<void> _pumpPlay(WidgetTester t, TextDirection direction) async {
  await t.binding.setSurfaceSize(const Size(390, 800));
  addTearDown(() => t.binding.setSurfaceSize(null));
  await t.pumpWidget(MaterialApp(
    localizationsDelegates: AppLocalizations.localizationsDelegates,
    supportedLocales: AppLocalizations.supportedLocales,
    locale: direction == TextDirection.rtl
        ? const Locale('ar')
        : const Locale('en'),
    home: Directionality(
      textDirection: direction,
      child: Scaffold(
        body: SingleChildScrollView(
          // Keyed by direction so a second pump inside one test rebuilds the
          // state rather than inheriting the value the first drag left behind.
          child: LessonParameterPlay(
            key: ValueKey(direction),
            play: _realPlay,
            caps: LessonPlayCaps.unknown,
          ),
        ),
      ),
    ),
  ));
  await t.pump();
}

/// The stop price the play is currently showing, read off its header readout.
double _shownValue(WidgetTester t) {
  final texts = t
      .widgetList<Text>(find.byType(Text))
      .map((w) => w.data)
      .whereType<String>()
      .where((s) => s.startsWith('\$'));
  return double.parse(texts.first.substring(1).replaceAll(',', ''));
}

/// How far the value moves for a fixed rightward drag, measured **from where
/// the gesture starts**, not from the value the card opened on.
///
/// The difference matters and was found by mutation: a Material `Slider` jumps
/// to the touch point on drag-start, and from this card's initial $459 that
/// jump alone lands above $459. So "the value went up" stays true even when the
/// drag delta is applied backwards, and the RTL check passes through the exact
/// inversion it exists to catch (the DEF190 shape). Reading the value after the
/// jump and before the move isolates the only thing under test.
Future<double> _dragDelta(WidgetTester t) async {
  final g = await t.startGesture(t.getCenter(find.byType(Slider)));
  await t.pump();
  final atTouch = _shownValue(t);
  await g.moveBy(const Offset(80, 0));
  await t.pump();
  final after = _shownValue(t);
  await g.up();
  await t.pump();
  return after - atTouch;
}

void main() {
  group('the toggle is gated on the registry, not on authoring discipline', () {
    testWidgets('a covered lesson offers both modes', (t) async {
      await _pumpReader(t, lessonId: _covered);
      expect(find.byType(AmiSegmentBar), findsOneWidget);
    });

    testWidgets('an uncovered lesson offers none', (t) async {
      await _pumpReader(t, lessonId: _uncovered);
      expect(find.byType(AmiSegmentBar), findsNothing,
          reason: 'CR040 — an empty interactive mode is the placeholder box '
              'the "not enough pictures" complaint was about, restated');
      expect(find.byType(LessonBeatDeck), findsNothing);
    });
  });

  group('the default is derived from the mandate, and a choice outranks it',
      () {
    testWidgets('quick lands on the deck', (t) async {
      await _pumpReader(t, lessonId: _covered, learningStyle: 'quick');
      expect(find.byType(LessonBeatDeck), findsOneWidget,
          reason: 'R3 — daily challenges are shipped, graded and interactive, '
              'and 4 of 172 users found them. Opt-in earns that number');
    });

    testWidgets('story lands on the book', (t) async {
      await _pumpReader(t, lessonId: _covered, learningStyle: 'story');
      expect(find.byType(LessonBeatDeck), findsNothing);
    });

    // Two tests, not one with two pumps: a second `pumpWidget` in the same
    // test reuses the element tree, so the ProviderScope keeps the notifier it
    // already built and the new override is never the thing under test.
    testWidgets('choosing the deck beats a story seed', (t) async {
      await _pumpReader(t,
          lessonId: _covered,
          learningStyle: 'story',
          chosen: LessonViewMode.interactive);
      expect(find.byType(LessonBeatDeck), findsOneWidget);
    });

    testWidgets('choosing the book beats a quick seed', (t) async {
      await _pumpReader(t,
          lessonId: _covered,
          learningStyle: 'quick',
          chosen: LessonViewMode.book);
      expect(find.byType(LessonBeatDeck), findsNothing);
    });

    test('an unreadable stored value is "unset", not a bucket', () {
      // DEF210 — the string outlives the build that wrote it. A future third
      // mode read by this build must fall back to the seed, not be silently
      // recorded as a preference for book.
      expect(resolveLessonViewMode(chosen: null, learningStyle: 'visual'),
          LessonViewMode.interactive);
      expect(resolveLessonViewMode(chosen: null, learningStyle: 'story'),
          LessonViewMode.book);
      expect(defaultLessonViewMode('a-style-this-build-does-not-know'),
          LessonViewMode.interactive);
    });
  });

  testWidgets('the deck opens on the model, not halfway through the body',
      (t) async {
    await _pumpReader(t, lessonId: _covered);
    final cards = cardsFor(
        _lesson(_covered), InteractiveRegistry.forLesson(_covered));
    final firstInteraction = cards.indexWhere((c) => c.isInteraction);
    expect(firstInteraction, lessThanOrEqualTo(1),
        reason: 'the recorded before-state is a first interaction at the 50% '
            'mark of the body');
    // A `PageView` builds only the page in view, so reaching the model is one
    // advance — which is the claim: one, not seven.
    for (var i = 0; i < firstInteraction; i++) {
      await t.tap(find.byIcon(Icons.chevron_right));
      await t.pumpAndSettle();
    }
    expect(find.byType(LessonParameterPlay), findsOneWidget);
  });

  testWidgets('a graded quiz in the deck reveals nothing before the server does',
      (t) async {
    await _pumpReader(t, lessonId: _covered);
    // Walk to the quiz card rather than asserting on the whole deck: PageView
    // builds neighbours, so "the card exists" is not the same as "it is shown".
    final cards = cardsFor(
        _lesson(_covered), InteractiveRegistry.forLesson(_covered));
    final quizIndex = cards.indexWhere((c) => c.kind == LessonCardKind.quiz);
    expect(quizIndex, greaterThan(0));

    final deck = t.state<State<LessonBeatDeck>>(find.byType(LessonBeatDeck));
    for (var i = 0; i < quizIndex; i++) {
      await t.tap(find.byIcon(Icons.chevron_right));
      await t.pumpAndSettle();
    }
    expect(deck.mounted, isTrue);
    final card = t.widget<LessonQuizCard>(find.byType(LessonQuizCard));
    expect(card.revealResult, isFalse,
        reason: 'DEF042 — an unlock-bearing answer is graded server-side, so '
            'the deck may not shortcut it for the instant loop');
  });

  group('acceptance #8 — the control shares its visual\'s direction', () {
    testWidgets('a rightward drag raises the value in en', (t) async {
      await _pumpPlay(t, TextDirection.ltr);
      expect(await _dragDelta(t), greaterThan(0));
    });

    testWidgets('the same drag raises it in ar too', (t) async {
      await _pumpPlay(t, TextDirection.rtl);
      expect(await _dragDelta(t), greaterThan(0),
          reason: 'a Slider mirrors under RTL and a CustomPaint canvas does '
              'not, so an unpinned control inverts the gesture silently, only '
              'in Arabic — CR174 acceptance #8');
    });

    testWidgets('and moves it by the same amount', (t) async {
      await _pumpPlay(t, TextDirection.ltr);
      final ltr = await _dragDelta(t);
      await _pumpPlay(t, TextDirection.rtl);
      expect(await _dragDelta(t), ltr);
    });

    testWidgets('numeric readouts stay LTR inside RTL prose', (t) async {
      await _pumpPlay(t, TextDirection.rtl);
      // `$480 − $459 = $21` reorders under bidi without isolation. Every figure
      // the model produces sits in its own LTR island.
      final islands = t
          .widgetList<Directionality>(find.descendant(
            of: find.byType(LessonParameterPlay),
            matching: find.byType(Directionality),
          ))
          .where((d) => d.textDirection == TextDirection.ltr)
          .length;
      expect(islands, greaterThanOrEqualTo(3),
          reason: 'the control plus the value header plus every readout');
    });
  });
}
