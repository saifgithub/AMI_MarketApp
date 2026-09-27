/// CR244 — Company Review screen: an Overview render from sample JSON, a
/// not_available section showing its reason (CR040 degrade-loudly), and the
/// Insider tab's structural controls — an M-code (option exercise) row never
/// gets a BUY badge, and a scheduled 10b5-1 row shows the tag.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/company_profile.dart';
import 'package:ami_trade/screens/sim/company_review_screen.dart';
import 'package:ami_trade/services/api/api_client.dart';
import 'package:ami_trade/state/onboarding_providers.dart';
import 'package:ami_trade/state/ticker_history_provider.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

class _FakeApi extends ApiClient {
  _FakeApi({
    this.profileJson,
    this.insiderJson,
    this.profileThrows = false,
  }) : super(baseUrl: 'test://localhost');

  final Map<String, dynamic>? profileJson;
  final Map<String, dynamic>? insiderJson;
  final bool profileThrows;

  @override
  Future<CompanyProfile> companyProfile(String ticker) async {
    if (profileThrows) {
      throw Exception('feed down');
    }
    return CompanyProfile.fromJson(profileJson!);
  }

  @override
  Future<InsiderActivity> insiderActivity(String ticker) async {
    return InsiderActivity.fromJson(insiderJson ??
        {
          'ticker': ticker,
          'state': 'live',
          'sources': ['edgar'],
          'window_days': 90,
          'summary': {
            'buys': 0,
            'sells': 0,
            'other': 0,
            'net_direction': 'none',
          },
          'transactions': <Map<String, dynamic>>[],
        });
  }
}

Map<String, dynamic> _liveProfile() => {
      'ticker': 'NVDA',
      'as_of': '2026-09-27T11:02:00Z',
      'cik': '0001045810',
      'overview': {
        'state': 'live',
        'sources': ['edgar', 'yfinance'],
        'legal_name': 'NVIDIA CORP',
        'display_name': 'NVIDIA Corporation',
        'description': 'Designs GPUs and AI computing platforms.',
        'sector': 'Technology',
        'industry': 'Semiconductors',
        'sic': '3674',
        'sic_description': 'Semiconductors & Related Devices',
        'exchange': 'Nasdaq',
        'employees': 29600,
        'website': 'https://nvidia.com',
        'address': '2788 San Tomas Expressway, Santa Clara, CA 95051',
        'phone': '408-486-2000',
      },
      'financials': {
        'state': 'live',
        'sources': ['yfinance'],
        'currency': 'USD',
        'market_cap': 4.3e12,
        'revenue_ttm': 1.65e11,
        'gross_margin': 0.72,
      },
      'filings': {
        'state': 'live',
        'sources': ['edgar'],
        'items': [
          {
            'form': '10-Q',
            'description': 'Quarterly report',
            'filed_date': '2026-08-27',
            'report_date': '2026-07-27',
            'accession_number': '0001045810-26-000123',
            'url': 'https://www.sec.gov/Archives/edgar/data/1045810/x.htm',
          },
        ],
      },
      'ownership': {
        'state': 'live',
        'sources': ['yfinance'],
        'shares_outstanding': 2.44e10,
        'float_shares': 2.34e10,
        'pct_institutions': 0.674,
        'pct_insiders': 0.042,
        'holders': [
          {
            'name': 'The Vanguard Group, Inc.',
            'kind': 'institution',
            'pct_held': 0.0824,
            'shares': 2.0e9,
            'date_reported': '2026-06-30',
          },
        ],
      },
    };

Future<void> _pump(
  WidgetTester tester, {
  required _FakeApi api,
  String ticker = 'NVDA',
  List<Override> extraOverrides = const [],
}) async {
  await tester.pumpWidget(ProviderScope(
    overrides: [
      apiClientProvider.overrideWithValue(api),
      ...extraOverrides,
    ],
    child: MaterialApp(
      localizationsDelegates: AppLocalizations.localizationsDelegates,
      supportedLocales: AppLocalizations.supportedLocales,
      home: CompanyReviewScreen(ticker: ticker),
    ),
  ));
  for (var i = 0; i < 10; i++) {
    await tester.pump(const Duration(milliseconds: 50));
  }
}

