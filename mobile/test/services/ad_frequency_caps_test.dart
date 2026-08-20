/// CR122-MOBILE-B — persisted frequency caps.
///
/// The load-bearing behaviours proven here:
///   * cap arithmetic at and around every `ads.md:59-60` boundary (1 per
///     5 lessons, ≤4/session, ≥10 min apart, ≤8/day);
///   * counters SURVIVE a simulated cold start (a new [AdFrequencyCaps] over
///     the same store keeps the session count inside the 30-min gap — the
///     force-quit laundering path stays closed) and reset only after a
///     genuine session gap, with the day cap still holding;
///   * an unreadable or corrupt cap store BLOCKS the ad
///     ([AdRefusalReason.capStoreUnreadable]) — never allows.
library;

import 'package:ami_trade/services/ads/ad_frequency_caps.dart';
import 'package:ami_trade/services/ads/ads_models.dart';
import 'package:flutter_test/flutter_test.dart';

import '../support/ad_cap_fakes.dart';

/// Mutable clock so gap/day boundaries are exact, not sleep-based.
class TestClock {
  TestClock(this.now);
  DateTime now;
  void advance(Duration d) => now = now.add(d);
}

void main() {
  late MemoryCapStore store;
  late TestClock clock;
  late AdFrequencyCaps caps;

  AdFrequencyCaps capsOver(AdCapStore s) =>
      AdFrequencyCaps(s, clock: () => clock.now);

  setUp(() {
    store = MemoryCapStore();
    clock = TestClock(DateTime(2026, 8, 20, 10));
    caps = capsOver(store);
  });

  Future<void> feedLessons([int n = 5]) async {
    for (var i = 0; i < n; i++) {
      await caps.recordLessonCompleted();
    }
  }

  group('interstitial caps', () {
    test('blocked until 5 lessons completed, allowed at exactly 5', () async {
      await feedLessons(4);
      expect(await caps.checkInterstitial(), AdRefusalReason.capReached);
      await caps.recordLessonCompleted();
      expect(await caps.checkInterstitial(), isNull);
    });

    test('impression resets the lesson counter', () async {
      await feedLessons();
      await caps.recordImpression(AdFormat.interstitial);
      clock.advance(const Duration(minutes: 11));
      expect(await caps.checkInterstitial(), AdRefusalReason.capReached);
    });

    test('10-minute gap: blocked at 9, allowed at 10', () async {
      await feedLessons();
      await caps.recordImpression(AdFormat.interstitial);
      await feedLessons();
      clock.advance(const Duration(minutes: 9));
      expect(await caps.checkInterstitial(), AdRefusalReason.capReached);
      clock.advance(const Duration(minutes: 1));
      expect(await caps.checkInterstitial(), isNull);
    });

    test('4 per session: the 5th is blocked with every other cap clear',
        () async {
      for (var i = 0; i < 4; i++) {
        await feedLessons();
        clock.advance(const Duration(minutes: 11));
        expect(await caps.checkInterstitial(), isNull);
        await caps.recordImpression(AdFormat.interstitial);
      }
      await feedLessons();
      clock.advance(const Duration(minutes: 11));
      expect(await caps.checkInterstitial(), AdRefusalReason.capReached);
    });
  });

  group('daily cap', () {
    test('8 impressions/day: 8th allowed, 9th blocked, next day clear',
        () async {
      for (var i = 0; i < 8; i++) {
        expect(await caps.checkNative(), isNull);
        await caps.recordImpression(AdFormat.nativeCard);
        clock.advance(const Duration(minutes: 40));
      }
      expect(await caps.checkNative(), AdRefusalReason.capReached);
      await feedLessons();
      expect(await caps.checkInterstitial(), AdRefusalReason.capReached);
      clock.advance(const Duration(days: 1));
      expect(await caps.checkNative(), isNull);
    });
  });

  group('cold-start persistence (the point of MOBILE-B)', () {
    test('session count survives a relaunch inside the session gap',
        () async {
      for (var i = 0; i < 4; i++) {
        await feedLessons();
        clock.advance(const Duration(minutes: 11));
        await caps.recordImpression(AdFormat.interstitial);
      }
      // Force-quit + relaunch 1 minute later: same store, new instance.
      clock.advance(const Duration(minutes: 1));
      final relaunched = capsOver(store);
      await relaunched.startSession();
      await relaunched.recordLessonCompleted();
      for (var i = 0; i < 4; i++) {
        await relaunched.recordLessonCompleted();
      }
      clock.advance(const Duration(minutes: 11));
      expect(
          await relaunched.checkInterstitial(), AdRefusalReason.capReached);
    });

    test('a genuine new session resets the session count, day cap holds',
        () async {
      for (var i = 0; i < 4; i++) {
        await feedLessons();
        clock.advance(const Duration(minutes: 11));
        await caps.recordImpression(AdFormat.interstitial);
      }
      clock.advance(const Duration(minutes: 31));
      final relaunched = capsOver(store);
      await relaunched.startSession();
      await feedLessonsOn(relaunched, 5);
      expect(await relaunched.checkInterstitial(), isNull);
      // ...but the day total (4 so far) still counts toward 8.
      for (var i = 0; i < 4; i++) {
        await relaunched.recordImpression(AdFormat.nativeCard);
        clock.advance(const Duration(minutes: 1));
      }
      expect(await relaunched.checkNative(), AdRefusalReason.capReached);
    });
  });

  group('unreadable store BLOCKS (never unlimited)', () {
    test('throwing store blocks native and interstitial', () async {
      final broken = capsOver(ThrowingCapStore());
      expect(await broken.checkNative(), AdRefusalReason.capStoreUnreadable);
      expect(await broken.checkInterstitial(),
          AdRefusalReason.capStoreUnreadable);
    });

    test('corrupt int blocks', () async {
      final corrupt = capsOver(
          MemoryCapStore({'ads.caps.day_impressions': 'not-a-number'}));
      expect(
          await corrupt.checkNative(), AdRefusalReason.capStoreUnreadable);
    });

    test('corrupt timestamp blocks', () async {
      final corrupt = capsOver(
          MemoryCapStore({'ads.caps.last_impression_at': 'yesterdayish'}));
      expect(await corrupt.checkInterstitial(),
          AdRefusalReason.capStoreUnreadable);
    });
  });
}

Future<void> feedLessonsOn(AdFrequencyCaps c, int n) async {
  for (var i = 0; i < n; i++) {
    await c.recordLessonCompleted();
  }
}
