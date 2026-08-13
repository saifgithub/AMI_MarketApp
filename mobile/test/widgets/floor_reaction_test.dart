/// CR173 §5.12 — the reaction card fires once and only once.
///
/// The acceptance is one sentence ("some capture path"), so the failure modes
/// are the interesting part: a prompt that asks on the first frame, a prompt
/// that comes back after being dismissed, or a prompt that thanks the user for
/// something that never left the device.
library;

import 'package:ami_trade/widgets/floor/floor_reaction_card.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  setUp(() => SharedPreferences.setMockInitialValues({}));

  test('it waits until there is something to react to', () async {
    for (var visit = 1; visit < kFloorReactionAfterVisits; visit++) {
      expect(await registerFloorVisit(), isFalse,
          reason: 'asking on visit $visit is asking about a screen the user '
              'has not used yet');
    }
    expect(await registerFloorVisit(), isTrue);
  });

  test('answering it retires it', () async {
    for (var i = 0; i < kFloorReactionAfterVisits; i++) {
      await registerFloorVisit();
    }
    await markFloorReactionDone();
    for (var i = 0; i < 20; i++) {
      expect(await registerFloorVisit(), isFalse,
          reason: 'a one-time prompt that returns is a nag, and a nag gets '
              'dismissed unread — which loses the very signal it exists for');
    }
  });

  test('a spent prompt stops writing the counter', () async {
    // Not cosmetic: without the early return the visit count grows forever on
    // a preference nothing will ever read again.
    for (var i = 0; i < kFloorReactionAfterVisits; i++) {
      await registerFloorVisit();
    }
    await markFloorReactionDone();
    final prefs = await SharedPreferences.getInstance();
    final parked = prefs.getInt('floor_v02_visits');
    await registerFloorVisit();
    expect(prefs.getInt('floor_v02_visits'), parked);
  });
}
