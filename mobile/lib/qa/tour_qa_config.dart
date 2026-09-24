/// DEF375 — a deterministic, test-build-only way to start the app with every
/// first-run coach-mark tour already marked seen.
///
/// The tours (`mobile/lib/features/tour/`) are modal: until one is dismissed,
/// the tab behind it is unreachable. On a fresh install — which is what the
/// UAT harness always drives, `noReset=False` (CR162) — that blocked 7 of 19
/// iOS gate tests, because tapping through a tour's own controls to dismiss
/// it (DEF382) collapses the iOS accessibility tree the harness reads from.
/// The tour-walking approach is dead on measurement; this is the other half
/// of DEF375's brief: don't fight the tour, don't show it in the first place,
/// on a build no real user ever runs.
///
/// Same shape as `AdMobConfig` (CR225): a dart-define, `AMI_QA_SKIP_TOURS`,
/// honoured ONLY when `AMI_RELEASE_CHANNEL` is NOT `production`. That is the
/// structural half of "never weaken what a real user sees" — a build that
/// somehow shipped this define could still not skip tours unless it also
/// shipped a non-production channel, and the store pipelines
/// (`build_testflight.sh`, `build_playstore.sh`) set `AMI_RELEASE_CHANNEL`
/// from `--production`/`--internal-only`, never by hand. `install_iphone.sh`
/// forwards neither define, so a cable-installed device build is unaffected
/// either way.
///
/// Read as a flexible truthy STRING, not `bool.fromEnvironment` — the same
/// lesson `AMI_QA_SEMANTICS` already paid for in `main.dart`: that
/// constructor accepts only the exact literals 'true'/'false', so
/// `--dart-define=AMI_QA_SKIP_TOURS=1` would silently resolve to `false` and
/// the flag would be dead without saying so.
library;

import 'package:flutter/foundation.dart';

/// CR225's channel enum is deliberately not reused directly (`admob_config`
/// is a sibling leaf, not a shared dependency this file should pull in) but
/// the three states and the conservative-default rule are identical: an
/// absent or unrecognised channel is never read as permission to skip tours
/// for a real user, so it resolves the same as `internal`.
enum TourQaReleaseChannel { unknown, internal_, production }

class TourQaConfig {
  const TourQaConfig._();

  static const String _skipFlag =
      String.fromEnvironment('AMI_QA_SKIP_TOURS', defaultValue: '');
  static const String _releaseChannelRaw =
      String.fromEnvironment('AMI_RELEASE_CHANNEL', defaultValue: '');

  static bool _resolved = false;
  static bool _skip = false;

  /// True only when `AMI_QA_SKIP_TOURS` was passed AND the build is not a
  /// production channel. `TourService.hasSeen` checks this before touching
  /// `SharedPreferences` at all, so every one of the five tours (floor,
  /// portfolio, journal, lessons, you) and the CR180 nav-change notice are
  /// covered by this one flag — there is nothing per-screen to wire.
  static bool get skipToursForQa {
    if (!_resolved) {
      _skip = resolve(
        skipFlagRaw: _skipFlag,
        channel: parseChannel(_releaseChannelRaw),
      );
      _resolved = true;
    }
    return _skip;
  }

  @visibleForTesting
  static bool resolve({
    required String skipFlagRaw,
    required TourQaReleaseChannel channel,
  }) {
    final requested = _truthy(skipFlagRaw);
    if (!requested) return false;
    if (channel == TourQaReleaseChannel.production) {
      debugPrint('DEF375 tour QA: AMI_QA_SKIP_TOURS set but '
          'AMI_RELEASE_CHANNEL=production — tours will show normally. '
          'The skip is only ever honoured on a non-production channel.');
      return false;
    }
    return true;
  }

  static bool _truthy(String raw) =>
      raw == '1' || raw == 'true' || raw == 'yes' || raw == 'on';

  @visibleForTesting
  static TourQaReleaseChannel parseChannel(String raw) {
    switch (raw) {
      case '':
        return TourQaReleaseChannel.unknown;
      case 'internal':
        return TourQaReleaseChannel.internal_;
      case 'production':
        return TourQaReleaseChannel.production;
      default:
        debugPrint('DEF375 tour QA MISCONFIGURED: unknown '
            'AMI_RELEASE_CHANNEL="$raw" (expected "", "internal" or '
            '"production") — treating as unset, the conservative default '
            '(tours show normally).');
        return TourQaReleaseChannel.unknown;
    }
  }

  /// Test-only: clears the memoised resolution.
  @visibleForTesting
  static void resetForTest() {
    _resolved = false;
    _skip = false;
  }
}
