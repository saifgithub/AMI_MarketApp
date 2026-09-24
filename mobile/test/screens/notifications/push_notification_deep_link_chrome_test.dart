/// CR232 round 2 (audit MAJOR-1) — the regression net for the one push
/// entry point CR232's original 60-site sweep did not reach.
///
/// `DeepLinkDispatcher` took a raw `NavigatorState` and the caller (a
/// `OneSignal` click callback, which has no `BuildContext`) had only
/// `appNavigatorKey` — the app's ROOT navigator — to give it. A tapped
/// price-alert push therefore landed `TickerDetailScreen` ABOVE
/// `HomeShell`'s Scaffold, covering the bottom nav, the ad slot and the
/// ticker tape: exactly the defect CR232 exists to eliminate, on the one
/// path its own review missed (it arrives via an injected `NavigatorState`
/// parameter, not a `BuildContext`, so the sweep that walked
/// `Navigator.of(context)` call sites never saw it — see the auditor's
/// finding in `orchestration/audit/cr/CR232.auditor.md` round 1).
///
/// This test pumps the REAL app shape — `MaterialApp(navigatorKey:
/// appNavigatorKey)` wrapping `PushNotificationListener` wrapping
/// `HomeShell`, exactly as `app.dart` wires it — feeds a `DeepLink` through
/// a fake `NotificationService`'s `notificationOpened()` stream (standing in
/// for OneSignal's click callback), and asserts the pushed page lands as a
/// DESCENDANT of `HomeShell`, not an ancestor covering it. That is the
/// assertion that actually distinguishes the two cases: `find.byType` alone
/// cannot, because an `IndexedStack` never unmounts its panes, so
/// `HexBottomNav`/`TickerTape` are still "found" in the tree, at the same
/// layout position, whether the push landed correctly inside the tab's own
/// `_TabNavigator` or incorrectly on the root navigator above `HomeShell`
/// entirely — confirmed by mutation-testing a `getTopLeft`-based positional
/// assertion first, which passed even with the defect reintroduced, before
/// this descendant check replaced it.
library;

import 'dart:async';

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/price_alert.dart';
import 'package:ami_trade/models/sim.dart';
import 'package:ami_trade/screens/feedback/bug_resolution_toasts.dart';
import 'package:ami_trade/screens/home_shell.dart';
import 'package:ami_trade/screens/notifications/push_notification_listener.dart';
import 'package:ami_trade/screens/sim/ticker_detail_screen.dart';
import 'package:ami_trade/services/api/api_client.dart';
import 'package:ami_trade/services/notifications/app_navigator_key.dart';
import 'package:ami_trade/services/notifications/notification_models.dart';
import 'package:ami_trade/services/notifications/notification_service.dart';
import 'package:ami_trade/state/alpaca_providers.dart';
import 'package:ami_trade/state/journal_providers.dart';
import 'package:ami_trade/state/notification_providers.dart';
import 'package:ami_trade/state/onboarding_providers.dart';
import 'package:ami_trade/state/sim_providers.dart';
import 'package:ami_trade/state/watchlist_providers.dart';
import 'package:ami_trade/widgets/hex/hex_bottom_nav.dart';
import 'package:ami_trade/widgets/ticker_tape.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

/// Benign, non-empty responses for every provider `TickerDetailScreen`
/// reads, so the screen renders its normal content rather than an error
/// panel — the test's assertions are about the SHELL underneath it, not
/// this screen's own data states, and an error panel would still exercise
/// the chrome-covering bug just as well but reads as a less faithful
/// reproduction of a real price-alert tap.
class _FakeApiClient extends ApiClient {
  _FakeApiClient() : super(baseUrl: 'test://localhost');

  @override
  Future<SimNews> simNews(String ticker) async =>
      SimNews(ticker: ticker, source: 'test', articles: const []);

  @override
  Future<SimEarnings> simEarnings(String ticker) async =>
      SimEarnings(ticker: ticker, source: 'test');

  @override
  Future<HoldingLots> simHoldingLots(String userId, String ticker) async =>
      HoldingLots(
        ticker: ticker,
        currentPrice: 100,
        priceSource: 'test',
        lots: const [],
        totals: const LotTotals(
          realisedPnl: 0,
          unrealisedPnl: 0,
          quantityOpen: 0,
        ),
      );

  @override
  Future<List<PriceAlert>> priceAlerts(String userId, {String? status}) async =>
      const [];
}

class _FakeNotificationService implements NotificationService {
  final _openedController = StreamController<DeepLink>.broadcast();
  final _foregroundController = StreamController<String>.broadcast();

  /// Simulates a tapped push arriving — the same call OneSignal's own click
  /// listener makes into `_openedController` in
  /// `onesignal_notification_service.dart`.
  void simulateTap(DeepLink link) => _openedController.add(link);

  @override
  bool get isConfigured => true;

  @override
  bool get permissionGranted => true;

  @override
  Future<void> initialize() async {}

  @override
  Future<bool> requestPermission() async => true;

  @override
  Future<void> login(String userId) async {}

  @override
  Future<void> logout() async {}

  @override
  Stream<DeepLink> notificationOpened() => _openedController.stream;

  @override
  Stream<String> foregroundNotificationTitle() => _foregroundController.stream;
}

class _FixedSimNotifier extends SimNotifier {
  _FixedSimNotifier(super.ref, SimState fixed) {
    state = fixed;
  }
}

class _FixedWatchlistNotifier extends WatchlistNotifier {
  _FixedWatchlistNotifier(super.ref, WatchlistState fixed) {
    state = fixed;
  }
}

class _FixedJournalNotifier extends JournalNotifier {
  _FixedJournalNotifier(super.ref, JournalState fixed) {
    state = fixed;
  }
}

