/// CR109 slice 2 — the entry sheet's no-rules disclosure fence
/// (design §7, §13.3): full text on a player's first entry ever, a
/// compressed (but still tappable) chip on every entry after.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/screens/games/games_entry_sheet.dart';
import 'package:ami_trade/state/onboarding_providers.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../../support/fake_games_api_client.dart';

/// Must stay byte-identical to `gamesDisclosureBody` in `app_en.arb`. The
/// halal clause is asserted explicitly below rather than left to this
/// constant, because it is the one omission a user cannot infer and the
/// reason CR109 accepts disclosure in place of a gate.
const _fullDisclosure =
    'No mandate, no position or sector limits, and no halal screening — '
    'names blocked on the training floor can be traded here. Real market '
    'frictions still apply: trading costs, and fills only during market hours.';

const _disclosureChip = 'NO MANDATE · NO HALAL SCREEN';

Future<void> _pump(WidgetTester tester) async {
  await tester.pumpWidget(
    ProviderScope(
      overrides: [apiClientProvider.overrideWithValue(FakeGamesApiClient())],
      child: MaterialApp(
        localizationsDelegates: AppLocalizations.localizationsDelegates,
        supportedLocales: AppLocalizations.supportedLocales,
        home: Scaffold(
          body: Builder(
            builder: (context) => ElevatedButton(
              onPressed: () =>
                  GamesEntrySheet.show(context, cadence: 'week'),
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
  testWidgets('first entry ever renders the full disclosure text',
      (tester) async {
    SharedPreferences.setMockInitialValues({});
    await _pump(tester);

    expect(find.text(_fullDisclosure), findsOneWidget);
    expect(find.text(_disclosureChip), findsNothing,
        reason: 'the compressed chip must not ALSO render on a first entry');
  });

  testWidgets('the disclosure names the halal screen, not a vague "no screens"',
      (tester) async {
    // CR109 accepts, as a recorded risk, that a halal-only user can trade
    // unscreened on a scored path — and makes DISCLOSURE the obligation that
    // stands in for the gate. That trade only holds if the sentence actually
    // conveys the fact: an earlier draft read "no screens", which a
    // halal-observant reader would not take to mean Sharia screening is off.
    // This asserts the specific word survives any future copy edit.
    SharedPreferences.setMockInitialValues({});
    await _pump(tester);

    final disclosure = tester.widget<Text>(find.text(_fullDisclosure));
    expect(
      disclosure.data!.toLowerCase(),
      contains('halal'),
      reason: 'the one omission a user cannot infer, and the only one with a '
          'real-world consequence for them, must be named outright',
    );
  });

  testWidgets('a later entry compresses to the chip, not the full text',
      (tester) async {
    SharedPreferences.setMockInitialValues({
      'ami_games_disclosure_seen': true,
    });
    await _pump(tester);

    expect(find.text(_disclosureChip), findsOneWidget);
    expect(find.text(_fullDisclosure), findsNothing,
        reason: 'a returning player must not be re-shown the full block '
            '(design §13.3\'s entry-screen-load fence)');
  });

  testWidgets('the chip stays tappable and re-opens the full text',
      (tester) async {
    SharedPreferences.setMockInitialValues({
      'ami_games_disclosure_seen': true,
    });
    await _pump(tester);

    await tester.tap(find.text(_disclosureChip));
    await tester.pumpAndSettle();

    expect(find.text(_fullDisclosure), findsOneWidget,
        reason: 'compressed must mean tappable, never buried (CR040)');
  });

  testWidgets('confirming entry marks the disclosure seen for next time',
      (tester) async {
    SharedPreferences.setMockInitialValues({});
    await _pump(tester);

    await tester.tap(find.text("ENTER THIS FIELD"));
    await tester.pumpAndSettle();

    final prefs = await SharedPreferences.getInstance();
    expect(prefs.getBool('ami_games_disclosure_seen'), isTrue);
  });
}
