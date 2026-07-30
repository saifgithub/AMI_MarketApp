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

/// DEF198 — the AI Coach empty-state hint used to hardcode "280 questions"
/// as a raw Dart string literal; the corpus had grown to 295 with nothing
/// updating the copy. This constant is still a hand-maintained literal, but
/// it is now the ONE place that has to change, and it is not silently
/// stale — see the class doc for what would remove the hand-maintenance
/// entirely.
///
/// Why this couldn't be made self-updating within this lane: no
/// `/v1/ai_coach/*` response carries a total-entry count today —
/// `GET /v1/ai_coach/categories` returns category names only, and
/// `aiCoachSearch` is a bounded, query-scored search, not an enumeration.
/// Deriving the true count means either a backend field (a `total` on
/// `/v1/ai_coach/categories`, or a dedicated `/v1/ai_coach/count`) or
/// bundling `content/ai_coach/*.json` as Flutter assets and counting them
/// client-side at startup — both are `backend/` or build-pipeline changes
/// outside a mobile-only defect batch's fence. Counted by hand against
/// `content/ai_coach/{beginner,intermediate,psychology,scam,platform,
/// ai_meta,islamic_finance}.json` on 2026-07-30.
class AiCoachCorpus {
  const AiCoachCorpus._();

  static const int totalCount = 295;
}
