/// CR109 slice 6 — the cadence lobby.
///
/// Saiful: *"How do I join the monthly, quarterly, etc games?"* These tests
/// pin the two things that make the answer correct rather than merely
/// present:
///
///   * all five cadences are offered, including any the backend adds that
///     this build does not have a name for — an unknown game the server is
///     running is a shipping-lag problem, not a reason to hide it;
///   * §4.1 — a cadence already held offers NO entry action at all. Not a
///     disabled button: a greyed-out CTA invites tapping at it, and the rule
///     is that there is nothing to do there.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/games.dart';
import 'package:ami_trade/screens/games/games_lobby_screen.dart';
import 'package:ami_trade/state/games_providers.dart';
import 'package:ami_trade/state/onboarding_providers.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import '../../support/fake_games_api_client.dart';

GameCadenceInfo _cadence(
  String cadence, {
  bool held = false,
  String state = 'entry_open',
  int queueCount = 0,
}) =>
    GameCadenceInfo(
      cadence: cadence,
      entryState: state,
      alreadyHolds: held,
      queueCount: queueCount,
      nextField: GameFieldSummary(
        fieldId: 'f-$cadence',
        startsOn: DateTime(2026, 8, 17),
        endsOn: DateTime(2026, 8, 21),
      ),
    );

Future<void> _pump(WidgetTester tester, List<GameCadenceInfo> cadences) async {
  await tester.pumpWidget(
    ProviderScope(
      overrides: [
        apiClientProvider.overrideWithValue(FakeGamesApiClient()),
        gamesCadencesProvider.overrideWith((ref) async => cadences),
      ],
      child: MaterialApp(
        localizationsDelegates: AppLocalizations.localizationsDelegates,
        supportedLocales: AppLocalizations.supportedLocales,
        home: const GamesLobbyScreen(),
      ),
    ),
  );
  await tester.pump();
  await tester.pump();
}

void main() {
  testWidgets('offers all five cadences by name', (tester) async {
    await _pump(tester, [
      _cadence('week'),
      _cadence('month'),
      _cadence('quarter'),
      _cadence('half'),
      _cadence('year'),
    ]);

    expect(find.text('Weekly'), findsOneWidget);
    expect(find.text('Monthly'), findsOneWidget);
    expect(find.text('Quarterly'), findsOneWidget);
    expect(find.text('Half-year', skipOffstage: false), findsOneWidget);
    expect(find.text('Annual', skipOffstage: false), findsOneWidget);
    expect(find.text('ENTER THIS FIELD', skipOffstage: false), findsNWidgets(5));
  });

  testWidgets('a cadence already held offers no entry action at all',
      (tester) async {
    await _pump(tester, [
      _cadence('week', held: true),
      _cadence('month'),
    ]);

    expect(find.text("You're in"), findsOneWidget);
    // One ENTER, for the monthly — not two, and not a disabled second one.
    expect(find.text('ENTER THIS FIELD'), findsOneWidget);
  });

  testWidgets('states the one-run-per-cadence rule where the choice is made',
      (tester) async {
    await _pump(tester, [_cadence('week')]);
    expect(
      find.text("One run of each at a time — five books, never two of a kind."),
      findsOneWidget,
    );
  });

  testWidgets('shows what a longer cadence is worth', (tester) async {
    await _pump(tester, [_cadence('week'), _cadence('quarter')]);
    expect(find.text('Worth 13× a weekly win'), findsOneWidget);
    // Weekly is the unit — printing "Worth 1× a weekly win" says nothing.
    expect(find.textContaining('Worth 1×'), findsNothing);
  });

  testWidgets('a locked cadence says when the next chance comes',
      (tester) async {
    await _pump(tester, [_cadence('month', state: 'locked')]);
    expect(
      find.text('Entry closed — next one opens when this run starts'),
      findsOneWidget,
    );
    expect(find.text('ENTER THIS FIELD'), findsNothing);
  });

  testWidgets('a cadence this build has no name for is still offered',
      (tester) async {
    await _pump(tester, [_cadence('fortnight')]);
    expect(find.text('FORTNIGHT'), findsOneWidget);
    expect(find.text('ENTER THIS FIELD'), findsOneWidget);
  });
}
