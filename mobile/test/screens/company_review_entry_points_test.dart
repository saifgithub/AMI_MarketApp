/// CR244 — the two Review entry points exist and are wired correctly:
/// the Floor screen's 1/4-width split button beside CONVENE, and the Ticker
/// Detail chip row's new REVIEW chip. Both open CompanyReviewScreen.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/sector_watch.dart';
import 'package:ami_trade/models/sim.dart';
import 'package:ami_trade/screens/floor/floor_providers.dart';
import 'package:ami_trade/screens/floor/floor_screen.dart';
import 'package:ami_trade/screens/floor/team_calls_data.dart';
import 'package:ami_trade/screens/sim/company_review_screen.dart';
import 'package:ami_trade/screens/sim/ticker_detail_screen.dart';
import 'package:ami_trade/services/api/api_client.dart';
import 'package:ami_trade/state/onboarding_providers.dart';
import 'package:ami_trade/state/sim_providers.dart';
import 'package:ami_trade/state/ticker_history_provider.dart';
import 'package:ami_trade/state/watchlist_providers.dart';
import 'package:ami_trade/models/company_profile.dart';
import 'package:ami_trade/models/tickers.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

const _reference = Size(390, 844);

class _FixedSim extends SimNotifier {
  _FixedSim(super.ref, SimState fixed) {
    state = fixed;
  }
}

class _FixedWatchlist extends WatchlistNotifier {
  _FixedWatchlist(super.ref, WatchlistState fixed) {
    state = fixed;
  }
}

class _ValidatingApi extends ApiClient {
  _ValidatingApi() : super(baseUrl: 'test://localhost');

  @override
  Future<TickerValidation> validateTicker(String ticker) async {
    return TickerValidation(
        ticker: ticker.toUpperCase(), exists: ticker.toUpperCase() == 'NVDA');
  }

  @override
  Future<CompanyProfile> companyProfile(String ticker) async {
    return CompanyProfile.fromJson({
      'ticker': ticker,
      'overview': {'state': 'live', 'sources': ['yfinance']},
      'financials': {'state': 'live', 'sources': ['yfinance']},
      'filings': {'state': 'live', 'sources': ['edgar'], 'items': []},
      'ownership': {'state': 'live', 'sources': ['yfinance']},
    });
  }

  @override
  Future<InsiderActivity> insiderActivity(String ticker) async {
    return InsiderActivity.fromJson({
      'ticker': ticker,
      'state': 'live',
      'sources': ['edgar'],
      'transactions': <Map<String, dynamic>>[],
    });
  }
}

Future<void> _settle(WidgetTester t) async {
  for (var i = 0; i < 10; i++) {
    await t.pump(const Duration(milliseconds: 50));
  }
}

void main() {
  setUp(() =>
      SharedPreferences.setMockInitialValues({'tour_floor_seen': true}));

  testWidgets(
      'Floor screen: typing a valid ticker arms the Review split button, '
      'which opens Company Review', (t) async {
    await t.binding.setSurfaceSize(_reference);
    addTearDown(() => t.binding.setSurfaceSize(null));
    t.view.devicePixelRatio = 1.0;
    addTearDown(t.view.resetDevicePixelRatio);

    await t.pumpWidget(ProviderScope(
      overrides: [
        apiClientProvider.overrideWithValue(_ValidatingApi()),
        simNotifierProvider.overrideWith((ref) => _FixedSim(
            ref,
            SimState(
                portfolio: SimPortfolio(
              userId: 'u',
              portfolioId: 'p',
              startingCapital: 10000,
              currentCash: 10000,
              holdings: const [],
              totalValue: 10000,
              drawdownPct: 0,
            )))),
        teamCallsProvider.overrideWith((ref) async => <TeamCall>[]),
        sectorWatchProvider
            .overrideWith((ref) async => const SectorWatch(state: 'empty')),
        callPriceProvider.overrideWith((ref, ticker) async => null),
        conveneCloseProvider.overrideWith((ref, k) async => null),
      ],
      child: const MaterialApp(
        localizationsDelegates: AppLocalizations.localizationsDelegates,
        supportedLocales: AppLocalizations.supportedLocales,
        home: FloorScreen(),
      ),
    ));
    await _settle(t);

    // Review's info-icon button exists beside CONVENE.
    expect(find.byIcon(Icons.info_outline), findsOneWidget);

    await t.enterText(find.byType(TextField), 'NVDA');
    await _settle(t);

    await t.tap(find.byIcon(Icons.info_outline));
    await _settle(t);

    expect(find.byType(CompanyReviewScreen), findsOneWidget);
  });

  testWidgets('Ticker Detail: the REVIEW chip is present and opens '
      'Company Review', (t) async {
    await t.binding.setSurfaceSize(_reference);
    addTearDown(() => t.binding.setSurfaceSize(null));
    t.view.devicePixelRatio = 1.0;
    addTearDown(t.view.resetDevicePixelRatio);

    await t.pumpWidget(ProviderScope(
      overrides: [
        apiClientProvider.overrideWithValue(_ValidatingApi()),
        simNotifierProvider.overrideWith(
            (ref) => _FixedSim(ref, const SimState(portfolio: null))),
        watchlistNotifierProvider.overrideWith(
            (ref) => _FixedWatchlist(ref, const WatchlistState())),
        tickerEarningsProvider.overrideWith(
            (ref, ticker) async => SimEarnings.fromJson({
                  'ticker': ticker,
                  'source': 'mock',
                })),
        tickerNewsProvider.overrideWith(
            (ref, ticker) async => SimNews.fromJson({
                  'ticker': ticker,
                  'source': 'mock',
                  'articles': <Map<String, dynamic>>[],
                })),
      ],
      child: const MaterialApp(
        localizationsDelegates: AppLocalizations.localizationsDelegates,
        supportedLocales: AppLocalizations.supportedLocales,
        home: TickerDetailScreen(ticker: 'NVDA'),
      ),
    ));
    await _settle(t);

    expect(find.text('REVIEW'), findsOneWidget);

    await t.tap(find.text('REVIEW'));
    await _settle(t);

    expect(find.byType(CompanyReviewScreen), findsOneWidget);
  });
}
