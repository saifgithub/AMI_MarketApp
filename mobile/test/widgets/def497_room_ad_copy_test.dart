/// DEF497 — an ad said "Your free Room is used" while the user held 3 credits.
/// The slot fires when the balance is below the Room price
/// (`HouseAdSignals.usedFreeRoom`), which is not the same fact as "a free Room
/// was used", so the copy must state the shortfall and nothing else.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/generated/l10n/app_localizations_ar.dart';
import 'package:ami_trade/generated/l10n/app_localizations_en.dart';
import 'package:ami_trade/generated/l10n/app_localizations_ms.dart';
import 'package:ami_trade/models/mandate.dart';
import 'package:ami_trade/services/ads/ads_models.dart';
import 'package:ami_trade/services/ads/house_ads_service.dart';
import 'package:ami_trade/widgets/ads/house_ad_card.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('3 credits against an 8-credit Room gets the shortfall copy', () {
    final m = UserMandate.fromJson({
      'user_id': 'u1',
      'plan': 'floor_pass',
      'credit_balance': 3,
      'room_cost': 8,
    });
    final creative = HouseAdsService.asFallback()
        .targetCreative(HouseAdSignals.fromMandate(m));
    expect(creative!.slot, HouseAdSlot.freeRoomToTrader);

    for (final AppLocalizations l in [
      AppLocalizationsEn(),
      AppLocalizationsAr(),
      AppLocalizationsMs(),
    ]) {
      final body = HouseAdCard.copyFor(l, creative.slot).body;
      expect(body.toLowerCase().contains('free room is used'), isFalse);
    }
    final en = HouseAdCard.copyFor(AppLocalizationsEn(), creative.slot).body;
    expect(en, contains('Not enough credits'));
  });

  test('the shortfall copy is translated, not the English string', () {
    final en = AppLocalizationsEn().houseAdRoomBody;
    expect(AppLocalizationsAr().houseAdRoomBody, isNot(en));
    expect(AppLocalizationsMs().houseAdRoomBody, isNot(en));
  });
}
