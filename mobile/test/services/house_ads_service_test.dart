/// CR122-MOBILE-A — house-slot targeting.
///
/// Each of the four `ads.md:85-88` slots fires on its own usage precondition
/// and not on the others'; plans outside {floor_pass, trader} get no house
/// inventory at all (a new plan can't inherit fill by default).
library;

import 'package:ami_trade/services/ads/ads_models.dart';
import 'package:ami_trade/services/ads/house_ads_service.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  final svc = HouseAdsService();

  HouseAdSlot? slotFor(HouseAdSignals s) => svc.targetCreative(s)?.slot;

  test('floor_pass out of 1-on-1s → oneOnOnesToTrader', () {
    expect(
      slotFor(const HouseAdSignals(
          effectivePlan: 'floor_pass', outOfFreeOneOnOnes: true)),
      HouseAdSlot.oneOnOnesToTrader,
    );
  });

  test('floor_pass used its free Room → freeRoomToTrader', () {
    expect(
      slotFor(const HouseAdSignals(
          effectivePlan: 'floor_pass', usedFreeRoom: true)),
      HouseAdSlot.freeRoomToTrader,
    );
  });

  test('floor_pass with no targeted signal → generic Trader upsell', () {
    expect(slotFor(const HouseAdSignals(effectivePlan: 'floor_pass')),
        HouseAdSlot.genericTrader);
  });

  test('trader near credit cap → creditCapToFloorManager', () {
    expect(
      slotFor(const HouseAdSignals(
          effectivePlan: 'trader', nearCreditCap: true)),
      HouseAdSlot.creditCapToFloorManager,
    );
  });

  test('trader on a halal mandate → halalToFloorManager', () {
    expect(
      slotFor(const HouseAdSignals(
          effectivePlan: 'trader', halalMandate: true)),
      HouseAdSlot.halalToFloorManager,
    );
  });

  test('trader signals do not fire floor_pass slots and vice versa', () {
    // A floor_pass user near the cap / on halal gets the generic Trader
    // upsell, never a Floor-Manager slot...
    expect(
      slotFor(const HouseAdSignals(
          effectivePlan: 'floor_pass',
          nearCreditCap: true,
          halalMandate: true)),
      HouseAdSlot.genericTrader,
    );
    // ...and a trader who is out of credits gets no Trader upsell.
    expect(
      slotFor(const HouseAdSignals(
          effectivePlan: 'trader',
          outOfFreeOneOnOnes: true,
          usedFreeRoom: true)),
      isNull,
    );
  });

  test('paying/unknown plans get no house inventory even with every signal',
      () {
    for (final plan in ['trial_trader', 'floor_manager', 'plan_2027']) {
      expect(
        slotFor(HouseAdSignals(
            effectivePlan: plan,
            outOfFreeOneOnOnes: true,
            usedFreeRoom: true,
            nearCreditCap: true,
            halalMandate: true)),
        isNull,
        reason: 'plan=$plan must not target any house slot',
      );
    }
  });
}
