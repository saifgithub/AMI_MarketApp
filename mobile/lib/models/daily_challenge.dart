/// DailyChallenge — one daily prediction/scenario question with options
/// and an explanation that surfaces after the user submits.
library;

import 'package:equatable/equatable.dart';

class DailyChallenge extends Equatable {
  const DailyChallenge({
    required this.id,
    required this.type,
    required this.difficulty,
    required this.locale,
    required this.scenario,
    required this.question,
    required this.options,
    required this.answer,
    required this.explanation,
    this.relatedLesson,
    this.relatedAgent,
    this.tags = const [],
  });

  final String id;
  final String type;
  final int difficulty;
  final String locale;
  final String scenario;
  final String question;
  final List<String> options;
  final int answer;
  final String explanation;
  final String? relatedLesson;
  final String? relatedAgent;
  final List<String> tags;

  factory DailyChallenge.fromJson(Map<String, dynamic> j) => DailyChallenge(
        id: j['id'] as String,
        type: j['type'] as String,
        difficulty: j['difficulty'] as int,
        locale: j['locale'] as String? ?? 'en',
        scenario: j['scenario'] as String,
        question: j['question'] as String,
        options: List<String>.from(j['options'] as List),
        answer: j['answer'] as int,
        explanation: j['explanation'] as String,
        relatedLesson: j['related_lesson'] as String?,
        relatedAgent: j['related_agent'] as String?,
        tags: List<String>.from((j['tags'] as List?) ?? const []),
      );

  @override
  List<Object?> get props => [id];
}


/// CR010 (B5) — the caller's stored attempt for today's challenge, from
/// `GET /today`'s `my_attempt`. Null when unauthenticated or unanswered.
class MyAttempt extends Equatable {
  const MyAttempt({
    required this.selectedOption,
    required this.correct,
    required this.attemptedAt,
  });

  final int selectedOption;
  final bool correct;
  final String attemptedAt; // ISO 8601

  factory MyAttempt.fromJson(Map<String, dynamic> j) => MyAttempt(
        selectedOption: (j['selected_option'] as num).toInt(),
        correct: j['correct'] as bool,
        attemptedAt: j['attempted_at'] as String? ?? '',
      );

  @override
  List<Object?> get props => [selectedOption, correct, attemptedAt];
}


class DailyChallengeWithDate extends Equatable {
  const DailyChallengeWithDate({
    required this.challenge,
    required this.date,
    this.myAttempt,
  });

  final DailyChallenge challenge;
  final String date; // YYYY-MM-DD
  final MyAttempt? myAttempt; // CR010 (B5): server-truth prior attempt

  factory DailyChallengeWithDate.fromJson(Map<String, dynamic> j) =>
      DailyChallengeWithDate(
        challenge:
            DailyChallenge.fromJson(j['challenge'] as Map<String, dynamic>),
        date: j['date'] as String,
        myAttempt: j['my_attempt'] == null
            ? null
            : MyAttempt.fromJson(j['my_attempt'] as Map<String, dynamic>),
      );

  @override
  List<Object?> get props => [challenge.id, date, myAttempt];
}


/// `POST /v1/daily_challenge/{id}/attempt` response — server-graded result.
/// `alreadyAttempted` is true when the challenge was answered before; the
/// result then reflects the STORED attempt, not a re-grade of the new answer.
class DailyChallengeAttemptResult extends Equatable {
  const DailyChallengeAttemptResult({
    required this.correct,
    required this.correctOption,
    required this.explanation,
    required this.selectedOption,
    required this.alreadyAttempted,
    this.relatedLesson,
    this.relatedAgent,
  });

  final bool correct;
  final int correctOption;
  final String explanation;
  final int selectedOption;
  final bool alreadyAttempted;
  final String? relatedLesson;
  final String? relatedAgent;

  factory DailyChallengeAttemptResult.fromJson(Map<String, dynamic> j) =>
      DailyChallengeAttemptResult(
        correct: j['correct'] as bool? ?? false,
        correctOption: (j['correct_option'] as num?)?.toInt() ?? 0,
        explanation: j['explanation'] as String? ?? '',
        selectedOption: (j['selected_option'] as num?)?.toInt() ?? 0,
        alreadyAttempted: j['already_attempted'] as bool? ?? false,
        relatedLesson: j['related_lesson'] as String?,
        relatedAgent: j['related_agent'] as String?,
      );

  @override
  List<Object?> get props =>
      [correct, correctOption, selectedOption, alreadyAttempted];
}
