/// DEF375 — `TourService.hasSeen` under the QA tour-skip.
///
/// `TourQaConfig.skipToursForQa` reads a real `String.fromEnvironment`
/// dart-define, which a test cannot flip (it is fixed for the whole test
/// binary, and this suite is run with none of the QA defines set). So this
/// exercises the same branch `TourQaConfig`'s own resolver already proved
/// correct (`tour_qa_config_test.dart`) through `TourService`'s injectable
/// constructor seam — proving the WIRING, not re-proving the resolver.
///
/// Three things DEF375's brief asks for, each its own group below:
///   * suppressed under the QA flag (stands in for "non-production channel")
///   * NOT suppressed when the flag resolves false (stands in for
///     "production channel", where `TourQaConfig.resolve` already proved the
///     flag is refused regardless of what was passed)
///   * a QA run never reads OR writes `SharedPreferences` — so it cannot
///     leave state a later, real check on the same install would misread.
library;

import 'package:ami_trade/features/tour/tour_service.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  group('skipToursForQa: true — the non-production QA build the harness '
      'runs', () {
    setUp(() => SharedPreferences.setMockInitialValues({}));

    test('every one of the five sections reports already-seen', () async {
      final service = TourService(skipToursForQa: true);
      for (final section in TourSection.values) {
        expect(await service.hasSeen(section), isTrue, reason: section.name);
      }
    });

    test('reports seen even on a section nothing has ever marked', () async {
      // The harness always drives a fresh install (CR162), so this is the
      // only case that matters, but it also proves the check does not
      // depend on SharedPreferences ever having a value for the key.
      SharedPreferences.setMockInitialValues({});
      final service = TourService(skipToursForQa: true);
      expect(await service.hasSeen(TourSection.floor), isTrue);
    });

    test('never writes tour_*_seen — a QA run leaves no residue a later '
        'real check could misread', () async {
      SharedPreferences.setMockInitialValues({});
      final service = TourService(skipToursForQa: true);
      await service.hasSeen(TourSection.floor);
      await service.hasSeen(TourSection.you);
      final prefs = await SharedPreferences.getInstance();
      for (final key in const [
        'tour_floor_seen',
        'tour_portfolio_seen',
        'tour_journal_seen',
        'tour_lessons_seen',
        'tour_you_seen',
      ]) {
        expect(prefs.getBool(key), isNull, reason: key);
      }
    });

    test('the CR180 nav-change notice does not fire either — no '
        'pre-restructure flag was ever set to trigger it', () async {
      SharedPreferences.setMockInitialValues({});
      final service = TourService(skipToursForQa: true);
      await service.hasSeen(TourSection.floor);
      expect(await service.shouldShowNavChange(), isFalse);
    });
  });

  group('skipToursForQa: false — production channel, or no QA define at '
      'all (every store build, every real user)', () {
    setUp(() => SharedPreferences.setMockInitialValues({}));

    test('an unseen section reports unseen — tours show normally', () async {
      final service = TourService(skipToursForQa: false);
      expect(await service.hasSeen(TourSection.floor), isFalse);
    });

    test('markSeen/hasSeen round-trip exactly as before DEF375', () async {
      final service = TourService(skipToursForQa: false);
      expect(await service.hasSeen(TourSection.portfolio), isFalse);
      await service.markSeen(TourSection.portfolio);
      expect(await service.hasSeen(TourSection.portfolio), isTrue);
    });

    test('default constructor (no override) behaves like production in '
        'this test binary — no AMI_QA_SKIP_TOURS define is passed to '
        '`flutter test`', () async {
      final service = TourService();
      expect(await service.hasSeen(TourSection.lessons), isFalse);
    });
  });
}
