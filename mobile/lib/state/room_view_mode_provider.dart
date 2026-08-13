/// CR106 — which view a Room run opens in: the Verdict Board, the collapsed
/// transcript, or (CR173) the live 12-seat floor.
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

/// One dial, three positions, read by two surfaces (CR173 Amendment B).
///
/// §1 mandates one enum, one key, one writer — which squeezes two independent
/// bits (live: briefing vs. roster; settled: board vs. prose) into three values,
/// so one combination is unrepresentable. Each surface reads the dial its own
/// way, and both readings live in [RoomViewModeX] below so neither can drift:
///
/// - live: `floor` ⇒ the 12-seat roster, anything else ⇒ the 4-stage briefing
/// - settled: `transcript` ⇒ the collapsed prose, anything else ⇒ the Board
///
/// So `floor` settles to the **Board**. The alternative — `floor` settling to
/// prose — means one tap on WATCH THE FLOOR during a live run silently replaces
/// the settled screen the user has always seen. The cost of this direction is
/// narrower: `transcript` does not survive a round trip through WATCH THE FLOOR.
enum RoomViewMode { board, transcript, floor }

extension RoomViewModeX on RoomViewMode {
  /// The live phase shows the twelve only when the user asked for them.
  bool get showsLiveFloor => this == RoomViewMode.floor;

  /// The settled run opens on prose only for the value that means prose.
  bool get showsTranscript => this == RoomViewMode.transcript;
}

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

  /// Anything unrecognised lands on the default rather than on a guess. The
  /// stored string outlives the build that wrote it: an install downgraded past
  /// CR173 reads `floor` and must fall back visibly to the shipped default, not
  /// be silently bucketed into `transcript` (DEF210).
  static RoomViewMode _fromString(String s) => switch (s) {
        'transcript' => RoomViewMode.transcript,
        'floor' => RoomViewMode.floor,
        _ => RoomViewMode.board,
      };

  static String _toString(RoomViewMode m) => switch (m) {
        RoomViewMode.transcript => 'transcript',
        RoomViewMode.floor => 'floor',
        RoomViewMode.board => 'board',
      };
}

final roomViewModeProvider =
    StateNotifierProvider<RoomViewModeNotifier, RoomViewMode>((ref) {
  return RoomViewModeNotifier();
});
