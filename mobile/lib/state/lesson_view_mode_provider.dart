/// CR174 §2 — which way a lesson opens: the book, or the beat deck.
///
/// Modelled on [roomViewModeProvider] deliberately, including the property that
/// carries the design there: **the write happens only inside [setMode]**. If the
/// resolved default were persisted the first time a reader rendered, today's
/// choice would freeze into every existing install and a later change of default
/// would never reach any of them.
///
/// The difference from the Room is the *shape of the default*. CR174 §2 seeds
/// the mode from `mandate.learning_style`, which is a live field that already
/// shapes agent tone (`overlay_generator.py:236`) and has never reached lessons.
/// A seed is not a stored preference, so this notifier holds `LessonViewMode?`:
///
///   - `null` — the user has never chosen, so [defaultLessonViewMode] answers,
///     and it answers freshly every time the mandate changes.
///   - a value — the user chose, and their choice outranks the seed forever.
///
/// Collapsing those two into one non-nullable field is what would make the seed
/// unreachable: there would be no way to tell "book because they picked book"
/// from "book because that is what we happened to default to on first render".
library;

import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

const lessonViewModePrefsKey = 'ami_lesson_view_mode';

enum LessonViewMode { book, interactive }

/// The seed for a user who has never chosen, from their mandate's
/// `learning_style` (`quick | story | visual | hands_on`).
///
/// **`story` is the only value that asks for prose**, and it maps to book mode
/// because it is the one style whose stated preference the beat deck would
/// contradict. Everything else — including a value this build does not
/// recognise — lands on the CR's declared default rather than on a guess about
/// what an unknown style might have wanted (DEF210). R3 is why the default is
/// derived at all: daily challenges are shipped, graded and interactive, and
/// **4 of 172 users found them**. An interactive mode nobody is defaulted into
/// earns that same number.
LessonViewMode defaultLessonViewMode(String? learningStyle) =>
    switch (learningStyle) {
      'story' => LessonViewMode.book,
      _ => LessonViewMode.interactive,
    };

/// The mode a reader actually renders in: the user's own choice when they made
/// one, otherwise the seed. One function so the reader and its tests cannot
/// disagree about the resolution order (DEF098).
LessonViewMode resolveLessonViewMode({
  required LessonViewMode? chosen,
  required String? learningStyle,
}) =>
    chosen ?? defaultLessonViewMode(learningStyle);

class LessonViewModeNotifier extends StateNotifier<LessonViewMode?> {
  LessonViewModeNotifier() : super(null) {
    _hydrate();
  }

  @visibleForTesting
  LessonViewModeNotifier.withoutHydration(super.initial);

  Future<void> _hydrate() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final stored = prefs.getString(lessonViewModePrefsKey);
      if (stored != null) state = _fromString(stored);
    } catch (_) {
      // Best-effort. An unreadable preference falls back to the seed rather
      // than blocking the reader.
    }
  }

  /// The ONLY writer.
  Future<void> setMode(LessonViewMode mode) async {
    state = mode;
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString(lessonViewModePrefsKey, _toString(mode));
    } catch (_) {}
  }

  /// An unrecognised stored string resolves to **unset**, not to a bucket.
  /// The value outlives the build that wrote it, and "we cannot read this" and
  /// "they chose book" are different facts — collapsing them would silently
  /// convert a future third mode into a recorded preference for book (DEF210).
  static LessonViewMode? _fromString(String s) => switch (s) {
        'book' => LessonViewMode.book,
        'interactive' => LessonViewMode.interactive,
        _ => null,
      };

  static String _toString(LessonViewMode m) => switch (m) {
        LessonViewMode.book => 'book',
        LessonViewMode.interactive => 'interactive',
      };
}

final lessonViewModeProvider =
    StateNotifierProvider<LessonViewModeNotifier, LessonViewMode?>((ref) {
  return LessonViewModeNotifier();
});
