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

import 'dart:async';

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
    this.reconnecting = false,
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
  // True while we've lost the SSE connection and are polling
  // GET /v1/room/{run_id} for the final state. Backend keeps the run
  // alive in the background; we just wait for it to land.
  final bool reconnecting;
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
    bool? reconnecting,
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
      reconnecting: reconnecting ?? this.reconnecting,
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
          case 'started':
            state = state.copyWith(runId: ev['run_id'] as String?);
            break;
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
      // Stream broke (phone sleep, network loss, etc.). The backend
      // keeps the run going in a detached task and persists the final
      // state to /v1/room/{run_id} — so as long as we captured the
      // run_id from the `started` event, we can recover.
      if (state.runId != null) {
        await _recoverViaPolling(state.runId!);
      } else {
        state = state.copyWith(streaming: false, error: 'Stream failed: $e');
      }
    }
  }

  /// Poll GET /v1/room/{run_id} until the backend reports a non-RUNNING
  /// status, then apply the final transcript + verdict to state. Caps
  /// total wait at ~90s to avoid hanging forever if something went wrong
  /// server-side.
  Future<void> _recoverViaPolling(String runId) async {
    state = state.copyWith(streaming: false, reconnecting: true, clearError: true);
    final api = _ref.read(apiClientProvider);
    final stopAt = DateTime.now().add(const Duration(seconds: 90));
    while (DateTime.now().isBefore(stopAt)) {
      try {
        final snap = await api.getRoom(runId);
        if (snap.status.toLowerCase() != 'running') {
          // Final state available — overlay it on top of whatever we
          // streamed before the disconnect.
          final transcript = <String, String>{};
          final order = <String>[];
          for (final line in snap.transcript) {
            transcript[line.agentId] = line.content;
            if (!order.contains(line.agentId)) order.add(line.agentId);
          }
          state = state.copyWith(
            reconnecting: false,
            done: true,
            transcript: transcript,
            order: order,
            verdict: snap.verdict,
            activeAgent: null,
          );
          await _ref.read(journalNotifierProvider.notifier).refresh();
          await _ref.read(lessonsNotifierProvider.notifier).refresh();
          return;
        }
      } catch (_) {
        // Transient failure — keep polling.
      }
      await Future.delayed(const Duration(seconds: 3));
    }
    state = state.copyWith(
      reconnecting: false,
      error: 'Reconnect timed out. The run is still saved — check Journal.',
    );
  }
}

final roomNotifierProvider = StateNotifierProvider.family
    .autoDispose<RoomNotifier, RoomState, String>((ref, ticker) {
  final n = RoomNotifier(ref, ticker);
  Future.microtask(n.start);
  return n;
});
