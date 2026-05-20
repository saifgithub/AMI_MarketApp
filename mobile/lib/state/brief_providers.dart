/// Riverpod state for a Coach Your Agent session.
///
/// Lifecycle:
///   1. `openSession(agentId)` — hits /v1/brief/start.
///   2. `send(text)` — streams /v1/brief/message tokens into the placeholder.
///   3. `propose()` — calls /v1/brief/propose to crystallise the conversation
///      into a structured BriefProposal. Sets `pendingProposal`.
///   4. `accept()` — calls /v1/brief/accept. On success, clears proposal
///      and refreshes history. On refusal (server-side safety floor or limit),
///      surfaces `refusal` for the UI.
///   5. `reject()` — discards the pending proposal.
///   6. `loadHistory()` / `rollback(version)` — version-history utilities.
library;

import 'package:ami_trade/models/brief.dart';
import 'package:ami_trade/models/one_on_one.dart';
import 'package:ami_trade/services/device_user.dart';
import 'package:ami_trade/state/onboarding_providers.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

@immutable
class CoachRefusal {
  const CoachRefusal({required this.reason, required this.message, this.suggestion});
  final String reason;
  final String message;
  final String? suggestion;
}

@immutable
class BriefState {
  const BriefState({
    this.session,
    this.currentOverlay,
    this.messages = const [],
    this.streaming = false,
    this.proposing = false,
    this.pendingProposal,
    this.history,
    this.error,
    this.refusal,
    this.savedOverlay,
  });

  final BriefSession? session;
  final UserOverlay? currentOverlay;
  final List<ChatMessage> messages;
  final bool streaming;
  final bool proposing;
  final BriefProposal? pendingProposal;
  final BriefHistory? history;
  final String? error;
  final CoachRefusal? refusal;
  final UserOverlay? savedOverlay;

  BriefState copyWith({
    BriefSession? session,
    UserOverlay? currentOverlay,
    List<ChatMessage>? messages,
    bool? streaming,
    bool? proposing,
    BriefProposal? pendingProposal,
    BriefHistory? history,
    String? error,
    CoachRefusal? refusal,
    UserOverlay? savedOverlay,
    bool clearProposal = false,
    bool clearError = false,
    bool clearRefusal = false,
    bool clearSaved = false,
  }) {
    return BriefState(
      session: session ?? this.session,
      currentOverlay: currentOverlay ?? this.currentOverlay,
      messages: messages ?? this.messages,
      streaming: streaming ?? this.streaming,
      proposing: proposing ?? this.proposing,
      pendingProposal: clearProposal ? null : (pendingProposal ?? this.pendingProposal),
      history: history ?? this.history,
      error: clearError ? null : (error ?? this.error),
      refusal: clearRefusal ? null : (refusal ?? this.refusal),
      savedOverlay: clearSaved ? null : (savedOverlay ?? this.savedOverlay),
    );
  }
}

class BriefNotifier extends StateNotifier<BriefState> {
  BriefNotifier(this._ref, this._agentId) : super(const BriefState());

  final Ref _ref;
  final String _agentId;

  Future<void> openSession({String locale = 'en'}) async {
    state = state.copyWith(clearError: true, clearRefusal: true, clearSaved: true);
    try {
      final api = _ref.read(apiClientProvider);
      final userId = await DeviceUser.getOrCreate();
      final resp = await api.startBrief(
        agentId: _agentId,
        userId: userId,
        mode: 'from_scratch',
        locale: locale,
      );
      final opener = ChatMessage(role: 'assistant', content: resp.openingMessage);
      state = state.copyWith(
        session: resp.session,
        currentOverlay: resp.currentOverlay,
        messages: [opener],
      );
      await loadHistory();
    } catch (e) {
      state = state.copyWith(error: 'Could not start briefing: $e');
    }
  }

