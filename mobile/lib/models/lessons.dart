/// Lessons + Agent Academy — client models.
/// Mirrors backend/app/schemas/lessons.py.
library;

class QuizQuestion {
  const QuizQuestion({
    required this.id,
    required this.question,
    required this.options,
    required this.answerIndex,
    this.explanation,
  });

  final String id;
  final String question;
  final List<String> options;
  final int answerIndex;
  final String? explanation;

  factory QuizQuestion.fromJson(Map<String, dynamic> j) {
    return QuizQuestion(
      id: j['id'] as String,
      question: j['question'] as String,
      options: ((j['options'] as List?) ?? const []).cast<String>(),
      answerIndex: ((j['answer_index'] as num?) ?? 0).toInt(),
      explanation: j['explanation'] as String?,
    );
  }
}

enum LessonBlockKind { markdown, quiz, chatWith }

class LessonBlock {
  const LessonBlock({
    required this.kind,
    this.markdown,
    this.quiz,
    this.chatWithAgent,
  });

  final LessonBlockKind kind;
  final String? markdown;
  final QuizQuestion? quiz;
  final String? chatWithAgent;

  factory LessonBlock.fromJson(Map<String, dynamic> j) {
    final kindStr = j['kind'] as String;
    LessonBlockKind kind;
    switch (kindStr) {
      case 'markdown':
        kind = LessonBlockKind.markdown;
        break;
      case 'quiz':
        kind = LessonBlockKind.quiz;
        break;
      case 'chat_with':
        kind = LessonBlockKind.chatWith;
        break;
      default:
        kind = LessonBlockKind.markdown;
    }
    return LessonBlock(
      kind: kind,
      markdown: j['markdown'] as String?,
      quiz: j['quiz'] == null
          ? null
          : QuizQuestion.fromJson(j['quiz'] as Map<String, dynamic>),
      chatWithAgent: j['chat_with_agent'] as String?,
    );
  }
}

class LessonMeta {
  const LessonMeta({
    required this.id,
    required this.title,
    required this.durationMin,
    required this.level,
    required this.track,
    required this.topic,
    required this.prerequisites,
    required this.tags,
    required this.agentCallouts,
  });

  final String id;
  final String title;
  final int durationMin;
  final int level;
  final String track;
  final String topic;
  final List<String> prerequisites;
  final List<String> tags;
  final List<String> agentCallouts;

  factory LessonMeta.fromJson(Map<String, dynamic> j) {
    return LessonMeta(
      id: j['id'] as String,
      title: j['title'] as String,
      durationMin: ((j['duration_min'] as num?) ?? 3).toInt(),
      level: ((j['level'] as num?) ?? 1).toInt(),
      track: j['track'] as String? ?? 'foundations',
      topic: j['topic'] as String? ?? 'general',
      prerequisites: ((j['prerequisites'] as List?) ?? const []).cast<String>(),
      tags: ((j['tags'] as List?) ?? const []).cast<String>(),
      agentCallouts: ((j['agent_callouts'] as List?) ?? const []).cast<String>(),
    );
  }
}

class Lesson {
  const Lesson({
    required this.meta,
    required this.blocks,
    required this.quizzes,
  });

  final LessonMeta meta;
  final List<LessonBlock> blocks;
  final List<QuizQuestion> quizzes;

  factory Lesson.fromJson(Map<String, dynamic> j) {
    return Lesson(
      meta: LessonMeta.fromJson(j['meta'] as Map<String, dynamic>),
      blocks: ((j['blocks'] as List?) ?? const [])
          .map((b) => LessonBlock.fromJson(b as Map<String, dynamic>))
          .toList(),
      quizzes: ((j['quizzes'] as List?) ?? const [])
          .map((q) => QuizQuestion.fromJson(q as Map<String, dynamic>))
          .toList(),
    );
  }
}

class TrackCatalogue {
  const TrackCatalogue({
    required this.track,
    required this.title,
    required this.lessons,
  });

  final String track;
  final String title;
  final List<LessonMeta> lessons;

  factory TrackCatalogue.fromJson(Map<String, dynamic> j) {
    return TrackCatalogue(
      track: j['track'] as String,
      title: j['title'] as String,
      lessons: ((j['lessons'] as List?) ?? const [])
          .map((l) => LessonMeta.fromJson(l as Map<String, dynamic>))
          .toList(),
    );
  }
}

class LessonCatalogue {
  const LessonCatalogue({required this.tracks, required this.totalLessons});

