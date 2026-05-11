/// Riverpod state for the Decision Journal.
library;

import 'package:ami_trade/models/journal.dart';
import 'package:ami_trade/services/device_user.dart';
import 'package:ami_trade/state/onboarding_providers.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

@immutable
class JournalState {
  const JournalState({
    this.entries = const [],
    this.loading = false,
    this.retentionDays,
    this.filterType,
    this.error,
  });

  final List<JournalEntry> entries;
  final bool loading;
  final int? retentionDays;
  final JournalEntryType? filterType;
  final String? error;

  JournalState copyWith({
    List<JournalEntry>? entries,
    bool? loading,
    int? retentionDays,
    JournalEntryType? filterType,
    String? error,
    bool clearError = false,
    bool clearFilter = false,
  }) {
    return JournalState(
      entries: entries ?? this.entries,
      loading: loading ?? this.loading,
      retentionDays: retentionDays ?? this.retentionDays,
      filterType: clearFilter ? null : (filterType ?? this.filterType),
      error: clearError ? null : (error ?? this.error),
    );
  }
}

class JournalNotifier extends StateNotifier<JournalState> {
  JournalNotifier(this._ref) : super(const JournalState());

  final Ref _ref;

  Future<void> refresh({JournalEntryType? filterType, String plan = 'trial_trader'}) async {
    state = state.copyWith(loading: true, clearError: true);
    try {
      final api = _ref.read(apiClientProvider);
      final userId = await DeviceUser.getOrCreate();
      final resp = await api.listJournal(
        userId: userId,
        plan: plan,
        entryType: filterType?.wire,
      );
      state = state.copyWith(
        entries: resp.entries,
        loading: false,
        retentionDays: resp.retentionDays,
        filterType: filterType,
      );
    } catch (e) {
      state = state.copyWith(loading: false, error: 'Could not load journal: $e');
    }
  }

  Future<void> setFilter(JournalEntryType? type) async {
    await refresh(filterType: type);
  }

  Future<void> annotate({
    required String entryId,
    String? note,
    List<String>? tags,
    String? outcome,
  }) async {
    try {
      final api = _ref.read(apiClientProvider);
      final userId = await DeviceUser.getOrCreate();
      final updated = await api.annotateJournalEntry(
        userId: userId,
        entryId: entryId,
        note: note,
        tags: tags,
        outcome: outcome,
      );
      final replaced = state.entries
          .map((e) => e.id == entryId ? updated : e)
          .toList(growable: false);
      state = state.copyWith(entries: replaced);
    } catch (e) {
      state = state.copyWith(error: 'Note save failed: $e');
    }
  }
}

final journalNotifierProvider =
    StateNotifierProvider<JournalNotifier, JournalState>((ref) {
  final n = JournalNotifier(ref);
  Future.microtask(n.refresh);
  return n;
});
