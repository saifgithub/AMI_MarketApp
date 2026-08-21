/// CR122 — structural controls on where ads can exist in the source tree.
///
/// Per CLAUDE.md an instruction is not a control, so the `ads.md:46-54`
/// denylist and the CR084-style SDK seam are enforced as source-level
/// invariants, not review conventions:
///
///   1. SDK seam — exactly ONE file may import an ad SDK
///      (`google_mobile_ads`, `huawei_ads`): the CR122-MOBILE-C adapter
///      `lib/services/ads/admob_real_sdk.dart`. Screens, widgets and every
///      other service — the facade impls included — see only the
///      `admob_sdk.dart` seam interfaces.
///   2. AdSlot call sites — the EXACT set of files allowed to instantiate
///      `AdSlot(` is asserted, so a future screen quietly gaining an ad slot
///      fails this suite (the static twin of the UAT regression net).
///   3. Forbidden contexts — the honeycomb Floor, Room / 1-on-1 / Brief,
///      Concierge/onboarding, agent surfaces, mandate editors and the trade
///      tickets must not reference the ads layer at all.
///
/// Files are DISCOVERED by walking `lib/`, mirroring how the DEF137 parity
/// guard globs its locales — no allowlist of scanned files to go stale.
library;

import 'dart:io';

import 'package:flutter_test/flutter_test.dart';

const _adSdkImports = ['google_mobile_ads', 'huawei_ads'];

/// The single file allowed to import an ad SDK. If the adapter moves, move
/// this pin with it — the positive assertion below fails on a silent orphan.
///
/// DEF351: the adapter is currently DELETED and no file imports an ad SDK —
/// `google_mobile_ads` cannot be linked into an iOS release build. The
/// no-file-imports-an-SDK half below still holds and is the half that matters
/// (an SDK import anywhere else is still a defect); the positive
/// "the adapter does import one" assertion is suspended until the plugin is
/// re-linkable, guarded by [_adSdkAdapterExpected] so re-linking flips one
/// boolean rather than rewriting the test.
const _adSdkAdapterFile = 'lib/services/ads/admob_real_sdk.dart';
const _adSdkAdapterExpected = false;

/// The only files allowed to contain an `AdSlot(` instantiation: the widget's
/// own definition plus the wired approved placements (`ads.md:39-44`).
/// `daily_challenge_results` is allowlisted in the facade but deliberately
/// unwired — today's challenge reveal lives on the Floor home screen, a
/// forbidden context — so no file for it appears here yet.
const _adSlotCallSites = {
  'lib/widgets/ads/ad_slot.dart',
  'lib/screens/journal/journal_screen.dart',
  'lib/screens/sim/portfolio_screen.dart',
  'lib/screens/lessons/lessons_screen.dart',
  'lib/screens/settings/settings_screen.dart',
};

/// The interstitial's single entry point (post-lesson, `ads.md:39`).
const _interstitialCallSites = {
  'lib/widgets/ads/house_ad_interstitial.dart',
  'lib/screens/lessons/lesson_reader_screen.dart',
};

/// `ads.md:46-54` — the seven forbidden contexts, as source paths.
const _forbiddenPrefixes = [
  'lib/screens/floor/', // the honeycomb home
  'lib/widgets/floor/',
  'lib/screens/onboarding/', // Concierge interview / first-run
  'lib/widgets/chat/', // Concierge + 1-on-1 conversation surfaces
  'lib/screens/room/', // Convene the Room
  'lib/widgets/room/', // incl. Brief Your Agent briefing widgets
  'lib/screens/agent/', // agent cards, 1-on-1, Brief Your Agent
];
const _forbiddenFiles = [
  'lib/screens/sim/trade_ticket_sheet.dart',
  'lib/screens/games/games_trade_ticket_screen.dart',
  'lib/screens/settings/risk_limits_section.dart', // mandate flow
  'lib/screens/settings/day_trader_disclosure_dialog.dart', // mandate flow
];

/// Any reference to the ads layer counts, not just AdSlot: a forbidden
/// screen must not even import the gate or the creatives.
const _adLayerMarkers = [
  'widgets/ads/',
  'state/ads_providers.dart',
  'services/ads/',
];

void main() {
  final libFiles = Directory('lib')
      .listSync(recursive: true)
      .whereType<File>()
      .where((f) => f.path.endsWith('.dart'))
      .toList();

  test('the ad SDK import is pinned to admob_real_sdk.dart alone', () {
    final offenders = <String>[];
    var adapterImportsSdk = false;
    for (final f in libFiles) {
      final src = f.readAsStringSync();
      final importsSdk =
          _adSdkImports.any((sdk) => src.contains("import 'package:$sdk"));
      if (f.path == _adSdkAdapterFile) {
        adapterImportsSdk = importsSdk;
        continue;
      }
      if (importsSdk) offenders.add(f.path);
    }
    expect(offenders, isEmpty,
        reason: 'Ad SDKs live behind the AdsService facade, imported by the '
            'single adapter file only (CR122, mirroring the CR084 purchase '
            'seam):\n${offenders.join('\n')}');
    expect(adapterImportsSdk, _adSdkAdapterExpected,
        reason: _adSdkAdapterExpected
            ? '$_adSdkAdapterFile no longer imports the ad SDK — if the '
                'adapter moved, move this pin with it so the seam stays '
                'enforced.'
            : 'An ad SDK is linked again (DEF351 said none is). If the plugin '
                'is fixed and the adapter is back, flip _adSdkAdapterExpected '
                'to true — do not delete this assertion.');
  });

  test('AdSlot is instantiated ONLY at the approved placements', () {
    final callSites = <String>{};
    for (final f in libFiles) {
      if (RegExp(r'\bAdSlot\(').hasMatch(f.readAsStringSync())) {
        callSites.add(f.path);
      }
    }
    expect(callSites, _adSlotCallSites,
        reason: 'A screen gained or lost an ad slot. New placements need a '
            'CR against ads.md:39-44 — the six approved surfaces are the '
            'whole allowlist.');
  });

  test('the interstitial has exactly one entry point (post-lesson)', () {
    final callSites = <String>{};
    for (final f in libFiles) {
      if (f
          .readAsStringSync()
          .contains('maybeShowPostLessonInterstitial')) {
        callSites.add(f.path);
      }
    }
    expect(callSites, _interstitialCallSites);
  });

  test('forbidden contexts (ads.md:46-54) never touch the ads layer', () {
    final offenders = <String>[];
    for (final f in libFiles) {
      final banned = _forbiddenPrefixes.any(f.path.startsWith) ||
          _forbiddenFiles.contains(f.path);
      if (!banned) continue;
      final src = f.readAsStringSync();
      for (final marker in _adLayerMarkers) {
        if (src.contains(marker)) {
          offenders.add('${f.path} references $marker');
        }
      }
    }
    expect(offenders, isEmpty,
        reason: 'ads.md:46-54 forbids ads in these contexts — the team '
            'metaphor and the signature screens stay clean:\n'
            '${offenders.join('\n')}');
  });
}
