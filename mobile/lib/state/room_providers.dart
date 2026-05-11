/// Riverpod state for a single Convene the Room session.
///
/// Holds:
///   - the live transcript map: agentId → accumulating text
///   - the active phase + active agent
///   - the final verdict (once it arrives)
///   - completion + error flags
///
/// The notifier is family-keyed by ticker so two parallel runs on
/// different tickers don't share state.
library;

import 'package:ami_trade/models/room.dart';
import 'package:ami_trade/services/device_user.dart';
import 'package:ami_trade/state/journal_providers.dart';
import 'package:ami_trade/state/lessons_providers.dart';
import 'package:ami_trade/state/onboarding_providers.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

@immutable
class RoomState {
  const RoomState({
    this.phase,
    this.activeAgent,
    this.transcript = const {},
    this.order = const [],
    this.verdict,
    this.runId,
    this.done = false,
    this.streaming = false,
    this.error,
  });

  final String? phase;
  final String? activeAgent;
  // agentId → current rolling text
  final Map<String, String> transcript;
  // visit-order so the console renders top-down by appearance
  final List<String> order;
  final RoomVerdict? verdict;
  final String? runId;
  final bool done;
  final bool streaming;
  final String? error;

  RoomState copyWith({
    String? phase,
    String? activeAgent,
    Map<String, String>? transcript,
    List<String>? order,
    RoomVerdict? verdict,
    String? runId,
    bool? done,
    bool? streaming,
    String? error,
    bool clearError = false,
  }) {
    return RoomState(
      phase: phase ?? this.phase,
      activeAgent: activeAgent ?? this.activeAgent,
      transcript: transcript ?? this.transcript,
      order: order ?? this.order,
      verdict: verdict ?? this.verdict,
      runId: runId ?? this.runId,
      done: done ?? this.done,
      streaming: streaming ?? this.streaming,
      error: clearError ? null : (error ?? this.error),
    );
  }
}

class RoomNotifier extends StateNotifier<RoomState> {
  RoomNotifier(this._ref, this._ticker) : super(const RoomState());

  final Ref _ref;
  final String _ticker;

  Future<void> start() async {
    if (state.streaming) return;
    state = const RoomState(streaming: true);
    try {
      final api = _ref.read(apiClientProvider);
      final userId = await DeviceUser.getOrCreate();
      final stream = api.streamRoom(userId: userId, ticker: _ticker);
      await for (final ev in stream) {
        switch (ev['kind']) {
          case 'phase':
            state = state.copyWith(phase: ev['label'] as String?);
            break;
          case 'agent_token':
            final agentId = ev['agent_id'] as String;
            final text = ev['text'] as String;
            final next = Map<String, String>.from(state.transcript);
            next[agentId] = (next[agentId] ?? '') + text;
            final order = state.order.contains(agentId)
                ? state.order
                : [...state.order, agentId];
            state = state.copyWith(
              transcript: next,
              order: order,
              activeAgent: agentId,
            );
            break;
          case 'agent_done':
            state = state.copyWith(activeAgent: null);
            break;
          case 'verdict':
            state = state.copyWith(verdict: ev['verdict'] as RoomVerdict);
            break;
          case 'done':
            state = state.copyWith(
              streaming: false,
              done: true,
              runId: ev['run_id'] as String?,
            );
            // Refresh dependent surfaces — journal got a new entry
            await _ref.read(journalNotifierProvider.notifier).refresh();
            await _ref.read(lessonsNotifierProvider.notifier).refresh();
            break;
          case 'error':
            state = state.copyWith(
              streaming: false,
              error: (ev['message'] as String?) ?? 'unknown',
            );
            break;
        }
      }
    } catch (e) {
      state = state.copyWith(streaming: false, error: 'Stream failed: $e');
    }
  }
}

final roomNotifierProvider = StateNotifierProvider.family
    .autoDispose<RoomNotifier, RoomState, String>((ref, ticker) {
  final n = RoomNotifier(ref, ticker);
  Future.microtask(n.start);
  return n;
});
