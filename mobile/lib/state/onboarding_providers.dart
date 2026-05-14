/// Riverpod state for the onboarding flow.
///
/// The state is a single immutable [OnboardingState] managed by
/// [OnboardingNotifier]. Backend interactions go through [ApiClient].
library;

import 'package:ami_trade/services/api/api_client.dart';
import 'package:ami_trade/state/backend_mode_provider.dart';
import 'package:ami_trade/widgets/chat/chat_bubble.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

const _kOnboardingDoneKey = 'ami_onboarding_done';

/// API client keyed on the active backend mode (Alpha / Beta / Prod —
/// see docs/08_tech/backend_modes.md). When the user flips the toggle
/// in Settings → Developer, this provider rebuilds with the new base
/// URL and every dependent provider picks up the change on next read.
final apiClientProvider = Provider<ApiClient>((ref) {
  final url = ref.watch(activeBackendUrlProvider);
  return ApiClient(baseUrl: url);
});

class ChatLine {
  const ChatLine({
    required this.id,
    required this.author,
    required this.content,
    this.chips = const [],
    this.streaming = false,
  });

  final String id; // unique key
  final ChatAuthor author;
  final String content;
  final List<String> chips;
  final bool streaming;
}

enum OnboardingPhase {
  notStarted,
  starting,
  inConversation,
  readback,
  completing,
  completed,
  error,
}

@immutable
class OnboardingState {
  const OnboardingState({
    this.phase = OnboardingPhase.notStarted,
    this.sessionId,
    this.lines = const [],
    this.currentStep,
    this.errorMessage,
    this.readbackSummary,
    this.mandatePreview,
    this.submitting = false,
  });

  final OnboardingPhase phase;
  final String? sessionId;
  final List<ChatLine> lines;
  final String? currentStep;
  final String? errorMessage;
  final Map<String, dynamic>? readbackSummary;
  final Map<String, dynamic>? mandatePreview;
  final bool submitting;

  /// Available chip suggestions for the most recent Concierge message
  /// (only when waiting on user input).
  List<String> get currentChips {
    if (submitting || lines.isEmpty) return const [];
    final last = lines.last;
    if (last.author != ChatAuthor.concierge) return const [];
    return last.chips;
  }

  OnboardingState copyWith({
    OnboardingPhase? phase,
    String? sessionId,
    List<ChatLine>? lines,
    String? currentStep,
    String? errorMessage,
    Map<String, dynamic>? readbackSummary,
    Map<String, dynamic>? mandatePreview,
    bool? submitting,
  }) {
    return OnboardingState(
      phase: phase ?? this.phase,
      sessionId: sessionId ?? this.sessionId,
      lines: lines ?? this.lines,
      currentStep: currentStep ?? this.currentStep,
      errorMessage: errorMessage,
      readbackSummary: readbackSummary ?? this.readbackSummary,
      mandatePreview: mandatePreview ?? this.mandatePreview,
      submitting: submitting ?? this.submitting,
    );
  }
}

class OnboardingNotifier extends StateNotifier<OnboardingState> {
  OnboardingNotifier(this._api) : super(const OnboardingState());

  final ApiClient _api;
  int _lineCounter = 0;

  String _nextId() => 'line_${_lineCounter++}';

  /// Persist completion so the app skips onboarding on next cold start.
  static Future<void> markComplete() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool(_kOnboardingDoneKey, true);
  }

  /// Clear the completion flag and reset state back to [OnboardingPhase.notStarted].
  /// Called by "Restart Onboarding" in Settings/Floor.
  Future<void> reset() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(_kOnboardingDoneKey);
    _lineCounter = 0;
    state = const OnboardingState();
  }

  Future<void> start({required String locale, required String timezone}) async {
    if (state.phase != OnboardingPhase.notStarted &&
        state.phase != OnboardingPhase.error) {
      return; // already in progress
    }
    state = state.copyWith(phase: OnboardingPhase.starting, errorMessage: null);
    try {
      final resp = await _api.startOnboarding(locale: locale, timezone: timezone);
      state = state.copyWith(
        phase: OnboardingPhase.inConversation,
        sessionId: resp.sessionId,
        currentStep: resp.firstQuestion.step,
        lines: [
          ChatLine(
            id: _nextId(),
            author: ChatAuthor.concierge,
            content: resp.welcomeMessage.content,
            chips: const [],
            streaming: true,
          ),
          ChatLine(
            id: _nextId(),
            author: ChatAuthor.concierge,
            content: resp.firstQuestion.content,
            chips: resp.firstQuestion.chips,
          ),
        ],
      );
    } catch (e) {
      state = state.copyWith(
        phase: OnboardingPhase.error,
        errorMessage: 'Could not reach the backend: $e',
      );
    }
  }

  Future<void> submitAnswer(String answer) async {
    final sid = state.sessionId;
    final step = state.currentStep;
    if (sid == null || step == null || state.submitting) return;

    // Append user message immediately for responsiveness
    final newLines = [
      ...state.lines,
      ChatLine(id: _nextId(), author: ChatAuthor.user, content: answer),
    ];
    state = state.copyWith(lines: newLines, submitting: true);

    try {
      final resp = await _api.submitAnswer(
        sessionId: sid,
        step: step,
        answer: answer,
      );

      // Update conversation state with Concierge reply
      final after = [
        ...state.lines,
        ChatLine(
          id: _nextId(),
          author: ChatAuthor.concierge,
          content: resp.conciergeReply.content,
          chips: resp.conciergeReply.chips,
        ),
      ];

      final isReadback = resp.nextStep == 'readback';
      state = state.copyWith(
        lines: after,
        currentStep: resp.nextStep,
        submitting: false,
        phase: isReadback
            ? OnboardingPhase.readback
            : OnboardingPhase.inConversation,
        readbackSummary: resp.readbackSummary,
      );
    } catch (e) {
      state = state.copyWith(
        submitting: false,
        phase: OnboardingPhase.error,
        errorMessage: 'Couldn\'t submit answer: $e',
      );
    }
  }

  Future<void> confirmReadback() async {
    final sid = state.sessionId;
    if (sid == null) return;
    state = state.copyWith(phase: OnboardingPhase.completing);
    try {
      final resp = await _api.confirmReadback(sessionId: sid, confirm: true);
      state = state.copyWith(
        phase: OnboardingPhase.completed,
        mandatePreview: resp.mandatePreview,
        lines: [
          ...state.lines,
          ChatLine(
            id: _nextId(),
            author: ChatAuthor.concierge,
            content: resp.followUpMessage.content,
          ),
        ],
      );
    } catch (e) {
      state = state.copyWith(
        phase: OnboardingPhase.error,
        errorMessage: 'Couldn\'t confirm: $e',
      );
    }
  }
}

final onboardingNotifierProvider =
    StateNotifierProvider<OnboardingNotifier, OnboardingState>((ref) {
  return OnboardingNotifier(ref.watch(apiClientProvider));
});
