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

enum LessonBlockKind { markdown, quiz, chatWith, animation, term }

class LessonBlock {
  const LessonBlock({
    required this.kind,
    this.markdown,
    this.quiz,
    this.chatWithAgent,
    this.animationName,
    this.termId,
  });

  final LessonBlockKind kind;
  final String? markdown;
  final QuizQuestion? quiz;
  final String? chatWithAgent;
  final String? animationName;
  final String? termId;

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
      case 'animation':
        kind = LessonBlockKind.animation;
        break;
      case 'term':
        kind = LessonBlockKind.term;
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
      animationName: j['animation_name'] as String?,
      termId: j['term_id'] as String?,
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
    this.code = '',
    this.gatesAgents = const [],
    this.number = 0,
    this.module = 0,
    this.difficulty = 0,
  });

  final String id;
  // CR018: the lesson's canonical reference number (the numeric prefix of
  // `id`, e.g. 23 for "023_support_and_resistance"), derived by the backend.
  // Stable per lesson; 0 for a legacy id with no numeric prefix.
  final int number;
  final String title;
  final int durationMin;
  final int level;
  final String track;
  // CR044: the group-scoped code the user says out loud — "TECH 12", "N&M 22".
  // Authored into the lesson's frontmatter and frozen there, so it stays valid
  // in a chat log or a screenshot long after the corpus grows.
  final String code;
  final String topic;
  final List<String> prerequisites;
  final List<String> tags;
  final List<String> agentCallouts;
  // DEF068: the agents this lesson actually gates — a strict subset of
  // `agentCallouts`. market_analyst is named by 71 lessons and gated by 5, and
  // before this the list couldn't tell them apart.
  final List<String> gatesAgents;
  // `module` + `difficulty` were introduced by the W18 curriculum_map. Older
  // lessons authored before W18 omit them; we default module to 0 and
  // difficulty to the lesson's level so the UI can sort consistently.
  final int module;
  final int difficulty;

  /// CR044 — the badge label. The group-scoped code ("TECH 12") when the
  /// lesson has one; otherwise CR018's zero-padded number, then the level tier.
  /// The fallbacks are for a lesson served by an older backend, not for missing
  /// content: `test_lesson_corpus_integrity` fails the build on an uncoded lesson.
  String get codeLabel => code.isNotEmpty
      ? code
      : (number > 0 ? number.toString().padLeft(3, '0') : 'L$level');

  /// DEF068 — does passing this lesson move an agent-unlock gate forward?
  bool get isGateway => gatesAgents.isNotEmpty;

  factory LessonMeta.fromJson(Map<String, dynamic> j) {
    final level = ((j['level'] as num?) ?? 1).toInt();
    return LessonMeta(
      id: j['id'] as String,
      number: ((j['number'] as num?) ?? 0).toInt(),
      title: j['title'] as String,
      durationMin: ((j['duration_min'] as num?) ?? 3).toInt(),
      level: level,
      track: j['track'] as String? ?? 'foundations',
      code: j['code'] as String? ?? '',
      gatesAgents: ((j['gates_agents'] as List?) ?? const []).cast<String>(),
      topic: j['topic'] as String? ?? 'general',
      prerequisites: ((j['prerequisites'] as List?) ?? const []).cast<String>(),
      tags: ((j['tags'] as List?) ?? const []).cast<String>(),
      agentCallouts: ((j['agent_callouts'] as List?) ?? const []).cast<String>(),
      module: ((j['module'] as num?) ?? 0).toInt(),
      difficulty: ((j['difficulty'] as num?) ?? level).toInt(),
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

/// DEF068 — one lesson in an agent's gateway set, with this user's progress.
class GatewayLessonStatus {
  const GatewayLessonStatus({
    required this.lessonId,
    required this.code,
    required this.title,
    required this.track,
    required this.passed,
  });

  final String lessonId;
  final String code;
  final String title;
  final String track;
  final bool passed;

  factory GatewayLessonStatus.fromJson(Map<String, dynamic> j) {
    return GatewayLessonStatus(
      lessonId: j['lesson_id'] as String,
      code: j['code'] as String? ?? '',
      title: j['title'] as String,
      track: j['track'] as String? ?? 'foundations',
      passed: j['passed'] as bool? ?? false,
    );
  }
}

/// DEF068 — what the user still has to pass to unlock one agent.
///
/// The locked-agent sheet used to work this out locally, filtering the catalogue
/// on `agentCallouts` and taking the first N behind its own copy of the gateway
/// size. That copy silently duplicated a backend constant; this type replaces it.
class AgentUnlockRequirement {
  const AgentUnlockRequirement({
    required this.agentId,
    required this.unlocked,
    required this.required_,
    required this.passedCount,
    required this.remainingCount,
  });

  final String agentId;
  final bool unlocked;
  final List<GatewayLessonStatus> required_;
  final int passedCount;
  final int remainingCount;

  factory AgentUnlockRequirement.fromJson(Map<String, dynamic> j) {
    return AgentUnlockRequirement(
      agentId: j['agent_id'] as String,
      unlocked: j['unlocked'] as bool? ?? false,
      required_: ((j['required'] as List?) ?? const [])
          .map((e) => GatewayLessonStatus.fromJson(e as Map<String, dynamic>))
          .toList(),
      passedCount: ((j['passed_count'] as num?) ?? 0).toInt(),
      remainingCount: ((j['remaining_count'] as num?) ?? 0).toInt(),
    );
  }
}

class LessonStatus {
  const LessonStatus({
    required this.userId,
    required this.lessonId,
    this.startedAt,
    this.completedAt,
    this.quizAttempts = 0,
    this.quizPassed = false,
    this.lastQuizScore,
  });

  final String userId;
  final String lessonId;
  final DateTime? startedAt;
  final DateTime? completedAt;
  final int quizAttempts;
  final bool quizPassed;
  final double? lastQuizScore;

  bool get isInProgress => startedAt != null && !quizPassed;
  bool get isCompleted => quizPassed;

  factory LessonStatus.fromJson(Map<String, dynamic> j) {
    return LessonStatus(
      userId: j['user_id'] as String,
      lessonId: j['lesson_id'] as String,
      startedAt: j['started_at'] != null
          ? DateTime.parse(j['started_at'] as String)
          : null,
      completedAt: j['completed_at'] != null
          ? DateTime.parse(j['completed_at'] as String)
          : null,
      quizAttempts: ((j['quiz_attempts'] as num?) ?? 0).toInt(),
      quizPassed: (j['quiz_passed'] as bool?) ?? false,
      lastQuizScore: (j['last_quiz_score'] as num?)?.toDouble(),
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