void main() {
  testWidgets('Overview tab renders from sample JSON', (tester) async {
    final api = _FakeApi(profileJson: _liveProfile());
    await _pump(tester, api: api);

    expect(find.text('NVDA'), findsWidgets);
    expect(find.textContaining('NVIDIA Corporation'), findsOneWidget);
    expect(
        find.textContaining('Designs GPUs and AI computing platforms.'),
        findsOneWidget);
    expect(find.text('3674'), findsOneWidget);
  });

  testWidgets('a not_available section shows its reason, never a blank card',
      (tester) async {
    final profile = _liveProfile();
    (profile['filings'] as Map<String, dynamic>)
      ..['state'] = 'not_available'
      ..['reason'] = 'No SEC registrant found for this symbol'
      ..['items'] = <Map<String, dynamic>>[];
    final api = _FakeApi(profileJson: profile);
    await _pump(tester, api: api);

    await tester.tap(find.text('FILINGS'));
    await tester.pumpAndSettle();

    expect(find.textContaining('No SEC registrant found for this symbol'),
        findsOneWidget);
  });

  testWidgets(
      'an M (option exercise) row never renders a BUY badge; scheduled '
      '10b5-1 row shows the tag', (tester) async {
    final insider = {
      'ticker': 'NVDA',
      'state': 'live',
      'sources': ['edgar'],
      'window_days': 90,
      'summary': {
        'buys': 0,
        'sells': 1,
        'other': 1,
        'net_direction': 'selling',
      },
      'transactions': [
        {
          'form': '4',
          'filed_date': '2026-08-30',
          'transaction_date': '2026-08-30',
          'insider_name': 'M. Kress',
          'role': 'CFO',
          'code': 'M',
          'code_label': 'Option exercise',
          'direction': 'other',
          'shares': 8200,
          'plan_type': 'unstated',
        },
        {
          'form': '4',
          'filed_date': '2026-09-16',
          'transaction_date': '2026-09-15',
          'insider_name': 'C. Kress',
          'role': 'EVP & CFO',
          'code': 'S',
          'code_label': 'Open-market sale',
          'direction': 'sell',
          'shares': 45000,
          'price': 178.32,
          'plan_type': 'scheduled_10b5-1',
        },
      ],
    };
    final api = _FakeApi(profileJson: _liveProfile(), insiderJson: insider);
    await _pump(tester, api: api);

    await tester.tap(find.text('INSIDER'));
    await tester.pumpAndSettle();

    // The option-exercise row shows its own code label, neutrally — never BUY.
    expect(find.text('BUY'), findsNothing);
    expect(find.text('OPTION EXERCISE'), findsOneWidget);
    // The scheduled sale is badged SELL and carries the 10b5-1 tag.
    expect(find.text('SELL'), findsOneWidget);
    expect(find.text('10b5-1'), findsOneWidget);
  });

  testWidgets('a whole-screen fetch failure shows a retry-able error state',
      (tester) async {
    final api = _FakeApi(profileThrows: true);
    await _pump(tester, api: api);

    expect(find.text("Couldn't load Company Review"), findsOneWidget);
    expect(find.text('Retry'), findsOneWidget);
  });

  testWidgets(
      'B1 — "See all N on Filings tab" actually jumps to the Filings tab',
      (tester) async {
    final profile = _liveProfile();
    (profile['filings'] as Map<String, dynamic>)['items'] = [
      {
        'form': '10-Q',
        'description': 'Quarterly report',
        'filed_date': '2026-08-27',
        'url': 'https://www.sec.gov/x.htm',
      },
      {
        'form': '8-K',
        'description': 'Current report',
        'filed_date': '2026-08-01',
        'url': 'https://www.sec.gov/y.htm',
      },
    ];
    final api = _FakeApi(profileJson: profile);
    await _pump(tester, api: api);

    // Sanity: starts on Overview.
    expect(find.text('All filings'), findsNothing);

    final seeAll = find.textContaining('See all');
    await tester.ensureVisible(seeAll);
    await tester.pumpAndSettle();
    await tester.tap(seeAll);
    await tester.pumpAndSettle();

    // The Filings tab's own heading is now visible — the tap landed on the
    // real TabController, not a no-op DefaultTabController lookup.
    expect(find.text('All filings'), findsOneWidget);
  });

  testWidgets('B2 — Overview shows its reason on a partial state, even with '
      'a live description', (tester) async {
    final profile = _liveProfile();
    (profile['overview'] as Map<String, dynamic>)
      ..['state'] = 'partial'
      ..['reason'] = 'EDGAR rate limited; description from yfinance only';
    final api = _FakeApi(profileJson: profile);
    await _pump(tester, api: api);

    expect(
        find.textContaining(
            'EDGAR rate limited; description from yfinance only'),
        findsWidgets);
  });

  testWidgets('B2 — Ownership not_available shows its reason', (tester) async {
    final profile = _liveProfile();
    (profile['ownership'] as Map<String, dynamic>)
      ..['state'] = 'not_available'
      ..['reason'] = 'yfinance holder data unavailable for this ticker'
      ..remove('shares_outstanding')
      ..remove('float_shares')
      ..remove('pct_institutions')
      ..remove('pct_insiders')
      ..['holders'] = <Map<String, dynamic>>[];
    final api = _FakeApi(profileJson: profile);
    await _pump(tester, api: api);

    await tester.tap(find.text('OWNERSHIP'));
    await tester.pumpAndSettle();

    expect(
        find.textContaining('yfinance holder data unavailable for this ticker'),
        findsOneWidget);
  });

  testWidgets('B2 — Insider not_available shows its reason', (tester) async {
    final api = _FakeApi(
      profileJson: _liveProfile(),
      insiderJson: {
        'ticker': 'NVDA',
        'state': 'not_available',
        'reason': 'No CIK match for this symbol',
        'sources': <String>[],
        'transactions': <Map<String, dynamic>>[],
      },
    );
    await _pump(tester, api: api);

    await tester.tap(find.text('INSIDER'));
    await tester.pumpAndSettle();

    expect(find.textContaining('No CIK match for this symbol'),
        findsOneWidget);
  });

  testWidgets(
      'B3 — an earnings-provider error renders an explicit error note, '
      'never "no upcoming earnings"', (tester) async {
    final profile = _liveProfile();
    (profile['filings'] as Map<String, dynamic>)['items'] =
        <Map<String, dynamic>>[];
    final api = _FakeApi(profileJson: profile);
    await _pump(
      tester,
      api: api,
      extraOverrides: [
        tickerEarningsProvider.overrideWith(
            (ref, ticker) async => throw Exception('earnings feed down')),
      ],
    );

    await tester.tap(find.text('EVENTS'));
    await tester.pumpAndSettle();

    expect(find.textContaining("Couldn't load earnings data"),
        findsOneWidget);
    expect(
        find.textContaining(
            'No upcoming earnings and no recent 8-K filings'),
        findsNothing);
  });
}
