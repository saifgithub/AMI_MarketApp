/// DEF336 — DEF332's guards could not cover a notifier the fan-out CREATES.
///
/// DEF332 put `mounted` guards on the three notifiers `SimNotifier.submit`
/// refreshes unawaited (Sim, Watchlist, Journal). But `JournalNotifier.refresh`
/// also READS `mandateNotifierProvider`, which lazily creates a
/// `MandateNotifier` — and that provider schedules its own first `refresh()`
/// via `Future.microtask`. So the fan-out can mint a brand-new notifier whose
/// refresh runs strictly after the container is disposed, and no guard on the
/// three fan-out notifiers can reach it.
///
/// It surfaced exactly the way DEF332 did: `def315_submit_window_test.dart`
/// red in a full-suite run ("This test failed after it had already
/// completed" — an unhandled microtask throw landing after the test's own
/// assertions), green in isolation, with the trace ending at
/// `MandateNotifier.refresh` → `Bad state: Tried to use MandateNotifier after
/// `dispose` was called`. Caught by the CR195 release gate's own suite run —
/// the gate is blocking, so this flake could not be left in it (DEF277).
///
/// The first test is the trace's exact shape: create, dispose, then let the
/// creation microtask fire. The second holds a failing request open across
/// disposal — DEF332's mutations showed the ERROR-path guard is the
/// load-bearing one (a throwing `state =` inside `try` is caught by the
/// notifier's own broad `catch`, so only the error path is independently
/// observable). The third is the vacuity check: with the container alive, the
/// error write still happens, so the guards are not swallowing real work.
library;

import 'dart:async';

import 'package:ami_trade/models/mandate.dart';
import 'package:ami_trade/services/api/api_client.dart';
import 'package:ami_trade/state/mandate_providers.dart';
import 'package:ami_trade/state/onboarding_providers.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

/// Fails after the test releases it, so "disposed while in flight" is
/// deterministic. A failing variant only: the success path needs a real
/// `UserMandate` and, per DEF332's recorded mutation result, is not
/// independently observable anyway — the error path is the one that throws.
class _HeldFailingApi extends ApiClient {
  _HeldFailingApi() : super(baseUrl: 'test://localhost');

  final Completer<void> release = Completer<void>();
  final Completer<void> entered = Completer<void>();

  @override
  Future<UserMandate> getMandate(String userId) async {
    if (!entered.isCompleted) entered.complete();
    await release.future;
    throw StateError('server said no');
  }
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  setUp(() => SharedPreferences.setMockInitialValues({}));

  test('the creation microtask outliving the container completes quietly',
      () async {
    final api = _HeldFailingApi();
    final container = ProviderContainer(
      overrides: [apiClientProvider.overrideWithValue(api)],
    );

    // Reading the notifier is all it takes: the provider schedules
    // `n.refresh` on a microtask that has not run yet…
    container.read(mandateNotifierProvider.notifier);
    // …and by the time it does, the container is gone. Without the entry
    // guard the very first `state =` throws into the microtask queue, which
    // is precisely the unhandled error that failed def315's test AFTER it
    // had completed.
    container.dispose();
    await Future<void>.microtask(() {});
    await Future<void>.delayed(Duration.zero);
  });

  test('a refresh that outlives its container and then fails stays quiet',
      () async {
    final api = _HeldFailingApi();
    final container = ProviderContainer(
      overrides: [apiClientProvider.overrideWithValue(api)],
    );

    final inFlight =
        container.read(mandateNotifierProvider.notifier).refresh();
    await api.entered.future; // the request is genuinely open
    container.dispose(); // the user left the screen
    api.release.complete(); // now the failure lands

    await expectLater(inFlight, completes);
  });

  test('the guard is not swallowing the normal error path', () async {
    final api = _HeldFailingApi();
    final container = ProviderContainer(
      overrides: [apiClientProvider.overrideWithValue(api)],
    );
    addTearDown(container.dispose);

    final notifier = container.read(mandateNotifierProvider.notifier);
    final inFlight = notifier.refresh();
    await api.entered.future;
    api.release.complete(); // container still alive — the write must happen
    await inFlight;

    expect(container.read(mandateNotifierProvider).error, isNotNull,
        reason: 'a live notifier still reports the failure to the user');
  });
}
