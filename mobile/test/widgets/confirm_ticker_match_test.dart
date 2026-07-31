/// CR128 — the "did you mean X?" confirmation gate shared by Convene the
/// Room, trade submit, and watchlist add.
///
/// Same two-halves shape as `confirm_restart_onboarding_test.dart`: the
/// dialog must treat Cancel and a dismissed barrier identically (both are
/// "abort, no side effects"), and it must actually return the suggested
/// ticker on confirm rather than the originally-typed one.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/widgets/confirm_ticker_match.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

Widget _harness(void Function(String?) onResult) {
  return MaterialApp(
    localizationsDelegates: AppLocalizations.localizationsDelegates,
    supportedLocales: AppLocalizations.supportedLocales,
    home: Scaffold(
      body: Builder(
        builder: (context) => TextButton(
          onPressed: () async => onResult(await confirmTickerMatch(
            context,
            typed: 'AAPLE',
            suggestedTicker: 'AAPL',
            suggestedCompanyName: 'Apple Inc.',
            exchange: 'NASDAQ',
          )),
          child: const Text('open'),
        ),
      ),
    ),
  );
}

void main() {
  group('CR128 — the ticker-match confirmation', () {
    testWidgets('shows the suggested ticker + company name before proceeding',
        (t) async {
      await t.pumpWidget(_harness((_) {}));
      await t.tap(find.text('open'));
      await t.pumpAndSettle();

      expect(find.byType(AlertDialog), findsOneWidget);
      final l = AppLocalizations.of(
          t.element(find.byType(AlertDialog)) as BuildContext);
      expect(find.text(l.tickerConfirmTitle('AAPL')), findsOneWidget);
      expect(
        find.text(l.tickerConfirmBody('AAPLE', 'Apple Inc.', 'NASDAQ')),
        findsOneWidget,
        reason: 'the CR\'s own acceptance criterion — company info must be '
            'shown before confirming',
      );
    });

    testWidgets('CANCEL returns null — zero side effects', (t) async {
      String? result = 'unset';
      await t.pumpWidget(_harness((r) => result = r));
      await t.tap(find.text('open'));
      await t.pumpAndSettle();

      await t.tap(find.text('CANCEL'));
      await t.pumpAndSettle();
      expect(result, isNull);
      expect(find.byType(AlertDialog), findsNothing);
    });

    testWidgets('dismissing the barrier is a NO, not a yes', (t) async {
      String? result = 'unset';
      await t.pumpWidget(_harness((r) => result = r));
      await t.tap(find.text('open'));
      await t.pumpAndSettle();

      await t.tapAt(const Offset(10, 10)); // the barrier, outside the dialog
      await t.pumpAndSettle();
      expect(result, isNull);
    });

    testWidgets('confirming returns the SUGGESTED ticker, not the typed one',
        (t) async {
      String? result;
      await t.pumpWidget(_harness((r) => result = r));
      await t.tap(find.text('open'));
      await t.pumpAndSettle();

      final l = AppLocalizations.of(
          t.element(find.byType(AlertDialog)) as BuildContext);
      await t.tap(find.text(l.tickerConfirmCta('AAPL')));
      await t.pumpAndSettle();
      expect(result, 'AAPL',
          reason: 'the whole point of the dialog is correcting the typo — '
              'returning the typed string back would silently un-fix it');
    });
  });
}
