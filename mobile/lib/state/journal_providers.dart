/// Riverpod state for the Decision Journal.
library;

import 'package:ami_trade/models/journal.dart';
import 'package:ami_trade/services/api/friendly_error.dart';
import 'package:ami_trade/services/device_user.dart';
import 'package:ami_trade/state/mandate_providers.dart';
import 'package:ami_trade/state/onboarding_providers.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

@immutable
class JournalState {
  const JournalState({
    this.entries = const [],
    this.loading = false,
    this.retentionDays,
    this.retentionLoaded = false,
    this.filterType,
    this.searchQuery = '',
    this.error,
  });

  final List<JournalEntry> entries;
  final bool loading;
  final int? retentionDays;

  /// CR120/D3 — `retentionDays == null` is ambiguous on its own: it means
  /// both "unlimited" and "never fetched", and a screen that never calls
  /// the journal endpoint (the Portfolio) cannot tell those apart from
  /// `retentionDays` alone. This flips true only once a `refresh()` call
  /// has actually completed successfully, so a caller can distinguish
  /// unknown (`!retentionLoaded`) from known-unlimited
  /// (`retentionLoaded && retentionDays == null`). Deliberately NOT set on
  /// a failed refresh — an error tells us nothing about retention either.
  final bool retentionLoaded;
  final JournalEntryType? filterType;
  final String searchQuery;
  final String? error;

  JournalState copyWith({
    List<JournalEntry>? entries,
    bool? loading,
    int? retentionDays,
    bool? retentionLoaded,
    JournalEntryType? filterType,
    String? searchQuery,
    String? error,
    bool clearError = false,
    bool clearFilter = false,
    // `retentionDays: null` cannot mean "unlimited" through `?? this.x` — it
    // reads as "unchanged". So an upgrade to an unlimited plan could never
    // clear a stale finite value, and the caveat kept showing (DEF156).
    bool clearRetentionDays = false,
  }) {
    return JournalState(
      entries: entries ?? this.entries,
      loading: loading ?? this.loading,
      retentionDays:
          clearRetentionDays ? null : (retentionDays ?? this.retentionDays),
      retentionLoaded: retentionLoaded ?? this.retentionLoaded,
      filterType: clearFilter ? null : (filterType ?? this.filterType),
      searchQuery: searchQuery ?? this.searchQuery,
      error: clearError ? null : (error ?? this.error),
    );
  }
}

class JournalNotifier extends StateNotifier<JournalState> {
  JournalNotifier(this._ref) : super(const JournalState());

  final Ref _ref;

  /// DEF173 — `plan` used to be a client-supplied argument with a default of
  /// `'trial_trader'`, so the retention window was computed against
  /// whichever plan the caller (or the default) happened to name, not the
  /// signed-in user's actual entitlement. It is derived here from the
  /// authenticated user's own mandate — never accepted as a parameter — so
  /// there is no client-controlled value on this entitlement-bearing read.
  /// If the mandate has not loaded yet, this bails without guessing: a
  /// wrong plan is worse than a stale/empty retention read, and
  /// `MandateNotifier.refresh()` re-triggers this once the real plan lands.
  Future<void> refresh({
    JournalEntryType? filterType,
    String? q,
  }) async {
    final plan = _ref.read(mandateNotifierProvider).mandate?.plan;
    if (plan == null) return;
    state = state.copyWith(loading: true, clearError: true);
    try {
      final api = _ref.read(apiClientProvider);
      final userId = await DeviceUser.getOrCreate();
      final resp = await api.listJournal(
        userId: userId,
        plan: plan,
        entryType: filterType?.wire,
        q: q,
      );
      state = state.copyWith(
        entries: resp.entries,
        loading: false,
        retentionDays: resp.retentionDays,
        clearRetentionDays: resp.retentionDays == null,
        retentionLoaded: true,
        filterType: filterType,
      );
    } catch (e) {
      state = state.copyWith(
          loading: false,
          error: friendlyError(e, action: 'load your journal'));
    }
  }

  Future<void> setFilter(JournalEntryType? type) async {
    await refresh(filterType: type, q: state.searchQuery.isEmpty ? null : state.searchQuery);
  }

