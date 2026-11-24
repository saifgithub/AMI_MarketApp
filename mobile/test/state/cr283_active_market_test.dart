/// CR283 - `selectedMarketProvider` is the app-wide market, and the ticker tape's
/// bourse follows it. With Bursa off nothing follows anything: US, always.
library;

import 'package:ami_trade/features/markets/market.dart';
import 'package:ami_trade/services/yahoo_finance_service.dart';
import 'package:ami_trade/state/bursa_providers.dart';
import 'package:ami_trade/state/ticker_tape_provider.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

void main() {
  setUp(() => SharedPreferences.setMockInitialValues({}));

  test('Bursa off: the bourse is US whatever the stored market says', () {
    final c = ProviderContainer(overrides: [
      bursaEnabledProvider.overrideWithValue(false),
    ]);
    addTearDown(c.dispose);
    expect(c.read(activeBourseProvider), Bourse.us);
  });

  test('Bursa on: the bourse follows the selected market', () async {
    final c = ProviderContainer(overrides: [
      bursaEnabledProvider.overrideWithValue(true),
    ]);
    addTearDown(c.dispose);
    expect(c.read(activeBourseProvider), Bourse.us);

    await c.read(selectedMarketProvider.notifier).select(AppMarket.my);
    expect(c.read(activeBourseProvider), Bourse.my);

    await c.read(selectedMarketProvider.notifier).select(AppMarket.us);
    expect(c.read(activeBourseProvider), Bourse.us);
  });

  test('Bursa off: select is a no-op, the market stays US', () async {
    final c = ProviderContainer(overrides: [
      bursaEnabledProvider.overrideWithValue(false),
    ]);
    addTearDown(c.dispose);
    await c.read(selectedMarketProvider.notifier).select(AppMarket.my);
    expect(c.read(selectedMarketProvider), AppMarket.us);
  });

  test('the Bursa default tape list is the .KL set', () {
    final my = YahooFinanceService.buildTickerList(const [], Bourse.my);
    expect(my.length, YahooFinanceService.kMinTickers);
    expect(my.every((s) => s.endsWith('.KL')), isTrue);
  });
}
