/// Persisted ad frequency caps (CR122-MOBILE-B).
///
/// The caps of `ads.md:59-60`: max 1 interstitial per 5 lessons completed,
/// max 4 interstitials per session, min 10 minutes between interstitials,
/// ≤ 8 ad impressions per day. Every counter lives in [AdCapStore] (backed by
/// SharedPreferences), NOT in memory, because an in-memory counter resets on
/// every cold start — which silently turns "max 4 per session" into
/// "unlimited" for anyone who force-quits, while looking exactly like normal
/// ad delivery. Two consequences of that reasoning are binding here:
///
///  * "Session" is defined against the persisted last-impression time: the
///    session interstitial count survives a relaunch and only resets when
///    [sessionGap] has passed since the last impression. A rapid force-quit
///    loop therefore keeps its count instead of laundering it away.
///  * A cap that cannot be read BLOCKS the ad (CR040 degrade-loudly): any
///    store read that throws, or any stored value that fails to parse,
///    returns [AdRefusalReason.capStoreUnreadable] — never "allow".
library;

import 'package:ami_trade/services/ads/ads_models.dart';
import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';

/// Minimal string KV seam so tests can inject throwing/corrupt stores.
abstract class AdCapStore {
  Future<String?> read(String key);
  Future<void> write(String key, String value);
}

class SharedPreferencesAdCapStore implements AdCapStore {
  @override
  Future<String?> read(String key) async =>
      (await SharedPreferences.getInstance()).getString(key);

  @override
  Future<void> write(String key, String value) async =>
      (await SharedPreferences.getInstance()).setString(key, value);
}

/// Parsed snapshot of all persisted counters. `null` from [_load] means the
/// store is unreadable — the caller must block, not default.
class _CapState {
  _CapState({
    required this.sessionInterstitials,
    required this.lessonsSinceInterstitial,
    required this.lastInterstitialAt,
    required this.lastImpressionAt,
    required this.dayKey,
    required this.dayImpressions,
  });

  int sessionInterstitials;
  int lessonsSinceInterstitial;
  DateTime? lastInterstitialAt;
  DateTime? lastImpressionAt;
  String? dayKey;
  int dayImpressions;
}

class AdFrequencyCaps {
  AdFrequencyCaps(this._store, {DateTime Function()? clock})
      : _clock = clock ?? DateTime.now;

  final AdCapStore _store;
  final DateTime Function() _clock;

  static const maxInterstitialsPerSession = 4;
  static const lessonsPerInterstitial = 5;
  static const minInterstitialGap = Duration(minutes: 10);
  static const maxImpressionsPerDay = 8;

  /// Quiet time after the last impression before a relaunch counts as a NEW
  /// session (the conventional analytics session boundary). Shorter would
  /// re-open the cold-start laundering hole; longer only under-serves.
  static const sessionGap = Duration(minutes: 30);

  static const _kSessionInterstitials = 'ads.caps.session_interstitials';
  static const _kLessonsSince = 'ads.caps.lessons_since_interstitial';
  static const _kLastInterstitialAt = 'ads.caps.last_interstitial_at';
  static const _kLastImpressionAt = 'ads.caps.last_impression_at';
  static const _kDayKey = 'ads.caps.day_key';
  static const _kDayImpressions = 'ads.caps.day_impressions';

  static String _dayKeyFor(DateTime now) =>
      '${now.year}-${now.month.toString().padLeft(2, '0')}-'
      '${now.day.toString().padLeft(2, '0')}';

  /// Load every counter. Missing keys are legitimate fresh-install zeros;
  /// a throwing read or an unparseable value is NOT — that returns null and
  /// the caller blocks the ad.
  Future<_CapState?> _load() async {
    try {
      final session = await _readInt(_kSessionInterstitials);
      final lessons = await _readInt(_kLessonsSince);
      final lastInterstitial = await _readTime(_kLastInterstitialAt);
      final lastImpression = await _readTime(_kLastImpressionAt);
      final dayKey = await _store.read(_kDayKey);
      final dayCount = await _readInt(_kDayImpressions);
      return _CapState(
        sessionInterstitials: session,
        lessonsSinceInterstitial: lessons,
        lastInterstitialAt: lastInterstitial,
        lastImpressionAt: lastImpression,
        dayKey: dayKey,
        dayImpressions: dayCount,
      );
    } catch (e) {
      debugPrint('CR122 AdFrequencyCaps: cap store unreadable — '
          'BLOCKING ads (never unlimited): $e');
      return null;
    }
  }