  Future<void> search(String q) async {
    state = state.copyWith(searchQuery: q);
    await refresh(
      filterType: state.filterType,
      q: q.isEmpty ? null : q,
    );
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
      state = state.copyWith(
          error: friendlyError(e, action: 'save your note'));
    }
  }

  Future<void> deleteEntry(String entryId) async {
    // Optimistic remove
    final previous = state.entries;
    state = state.copyWith(
      entries: previous.where((e) => e.id != entryId).toList(growable: false),
    );
    try {
      final api = _ref.read(apiClientProvider);
      final userId = await DeviceUser.getOrCreate();
      await api.deleteJournalEntry(userId: userId, entryId: entryId);
    } catch (e) {
      // Restore on failure
      state = state.copyWith(
          entries: previous,
          error: friendlyError(e, action: 'delete that entry'));
    }
  }

  /// Undo a soft-delete: clears `deleted_at` on the backend and refreshes
  /// the current list so the entry slots back into its created_at-desc
  /// position.
  Future<void> restoreEntry(String entryId) async {
    try {
      final api = _ref.read(apiClientProvider);
      final userId = await DeviceUser.getOrCreate();
      await api.restoreJournalEntry(userId: userId, entryId: entryId);
      // Re-fetch to pick up the un-deleted row in its right place.
      await refresh(
        filterType: state.filterType,
        q: state.searchQuery.isEmpty ? null : state.searchQuery,
      );
    } catch (e) {
      state = state.copyWith(
          error: friendlyError(e, action: 'undo that delete'));
    }
  }
}

final journalNotifierProvider =
    StateNotifierProvider<JournalNotifier, JournalState>((ref) {
  final n = JournalNotifier(ref);
  Future.microtask(n.refresh);
  return n;
});


// ── Trash ──────────────────────────────────────────────────────────────────

@immutable
class JournalTrashState {
  const JournalTrashState({
    this.entries = const [],
    this.loading = false,
    this.error,
  });

  final List<JournalEntry> entries;
  final bool loading;
  final String? error;

  JournalTrashState copyWith({
    List<JournalEntry>? entries,
    bool? loading,
    String? error,
    bool clearError = false,
  }) {
    return JournalTrashState(
      entries: entries ?? this.entries,
      loading: loading ?? this.loading,
      error: clearError ? null : (error ?? this.error),
    );
  }
}


/// Separate notifier so the trash list can be fetched only when the
/// user opens the screen — keeps the main Journal tab's payload small.
class JournalTrashNotifier extends StateNotifier<JournalTrashState> {
  JournalTrashNotifier(this._ref) : super(const JournalTrashState());

  final Ref _ref;

  Future<void> refresh() async {
    state = state.copyWith(loading: true, clearError: true);
    try {
      final api = _ref.read(apiClientProvider);
      final userId = await DeviceUser.getOrCreate();
      final resp = await api.listJournalTrash(userId: userId);
      state = state.copyWith(entries: resp.entries, loading: false);
    } catch (e) {
      state = state.copyWith(
          loading: false,
          error: friendlyError(e, action: 'load your trash'));
    }
  }

  /// Restore an entry; on success drop it from the trash list AND refresh
  /// the main Journal so it re-appears in its original date-desc slot.
  Future<void> restore(String entryId) async {
    final previous = state.entries;
    state = state.copyWith(
      entries: previous.where((e) => e.id != entryId).toList(growable: false),
    );
    try {
      final api = _ref.read(apiClientProvider);
      final userId = await DeviceUser.getOrCreate();
      await api.restoreJournalEntry(userId: userId, entryId: entryId);
      await _ref.read(journalNotifierProvider.notifier).refresh(
            filterType: _ref.read(journalNotifierProvider).filterType,
          );
    } catch (e) {
      state = state.copyWith(
          entries: previous,
          error: friendlyError(e, action: 'restore that entry'));
    }
  }
}


final journalTrashNotifierProvider =
    StateNotifierProvider<JournalTrashNotifier, JournalTrashState>((ref) {
  return JournalTrashNotifier(ref);
});
