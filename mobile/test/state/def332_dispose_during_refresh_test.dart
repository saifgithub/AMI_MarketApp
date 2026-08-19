/// DEF332 — a notifier refreshed with `unawaited(...)` writes `state` after the
/// container that owns it is gone.
///
/// `SimNotifier.submit` deliberately does not await the journal and watchlist
/// refreshes (see the comment there: the sheet closes and neither surface is on
/// screen). That decision is right, and it means both refreshes routinely
/// outlive whatever disposed the container — a user navigating away mid-trade,
/// or a test's `addTearDown`. Every `state =` after an `await` therefore lands
/// on a possibly-disposed notifier and throws
/// `Bad state: Tried to use <Notifier> after \`dispose\` was called`.
///
/// It surfaced as an intermittent red in the full Flutter suite while CR195 was
/// wiring `flutter test` in as a release gate: `def315_submit_window_test.dart`
/// failed 3 times in ~14 runs and passed 3/3 in isolation, because the flake is
/// a race between the unawaited fan-out and tearDown — not anything that file
/// does. A blocking release gate that reds for reasons unrelated to the change
/// is the habit DEF277 is about, so the gate could not ship over it.
///
/// These tests dispose the container WHILE a refresh is in flight and assert
/// the future completes quietly. Without the `mounted` guards they throw.
///
/// WHAT THE MUTATIONS ACTUALLY SHOWED — recorded because one of them did NOT
/// behave the way the fix's author expected (P24: report the run, not the
/// intention):
///
///   * Removing the **error-path** guard reds
///     `and so does one that outlives its container and then fails`, and only
///     that. It is the load-bearing guard.
///   * Removing the **success-path** guard alone changes nothing — all three
///     still pass. The reason is structural: a `state =` inside the `try` that
///     throws is caught by the notifier's own `catch (e)`, which then takes the
///     error path, which is guarded, so the future still completes. The
///     success-path guard is therefore NOT independently observable from
///     outside.
///
/// It is kept anyway, and not as decoration: without it every disposed refresh
/// raises and swallows an exception, `friendlyError` runs on a disposal that is
/// not an error, and the whole thing depends on that `catch` staying broad. The
/// day someone narrows it to the API exceptions it is actually meant for — a
/// reasonable change — the swallowed `Bad state` becomes an unhandled throw
/// again. Guarding the write is what makes that refactor safe; the test suite
/// cannot see the difference today, and saying so here is cheaper than letting
/// a future reader infer coverage that does not exist.
library;

import 'dart:async';

import 'package:ami_trade/models/watchlist.dart';
import 'package:ami_trade/services/api/api_client.dart';
import 'package:ami_trade/state/onboarding_providers.dart';
import 'package:ami_trade/state/watchlist_providers.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

/// Holds the response open until the test releases it, so "disposed while in
/// flight" is deterministic rather than a sleep race.
class _HeldApi extends ApiClient {
  _HeldApi() : super(baseUrl: 'test://localhost');

  final Completer<void> release = Completer<void>();
  final Completer<void> entered = Completer<void>();

  @override
  Future<List<WatchlistEntry>> watchlistList(String userId) async {
    if (!entered.isCompleted) entered.complete();
    await release.future;
    return const [];
  }
}

/// Same, but the call fails — the error path writes `state` too, and a disposed
/// notifier cannot report an error any more than it can report success.
class _HeldFailingApi extends ApiClient {
  _HeldFailingApi() : super(baseUrl: 'test://localhost');

  final Completer<void> release = Completer<void>();
  final Completer<void> entered = Completer<void>();

  @override
  Future<List<WatchlistEntry>> watchlistList(String userId) async {
    if (!entered.isCompleted) entered.complete();
    await release.future;
    throw StateError('server said no');
  }
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  setUp(() => SharedPreferences.setMockInitialValues({}));

  test('a refresh that outlives its container completes quietly', () async {
    final api = _HeldApi();
    final container = ProviderContainer(
      overrides: [apiClientProvider.overrideWithValue(api)],
    );

    final inFlight = container.read(watchlistNotifierProvider.notifier).refresh();
    await api.entered.future; // the request is genuinely open
    container.dispose(); // the user left the screen
    api.release.complete(); // now the response lands

    await expectLater(inFlight, completes);
  });

  test('and so does one that outlives its container and then fails', () async {
    final api = _HeldFailingApi();
    final container = ProviderContainer(
      overrides: [apiClientProvider.overrideWithValue(api)],
    );

    final inFlight = container.read(watchlistNotifierProvider.notifier).refresh();
    await api.entered.future;
    container.dispose();
    api.release.complete();

    await expectLater(inFlight, completes);
  });

  test('the guard is not swallowing the normal path', () async {
    // Non-vacuity: `if (!mounted) return` must skip the write only when the
    // notifier really is disposed. An undisposed refresh still lands.
    final api = _HeldApi();
    final container = ProviderContainer(
      overrides: [apiClientProvider.overrideWithValue(api)],
    );
    addTearDown(container.dispose);

    final inFlight = container.read(watchlistNotifierProvider.notifier).refresh();
    await api.entered.future;
    api.release.complete();
    await inFlight;

    expect(container.read(watchlistNotifierProvider).loading, isFalse);
  });
}
