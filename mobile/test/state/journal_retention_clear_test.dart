/// DEF156 — a plan upgrade could never clear the journal retention caveat.
///
/// `JournalState.copyWith` used `retentionDays ?? this.retentionDays`, so
/// passing null read as "leave it alone" rather than "unlimited". A user on
/// Floor Pass has a finite `retentionDays`; when they upgrade in-session
/// through RevenueCat, `refresh()` receives null and the stale finite value
/// survived — so the app kept showing the retention warning, and CR120's
/// Portfolio Journal pointer kept computing an older-entry count from a cap
/// that no longer applied, until the user relaunched.
///
/// Found by the CR120 builder, which correctly declined to fix it in-lane
/// (out of scope) and disclosed it instead.
library;

import 'package:ami_trade/state/journal_providers.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('DEF156 — retention can be cleared, not only replaced', () {
    test('the upgrade path: a finite cap becomes unlimited', () {
      const capped = JournalState(retentionDays: 30, retentionLoaded: true);
      final upgraded = capped.copyWith(
        retentionDays: null,
        clearRetentionDays: true,
        retentionLoaded: true,
      );
      expect(upgraded.retentionDays, isNull);
      expect(upgraded.retentionLoaded, isTrue,
          reason: 'unlimited is a known answer, not an unknown one');
    });

    test('the trap it replaces: passing null alone still means "unchanged"', () {
      // Documented deliberately. `?? this.x` is the right default for every
      // other field on this class, so the fix is an explicit flag rather than
      // a sentinel — and a future edit that drops the flag lands right back
      // on this behaviour.
      const capped = JournalState(retentionDays: 30, retentionLoaded: true);
      expect(capped.copyWith(retentionDays: null).retentionDays, 30);
    });

    test('a finite cap still replaces another finite cap', () {
      const capped = JournalState(retentionDays: 30, retentionLoaded: true);
      expect(capped.copyWith(retentionDays: 7).retentionDays, 7);
    });

    test('clearing does not disturb the rest of the state', () {
      const before = JournalState(
        retentionDays: 30,
        retentionLoaded: true,
        searchQuery: 'nvda',
      );
      final after = before.copyWith(clearRetentionDays: true);
      expect(after.retentionDays, isNull);
      expect(after.searchQuery, 'nvda');
    });
  });
}