  final List<TrackCatalogue> tracks;
  final int totalLessons;

  factory LessonCatalogue.fromJson(Map<String, dynamic> j) {
    return LessonCatalogue(
      tracks: ((j['tracks'] as List?) ?? const [])
          .map((t) => TrackCatalogue.fromJson(t as Map<String, dynamic>))
          .toList(),
      totalLessons: ((j['total_lessons'] as num?) ?? 0).toInt(),
    );
  }
}

class QuizResultPerQuestion {
  const QuizResultPerQuestion({
    required this.questionId,
    required this.correct,
    required this.correctIndex,
    this.givenIndex,
    this.explanation,
  });

  final String questionId;
  final bool correct;
  final int correctIndex;
  final int? givenIndex;
  final String? explanation;

  factory QuizResultPerQuestion.fromJson(Map<String, dynamic> j) {
    return QuizResultPerQuestion(
      questionId: j['question_id'] as String,
      correct: (j['correct'] as bool?) ?? false,
      correctIndex: ((j['correct_index'] as num?) ?? 0).toInt(),
      givenIndex: j['given_index'] == null ? null : (j['given_index'] as num).toInt(),
      explanation: j['explanation'] as String?,
    );
  }
}

class QuizResult {
  const QuizResult({
    required this.lessonId,
    required this.correct,
    required this.total,
    required this.passed,
    required this.score,
    required this.perQuestion,
    required this.unlockedAgents,
  });

  final String lessonId;
  final int correct;
  final int total;
  final bool passed;
  final double score;
  final List<QuizResultPerQuestion> perQuestion;
  final List<String> unlockedAgents;

  factory QuizResult.fromJson(Map<String, dynamic> j) {
    return QuizResult(
      lessonId: j['lesson_id'] as String,
      correct: ((j['correct'] as num?) ?? 0).toInt(),
      total: ((j['total'] as num?) ?? 0).toInt(),
      passed: (j['passed'] as bool?) ?? false,
      score: ((j['score'] as num?) ?? 0).toDouble(),
      perQuestion: ((j['per_question'] as List?) ?? const [])
          .map((p) => QuizResultPerQuestion.fromJson(p as Map<String, dynamic>))
          .toList(),
      unlockedAgents:
          ((j['unlocked_agents'] as List?) ?? const []).cast<String>(),
    );
  }
}

class AgentActivationRecord {
  const AgentActivationRecord({
    required this.userId,
    required this.agentId,
    required this.activationMethod,
    required this.activatedAt,
    this.triggeringLessonId,
  });

  final String userId;
  final String agentId;
  final String activationMethod;
  final DateTime activatedAt;
  final String? triggeringLessonId;

  factory AgentActivationRecord.fromJson(Map<String, dynamic> j) {
    return AgentActivationRecord(
      userId: j['user_id'] as String,
      agentId: j['agent_id'] as String,
      activationMethod: j['activation_method'] as String,
      activatedAt: DateTime.parse(j['activated_at'] as String),
      triggeringLessonId: j['triggering_lesson_id'] as String?,
    );
  }
}

class ProgressSummary {
  const ProgressSummary({
    required this.userId,
    required this.lessonsCompleted,
    required this.lessonsTotal,
    required this.byTrack,
    required this.agentsUnlocked,
    this.nextRecommendedLesson,
  });

  final String userId;
  final int lessonsCompleted;
  final int lessonsTotal;
  final Map<String, Map<String, int>> byTrack;
  final List<String> agentsUnlocked;
  final String? nextRecommendedLesson;

  factory ProgressSummary.fromJson(Map<String, dynamic> j) {
    final raw = (j['by_track'] as Map?)?.cast<String, dynamic>() ?? const {};
    final byTrack = <String, Map<String, int>>{};
    raw.forEach((k, v) {
      final inner = (v as Map).cast<String, dynamic>();
      byTrack[k] = inner.map((kk, vv) => MapEntry(kk, (vv as num).toInt()));
    });
    return ProgressSummary(
      userId: j['user_id'] as String,
      lessonsCompleted: ((j['lessons_completed'] as num?) ?? 0).toInt(),
      lessonsTotal: ((j['lessons_total'] as num?) ?? 0).toInt(),
      byTrack: byTrack,
      agentsUnlocked:
          ((j['agents_unlocked'] as List?) ?? const []).cast<String>(),
      nextRecommendedLesson: j['next_recommended_lesson'] as String?,
    );
  }
}
