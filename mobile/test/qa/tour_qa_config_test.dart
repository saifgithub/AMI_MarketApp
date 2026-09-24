/// DEF375 — the pure resolver behind the QA-only tour skip.
///
/// Same shape as `admob_config_test.dart` (CR225): `resolve`/`parseChannel`
/// take their inputs as parameters so the compile-time dart-define constants
/// (fixed for this whole test binary) can still be varied from a test.
///
/// The one guarantee this file exists to prove: `AMI_QA_SKIP_TOURS` is never
/// honoured on `channel: production`, whatever the flag says — that is the
/// entire "never weaken what a real user sees" contract. Everything else
/// (unknown/internal both count as skippable, unrecognised channel strings
/// fall back to the conservative default) mirrors CR225's own reasoning
/// because it is the same problem shape.
library;

import 'package:ami_trade/qa/tour_qa_config.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  setUp(TourQaConfig.resetForTest);
  tearDown(TourQaConfig.resetForTest);

  group('AMI_QA_SKIP_TOURS is never honoured on production', () {
    test('flag set, channel production => tours show (skip refused)', () {
      final skip = TourQaConfig.resolve(
        skipFlagRaw: 'true',
        channel: TourQaReleaseChannel.production,
      );
      expect(skip, isFalse);
    });

    test('flag set, channel internal => skip', () {
      final skip = TourQaConfig.resolve(
        skipFlagRaw: 'true',
        channel: TourQaReleaseChannel.internal_,
      );
      expect(skip, isTrue);
    });

    test('flag set, channel unset/unknown => skip (conservative default '
        'still allows a QA build with no channel forwarded, e.g. '
        'build_qa_ios_sim.sh)', () {
      final skip = TourQaConfig.resolve(
        skipFlagRaw: 'true',
        channel: TourQaReleaseChannel.unknown,
      );
      expect(skip, isTrue);
    });
  });

  group('no define, no skip — the store-pipeline default', () {
    test('flag empty, any channel => never skip', () {
      for (final channel in TourQaReleaseChannel.values) {
        final skip = TourQaConfig.resolve(skipFlagRaw: '', channel: channel);
        expect(skip, isFalse, reason: channel.toString());
      }
    });
  });

  group('flag parsing — flexible truthy string, same lesson as '
      'AMI_QA_SEMANTICS (main.dart)', () {
    test('accepted spellings', () {
      for (final raw in const ['1', 'true', 'yes', 'on']) {
        expect(
          TourQaConfig.resolve(
            skipFlagRaw: raw,
            channel: TourQaReleaseChannel.unknown,
          ),
          isTrue,
          reason: raw,
        );
      }
    });

    test('anything else (including bool.fromEnvironment-style "false") is '
        'off', () {
      for (final raw in const ['false', '0', 'no', 'TRUE', ' true', '']) {
        expect(
          TourQaConfig.resolve(
            skipFlagRaw: raw,
            channel: TourQaReleaseChannel.unknown,
          ),
          isFalse,
          reason: raw,
        );
      }
    });
  });

  group('channel parsing', () {
    test('recognised literals', () {
      expect(TourQaConfig.parseChannel(''), TourQaReleaseChannel.unknown);
      expect(TourQaConfig.parseChannel('internal'),
          TourQaReleaseChannel.internal_);
      expect(TourQaConfig.parseChannel('production'),
          TourQaReleaseChannel.production);
    });

    test('unrecognised string falls back to unknown, never production', () {
      expect(TourQaConfig.parseChannel('prod'), TourQaReleaseChannel.unknown);
      expect(TourQaConfig.parseChannel('PRODUCTION'),
          TourQaReleaseChannel.unknown);
    });
  });

  group('memoised getter, no dart-define in this test binary', () {
    test('skipToursForQa is false with no defines passed to flutter test',
        () {
      expect(TourQaConfig.skipToursForQa, isFalse);
    });
  });
}
