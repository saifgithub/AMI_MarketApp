/// DEF294 — the client half: the reveal reads the server's graded answer, and the
/// question itself cannot carry one.
///
/// The backend stopped shipping `answer_index` / `explanation` on
/// `GET /v1/lessons/{id}`. If the client had kept reading the key off the question, the
/// reveal would silently degrade to "option 0 is always correct" (the old `?? 0` default)
/// — a fix on one side producing a wrong answer on the other. These tests pin that the
/// card is driven by `QuizResultPerQuestion` and by nothing else.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/lessons.dart';
import 'package:ami_trade/widgets/lessons/lesson_quiz_card.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

const _question = QuizQuestion(
  id: 'q1',
  question: 'What does a stop-loss cap?',
  options: ['Upside', 'Downside', 'Volatility'],
);

Widget _host({
  required bool revealResult,
  QuizResultPerQuestion? result,
  int? selected,
}) {
  return MaterialApp(
    localizationsDelegates: AppLocalizations.localizationsDelegates,
    supportedLocales: AppLocalizations.supportedLocales,
    home: Scaffold(
      body: LessonQuizCard(
        question: _question,
        selected: selected,
        locked: revealResult,
        revealResult: revealResult,
        result: result,
        onSelect: (_) {},
      ),
    ),
  );
}

void main() {
  test('a question cannot express an answer key at all', () {
    // Structural: the reveal cannot regress to reading the question, because there is
    // nothing on it to read. Mirrors `LessonQuizPublic` on the server.
    final json = QuizQuestion.fromJson(const {
      'id': 'q1',
      'question': 'q',
      'options': ['a', 'b'],
      // A server that regressed and sent these must not resurrect the old behaviour.
      'answer_index': 1,
      'explanation': 'leaked',
    });
    expect(json.id, 'q1');
    expect(json.options, ['a', 'b']);
    expect(
      json.toString().contains('leaked'),
      isFalse,
      reason: 'the explanation was parsed off the question payload',
    );
  });

  testWidgets('no graded result means nothing is revealed', (tester) async {
    await tester.pumpWidget(_host(revealResult: true, result: null, selected: 0));
    await tester.pumpAndSettle();

    // With no result there is no correct answer to mark, so no verdict iconography.
    expect(find.byIcon(Icons.check_circle), findsNothing);
    expect(find.byIcon(Icons.cancel), findsNothing);
  });

  testWidgets('the revealed answer is the one the SERVER named', (tester) async {
    // The server says option 1 is correct. Option 0 is deliberately the one the old
    // `answer_index ?? 0` default would have marked, so a regression is visible.
    await tester.pumpWidget(_host(
      revealResult: true,
      selected: 0,
      result: const QuizResultPerQuestion(
        questionId: 'q1',
        correct: false,
        correctIndex: 1,
        givenIndex: 0,
        explanation: 'A stop caps the downside.',
      ),
    ));
    await tester.pumpAndSettle();

    expect(find.byIcon(Icons.check_circle), findsOneWidget,
        reason: 'the correct option was not marked');
    expect(find.byIcon(Icons.cancel), findsOneWidget,
        reason: 'the wrong chosen option was not marked');
    expect(find.text('A stop caps the downside.'), findsOneWidget,
        reason: 'the explanation must come from the graded result');
  });

  testWidgets('before submitting, the card gives nothing away', (tester) async {
    await tester.pumpWidget(_host(revealResult: false, selected: 2));
    await tester.pumpAndSettle();

    expect(find.byIcon(Icons.check_circle), findsNothing);
    expect(find.byIcon(Icons.cancel), findsNothing);
    expect(find.byIcon(Icons.radio_button_checked), findsOneWidget);
  });

  test('forQuestion is the single lookup both surfaces share', () {
    // DEF098's shape: the book reader and the beat deck must not each walk perQuestion
    // themselves, or they can disagree about which option was correct.
    const result = QuizResult(
      lessonId: 'L1',
      correct: 1,
      total: 2,
      passed: false,
      score: 0.5,
      perQuestion: [
        QuizResultPerQuestion(
            questionId: 'q1', correct: true, correctIndex: 2, givenIndex: 2),
        QuizResultPerQuestion(
            questionId: 'q2', correct: false, correctIndex: 0, givenIndex: 1),
      ],
      unlockedAgents: [],
    );

    expect(result.forQuestion('q1')?.correctIndex, 2);
    expect(result.forQuestion('q2')?.correctIndex, 0);
    expect(result.forQuestion('nope'), isNull,
        reason: 'an unknown question must be null, never a wrong-but-plausible entry');
  });
}
