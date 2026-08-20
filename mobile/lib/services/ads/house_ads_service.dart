/// House-ad inventory — the first [AdsService] implementation (CR122-MOBILE-A).
///
/// Serves the upsell slots of `ads.md:85-88`, targeted on usage signals and
/// nothing else: no SDK, no consent flow, no network. Earning happens through
/// the CR084 paywall the creative's CTA opens.
///
/// Targeting is first-match in priority order per plan:
///   floor_pass: out of 1-on-1s → used free Room → generic Trader upsell
///   trader:     near credit cap → halal mandate
/// Any other plan value (trial_trader, floor_manager, future plans) gets no
/// house inventory — the plan gate upstream refuses those anyway, and this
/// service failing closed too means a gate regression cannot invent fill.
library;

import 'package:ami_trade/services/ads/ads_models.dart';
import 'package:ami_trade/services/ads/ads_service.dart';
import 'package:flutter/foundation.dart';

class HouseAdsService implements AdsService {
  HouseAdsService() {
    // CR122: one loud line at init while AdMob (MOBILE-C) is not wired, so a
    // log reader can see WHY every impression is house (`ads.md` unset-AdMob
    // rule: 100% house fill, never a blank slot).
    debugPrint('CR122 AdsService=house — AdMob not configured, 100% house fill');
  }

  @override
  String get network => 'house';

  @override
  Future<AdFill?> requestFill(
      AdPlacement placement, HouseAdSignals signals) async {
    final creative = targetCreative(signals);
    return creative == null ? null : HouseAdFill(creative);
  }

  /// Pure targeting: each slot fires on its own usage precondition only.
  @visibleForTesting
  HouseAdCreative? targetCreative(HouseAdSignals s) {
    switch (s.effectivePlan) {
      case 'floor_pass':
        if (s.outOfFreeOneOnOnes) {
          return const HouseAdCreative(
              slot: HouseAdSlot.oneOnOnesToTrader,
              targetTier: HouseAdTargetTier.trader);
        }
        if (s.usedFreeRoom) {
          return const HouseAdCreative(
              slot: HouseAdSlot.freeRoomToTrader,
              targetTier: HouseAdTargetTier.trader);
        }
        return const HouseAdCreative(
            slot: HouseAdSlot.genericTrader,
            targetTier: HouseAdTargetTier.trader);
      case 'trader':
        if (s.nearCreditCap) {
          return const HouseAdCreative(
              slot: HouseAdSlot.creditCapToFloorManager,
              targetTier: HouseAdTargetTier.floorManager);
        }
        if (s.halalMandate) {
          return const HouseAdCreative(
              slot: HouseAdSlot.halalToFloorManager,
              targetTier: HouseAdTargetTier.floorManager);
        }
        return null;
      default:
        return null;
    }
  }
}
