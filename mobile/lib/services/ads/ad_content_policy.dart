/// Programmatic ad content policy (CR122-MOBILE-C) — `ads.md:20-31` as data.
///
/// AdMob has NO per-request "banned categories" parameter: category blocking
/// lives in the AdMob console's Blocking controls (sensitive categories +
/// advertiser URL blocks), which is account material and therefore a Saiful
/// liaison step (`CR122_admob_compliance_and_liaison.md` carries the exact
/// console checklist generated from [bannedCategories]).
///
/// What a request CAN carry, it must — so every programmatic request is built
/// from [AdContentPolicy] and the unit test pins that no [AdMobRequestSpec]
/// or [AdMobSdkConfigSpec] escapes without it:
///   * `maxAdContentRating: 'T'` — the strictest rating that still fills;
///     brand safety over fill rate (`ads.md:33`);
///   * age treatment: NONE — the app is rated 17+ precisely to stay OUT of
///     COPPA child-directed scope and GDPR under-age-of-consent treatment
///     (`ads.md:109`); tagging it child or teen would be a false
///     declaration (the SDK's `AgeRestrictedTreatment` enum, mapped in
///     `admob_real_sdk.dart`);
///   * CCPA restricted data processing (`rdp=1`) when the Settings
///     "Do Not Sell" toggle is on (`ad_privacy_prefs.dart`).
///
/// The banned-category list is pinned to `ads.md:20-31` by test so the
/// console checklist can never drift from the locked policy.
library;

class AdContentPolicy {
  const AdContentPolicy._();

  /// The ten banned categories of `ads.md:20-31`, in the spec's order.
  /// Consumed by the liaison checklist and pinned by test — not sent on the
  /// wire (no AdMob request parameter exists for it; see library doc).
  static const bannedCategories = [
    'get_rich_quick',
    'unregulated_brokers',
    'binary_options',
    'high_leverage_cfds',
    'crypto_pump_dump',
    'pump_newsletters_signal_services',
    'lottery_gambling',
    'adult_content',
    'politics',
    'religious_solicitation',
  ];

  /// RequestConfiguration.maxAdContentRating — 'T' (teen), the strictest
  /// tier below MA. Brand safety over fill rate (`ads.md:33`).
  static const maxAdContentRating = 'T';

  /// 17+ app, deliberately outside COPPA child-directed scope and GDPR
  /// under-age-of-consent treatment (`ads.md:109`).
  static const ageTreatment = AdAgeTreatment.none;
}

/// Age treatment for ad requests, decoupled from the SDK enum so policy and
/// tests never import `google_mobile_ads`. Only [none] is ever used — the
/// app is 17+ — but the type mirrors the SDK's so the adapter mapping is
/// total.
enum AdAgeTreatment { none, child, teen }
