/// Tour service — tracks which per-section walkthroughs have been seen and
/// exposes a reset method wired to Settings → Restart app tour.
library;

import 'package:shared_preferences/shared_preferences.dart';

enum TourSection { floor, portfolio, journal, lessons, you }

class TourService {
  static const _keys = {
    TourSection.floor: 'tour_floor_seen',
    TourSection.portfolio: 'tour_portfolio_seen',
    // CR133 moved the Journal inside `YOU`. The KEY is deliberately unchanged:
    // the Journal itself did not change, only its address, so a user who has
    // already taken this tour must not be made to take it again.
    TourSection.journal: 'tour_journal_seen',
    TourSection.lessons: 'tour_lessons_seen',
    TourSection.you: 'tour_you_seen',
  };

  /// CR180 — the one-time notice that the bottom nav was restructured.
  static const _navChangeKey = 'tour_nav_v2_seen';

  Future<bool> hasSeen(TourSection section) async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getBool(_keys[section]!) ?? false;
  }

  Future<void> markSeen(TourSection section) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool(_keys[section]!, true);
  }

  /// Whether to tell this user that the bar moved (CR180).
  ///
  /// Only for someone who **learned the old bar**: at least one section tour
  /// seen from before the restructure, and no acknowledgement yet. A brand-new
  /// user has neither flag and gets the ordinary tour instead — a migration
  /// notice about a layout they never saw is noise, and it would land in the
  /// same moment as the Floor tour it would then be competing with.
  ///
  /// `TourSection.you` is excluded from the "learned the old bar" test on
  /// purpose: it did not exist before the restructure, so seeing it proves the
  /// opposite of what this asks.
  Future<bool> shouldShowNavChange() async {
    final prefs = await SharedPreferences.getInstance();
    if (prefs.getBool(_navChangeKey) ?? false) return false;
    return _preRestructureKeys.any((k) => prefs.getBool(k) ?? false);
  }

  Future<void> markNavChangeSeen() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool(_navChangeKey, true);
  }

  static const _preRestructureKeys = [
    'tour_floor_seen',
    'tour_portfolio_seen',
    'tour_journal_seen',
    'tour_lessons_seen',
  ];

  Future<void> resetAll() async {
    final prefs = await SharedPreferences.getInstance();
    for (final key in _keys.values) {
      await prefs.remove(key);
    }
    // A "restart" that leaves one thing un-restartable is the same half-truth
    // as a stale path. Cleared last so a crash mid-reset cannot leave the
    // notice armed against a user who now has no section flags at all — with
    // every section flag gone, `shouldShowNavChange` is false regardless.
    await prefs.remove(_navChangeKey);
  }
}
