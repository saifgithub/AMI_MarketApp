// DEF486 — the "Removed from watchlist — UNDO" snackbar persisted forever while
// an accessibility service was active (Flutter keeps action snackbars up under
// accessibleNavigation) and could sit over the next sheet's primary button.
// It must auto-dismiss (with a longer window under a screen reader so UNDO is
// still reachable), and opening the watchlist sheet must clear it.

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/screens/sim/portfolio_screen.dart';
import 'package:ami_trade/state/watchlist_providers.dart';
import 'package:ami_trade/widgets/watchlist_sheet.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

Widget _app({
  required bool accessible,
  required void Function(BuildContext, WidgetRef) onTap,
}) =>
    ProviderScope(
      overrides: [
        watchlistNotifierProvider.overrideWith((ref) => WatchlistNotifier(ref)),
      ],
      child: MaterialApp(
        localizationsDelegates: AppLocalizations.localizationsDelegates,
        supportedLocales: AppLocalizations.supportedLocales,
        builder: (context, child) => MediaQuery(
          data: MediaQuery.of(context)
              .copyWith(accessibleNavigation: accessible),
          child: child!,
        ),
        home: Scaffold(
          body: Consumer(
            builder: (context, ref, _) => ElevatedButton(
              onPressed: () => onTap(context, ref),
              child: const Text('go'),
            ),
          ),
        ),
      ),
    );

void _showUndo(BuildContext context) {
  ScaffoldMessenger.of(context).showSnackBar(buildWatchlistUndoSnackBar(
    context,
    message: 'Removed from watchlist',
    undoLabel: 'UNDO',
    onUndo: () {},
  ));
}

void main() {
  for (final accessible in [false, true]) {
    testWidgets(
        'the UNDO snackbar auto-dismisses (accessibleNavigation=$accessible)',
        (tester) async {
      await tester.pumpWidget(
          _app(accessible: accessible, onTap: (c, _) => _showUndo(c)));
      await tester.tap(find.text('go'));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 400));
      expect(find.text('Removed from watchlist'), findsOneWidget);

      // Still reachable well after the plain 4s window under a screen reader.
      await tester.pump(const Duration(seconds: 5));
      await tester.pump(const Duration(milliseconds: 400));
      expect(find.text('Removed from watchlist'),
          accessible ? findsOneWidget : findsNothing);

      await tester.pump(const Duration(seconds: 7));
      await tester.pump(const Duration(milliseconds: 400));
      expect(find.text('Removed from watchlist'), findsNothing,
          reason: 'an action snackbar that never goes away covers the UI '
              'beneath it for a screen-reader user');
    });
  }

  testWidgets('opening the watchlist sheet clears a lingering UNDO bar',
      (tester) async {
    await tester.pumpWidget(_app(
      accessible: true,
      onTap: (c, ref) {
        _showUndo(c);
        showWatchlistSheet(c, ref, ticker: 'AAPL');
      },
    ));
    await tester.tap(find.text('go'));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 500));

    expect(find.text('AAPL'), findsOneWidget);
    expect(find.text('Removed from watchlist'), findsNothing);
  });
}
