/// CR278 (CR267 WP-36) - state behind the Beta "Did the verdict and its reasons
/// make sense?" card.
///
/// One notifier per Room run id. It is deliberately NOT autoDispose: dismissing
/// the card (or answering) should hold for the rest of the app session even if
/// the user leaves the Room and comes back to it.
///
/// Nothing here blocks anything. A failed save is a quiet message on the card
/// and the user can tap a thumb again; the Room, its verdict and its actions
/// never wait on this.
library;

import 'package:ami_trade/state/onboarding_providers.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

@immutable
class RoomRatingState {
  const RoomRatingState({
    this.helpful,
    this.submitting = false,
    this.failed = false,
    this.dismissed = false,
  });

  /// The saved answer; null until one was saved.
  final bool? helpful;
  final bool submitting;
  final bool failed;
  final bool dismissed;

  RoomRatingState copyWith({
    bool? helpful,
    bool? submitting,
    bool? failed,
    bool? dismissed,
  }) =>
      RoomRatingState(
        helpful: helpful ?? this.helpful,
        submitting: submitting ?? this.submitting,
        failed: failed ?? this.failed,
        dismissed: dismissed ?? this.dismissed,
      );
}

class RoomRatingNotifier extends StateNotifier<RoomRatingState> {
  RoomRatingNotifier(this._ref, this.runId) : super(const RoomRatingState());

  final Ref _ref;
  final String runId;

  Future<void> rate(bool helpful) async {
    if (state.submitting) return;
    state = state.copyWith(submitting: true, failed: false);
    try {
      await _ref
          .read(apiClientProvider)
          .rateRoom(runId: runId, helpful: helpful);
      if (!mounted) return;
      state = state.copyWith(helpful: helpful, submitting: false);
    } catch (_) {
      if (!mounted) return;
      state = state.copyWith(submitting: false, failed: true);
    }
  }

  void dismiss() => state = state.copyWith(dismissed: true);
}

final roomRatingProvider = StateNotifierProvider.family<RoomRatingNotifier,
    RoomRatingState, String>(
  (ref, runId) => RoomRatingNotifier(ref, runId),
);
