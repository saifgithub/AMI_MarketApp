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


class DailyChallengeWithDate extends Equatable {
  const DailyChallengeWithDate({required this.challenge, required this.date});
  final DailyChallenge challenge;
  final String date; // YYYY-MM-DD

  factory DailyChallengeWithDate.fromJson(Map<String, dynamic> j) =>
      DailyChallengeWithDate(
        challenge:
            DailyChallenge.fromJson(j['challenge'] as Map<String, dynamic>),
        date: j['date'] as String,
      );

  @override
  List<Object?> get props => [challenge.id, date];
}