Future<void> _settle(WidgetTester t) async {
  for (var i = 0; i < 10; i++) {
    await t.pump(const Duration(milliseconds: 50));
  }
}

void main() {
  testWidgets(
      'CR232 round 2 (MAJOR-1): a notification-opened page still shows '
      'HexBottomNav and TickerTape', (t) async {
    t.view.physicalSize = const Size(390, 844);
    t.view.devicePixelRatio = 1.0;
    addTearDown(t.view.reset);

    final fakeNotifications = _FakeNotificationService();
    addTearDown(fakeNotifications._openedController.close);
    addTearDown(fakeNotifications._foregroundController.close);

    await t.pumpWidget(
      ProviderScope(
        overrides: [
          apiClientProvider.overrideWithValue(_FakeApiClient()),
          notificationServiceProvider.overrideWithValue(fakeNotifications),
          simNotifierProvider.overrideWith((ref) => _FixedSimNotifier(
                ref,
                SimState(
                  portfolio: SimPortfolio(
                    userId: 'u1',
                    portfolioId: 'p1',
                    startingCapital: 100000,
                    currentCash: 100000,
                    holdings: const [],
                    totalValue: 100000,
                    drawdownPct: 0.0,
                    priceSource: 'yahoo',
                  ),
                  trades: const [],
                ),
              )),
          watchlistNotifierProvider.overrideWith(
              (ref) => _FixedWatchlistNotifier(ref, const WatchlistState())),
          journalNotifierProvider.overrideWith(
              (ref) => _FixedJournalNotifier(ref, const JournalState())),
          alpacaLinkedProvider.overrideWith((ref) async => false),
        ],
        // The real production shape (app.dart's `_AuthGate`, `startOnFloor`
        // branch): `MaterialApp(navigatorKey: appNavigatorKey, ...)` wrapping
        // `PushNotificationListener` wrapping `BugResolutionToasts` wrapping
        // `HomeShell`. `navigatorKey: appNavigatorKey` matters here — without
        // it this harness's root navigator is a DIFFERENT, unnamed one than
        // production's, which would make a regression to the old
        // `appNavigatorKey`-push defect invisible to this test (confirmed:
        // the mutation-kill check for this test needed this wired to catch
        // the reintroduced defect at all). Built directly rather than
        // through `AmiTradeApp` + the auth/version gates, which need their
        // own network-backed bootstrap — irrelevant to what this test checks
        // and already exercised elsewhere.
        child: MaterialApp(
          navigatorKey: appNavigatorKey,
          localizationsDelegates: AppLocalizations.localizationsDelegates,
          supportedLocales: AppLocalizations.supportedLocales,
          home: const PushNotificationListener(
            child: BugResolutionToasts(child: HomeShell()),
          ),
        ),
      ),
    );
    await t.pump();
    await _settle(t);

    expect(find.byType(HexBottomNav), findsOneWidget,
        reason: 'the chrome must be showing before the tap — otherwise the '
            'rest of this test is vacuous');
    expect(find.byType(TickerTape), findsOneWidget);
    expect(find.byType(TickerDetailScreen), findsNothing,
        reason: 'the ticker page must not exist yet — otherwise the pushed '
            'assertion below is vacuous');

    // The tap itself — mirrors `_openedSub` in push_notification_listener.dart
    // listening to `service.notificationOpened()`.
    fakeNotifications.simulateTap(
      const DeepLink(route: 'open_holding_detail', params: {'ticker': 'AAPL'}),
    );
    await _settle(t);

    expect(find.byType(TickerDetailScreen), findsOneWidget,
        reason: 'the push must have landed on a real pushed page — '
            'otherwise the chrome assertions below are vacuous');
    // `find.byType` alone is NOT the MAJOR-1 assertion: `HexBottomNav` stays
    // in the Element tree either way (an `IndexedStack` never unmounts its
    // panes, pushed-on-top or not), and `getTopLeft` is equally useless here
    // — a widget's LAYOUT position is unaffected by something else in a
    // DIFFERENT subtree painting over it, so both a correct push and the
    // root-navigator defect report the identical `dy`. The only assertion
    // that actually distinguishes "pushed inside the tab, below the chrome"
    // from "pushed on the root navigator, covering the chrome entirely" is
    // WHERE in the tree the pushed page landed: a correct push nests
    // `TickerDetailScreen` inside `HomeShell` (specifically inside the tab's
    // own `_TabNavigator`, itself inside `HomeShell`'s `IndexedStack`); the
    // MAJOR-1 defect pushes it on `appNavigatorKey`'s navigator, which sits
    // ABOVE `HomeShell` — an ANCESTOR-level sibling, not a descendant. This
    // is what actually failed the mutation-kill check below before this
    // assertion replaced a positional one that didn't.
    expect(
        find.descendant(
            of: find.byType(HomeShell),
            matching: find.byType(TickerDetailScreen)),
        findsOneWidget,
        reason: 'CR232 round 2 (MAJOR-1): the pushed page must be a '
            "descendant of HomeShell (i.e. inside the active tab's own "
            'nested Navigator) — before the fix it pushed on the ROOT '
            "navigator instead, landing as HomeShell's own ANCESTOR and "
            "covering the chrome entirely, which `find.byType` alone "
            'cannot tell apart from a correct push');
    expect(find.byType(HexBottomNav), findsOneWidget,
        reason: 'CR232 round 2 (MAJOR-1): the bottom nav must still be in '
            'the tree');
    expect(find.byType(TickerTape), findsOneWidget,
        reason: 'CR232 round 2 (MAJOR-1): the ticker tape is part of the '
            'same persistent chrome as the bottom nav');
  });
}
