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
import 'package:ami_trade/services/api/api_exceptions.dart';
import 'package:ami_trade/services/device_user.dart';
import 'package:ami_trade/state/journal_providers.dart';
import 'package:ami_trade/state/lessons_providers.dart';
import 'package:ami_trade/state/onboarding_providers.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

/// CR090: the structural live-data disclosure for one Room run. One-shot,
/// like [paywall] — set once from the `live_data_notice` SSE event and never
/// re-derived. `news`/`social` are each one of `live` / `withheld_paid` /
/// `unavailable` (see `LiveDataState` on the backend); `surchargeCharged` is
/// the credits actually debited for this run, rendered as sent (D5) — never
/// recomputed client-side.
@immutable
class RoomLiveDataNotice {
  const RoomLiveDataNotice({
    required this.news,
    required this.social,
    required this.surchargeCharged,
  });

  final String news;
  final String social;
  final int surchargeCharged;
}

/// CR098 — one withheld analyst chair. `nextStepAgentId`/`nextStepDays` are
/// carried here too even though they're roster-level (identical across every
/// `agent_withheld` event this run) so a single chair's widget doesn't need
/// to reach back into `RoomState` for them.
@immutable
class WithheldAgentInfo {
  const WithheldAgentInfo({
    required this.agentId,
    required this.reason,
    this.nextStepAgentId,
    this.nextStepDays,
  });

  final String agentId;
  final String reason;
  final String? nextStepAgentId;
  final int? nextStepDays;
}

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
    this.paywall,
    this.serverError = false,
    this.liveDataNotice,
    this.withheldAgents = const {},
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
  // CR047: set when a convene was refused for credits (HTTP 402). Drives the
  // paywall / Winzip countdown card instead of the generic error banner.
  final InsufficientCreditsException? paywall;
  // DEF073: set when a convene hit a 5xx (502/503/504). Drives a friendly
  // "AMI's briefly offline — try again" card with a Retry, never a raw code.
  final bool serverError;
  // CR090 (D4): null unless the `live_data_notice` event actually arrived.
  // Absence renders nothing — never a defaulted "no surcharge" state.
  final RoomLiveDataNotice? liveDataNotice;
  // CR098: agentId -> its withhold info. Populated from `agent_withheld`
  // events, all emitted before any ANALYSTS-phase agent speaks. Also mirrored
  // into `order` (see the `agent_withheld` case below) so the locked chair
  // renders inline, in seat, at the top of the phase (D4) — not in a
  // separate list that could drift out of position.
  final Map<String, WithheldAgentInfo> withheldAgents;

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
    InsufficientCreditsException? paywall,
    bool clearPaywall = false,
    bool? serverError,
    RoomLiveDataNotice? liveDataNotice,
    Map<String, WithheldAgentInfo>? withheldAgents,
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
      paywall: clearPaywall ? null : (paywall ?? this.paywall),
      serverError: serverError ?? this.serverError,
      liveDataNotice: liveDataNotice ?? this.liveDataNotice,
      withheldAgents: withheldAgents ?? this.withheldAgents,
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
          case 'live_data_notice':
            state = state.copyWith(
              liveDataNotice: RoomLiveDataNotice(
                news: ev['news'] as String,
                social: ev['social'] as String,
                surchargeCharged: ev['surcharge_charged'] as int,
              ),
            );
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
          case 'agent_withheld':
            // CR098: one event per withheld analyst, all emitted before any
            // ANALYSTS-phase agent speaks. Mirror the agentId into `order`
            // (never into `transcript`) so the console renders a locked
            // chair in the analyst's real seat, at the top of the phase,
            // rather than appearing late once other analysts have spoken.
            // Shape-checked, not hard-cast. `parseRoomSseEvent` swallows a
            // malformed event, but this case performs no casts inside it — it
            // forwards raw `dynamic`, so a bad field threw here instead, inside
            // `await for`, where the generic catch reads any throw as a dropped
            // socket and diverts to polling recovery. The disclosure then
            // vanished with nothing reported. Drop the event, keep the run.
            final rawWithheldId = ev['agent_id'];
            if (rawWithheldId is! String || rawWithheldId.isEmpty) {
              debugPrint('room stream: agent_withheld without a usable agent_id');
              break;
            }
            final withheldAgentId = rawWithheldId;
            final rawReason = ev['reason'];
            final rawNextAgent = ev['next_step_agent'];
            final rawNextDays = ev['next_step_days'];
            final withheldNext = Map<String, WithheldAgentInfo>.from(
              state.withheldAgents,
            );
            withheldNext[withheldAgentId] = WithheldAgentInfo(
              agentId: withheldAgentId,
              reason: rawReason is String ? rawReason : 'upgrade',
              nextStepAgentId: rawNextAgent is String ? rawNextAgent : null,
              nextStepDays: rawNextDays is num ? rawNextDays.toInt() : null,
            );
            final orderWithChair = state.order.contains(withheldAgentId)
                ? state.order
                : [...state.order, withheldAgentId];
            state = state.copyWith(
              withheldAgents: withheldNext,
              order: orderWithChair,
            );
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
          default:
            // CR090 (D2): same silent-tolerance guarantee as the SSE parser —
            // log an unrecognised kind, never throw, never surface to the user.
            debugPrint('room stream: unhandled event kind "${ev['kind']}"');
            break;
        }
      }
    } on InsufficientCreditsException catch (e) {
      // CR047: the credit wall. This lands before any `started` event (no
      // run_id yet), so surface it as a paywall — for Winzip, a live cooldown
      // countdown — never a generic "Stream failed".
      state = state.copyWith(streaming: false, paywall: e);
    } on ServerUnavailableException {
      // DEF073: a 5xx at the convene POST (no run started). Show a friendly
      // "AMI's briefly offline — try again" card with Retry, not a raw code.
      state = state.copyWith(streaming: false, serverError: true);
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
          // Re-seat the locked chairs. `order` is rebuilt from the transcript
          // alone, and a withheld analyst is deliberately never in the
          // transcript — so without this the console, which renders by
          // iterating `order`, silently drops every locked chair on the most
          // ordinary mobile failure there is. `withheldAgents` still holds
          // them; nothing would look. Front of the queue, in arrival order,
          // matching where the stream seats them (all arrive before any
          // analyst speaks). CR090's notice on this screen survives recovery
          // because it renders from its own field rather than through `order`.
          final chairs = state.withheldAgents.keys
              .where((id) => !order.contains(id))
              .toList();
          order.insertAll(0, chairs);
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
