/// CR109 slice 1 — PortfolioEquityChart's own states, isolated from the
/// full Portfolio screen. Mirrors `ticker_chart_states_test.dart`'s harness
/// shape: override the provider directly, pump just the widget.
///
/// Covers what `portfolio_screen_test.dart`'s heavy-profile fixture does not
/// exercise on its own: the <2-point empty state (never a blank frame, never
/// a flat zero line) and the CR040/CR134 degrade-loud marking (a simulated
/// point is visibly flagged — never merely dimmed).
library;

import 'dart:async';

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/sim.dart';
import 'package:ami_trade/state/sim_providers.dart';
import 'package:ami_trade/widgets/portfolio_equity_chart.dart';
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

DioException _status(int code) => DioException(
      requestOptions:
          RequestOptions(path: '/v1/sim/portfolio/u1/history'),
      type: DioExceptionType.badResponse,
      response: Response<dynamic>(
        requestOptions:
            RequestOptions(path: '/v1/sim/portfolio/u1/history'),
        statusCode: code,
      ),
    );

SimPortfolioHistoryPoint _point(
  int daysAgo, {
  required double nav,
  String priceSource = 'live',
}) =>
    SimPortfolioHistoryPoint(
      asOfDate: DateTime(2026, 8, 9).subtract(Duration(days: daysAgo)),
      nav: nav,
      cash: 10000,
      priceSource: priceSource,
    );

Future<void> _pumpCurve(
  WidgetTester tester, {
  Object? throwing,
  SimPortfolioHistory? data,
}) async {
  await tester.pumpWidget(const SizedBox.shrink());
  await tester.pumpWidget(
    ProviderScope(
      overrides: [
        portfolioHistoryProvider.overrideWith((ref) async {
          if (throwing != null) throw throwing;
          return data!;
        }),
      ],
      child: MaterialApp(
        localizationsDelegates: AppLocalizations.localizationsDelegates,
        supportedLocales: AppLocalizations.supportedLocales,
        home: const Scaffold(body: PortfolioEquityChart()),
      ),
    ),
  );
  await tester.pump();
  await tester.pump();
}

/// `_EquityCurvePainter` is private to `portfolio_equity_chart.dart`; a
/// `CustomPaint` finder alone is too broad (Material's own ink/shadow layers
/// use `CustomPaint` too), so this matches on the painter's runtime type
/// name instead — the same technique `portfolio_screen_test.dart` uses for
/// `_LivePip`.
Finder get _curvePainterFinder => find.byWidgetPredicate(
      (w) =>
          w is CustomPaint &&
          w.painter.runtimeType.toString() == '_EquityCurvePainter',
    );

void main() {
  group('CR109 slice 1 — empty state', () {
    testWidgets('fewer than two snapshots draws no curve and says why',
        (tester) async {
      await _pumpCurve(
        tester,
        data: SimPortfolioHistory(points: [_point(0, nav: 100000)], twrPct: 0),
      );

      expect(find.text('Your history starts building from today.'),
          findsOneWidget);
      expect(_curvePainterFinder, findsNothing);
      expect(tester.takeException(), isNull);
    });

    testWidgets('zero snapshots also draws no curve, not a flat line',
        (tester) async {
      await _pumpCurve(
        tester,
        data: const SimPortfolioHistory(points: [], twrPct: 0),
      );

      expect(find.text('Your history starts building from today.'),
          findsOneWidget);
      expect(_curvePainterFinder, findsNothing);
      expect(tester.takeException(), isNull);
    });
  });

  group('CR109 slice 1 — populated curve', () {
    testWidgets('two or more live snapshots draw the curve, no caveat line',
        (tester) async {
      await _pumpCurve(
        tester,
        data: SimPortfolioHistory(
          points: [
            _point(2, nav: 99000),
            _point(1, nav: 100500),
            _point(0, nav: 101200),
          ],
          twrPct: 1.2,
        ),
      );

      expect(find.text('EQUITY CURVE'), findsOneWidget);
      expect(_curvePainterFinder, findsOneWidget);
      expect(
        find.text('Dashed segments used simulated pricing, not a live quote.'),
        findsNothing,
        reason: 'every point is live — no CR040 caveat to show',
      );
      expect(tester.takeException(), isNull);
    });

    testWidgets(
        'CR040/CR134 — a non-live point shows the simulated-pricing caveat',
        (tester) async {
      await _pumpCurve(
        tester,
        data: SimPortfolioHistory(
          points: [
            _point(2, nav: 99000),
            _point(1, nav: 100500, priceSource: 'mock'),
            _point(0, nav: 101200),
          ],
          twrPct: 2.2,
        ),
      );

      expect(
        find.text('Dashed segments used simulated pricing, not a live quote.'),
        findsOneWidget,
        reason: 'a mock-priced day must be visibly marked, not drawn as fact',
      );
      expect(tester.takeException(), isNull);
    });
  });

  group('CR109 slice 1 — loading / error', () {
    testWidgets('loading renders the skeleton with no exception',
        (tester) async {
      await tester.pumpWidget(const SizedBox.shrink());
      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            portfolioHistoryProvider.overrideWith(
              (ref) => Completer<SimPortfolioHistory>().future,
            ),
          ],
          child: const MaterialApp(
            localizationsDelegates: AppLocalizations.localizationsDelegates,
            supportedLocales: AppLocalizations.supportedLocales,
            home: Scaffold(body: PortfolioEquityChart()),
          ),
        ),
      );
      await tester.pump();
      expect(tester.takeException(), isNull);
    });

    testWidgets('a retryable failure offers a tappable retry', (tester) async {
      await _pumpCurve(
        tester,
        throwing: DioException(
          requestOptions:
              RequestOptions(path: '/v1/sim/portfolio/u1/history'),
          type: DioExceptionType.connectionError,
        ),
      );
      final retry = find.descendant(
        of: find.byType(PortfolioEquityChart),
        matching: find.byType(InkWell),
      );
      expect(retry, findsOneWidget);
      expect(tester.takeException(), isNull);
    });

    testWidgets('a rejected request offers no retry', (tester) async {
      await _pumpCurve(tester, throwing: _status(422));
      final retry = find.descendant(
        of: find.byType(PortfolioEquityChart),
        matching: find.byType(InkWell),
      );
      expect(retry, findsNothing);
      expect(tester.takeException(), isNull);
    });
  });
}
