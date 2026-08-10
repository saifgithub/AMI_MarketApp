/// CR109 slice 2 — the 3-tap trade ticket (design §5.4, Amendment D).
///
/// TAP 1 (ticker) → TAP 2 (size, 25% the visual default) → TAP 3 (confirm:
/// shares, est. fee, book-%, one quote round trip) → submit. Also proves
/// the queue-first framing (§5.1) reads as the normal path, not a warning.
library;

import 'dart:async';

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/games.dart';
import 'package:ami_trade/screens/games/games_trade_ticket_screen.dart';
import 'package:ami_trade/state/games_providers.dart';
import 'package:ami_trade/state/onboarding_providers.dart';
import 'package:ami_trade/state/watchlist_providers.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:ami_trade/widgets/hex/hex_chip.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import '../../support/fake_games_api_client.dart';

Future<void> _pump(WidgetTester tester, FakeGamesApiClient api) async {
  await tester.pumpWidget(
    ProviderScope(
      overrides: [
        apiClientProvider.overrideWithValue(api),
        // Deterministic, empty, no network — same technique
        // games_trade_ticket_test's manual-entry path relies on.
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
  testWidgets(
    'TAP1 ticker -> TAP2 size -> TAP3 confirm shows shares/fee/book%',
    (tester) async {
      final api = FakeGamesApiClient(
        tradeQuote: const GameTradeQuote(
          ticker: 'AAPL',
          side: 'buy',
          shares: 13.8889,
          price: 180.0,
          notional: 2500.0,
          estFee: 2.5,
          bookPercentage: 25.0,
          priceSource: 'live',
          willQueue: false,
        ),
      );
      await _pump(tester, api);

      // Before TAP 1, no size step and no confirm step are visible yet.
      expect(find.text('2 · PICK A SIZE'), findsNothing);
      expect(find.text('3 · CONFIRM'), findsNothing);

      // TAP 1 — type + submit a ticker (no watchlist chips in this fixture).
      await tester.enterText(find.byType(TextField), 'AAPL');
      await tester.testTextInput.receiveAction(TextInputAction.done);
      await tester.pumpAndSettle();

      expect(find.text('2 · PICK A SIZE'), findsOneWidget);
      // §5.4: "the 25% chip renders as the visually-default choice" —
      // filled/hexGreen BEFORE any size tap has committed a value.
      final defaultChip = tester.widget<HexChip>(find.ancestor(
        of: find.text('25%'),
        matching: find.byType(HexChip),
      ));
      expect(defaultChip.variant, HexChipVariant.filled);
      expect(defaultChip.color, AmiColors.hexGreen);
      final tenPctChip = tester.widget<HexChip>(find.ancestor(
        of: find.text('10%'),
        matching: find.byType(HexChip),
      ));
      expect(tenPctChip.variant, HexChipVariant.outlined,
          reason: 'only the default chip is pre-selected — every other '
              'size chip stays a plain, unselected choice');

      // TAP 2 — commit a size chip.
      await tester.tap(find.text('25%'));
      await tester.pumpAndSettle();

      // TAP 3 — the confirm card, fetched with one quote round trip.
      expect(find.text('3 · CONFIRM'), findsOneWidget);
      expect(api.quoteCallsSeen, hasLength(1));
      expect(api.quoteCallsSeen.single.ticker, 'AAPL');
      expect(api.quoteCallsSeen.single.notional, closeTo(2500.0, 0.001));

      expect(find.text('13.8889'), findsOneWidget);
      expect(find.text('\$2.50'), findsOneWidget);
      expect(find.text('25.0%'), findsOneWidget);
    },
  );

  testWidgets('a queued result reads as the normal path, not a warning',
      (tester) async {
    final api = FakeGamesApiClient(
      tradeQuote: const GameTradeQuote(
        ticker: 'AAPL',
        side: 'buy',
        shares: 1,
        price: 180.0,
        notional: 180.0,
        estFee: 1.0,
        bookPercentage: 1.8,
        willQueue: true,
      ),
      tradeResult: const GameTradeResult(
        status: 'queued',
        ticker: 'AAPL',
        side: 'buy',
      ),
    );
    await _pump(tester, api);

    await tester.enterText(find.byType(TextField), 'AAPL');
    await tester.testTextInput.receiveAction(TextInputAction.done);
    await tester.pumpAndSettle();
    await tester.tap(find.text('25%'));
    await tester.pumpAndSettle();

    // The queue-first rule is no longer standing copy. It printed as a
    // three-line paragraph at the top of the sheet AND again on the confirm
    // card — twice on one ticket, unchanged every time, which is how a rule
    // becomes wallpaper. Saiful, on build 76: "does not need to be displayed
    // all the time." It now lives behind a ⓘ, one tap away, same string.
    expect(
      find.textContaining('queues for the next open'),
      findsNothing,
      reason: 'standing copy, not a state — it belongs behind the info icon',
    );
    expect(find.byIcon(Icons.info_outline), findsOneWidget);

    await tester.tap(find.byIcon(Icons.info_outline));
    await tester.pumpAndSettle();
    expect(
      find.textContaining('queues for the next open'),
      findsOneWidget,
      reason: 'hidden by default is not the same as deleted — for a first-'
          'time player this is the single most surprising thing the game does',
    );
    await tester.tap(find.text('Got it'));
    await tester.pumpAndSettle();

    // And the per-share price is on the card, because a share count and a
    // total with nothing to check them against is not a quote.
    expect(find.text('PRICE PER SHARE'), findsOneWidget);
    expect(find.text('\$180.00'), findsOneWidget);

    // The ticket grew a cash header and a 1–100% size slider, so the button
    // now sits below an 800x600 test surface. Scroll to it rather than
    // shrinking the UI to fit the test.
    await tester.ensureVisible(find.text('PLACE ORDER'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('PLACE ORDER'));
    await tester.pumpAndSettle();

    expect(api.tradeCallsSeen, hasLength(1));
    expect(
      find.text('Queued — fills at the next US market open. Free to '
          'cancel any time before then.'),
      findsOneWidget,
    );
  });

  testWidgets(
    'a failed quote offers a RETRY, never a spinner that never stops',
    (tester) async {
      // Saiful hit this for real: the Cloudflare tunnel dropped all four edge
      // connectors for ~70 seconds, his phone got a 502, and the confirm card
      // sat there turning a progress indicator underneath the error message
      // for as long as the sheet stayed open. Nothing was in flight. The app
      // was showing work it was not doing, and the only way out was to go back
      // and re-pick a size.
      final api = FakeGamesApiClient(quoteError: Exception('502'));
      await _pump(tester, api);

      await tester.enterText(find.byType(TextField), 'AMD');
      await tester.testTextInput.receiveAction(TextInputAction.done);
      await tester.pumpAndSettle();
      await tester.tap(find.widgetWithText(HexChip, '25%'));
      await tester.pumpAndSettle();

      expect(api.quoteCallsSeen, hasLength(1));
      expect(
        find.byType(CircularProgressIndicator),
        findsNothing,
        reason: 'nothing is in flight — a spinner here is a lie about state',
      );
      expect(find.text('RETRY'), findsOneWidget);

      // And the retry actually re-quotes.
      api.quoteError = null;
      await tester.ensureVisible(find.text('RETRY'));
      await tester.tap(find.text('RETRY'));
      await tester.pumpAndSettle();

      expect(api.quoteCallsSeen, hasLength(2));
      expect(find.text('RETRY'), findsNothing);
      expect(find.text('PLACE ORDER'), findsOneWidget);
    },
  );

  testWidgets(
    'a refreshing run detail never sizes the next order against zero',
    (tester) async {
      // THE ONE THAT BROKE THE SECOND ORDER. Placing an order invalidates
      // gamesRunDetailProvider, and during the refetch Riverpod's
      // AsyncLoading — even carrying the previous value — answers `asData`
      // with null. The ticket's `?? 0` then quoted against zero cash, the API
      // refused it (422, notional must be > 0), and the player got "that
      // request wasn't accepted. Check the details" while the header on the
      // same screen showed the correct 4,758.13.
      //
      // Saiful: "Suddenly this does not work." It worked until his first
      // order and failed for every one after it.
      final api = FakeGamesApiClient();
      final completer = Completer<GameRunDetail>();
      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            apiClientProvider.overrideWithValue(api),
            watchlistNotifierProvider
                .overrideWith((ref) => WatchlistNotifier(ref)),
            // Still in flight — exactly the window a placed order opens.
            gamesRunDetailProvider('run-1').overrideWith((ref) => completer.future),
          ],
          child: MaterialApp(
            localizationsDelegates: AppLocalizations.localizationsDelegates,
            supportedLocales: AppLocalizations.supportedLocales,
            home: Scaffold(
              body: Builder(
                builder: (context) => ElevatedButton(
                  onPressed: () =>
                      GamesTradeTicketScreen.show(context, runId: 'run-1'),
                  child: const Text('open'),
                ),
              ),
            ),
          ),
        ),
      );
      await tester.tap(find.text('open'));
      await tester.pumpAndSettle();

      await tester.enterText(find.byType(TextField), 'BAC');
      await tester.testTextInput.receiveAction(TextInputAction.done);
      await tester.pumpAndSettle();
      await tester.tap(find.widgetWithText(HexChip, '25%'));
      // Not pumpAndSettle: the card is legitimately in its loading state and
      // a CircularProgressIndicator animates forever, so settling never
      // happens. That the spinner IS showing is the point — cash really is
      // still arriving.
      await tester.pump();
      await tester.pump();
      expect(find.byType(CircularProgressIndicator), findsOneWidget);

      expect(
        api.quoteCallsSeen,
        isEmpty,
        reason: 'a quote against zero cash cannot succeed — do not send it',
      );
      expect(find.textContaining("wasn't accepted"), findsNothing);

      // Cash lands. The real quote goes out, against the real number.
      completer.complete(const GameRunDetail(
        runId: 'run-1',
        fieldId: 'f1',
        cadence: 'week',
        state: 'active',
        stake: 10000,
        cash: 10000,
        cashCommitted: 5241.87,
        cashAvailable: 4758.13,
        queuedOrderCount: 5,
      ));
      await tester.pump();
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));

      expect(api.quoteCallsSeen, hasLength(1));
      expect(
        api.quoteCallsSeen.single.notional,
        closeTo(4758.13 * 0.25, 0.01),
        reason: 'sized against cash_available, not against zero',
      );
    },
  );
}
