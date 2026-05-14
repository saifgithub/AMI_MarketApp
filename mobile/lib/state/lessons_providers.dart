/// Riverpod state for Lessons + Agent Academy progress.
library;

import 'package:ami_trade/models/lessons.dart';
import 'package:ami_trade/services/device_user.dart';
import 'package:ami_trade/state/onboarding_providers.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

@immutable
class LessonsState {
  const LessonsState({
    this.catalogue,
    this.progress,
    this.activations = const [],
    this.lessonStatuses = const {},
    this.loading = false,
    this.error,
  });

  final LessonCatalogue? catalogue;
  final ProgressSummary? progress;
  final List<AgentActivationRecord> activations;
  /// Per-lesson status keyed by lessonId. Empty until the first refresh completes.
  final Map<String, LessonStatus> lessonStatuses;
  final bool loading;
  final String? error;

  Set<String> get unlockedAgentIds =>
      {for (final a in activations) a.agentId};

  bool isLessonCompleted(String lessonId) =>
      lessonStatuses[lessonId]?.quizPassed ?? false;

  bool isLessonInProgress(String lessonId) =>
      lessonStatuses[lessonId]?.isInProgress ?? false;

  LessonsState copyWith({
    LessonCatalogue? catalogue,
    ProgressSummary? progress,
    List<AgentActivationRecord>? activations,
    Map<String, LessonStatus>? lessonStatuses,
    bool? loading,
    String? error,
    bool clearError = false,
  }) {
    return LessonsState(
      catalogue: catalogue ?? this.catalogue,
      progress: progress ?? this.progress,
      activations: activations ?? this.activations,
      lessonStatuses: lessonStatuses ?? this.lessonStatuses,
      loading: loading ?? this.loading,
      error: clearError ? null : (error ?? this.error),
    );
  }
}

class LessonsNotifier extends StateNotifier<LessonsState> {
  LessonsNotifier(this._ref) : super(const LessonsState());

  final Ref _ref;

  Future<void> refresh() async {
    state = state.copyWith(loading: true, clearError: true);
    try {
      final api = _ref.read(apiClientProvider);
      final userId = await DeviceUser.getOrCreate();
      final cat = await api.lessonCatalogue();
      final prog = await api.lessonsProgress(userId);
      final acts = await api.agentActivations(userId);
      final statuses = await api.lessonStatusByLesson(userId);
      state = state.copyWith(
        catalogue: cat,
        progress: prog,
        activations: acts,
        lessonStatuses: statuses,
        loading: false,
      );
    } catch (e) {
      state = state.copyWith(loading: false, error: 'Could not load lessons: $e');
    }
  }
}

final lessonsNotifierProvider =
    StateNotifierProvider<LessonsNotifier, LessonsState>((ref) {
  final n = LessonsNotifier(ref);
  Future.microtask(n.refresh);
  return n;
});

/// Quiz state per (lesson_id) — autoDispose, so it resets on leave.
class QuizSession {
  QuizSession({required this.lesson});
  final Lesson lesson;
  final Map<String, int> selected = {};
  QuizResult? result;
}

class LessonReaderState {
  const LessonReaderState({
    this.lesson,
    this.loading = true,
    this.error,
    this.selectedAnswers = const {},
    this.result,
    this.submitting = false,
  });

  final Lesson? lesson;
  final bool loading;
  final String? error;
  final Map<String, int> selectedAnswers;
  final QuizResult? result;
  final bool submitting;

  LessonReaderState copyWith({
    Lesson? lesson,
    bool? loading,
    String? error,
    Map<String, int>? selectedAnswers,
    QuizResult? result,
    bool? submitting,
    bool clearError = false,
    bool clearResult = false,
  }) {
    return LessonReaderState(
      lesson: lesson ?? this.lesson,
      loading: loading ?? this.loading,
      error: clearError ? null : (error ?? this.error),
      selectedAnswers: selectedAnswers ?? this.selectedAnswers,
      result: clearResult ? null : (result ?? this.result),
      submitting: submitting ?? this.submitting,
    );
  }
}

class LessonReaderNotifier extends StateNotifier<LessonReaderState> {
  LessonReaderNotifier(this._ref, this._lessonId) : super(const LessonReaderState());

  final Ref _ref;
  final String _lessonId;

  Future<void> load() async {
    state = state.copyWith(loading: true, clearError: true, clearResult: true,
        selectedAnswers: const {});
    try {
      final api = _ref.read(apiClientProvider);
      final userId = await DeviceUser.getOrCreate();
      final lesson = await api.getLesson(_lessonId);
      await api.startLesson(userId: userId, lessonId: _lessonId);
      state = state.copyWith(lesson: lesson, loading: false);
    } catch (e) {
      state = state.copyWith(loading: false, error: 'Lesson load failed: $e');
    }
  }

  void selectAnswer(String questionId, int optionIndex) {
    final updated = Map<String, int>.from(state.selectedAnswers);
    updated[questionId] = optionIndex;
    state = state.copyWith(selectedAnswers: updated);
  }

  bool get allAnswered {
    final l = state.lesson;
    if (l == null) return false;
    return l.quizzes.every((q) => state.selectedAnswers.containsKey(q.id));
  }

  Future<void> submit() async {
    final l = state.lesson;
    if (l == null || !allAnswered || state.submitting) return;
    state = state.copyWith(submitting: true, clearError: true);
    try {
      final api = _ref.read(apiClientProvider);
      final userId = await DeviceUser.getOrCreate();
      final answers = l.quizzes.map((q) => state.selectedAnswers[q.id] ?? -1).toList();
      final result = await api.submitQuiz(
        userId: userId,
        lessonId: _lessonId,
        answers: answers,
      );
      state = state.copyWith(submitting: false, result: result);
      // Refresh the top-level lessons state so unlocks and progress propagate
      await _ref.read(lessonsNotifierProvider.notifier).refresh();
    } catch (e) {
      state = state.copyWith(submitting: false, error: 'Submit failed: $e');
    }
  }

  void retry() {
    state = state.copyWith(
      clearResult: true,
      selectedAnswers: const {},
    );
  }
}

final lessonReaderProvider = StateNotifierProvider.family
    .autoDispose<LessonReaderNotifier, LessonReaderState, String>((ref, lessonId) {
  final n = LessonReaderNotifier(ref, lessonId);
  Future.microtask(n.load);
  return n;
});
