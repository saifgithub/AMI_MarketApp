// DEF474 — the games no-cash panel's SEE QUEUED ORDERS / SEE POSITIONS only
// popped the route, assuming the run screen sat underneath. The ticket is also
// opened straight from Games Home, where the pop lands on a screen that shows
// neither list. Opened from Home it must now open the run screen in its place;
// opened from the run screen it still just returns to it.

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/games.dart';
import 'package:ami_trade/screens/games/games_run_screen.dart';
import 'package:ami_trade/screens/games/games_trade_ticket_screen.dart';
import 'package:ami_trade/state/onboarding_providers.dart';
import 'package:ami_trade/state/watchlist_providers.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import '../../support/fake_games_api_client.dart';

class _NoCashApi extends FakeGamesApiClient {
  @override
  Future<GameRunDetail> gamesRunDetail(String runId) async => GameRunDetail(
        runId: runId,
        fieldId: 'field-1',
        cadence: 'week',
        state: 'active',
        stake: 10000,
        cash: 0,
      );
}

Future<void> _openTicket(WidgetTester tester,
    {required bool openedFromRun}) async {
  await tester.pumpWidget(
    ProviderScope(
      overrides: [
        apiClientProvider.overrideWithValue(_NoCashApi()),
        watchlistNotifierProvider.overrideWith((ref) => WatchlistNotifier(ref)),
      ],
      child: MaterialApp(
        localizationsDelegates: AppLocalizations.localizationsDelegates,
        supportedLocales: AppLocalizations.supportedLocales,
        home: Scaffold(
          body: Builder(
            builder: (context) => ElevatedButton(
              onPressed: () => GamesTradeTicketScreen.show(
                context,
                runId: 'run-1',
                openedFromRun: openedFromRun,
              ),
              child: const Text('open'),
            ),
          ),
        ),
      ),
    ),
  );
  await tester.tap(find.text('open'));
  await tester.pumpAndSettle();
}

void main() {
  testWidgets('opened from Home: the CTA lands on the run screen',
      (tester) async {
    await _openTicket(tester, openedFromRun: false);
    expect(find.byType(GamesTradeTicketScreen), findsOneWidget);
    expect(find.byType(GamesRunScreen), findsNothing);

    await tester.tap(find.text('SEE POSITIONS'));
    await tester.pumpAndSettle();

    expect(find.byType(GamesRunScreen), findsOneWidget,
        reason: 'popping would land on Home, which shows neither list');
    expect(find.byType(GamesTradeTicketScreen), findsNothing);
  });

  testWidgets('opened from the run screen: the CTA still just pops back',
      (tester) async {
    await _openTicket(tester, openedFromRun: true);

    await tester.tap(find.text('SEE POSITIONS'));
    await tester.pumpAndSettle();

    expect(find.byType(GamesTradeTicketScreen), findsNothing);
    expect(find.byType(GamesRunScreen), findsNothing);
    expect(find.text('open'), findsOneWidget);
  });
}
