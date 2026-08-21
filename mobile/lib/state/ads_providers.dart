/// Riverpod wiring + the single ad gate (CR122-MOBILE-A/B).
///
/// [AdGate.request] is the ONLY path to an ad decision, and it runs the
/// checks in fail-closed order:
///
///   1. placement allowlist — anything outside [AdPlacement.approved] is
///      refused (a screen cannot opt itself into ads);
///   2. plan gate — ads exist for `floor_pass` ONLY. The plan comes from the
///      mandate the backend stamps with `effective_plan`, so `trial_trader`
///      counts as paying; an unloaded mandate or an unrecognised (future)
///      plan value refuses — a new plan can never default to ad-serving;
///   3. paying-plan latch — once a paying plan is seen this app run, ads stay
///      off for the rest of it: an upgrade removes ads immediately
///      (`ads.md:113`), a downgrade restores them next session (`ads.md:115`);
///   4. frequency caps (MOBILE-B) — persisted; unreadable store BLOCKS;
///   5. network fill via the [AdsService] facade — house by default; with
///      the CR122-MOBILE-C `ADMOB_MODE` dart-define set, AdMob behind the
///      same facade (consent-gated, house fallback for every unfilled
///      request; unset config keeps 100% house fill).
library;

import 'package:ami_trade/services/ads/ad_frequency_caps.dart';
import 'package:ami_trade/services/ads/ad_privacy_prefs.dart';
import 'package:ami_trade/services/ads/admob_sdk.dart';
import 'package:ami_trade/services/ads/ads_models.dart';
import 'package:ami_trade/services/ads/ads_service.dart';
import 'package:ami_trade/services/ads/house_ads_service.dart';
import 'package:ami_trade/state/mandate_providers.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

/// The one plan string that sees ads. A set so the AdMob/compliance lanes
/// test against the same table the gate enforces — membership here is the
/// decision, everything else refuses.
const plansWithAds = {'floor_pass'};

/// CR122-MOBILE-C: the facade impl is chosen by `AdMobConfig` alone. No
/// `ADMOB_MODE` dart-define → `setup` is null → the MOBILE-A house service,
/// no SDK object ever constructed, no platform channel ever touched — the
/// store pipelines behave exactly as before this lane landed.
// DEF351: the `google_mobile_ads` plugin cannot be linked into an iOS release
// build (its headers import a private header out of the vendored framework,
// which Clang refuses inside a framework module), so the SDK is UNLINKED and
// `admob_real_sdk.dart` is deleted rather than left as an orphan import. Every
// build therefore serves house inventory. `AdMobAdsService` and its config,
// policy and consent seams are kept and still tested — they are what a working
// plugin plugs back into, and re-linking is a pubspec line plus restoring one
// adapter file. Nothing here degrades silently: with no SDK there is no fill to
// mistake for one.
final adsServiceProvider = Provider<AdsService>((ref) => HouseAdsService());

final adPrivacyPrefsProvider = Provider<AdPrivacyPrefs>(
    (ref) => AdPrivacyPrefs(SharedPreferencesAdCapStore()));

/// The UMP consent seam for the Settings re-consent entry point — null when
/// AdMob is off, which is also what hides the Settings section (a consent
/// control for an SDK that isn't in play would be a false claim, the DEF085
/// class).
// DEF351: null always, because no SDK is linked — which correctly hides the
// Settings re-consent row. A consent control for an SDK that isn't in play
// would be a false claim (the DEF085 class), and that reasoning is exactly why
// this seam was nullable in the first place.
final adMobUmpConsentProvider = Provider<AdMobUmpConsent?>((ref) => null);

final adCapStoreProvider =
    Provider<AdCapStore>((ref) => SharedPreferencesAdCapStore());

final adFrequencyCapsProvider = Provider<AdFrequencyCaps>(
    (ref) => AdFrequencyCaps(ref.watch(adCapStoreProvider)));

class AdGate {
  AdGate({
    required AdsService service,
    required AdFrequencyCaps caps,
    required HouseAdSignals? Function() readSignals,
  })  : _service = service,
        _caps = caps,
        _readSignals = readSignals;

  final AdsService _service;
  final AdFrequencyCaps _caps;

  /// Reads the CURRENT signals (null while the mandate hasn't loaded) —
  /// read per request, never cached, so a CR084 upgrade flips the answer
  /// without an app restart.
  final HouseAdSignals? Function() _readSignals;

  /// `ads.md:115` — a downgrade restores ads next session, not mid-session.
  /// The gate object lives for the app run, so this latch does too.
  bool _sawPayingPlan = false;

  Future<AdDecision> request(AdPlacement placement) async {
    if (!AdPlacement.approved.contains(placement)) {
      debugPrint('CR122 AdGate: REFUSED unapproved placement '
          '"${placement.id}" — the allowlist is the six of ads.md:39-44');
      return const AdDecision.refused(AdRefusalReason.unapprovedPlacement);
    }
    final signals = _readSignals();
    if (signals == null) {
      return const AdDecision.refused(AdRefusalReason.planUnknown);
    }
    if (!plansWithAds.contains(signals.effectivePlan)) {
      _sawPayingPlan = true;
      return const AdDecision.refused(AdRefusalReason.planHasNoAds);
    }
    if (_sawPayingPlan) {
      return const AdDecision.refused(AdRefusalReason.planHasNoAds);
    }
    final capBlock = placement.format == AdFormat.interstitial
        ? await _caps.checkInterstitial()
        : await _caps.checkNative();
    if (capBlock != null) return AdDecision.refused(capBlock);
    final fill = await _service.requestFill(placement, signals);
    if (fill == null) {
      return const AdDecision.refused(AdRefusalReason.noInventory);
    }
    return AdDecision.filled(fill);
  }

  /// Called once when a filled ad actually renders.
  Future<void> recordShown(AdPlacement placement) =>
      _caps.recordImpression(placement.format);

  /// Lesson-completion hook for the 1-per-5-lessons interstitial cap.
  Future<void> recordLessonCompleted() => _caps.recordLessonCompleted();
}

final adGateProvider = Provider<AdGate>((ref) {
  return AdGate(
    service: ref.watch(adsServiceProvider),
    caps: ref.watch(adFrequencyCapsProvider),
    readSignals: () {
      final m = ref.read(mandateNotifierProvider).mandate;
      return m == null ? null : HouseAdSignals.fromMandate(m);
    },
  );
});
