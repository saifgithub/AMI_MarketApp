/// Riverpod state for the user mandate (Settings → My Mandate editor).
library;

import 'package:ami_trade/models/mandate.dart';
import 'package:ami_trade/services/api/friendly_error.dart';
import 'package:ami_trade/services/device_user.dart';
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
    state = state.copyWith(loading: true, clearError: true);
    try {
      final api = _ref.read(apiClientProvider);
      final userId = await DeviceUser.getOrCreate();
      final m = await api.getMandate(userId);
      state = state.copyWith(mandate: m, loading: false);
      // DEF173 — the Journal derives its retention plan from this mandate
      // and bails out of its own refresh if the mandate isn't loaded yet;
      // re-trigger it now that the real plan is known.
      await _ref.read(journalNotifierProvider.notifier).refresh();
    } catch (e) {
      state = state.copyWith(
          loading: false,
          error: friendlyError(e, action: 'load your mandate'));
    }
  }

  Future<void> patch(Map<String, dynamic> updates) async {
    state = state.copyWith(saving: true, clearError: true);
    try {
      final api = _ref.read(apiClientProvider);
      final userId = await DeviceUser.getOrCreate();
      final updated = await api.patchMandate(userId: userId, updates: updates);
      state = state.copyWith(mandate: updated, saving: false);
      await _ref.read(journalNotifierProvider.notifier).refresh();
    } catch (e) {
      state = state.copyWith(
          saving: false,
          error: friendlyError(e, action: 'save your mandate'));
    }
  }
}

final mandateNotifierProvider =
    StateNotifierProvider<MandateNotifier, MandateState>((ref) {
  final n = MandateNotifier(ref);
  Future.microtask(n.refresh);
  return n;
});
