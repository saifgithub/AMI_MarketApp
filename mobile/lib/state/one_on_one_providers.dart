/// Riverpod state for a single 1-on-1 chat session.
library;

import 'package:ami_trade/models/one_on_one.dart';
import 'package:ami_trade/services/api/friendly_error.dart';
import 'package:ami_trade/state/onboarding_providers.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

@immutable
class OneOnOneState {
  const OneOnOneState({
    this.session,
    this.messages = const [],
    this.streaming = false,
    this.error,
  });

  final OneOnOneSession? session;
  final List<ChatMessage> messages;
  final bool streaming;
  final String? error;

  OneOnOneState copyWith({
    OneOnOneSession? session,
    List<ChatMessage>? messages,
    bool? streaming,
    String? error,
    bool clearError = false,
  }) {
    return OneOnOneState(
      session: session ?? this.session,
      messages: messages ?? this.messages,
      streaming: streaming ?? this.streaming,
      error: clearError ? null : (error ?? this.error),
    );
  }
}

class OneOnOneNotifier extends StateNotifier<OneOnOneState> {
  OneOnOneNotifier(this._ref) : super(const OneOnOneState());

  final Ref _ref;

  Future<void> openSession(String agentId, {String locale = 'en'}) async {
    final api = _ref.read(apiClientProvider);
    state = state.copyWith(error: null, clearError: true);
    try {
      final session = await api.startOneOnOne(
        agentId: agentId,
        locale: locale,
      );
      state = state.copyWith(session: session, messages: const []);
    } catch (e) {
      state = state.copyWith(
          error: friendlyError(e, action: 'open this 1-on-1'));
    }
  }

  Future<void> send(String text) async {
    final session = state.session;
    if (session == null || state.streaming) return;
    final trimmed = text.trim();
    if (trimmed.isEmpty) return;

    final api = _ref.read(apiClientProvider);

    // Add user message
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
      final stream = api.streamOneOnOneMessage(
        sessionId: session.id,
        userMessage: trimmed,
        history: history,
      );
      await for (final chunk in stream) {
        buffer.write(chunk);
        // Update the streaming assistant message
        final updated = List<ChatMessage>.from(state.messages);
        updated[assistantIdx] = ChatMessage(
          role: 'assistant',
          content: buffer.toString(),
          isStreaming: true,
        );
        state = state.copyWith(messages: updated);
      }
      // Mark as done
      final finalised = List<ChatMessage>.from(state.messages);
      finalised[assistantIdx] = ChatMessage(
        role: 'assistant',
        content: buffer.toString(),
        isStreaming: false,
      );
      state = state.copyWith(messages: finalised, streaming: false);
    } catch (e) {
      // Replace placeholder with an error bubble
      final updated = List<ChatMessage>.from(state.messages);
      updated[assistantIdx] = ChatMessage(
        role: 'assistant',
        content: friendlyError(e, action: 'reach your analyst'),
        isStreaming: false,
      );
      state = state.copyWith(
          messages: updated,
          streaming: false,
          error: friendlyError(e, action: 'reach your analyst'));
    }
  }

  void reset() {
    state = const OneOnOneState();
  }
}

/// Family-keyed by agentId so multiple agents can have their own state if needed.
final oneOnOneNotifierProvider = StateNotifierProvider.family
    .autoDispose<OneOnOneNotifier, OneOnOneState, String>((ref, agentId) {
  final notifier = OneOnOneNotifier(ref);
  // Auto-open session on first access
  Future.microtask(() => notifier.openSession(agentId));
  return notifier;
});
