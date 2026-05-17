/// Tour service — tracks which per-section walkthroughs have been seen and
/// exposes a reset method wired to Settings → Restart app tour.
library;

import 'package:shared_preferences/shared_preferences.dart';

enum TourSection { floor, portfolio, journal, lessons }

class TourService {
  static const _keys = {
    TourSection.floor: 'tour_floor_seen',
    TourSection.portfolio: 'tour_portfolio_seen',
    TourSection.journal: 'tour_journal_seen',
    TourSection.lessons: 'tour_lessons_seen',
  };

  Future<bool> hasSeen(TourSection section) async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getBool(_keys[section]!) ?? false;
  }

  Future<void> markSeen(TourSection section) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool(_keys[section]!, true);
  }

  Future<void> resetAll() async {
    final prefs = await SharedPreferences.getInstance();
    for (final key in _keys.values) {
      await prefs.remove(key);
    }
  }
}