  Future<int> _readInt(String key) async {
    final raw = await _store.read(key);
    if (raw == null) return 0;
    final v = int.tryParse(raw);
    if (v == null) throw FormatException('corrupt int for $key: "$raw"');
    return v;
  }

  Future<DateTime?> _readTime(String key) async {
    final raw = await _store.read(key);
    if (raw == null) return null;
    final v = DateTime.tryParse(raw);
    if (v == null) throw FormatException('corrupt time for $key: "$raw"');
    return v;
  }

  /// App-launch hook. Resets the per-session interstitial count ONLY when
  /// [sessionGap] has passed since the last impression — a relaunch inside
  /// the gap keeps its count (the cold-start laundering this lane closes).
  Future<void> startSession() async {
    final s = await _load();
    if (s == null) return; // unreadable ⇒ checks below block anyway
    final now = _clock();
    final last = s.lastImpressionAt;
    if (last == null || now.difference(last) >= sessionGap) {
      await _store.write(_kSessionInterstitials, '0');
    }
  }

  /// Null ⇒ allowed. Non-null ⇒ the reason to block.
  Future<AdRefusalReason?> checkNative() async {
    final s = await _load();
    if (s == null) return AdRefusalReason.capStoreUnreadable;
    if (_dayImpressionsFor(s, _clock()) >= maxImpressionsPerDay) {
      return AdRefusalReason.capReached;
    }
    return null;
  }

  /// Null ⇒ allowed. Applies all four `ads.md` caps.
  Future<AdRefusalReason?> checkInterstitial() async {
    final s = await _load();
    if (s == null) return AdRefusalReason.capStoreUnreadable;
    final now = _clock();
    if (_dayImpressionsFor(s, now) >= maxImpressionsPerDay) {
      return AdRefusalReason.capReached;
    }
    if (s.sessionInterstitials >= maxInterstitialsPerSession) {
      return AdRefusalReason.capReached;
    }
    if (s.lessonsSinceInterstitial < lessonsPerInterstitial) {
      return AdRefusalReason.capReached;
    }
    final last = s.lastInterstitialAt;
    if (last != null && now.difference(last) < minInterstitialGap) {
      return AdRefusalReason.capReached;
    }
    return null;
  }

  int _dayImpressionsFor(_CapState s, DateTime now) =>
      s.dayKey == _dayKeyFor(now) ? s.dayImpressions : 0;

  /// Called once per ad actually shown. Persists everything immediately so a
  /// kill right after an impression still counts it.
  Future<void> recordImpression(AdFormat format) async {
    final s = await _load();
    if (s == null) {
      // Unreadable ⇒ the check should have blocked; nothing sane to write.
      debugPrint('CR122 AdFrequencyCaps: recordImpression on unreadable '
          'store — skipped (ads are blocked in this state)');
      return;
    }
    final now = _clock();
    await _store.write(_kDayKey, _dayKeyFor(now));
    await _store.write(
        _kDayImpressions, '${_dayImpressionsFor(s, now) + 1}');
    await _store.write(_kLastImpressionAt, now.toIso8601String());
    if (format == AdFormat.interstitial) {
      await _store.write(
          _kSessionInterstitials, '${s.sessionInterstitials + 1}');
      await _store.write(_kLastInterstitialAt, now.toIso8601String());
      await _store.write(_kLessonsSince, '0');
    }
  }

  /// Advances the 1-interstitial-per-5-lessons counter.
  Future<void> recordLessonCompleted() async {
    final s = await _load();
    if (s == null) return;
    await _store.write(_kLessonsSince, '${s.lessonsSinceInterstitial + 1}');
  }
}
