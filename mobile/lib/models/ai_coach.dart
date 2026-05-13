/// AI Coach Q&A models — categorised knowledge base entries surfaced
/// via /v1/ai_coach/* endpoints.
library;

import 'package:equatable/equatable.dart';

class CoachQA extends Equatable {
  const CoachQA({
    required this.id,
    required this.category,
    required this.question,
    required this.shortAnswer,
    required this.longAnswer,
    this.relatedLessons = const [],
    this.relatedAgents = const [],
    this.tags = const [],
  });

  final String id;
  final String category;
  final String question;
  final String shortAnswer;
  final String longAnswer;
  final List<String> relatedLessons;
  final List<String> relatedAgents;
  final List<String> tags;

  factory CoachQA.fromJson(Map<String, dynamic> j) => CoachQA(
        id: j['id'] as String,
        category: j['category'] as String,
        question: j['question'] as String,
        shortAnswer: j['short_answer'] as String,
        longAnswer: j['long_answer'] as String,
        relatedLessons:
            List<String>.from((j['related_lessons'] as List?) ?? const []),
        relatedAgents:
            List<String>.from((j['related_agents'] as List?) ?? const []),
        tags: List<String>.from((j['tags'] as List?) ?? const []),
      );

  @override
  List<Object?> get props => [id];
}


class CoachSearchHit extends Equatable {
  const CoachSearchHit({required this.qa, required this.score});
  final CoachQA qa;
  final int score;

  factory CoachSearchHit.fromJson(Map<String, dynamic> j) => CoachSearchHit(
        qa: CoachQA.fromJson(j['qa'] as Map<String, dynamic>),
        score: j['score'] as int,
      );

  @override
  List<Object?> get props => [qa.id, score];
}
