/// CR109 slice 2 — the 3-tap trade ticket (design §5.4, Amendment D).
///
/// TAP 1 (ticker) → TAP 2 (size, 25% the visual default) → TAP 3 (confirm:
/// shares, est. fee, book-%, one quote round trip) → submit. Also proves
/// the queue-first framing (§5.1) reads as the normal path, not a warning.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/games.dart';
import 'package:ami_trade/screens/games/games_trade_ticket_screen.dart';
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

    // The confirm card itself surfaces the queue-first note because the
    // quote says will_queue.
    expect(
      find.textContaining('queues for the next open'),
      findsWidgets,
      reason: 'the queue-first note is the top-of-ticket copy AND the '
          "confirm card's when will_queue is true — both present",
    );

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
}
