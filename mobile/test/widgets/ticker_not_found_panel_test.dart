/// DEF208 — the one not-found surface, and the one piece of behaviour that
/// decides when to show it.
///
/// Guards the two properties that made three designs collapse into one:
/// the panel says something *different* depending on whether it has an
/// answer to offer (the DEF207 copy bug), and the validator never accuses a
/// real ticker just because the network dropped (the DEF207 fabrication
/// lesson, inverted).
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/tickers.dart';
import 'package:ami_trade/widgets/ticker_not_found_panel.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

const _nflx = TickerSuggestion(
  ticker: 'NFLX',
  companyName: 'Netflix, Inc.',
  exchange: 'NASDAQ',
);

Widget _harness({
  required String typed,
  required TickerSuggestion? suggestion,
  ValueChanged<String>? onAccept,
}) {
  return MaterialApp(
    localizationsDelegates: AppLocalizations.localizationsDelegates,
    supportedLocales: AppLocalizations.supportedLocales,
    home: Scaffold(
      body: TickerNotFoundPanel(
        typed: typed,
        suggestion: suggestion,
        onAccept: onAccept ?? (_) {},
      ),
    ),
  );
}

AppLocalizations _l(WidgetTester t) => AppLocalizations.of(
    t.element(find.byType(TickerNotFoundPanel)) as BuildContext);

void main() {
  group('DEF208 — TickerNotFoundPanel', () {
    testWidgets('with a suggestion, does NOT tell the user to try again',
        (t) async {
      await t.pumpWidget(_harness(typed: 'NETFLIX', suggestion: _nflx));
      final l = _l(t);

      expect(find.text(l.tickerNotFoundWithSuggestion('NETFLIX')),
          findsOneWidget);
      expect(
        find.text(l.tickerNotFound('NETFLIX')),
        findsNothing,
        reason: '"check the symbol and try again" directly above a tappable '
            'answer contradicts itself — DEF207\'s copy bug',
      );
      expect(find.text(l.tickerDidYouMean('NFLX', 'Netflix, Inc.')),
          findsOneWidget);
    });

    testWidgets('with no suggestion, says what to do and offers no button',
        (t) async {
      await t.pumpWidget(_harness(typed: 'ZZZZQQ', suggestion: null));
      final l = _l(t);

      expect(find.text(l.tickerNotFound('ZZZZQQ')), findsOneWidget);
      expect(find.byType(OutlinedButton), findsNothing,
          reason: 'nothing to offer means nothing to tap');
    });

    testWidgets('tapping the suggestion hands back the SYMBOL, not the typed '
        'string', (t) async {
      String? accepted;
      await t.pumpWidget(_harness(
        typed: 'NETFLIX',
        suggestion: _nflx,
        onAccept: (v) => accepted = v,
      ));
      await t.tap(find.byType(OutlinedButton));
      await t.pump();

      expect(accepted, 'NFLX',
          reason: 'handing the typed string back would silently un-fix the '
              'very thing the panel exists to fix');
    });
  });

  group('DEF208 — TickerFieldValidator', () {
    TickerValidation missing({TickerSuggestion? s}) =>
        TickerValidation(ticker: 'X', exists: false, suggestion: s);

    test('a resolved not-found check raises the panel with its suggestion',
        () async {
      var notified = 0;
      final v = TickerFieldValidator(
        validate: (_) async => missing(s: _nflx),
        onChanged: () => notified++,
      );
      addTearDown(v.dispose);

      expect(await v.check('NETFLIX'), isFalse);
      expect(v.unknownTicker, 'NETFLIX');
      expect(v.suggestion?.ticker, 'NFLX');
      expect(notified, greaterThan(0));
      expect(v.checking, isFalse);
    });

    test('an existing ticker clears the panel and fires onExists once',
        () async {
      final seen = <String>[];
      final v = TickerFieldValidator(
        validate: (t) async => TickerValidation(ticker: t, exists: true),
        onChanged: () {},
        onExists: seen.add,
      );
      addTearDown(v.dispose);

      expect(await v.check('nflx'), isTrue);
      expect(v.unknownTicker, isNull);
      expect(seen, ['NFLX'], reason: 'the field is normalized before use');
    });

    test('a network failure fails OPEN and accuses nobody', () async {
      final v = TickerFieldValidator(
        validate: (_) async => throw Exception('offline'),
        onChanged: () {},
      );
      addTearDown(v.dispose);

      expect(await v.check('AAPL'), isTrue,
          reason: 'the server-side guard is the real gate; blocking here '
              'would strand a user with a real ticker and bad wifi');
      expect(v.unknownTicker, isNull,
          reason: 'DEF207 — a dropped connection is not evidence that a '
              'ticker does not exist');
    });

    test('typing again clears a stale panel before the next check resolves',
        () async {
      final v = TickerFieldValidator(
        validate: (_) async => missing(),
        onChanged: () {},
        debounce: const Duration(milliseconds: 5),
      );
      addTearDown(v.dispose);

      await v.check('NETFLIX');
      expect(v.unknownTicker, 'NETFLIX');

      v.onTextChanged('NFL');
      expect(v.unknownTicker, isNull,
          reason: '"NETFLIX was not found" above a field reading "NFL" is '
              'its own small lie');
    });

    test('an empty field is never reported as a missing ticker', () async {
      var calls = 0;
      final v = TickerFieldValidator(
        validate: (_) async {
          calls++;
          return missing();
        },
        onChanged: () {},
      );
      addTearDown(v.dispose);

      expect(await v.check('   '), isFalse);
      expect(calls, 0, reason: 'nothing typed is not a lookup');
      expect(v.unknownTicker, isNull);
    });
  });
}
