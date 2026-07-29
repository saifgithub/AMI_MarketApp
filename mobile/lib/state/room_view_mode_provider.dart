/// CR106 — which view a finished Room run opens in: the Verdict Board or the
/// collapsed transcript.
///
/// Saiful, 2026-07-28: *"Let's give the user the option to show the verdict
/// board or to see the detail of the agent response as a default."* — so a
/// persisted preference, not a hard-coded default.
///
/// Modelled on [themeModeProvider] deliberately, down to the async `_hydrate`
/// with a swallowed failure, because one property of that shape is
/// load-bearing here: **the write happens only inside [setMode]**. Eagerly
/// persisting the default the first time the screen renders would freeze
/// today's choice into every existing install, and a later change of default
/// would silently never reach any of them.
library;

import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

const roomViewModePrefsKey = 'ami_room_view_mode';

enum RoomViewMode { board, transcript }

class RoomViewModeNotifier extends StateNotifier<RoomViewMode> {
  /// A fresh install lands on **BOARD**. The complaint this CR answers is
  /// "too much to read"; the default has to be the thing that answers it. A
  /// user who wants the prose will find a two-segment toggle sitting above it;
  /// a user drowning in prose does not go looking for a shortening control.
  RoomViewModeNotifier() : super(RoomViewMode.board) {
    _hydrate();
  }

  @visibleForTesting
  RoomViewModeNotifier.withoutHydration(super.initial);

  Future<void> _hydrate() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final stored = prefs.getString(roomViewModePrefsKey);
      if (stored != null) state = _fromString(stored);
    } catch (_) {
      // Best-effort. An unreadable preference falls back to the default rather
      // than blocking the screen.
    }
  }

  /// The ONLY writer. CR106 T-MODESIDE: a mode change triggered as a side
  /// effect of something else — the peek sheet's `READ THE FULL DEBATE`, most
  /// obviously — must not rewrite what every future Room opens as. One curious
  /// tap is not a preference.
  Future<void> setMode(RoomViewMode mode) async {
    state = mode;
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString(roomViewModePrefsKey, _toString(mode));
    } catch (_) {}
  }

  static RoomViewMode _fromString(String s) =>
      s == 'transcript' ? RoomViewMode.transcript : RoomViewMode.board;

  static String _toString(RoomViewMode m) =>
      m == RoomViewMode.transcript ? 'transcript' : 'board';
}

final roomViewModeProvider =
    StateNotifierProvider<RoomViewModeNotifier, RoomViewMode>((ref) {
  return RoomViewModeNotifier();
});
