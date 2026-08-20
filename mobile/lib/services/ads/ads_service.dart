/// Ads network facade (CR122-MOBILE-A).
///
/// The seam between app code and any ad network, per
/// `docs/initial_specs/08_tech/platform_facade.md:98` and the CR084
/// `purchase_service.dart` pattern: screens never import an ad SDK — they go
/// through [AdGate] (state/ads_providers.dart), which consults the configured
/// [AdsService] for fill only AFTER the allowlist, plan and cap checks pass.
///
/// Implementations:
///  * [HouseAdsService] — house upsell inventory, zero SDK (this slice).
///  * `AdMobAdsService` — CR122-MOBILE-C, behind `--dart-define` config;
///    unset config keeps fill 100% house.
///  * `HuaweiAdsService` — v1.1 with AppGallery; the seam is left, nothing
///    is built.
library;

import 'package:ami_trade/services/ads/ads_models.dart';

abstract class AdsService {
  /// Stable name for logs ('house', 'admob', ...).
  String get network;

  /// Fill [placement], or return null when this network has nothing —
  /// never throw for an empty-inventory case and never render-side-effect.
  Future<AdFill?> requestFill(AdPlacement placement, HouseAdSignals signals);
}
