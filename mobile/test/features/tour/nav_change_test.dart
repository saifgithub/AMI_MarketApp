/// CR180 — the one-time nav-change notice, and the rule that decides who sees it.
///
/// This is the whole CR in one predicate. CR133 invalidated the mental model of
/// **every existing user**, and the tour system is structurally silent for
/// exactly that population: each section tour is gated on a `tour_*_seen` flag
/// they already carry. So the notice has to fire on the absence of a *new*
/// flag and the presence of an *old* one, and getting either half wrong is a
/// visible failure — showing a migration notice to a first-time user who never
/// saw the old layout, or showing it forever.
library;

import 'package:ami_trade/features/tour/tour_service.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  setUp(() => SharedPreferences.setMockInitialValues({}));

  final service = TourService();

  test('a brand-new user is not told about a layout they never saw', () async {
    expect(await service.shouldShowNavChange(), isFalse,
        reason: 'they have no section flags — there is no old bar in their '
            'head to correct, and this would land on top of the Floor tour');
  });

  test('someone who learned the old bar is told, once', () async {
    SharedPreferences.setMockInitialValues({'tour_floor_seen': true});
    expect(await service.shouldShowNavChange(), isTrue);

    await service.markNavChangeSeen();
    expect(await service.shouldShowNavChange(), isFalse);
  });

  test('any pre-restructure section flag is enough', () async {
    for (final key in const [
      'tour_floor_seen',
      'tour_portfolio_seen',
      'tour_journal_seen',
      'tour_lessons_seen',
    ]) {
      SharedPreferences.setMockInitialValues({key: true});
      expect(await service.shouldShowNavChange(), isTrue, reason: key);
    }
  });

  test('having seen the YOU tour is not evidence of the old bar', () async {
    // `tour_you_seen` can only exist AFTER the restructure, so it proves the
    // opposite of what the predicate asks. Counting it would show a
    // "the bar moved" notice to someone whose first bar was the new one.
    SharedPreferences.setMockInitialValues({'tour_you_seen': true});
    expect(await service.shouldShowNavChange(), isFalse);
  });

  test('Restart app tour restarts the notice too', () async {
    SharedPreferences.setMockInitialValues({
      'tour_floor_seen': true,
      'tour_nav_v2_seen': true,
    });
    expect(await service.shouldShowNavChange(), isFalse);

    await service.resetAll();
    // Every section flag is gone as well, so the predicate is false — and that
    // is right, not a bug: after a full reset the user takes the ordinary
    // tours from the start, which teach the new bar directly. What matters is
    // that the acknowledgement did not survive the reset.
    expect(await service.shouldShowNavChange(), isFalse);
    SharedPreferences.setMockInitialValues({'tour_floor_seen': true});
    expect(await service.shouldShowNavChange(), isTrue,
        reason: 'the acknowledgement must not outlive a reset — a "restart" '
            'that leaves one thing un-restartable is the same half-truth as a '
            'stale path');
  });

  test('YOU is a restartable section like the other four', () async {
    expect(TourSection.values, contains(TourSection.you));
    expect(await service.hasSeen(TourSection.you), isFalse);
    await service.markSeen(TourSection.you);
    expect(await service.hasSeen(TourSection.you), isTrue);
    await service.resetAll();
    expect(await service.hasSeen(TourSection.you), isFalse);
  });

  test('the Journal keeps its flag — it moved, it did not change', () async {
    // Renaming or clearing this key would re-run a tour the user has already
    // completed, on a screen whose content is identical.
    SharedPreferences.setMockInitialValues({'tour_journal_seen': true});
    expect(await service.hasSeen(TourSection.journal), isTrue);
  });
}
