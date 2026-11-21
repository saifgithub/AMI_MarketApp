/// Riverpod state for the user mandate (Settings → My Mandate editor).
library;

import 'dart:async';

import 'package:ami_trade/models/mandate.dart';
import 'package:ami_trade/services/api/friendly_error.dart';
import 'package:ami_trade/services/device_user.dart';
import 'package:ami_trade/services/diagnostics/save_timeline.dart';
import 'package:ami_trade/state/journal_providers.dart';
import 'package:ami_trade/state/onboarding_providers.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

@immutable
class MandateState {
  const MandateState({this.mandate, this.loading = false, this.saving = false, this.error});

  final UserMandate? mandate;
  final bool loading;
  final bool saving;
  final String? error;

  MandateState copyWith({
    UserMandate? mandate,
    bool? loading,
    bool? saving,
    String? error,
    bool clearError = false,
  }) {
    return MandateState(
      mandate: mandate ?? this.mandate,
      loading: loading ?? this.loading,
      saving: saving ?? this.saving,
      error: clearError ? null : (error ?? this.error),
    );
  }
}

class MandateNotifier extends StateNotifier<MandateState> {
  MandateNotifier(this._ref) : super(const MandateState());

  final Ref _ref;

  Future<void> refresh() async {
    // DEF336 — this notifier is created LAZILY by whatever first reads it
    // (JournalNotifier.refresh does, on SimNotifier.submit's unawaited
    // fan-out), and its provider schedules this refresh via Future.microtask.
    // Both mean the container can already be disposed before this line runs,
    // and DEF332's guards on the three fan-out notifiers could not cover a
    // notifier that is only CREATED by the fan-out. Same rule as DEF332:
    // check `mounted` at entry and after every await, before any write.
    if (!mounted) return;
    state = state.copyWith(loading: true, clearError: true);
    try {
      final api = _ref.read(apiClientProvider);
      final userId = await DeviceUser.getOrCreate();
      final m = await api.getMandate(userId);
      if (!mounted) return;
      state = state.copyWith(mandate: m, loading: false);
      // DEF173 — the Journal derives its retention plan from this mandate
      // and bails out of its own refresh if the mandate isn't loaded yet;
      // re-trigger it now that the real plan is known.
      await _ref.read(journalNotifierProvider.notifier).refresh();
    } catch (e) {
      if (!mounted) return;
      state = state.copyWith(
          loading: false,
          error: friendlyError(e, action: 'load your mandate'));
    }
  }

  /// DEF522 — returns whether the PATCH landed. A failure is also written to
  /// [MandateState.error], but callers must act on the return value: a stale
  /// `error` from an earlier load is indistinguishable from this call's.
  Future<bool> patch(Map<String, dynamic> updates) async {
    SaveTimeline.mark('patch start');
    state = state.copyWith(saving: true, clearError: true);
    try {
      final api = _ref.read(apiClientProvider);
      final userId = await DeviceUser.getOrCreate();
      final updated = await api.patchMandate(userId: userId, updates: updates);
      SaveTimeline.mark('patch response');
      if (!mounted) return true;
      state = state.copyWith(mandate: updated, saving: false);
      // DEF521 — NOT awaited. The journal list is up to 100 full-payload rows
      // and, on a phone behind the tunnel, took ~17 s to arrive; awaiting it
      // here held the Settings screen's dirty flag, keyboard and the
      // retro-tightening audit behind a re-read that none of them depend on.
      // The journal only needs the new plan, which is already in state.
      unawaited(_ref
          .read(journalNotifierProvider.notifier)
          .refresh()
          .whenComplete(() => SaveTimeline.mark('journal refresh done')));
      return true;
    } catch (e) {
      SaveTimeline.mark('patch failed');
      if (!mounted) return false;
      state = state.copyWith(
          saving: false,
          error: friendlyError(e, action: 'save your mandate'));
      return false;
    }
  }
}

final mandateNotifierProvider =
    StateNotifierProvider<MandateNotifier, MandateState>((ref) {
  final n = MandateNotifier(ref);
  Future.microtask(n.refresh);
  return n;
});
