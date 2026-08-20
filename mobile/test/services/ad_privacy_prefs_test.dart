/// CR122-COMPLIANCE — the persisted CCPA "Do Not Sell" election.
///
/// Failure direction is the point: an unreadable store answers true (fail
/// toward privacy — AdMob gets rdp=1 on a pref we could not read), and a
/// failed write SURFACES instead of silently dropping the election.
library;

import 'package:ami_trade/services/ads/ad_privacy_prefs.dart';
import 'package:flutter_test/flutter_test.dart';

import '../support/ad_cap_fakes.dart';

void main() {
  test('defaults to false when nothing is recorded', () async {
    expect(await AdPrivacyPrefs(MemoryCapStore()).doNotSell(), isFalse);
  });

  test('a set election persists and reads back', () async {
    final store = MemoryCapStore();
    final prefs = AdPrivacyPrefs(store);
    await prefs.setDoNotSell(true);
    expect(await AdPrivacyPrefs(store).doNotSell(), isTrue);
    await prefs.setDoNotSell(false);
    expect(await AdPrivacyPrefs(store).doNotSell(), isFalse);
  });

  test('an unreadable store fails TOWARD privacy: doNotSell = true',
      () async {
    expect(await AdPrivacyPrefs(ThrowingCapStore()).doNotSell(), isTrue);
  });

  test('a failed write surfaces to the caller, never silently drops',
      () async {
    expect(AdPrivacyPrefs(ThrowingCapStore()).setDoNotSell(true),
        throwsStateError);
  });
}
