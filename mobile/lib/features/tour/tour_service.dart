/// Tour service — tracks which per-section walkthroughs have been seen and
/// exposes a reset method wired to Settings → Restart app tour.
library;

import 'package:ami_trade/qa/tour_qa_config.dart';
import 'package:shared_preferences/shared_preferences.dart';

enum TourSection { floor, portfolio, journal, lessons, you }

class TourService {
  TourService({bool? skipToursForQa})
      : _skipToursForQa = skipToursForQa ?? TourQaConfig.skipToursForQa;

  /// Overridable only from a test — `tourServiceProvider` always constructs
  /// with the default, which reads the real dart-define. A test cannot flip
  /// a compile-time `String.fromEnvironment` constant, so this is the seam
  /// that lets `hasSeen`'s QA branch be exercised both ways without one.
  final bool _skipToursForQa;

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

  /// DEF375 — every call site (`floor_screen.dart`, `portfolio_screen.dart`,
  /// `journal_screen.dart`, `lessons_screen.dart`, `you_screen.dart`) checks
  /// this before ever showing a tour, so gating it here covers all five
  /// without touching a single screen. `TourQaConfig.skipToursForQa` is only
  /// ever true on a non-production channel with the QA dart-define set — see
  /// its doc for the structural guarantee. Deliberately checked BEFORE
  /// `SharedPreferences` is touched: a QA run never reads or writes the
  /// `tour_*_seen` flags at all, so it cannot leave state a later, non-QA
  /// check on the same install would misread.
  Future<bool> hasSeen(TourSection section) async {
    if (_skipToursForQa) return true;
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
