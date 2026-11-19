/// DEF501 — Ticker Detail's earnings pill never vanishes.
///
/// AMI-DL-3 (E5-TICK-01): no earnings pill anywhere on the detail, so a tester
/// could not tell "nothing scheduled" from "the feed is down". The pill used to
/// render only when a date existed; a quiet calendar, an unreadable feed and a
/// failed request all hid it. All three states now say what they are.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/sim.dart';
import 'package:ami_trade/screens/sim/ticker_detail_screen.dart';
import 'package:ami_trade/services/api/api_client.dart';
import 'package:ami_trade/state/onboarding_providers.dart';
import 'package:ami_trade/state/ticker_history_provider.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

class _OfflineApi extends ApiClient {
  _OfflineApi() : super(baseUrl: 'test://localhost');
}

Future<AppLocalizations> _pump(
  WidgetTester t,
  Future<SimEarnings> Function() earnings,
) async {
  t.view.physicalSize = const Size(390, 2400);
  t.view.devicePixelRatio = 1.0;
  addTearDown(t.view.reset);
  await t.pumpWidget(ProviderScope(
    overrides: [
      apiClientProvider.overrideWithValue(_OfflineApi()),
      tickerEarningsProvider('MSFT').overrideWith((ref) => earnings()),
    ],
    child: MaterialApp(
      localizationsDelegates: AppLocalizations.localizationsDelegates,
      supportedLocales: AppLocalizations.supportedLocales,
      home: const TickerDetailScreen(ticker: 'MSFT'),
    ),
  ));
  await t.pump();
  await t.pump(const Duration(milliseconds: 50));
  return AppLocalizations.of(t.element(find.byType(TickerDetailScreen)));
}

void main() {
  setUp(() => SharedPreferences.setMockInitialValues({}));

  testWidgets('a scheduled report shows its quarter and date', (t) async {
    final l = await _pump(
      t,
      () async => SimEarnings.fromJson({
        'ticker': 'MSFT',
        'source': 'yfinance',
        'status': 'scheduled',
        'earnings_date': '2026-12-20',
        'quarter': 'Q4',
        'eps_estimate': 3.1,
      }),
    );
    expect(find.byKey(const Key('earningsStatusPill')), findsNothing);
    expect(find.text('Q4'), findsOneWidget);
    expect(find.text(l.tickerDetailEarningsNone), findsNothing);
  });

  testWidgets('a read calendar with nothing in the window says none scheduled',
      (t) async {
    final l = await _pump(
      t,
      () async => SimEarnings.fromJson({
        'ticker': 'MSFT',
        'source': 'yfinance',
        'status': 'none_scheduled',
        'earnings_date': null,
      }),
    );
    expect(find.byKey(const Key('earningsStatusPill')), findsOneWidget);
    expect(find.text(l.tickerDetailEarningsNone), findsOneWidget);
    expect(find.text(l.tickerDetailEarningsUnavailable), findsNothing);
  });

  testWidgets('an unreadable feed says unavailable, not none scheduled',
      (t) async {
    final l = await _pump(
      t,
      () async => SimEarnings.fromJson({
        'ticker': 'MSFT',
        'source': 'unavailable',
        'status': 'unavailable',
        'earnings_date': null,
      }),
    );
    expect(find.text(l.tickerDetailEarningsUnavailable), findsOneWidget);
    expect(find.text(l.tickerDetailEarningsNone), findsNothing);
  });

  testWidgets('a failed request also says unavailable', (t) async {
    final l = await _pump(t, () async => throw Exception('network'));
    expect(find.text(l.tickerDetailEarningsUnavailable), findsOneWidget);
  });

  test('a backend that predates `status` is read from its source', () {
    final none = SimEarnings.fromJson({
      'ticker': 'MSFT',
      'source': 'yfinance',
      'earnings_date': null,
    });
    final down = SimEarnings.fromJson({
      'ticker': 'MSFT',
      'source': 'unavailable',
      'earnings_date': null,
    });
    final dated = SimEarnings.fromJson({
      'ticker': 'MSFT',
      'source': 'yfinance',
      'earnings_date': '2026-12-20',
    });
    expect(none.status, 'none_scheduled');
    expect(down.status, 'unavailable');
    expect(dated.status, 'scheduled');
  });
}