  Future<void> send(String text) async {
    final session = state.session;
    if (session == null || state.streaming) return;
    final trimmed = text.trim();
    if (trimmed.isEmpty) return;

    final api = _ref.read(apiClientProvider);
    final userMsg = ChatMessage(role: 'user', content: trimmed);
    final placeholder = const ChatMessage(role: 'assistant', content: '', isStreaming: true);
    final history = List<ChatMessage>.from(state.messages);
    state = state.copyWith(
      messages: [...state.messages, userMsg, placeholder],
      streaming: true,
    );
    final assistantIdx = state.messages.length - 1;
    final buffer = StringBuffer();

    try {
      final stream = api.streamBriefMessage(
        sessionId: session.id,
        userMessage: trimmed,
        history: history,
      );
      await for (final chunk in stream) {
        buffer.write(chunk);
        final updated = List<ChatMessage>.from(state.messages);
        updated[assistantIdx] = ChatMessage(
          role: 'assistant',
          content: buffer.toString(),
          isStreaming: true,
        );
        state = state.copyWith(messages: updated);
      }
      final finalised = List<ChatMessage>.from(state.messages);
      finalised[assistantIdx] = ChatMessage(
        role: 'assistant',
        content: buffer.toString(),
        isStreaming: false,
      );
      state = state.copyWith(messages: finalised, streaming: false);
    } catch (e) {
      final updated = List<ChatMessage>.from(state.messages);
      updated[assistantIdx] = ChatMessage(
        role: 'assistant',
        content: 'Coach couldn\'t reach the agent: $e',
        isStreaming: false,
      );
      state = state.copyWith(messages: updated, streaming: false, error: '$e');
    }
  }

  Future<void> propose() async {
    final session = state.session;
    if (session == null || state.proposing) return;
    state = state.copyWith(proposing: true, clearRefusal: true);
    try {
      final api = _ref.read(apiClientProvider);
      final proposal = await api.proposeBriefChange(
        sessionId: session.id,
        history: state.messages,
      );
      state = state.copyWith(pendingProposal: proposal, proposing: false);
    } catch (e) {
      state = state.copyWith(proposing: false, error: 'Could not propose: $e');
    }
  }

  Future<void> accept() async {
    final session = state.session;
    final proposal = state.pendingProposal;
    if (session == null || proposal == null) return;
    try {
      final api = _ref.read(apiClientProvider);
      final result = await api.acceptBriefProposal(
        sessionId: session.id,
        proposalId: proposal.id,
      );
      if (result['ok'] == true) {
        final saved = UserOverlay.fromJson(result['overlay'] as Map<String, dynamic>);
        state = state.copyWith(
          clearProposal: true,
          currentOverlay: saved,
          savedOverlay: saved,
        );
        await loadHistory();
      } else {
        final r = (result['refusal'] as Map<String, dynamic>?) ?? const {};
        state = state.copyWith(
          clearProposal: true,
          refusal: CoachRefusal(
            reason: (r['reason'] as String?) ?? 'internal_error',
            message: (r['message'] as String?) ?? 'Coach refused the change.',
            suggestion: r['suggestion'] as String?,
          ),
        );
      }
    } catch (e) {
      state = state.copyWith(error: 'Could not save: $e');
    }
  }

  Future<void> reject() async {
    final session = state.session;
    final proposal = state.pendingProposal;
    if (session == null || proposal == null) return;
    try {
      final api = _ref.read(apiClientProvider);
      await api.rejectBriefProposal(sessionId: session.id, proposalId: proposal.id);
    } catch (_) {
      // Best-effort — the proposal is local-only state if the call fails.
    }
    state = state.copyWith(clearProposal: true);
  }

  Future<void> loadHistory() async {
    try {
      final api = _ref.read(apiClientProvider);
      final userId = await DeviceUser.getOrCreate();
      final h = await api.briefHistory(userId: userId, agentId: _agentId);
      state = state.copyWith(history: h);
    } catch (_) {
      // non-fatal
    }
  }

  Future<void> rollback(int version) async {
    try {
      final api = _ref.read(apiClientProvider);
      final userId = await DeviceUser.getOrCreate();
      final rolled = await api.rollbackBrief(
        userId: userId,
        agentId: _agentId,
        toVersion: version,
      );
      state = state.copyWith(currentOverlay: rolled, savedOverlay: rolled);
      await loadHistory();
    } catch (e) {
      state = state.copyWith(error: 'Rollback failed: $e');
    }
  }

  void clearTransientFlags() {
    state = state.copyWith(clearError: true, clearRefusal: true, clearSaved: true);
  }
}

final briefNotifierProvider = StateNotifierProvider.family
    .autoDispose<BriefNotifier, BriefState, String>((ref, agentId) {
  final notifier = BriefNotifier(ref, agentId);
  Future.microtask(() => notifier.openSession());
  return notifier;
});
