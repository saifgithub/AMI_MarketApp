/// DEF151 follow-up — the chart's three states stop pretending to be one.
///
/// The original defect was a 100% outage that read as a flaky network: every
/// request 422'd, and the client said "Chart unavailable. Tap to retry." over
/// a request that could never succeed. The server-side fix stopped the 422s.
/// This pins the half that made the outage invisible for weeks — a retry
/// affordance offered for failures a retry cannot change.
///
/// Three states, and the third is the one nobody had noticed: a `data:`
/// response with zero candles is not a failure at all. The server answered.
/// A recently listed ticker viewed on 5Y hits it on every visit and can never
/// clear it, so offering a retry there is a deterministic broken promise.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/sim.dart';
import 'package:ami_trade/services/api/api_exceptions.dart';
import 'package:ami_trade/services/api/friendly_error.dart';
import 'package:ami_trade/state/ticker_history_provider.dart';
import 'package:ami_trade/widgets/ticker_chart.dart';
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

DioException _status(int code) => DioException(
      requestOptions: RequestOptions(path: '/v1/sim/history/AAPL'),
      type: DioExceptionType.badResponse,
      response: Response<dynamic>(
        requestOptions: RequestOptions(path: '/v1/sim/history/AAPL'),
        statusCode: code,
      ),
    );

DioException _type(DioExceptionType t) => DioException(
      requestOptions: RequestOptions(path: '/v1/sim/history/AAPL'),
      type: t,
    );

const _emptyHistory = SimHistory(
  ticker: 'AAPL',
  period: '1m',
  source: 'yfinance',
  candles: [],
);

Future<void> _pumpChart(
  WidgetTester tester, {
  Object? throwing,
  SimHistory? data,
}) async {
  await tester.pumpWidget(const SizedBox.shrink());
  await tester.pumpWidget(
    ProviderScope(
      overrides: [
        tickerHistoryProvider.overrideWith((ref, key) async {
          if (throwing != null) throw throwing;
          return data!;
        }),
      ],
      child: MaterialApp(
        localizationsDelegates: AppLocalizations.localizationsDelegates,
        supportedLocales: AppLocalizations.supportedLocales,
        home: const Scaffold(
          body: TickerChart(ticker: 'AAPL', height: 220),
        ),
      ),
    ),
  );
  await tester.pump();
  await tester.pump();
}

/// The retry affordance, as the user meets it: something tappable wrapping the
/// notice. Asserting on the InkWell rather than on copy is deliberate — the
/// promise is the tap, not the sentence.
Finder get _retryAffordance => find.descendant(
      of: find.byType(TickerChart),
      matching: find.byType(InkWell),
    );

void main() {
  group('DEF151 — isRetryable names the cases that must not offer a retry', () {
    test('a rejected request is never retryable', () {
      // 422 is the exact status that made the chart dark on every ticker.
      for (final code in [400, 401, 403, 404, 422]) {
        expect(isRetryable(_status(code)), isFalse, reason: '$code');
      }
    });

    test('rate limiting and server faults are', () {
      for (final code in [429, 500, 502, 503]) {
        expect(isRetryable(_status(code)), isTrue, reason: '$code');
      }
      expect(isRetryable(const ServerUnavailableException(503)), isTrue);
    });

    test('transport failures are, and unknown errors default to retryable', () {
      for (final t in [
        DioExceptionType.connectionTimeout,
        DioExceptionType.sendTimeout,
        DioExceptionType.receiveTimeout,
        DioExceptionType.connectionError,
        DioExceptionType.unknown,
      ]) {
        expect(isRetryable(_type(t)), isTrue, reason: '$t');
      }
      expect(isRetryable(Exception('something new')), isTrue,
          reason: 'refusing a retry that would have worked is the worse error');
    });

    test('cancelled and untrusted-certificate are not', () {
      expect(isRetryable(_type(DioExceptionType.cancel)), isFalse);
      expect(isRetryable(_type(DioExceptionType.badCertificate)), isFalse);
    });
  });

  group('DEF151 — the chart renders three distinct states', () {
    testWidgets('transient failure keeps the retry, and it is tappable',
        (t) async {
      await _pumpChart(t, throwing: _type(DioExceptionType.connectionError));
      expect(find.text('Chart unavailable. Tap to retry.'), findsOneWidget);
      expect(_retryAffordance, findsOneWidget,
          reason: 'a network blip is exactly what retry is for');
    });

    testWidgets('a rejected request offers no retry', (t) async {
      await _pumpChart(t, throwing: _status(422));
      expect(find.text("AMI can't chart this one."), findsOneWidget);
      expect(find.text('Chart unavailable. Tap to retry.'), findsNothing,
          reason: 'this was the copy that hid a total outage for weeks');
      expect(_retryAffordance, findsNothing,
          reason: 'every tap would re-send the identical rejected request');
    });

    testWidgets('a successful empty response is not an error and offers no '
        'retry', (t) async {
      await _pumpChart(t, data: _emptyHistory);
      expect(find.text('No price history for this period.'), findsOneWidget);
      expect(_retryAffordance, findsNothing,
          reason: 'the request succeeded — a retry returns the same emptiness');
      expect(find.byIcon(Icons.refresh), findsNothing,
          reason: 'a refresh glyph depicts an action that cannot help');
    });

    testWidgets('the three states really are three different strings',
        (t) async {
      // The defect was one string for three conditions. If a future edit
      // collapses any two of them, this fails even though each test above
      // would still find its own text somewhere on screen.
      final seen = <String>{};
      for (final pump in [
        () => _pumpChart(t, throwing: _type(DioExceptionType.connectionError)),
        () => _pumpChart(t, throwing: _status(422)),
        () => _pumpChart(t, data: _emptyHistory),
      ]) {
        await pump();
        final notice = t.widgetList<Text>(find.descendant(
          of: find.byType(TickerChart),
          matching: find.byType(Text),
        ));
        // The period chips are Texts too; the notice is the one that is not a
        // period label.
        final labels = notice
            .map((w) => w.data)
            .whereType<String>()
            .where((s) => !const ['1D', '1W', '1M', '3M', '1Y', '5Y']
                .contains(s));
        expect(labels, isNotEmpty);
        seen.add(labels.first);
      }
      expect(seen, hasLength(3),
          reason: 'two states collapsed back into one message: $seen');
    });
  });
}
