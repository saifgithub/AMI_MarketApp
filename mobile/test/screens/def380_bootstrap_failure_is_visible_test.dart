/// DEF380 — the app's first screen must not show a failed bootstrap as a
/// loading spinner.
///
/// `_AuthGate` renders on `auth.token == null`, and until this defect it
/// rendered the brand `HexPulseLoader` for that whole branch — including the
/// case its own comment named, "or errored". `bootstrapAnon` sets
/// `AuthState.error` and clears `loading` when the call throws, so the two
/// states were distinguishable in the data and identical on screen. Measured
/// in the iOS simulator against a flaky Cloudflare path:
/// `ServerUnavailableException(status: 502)` in the log and 60s+ on the
/// animating hexagon, with no message and no way forward.
///
/// The assertions are a PAIR, deliberately. "The error text is somewhere on
/// screen" would still pass with the spinner underneath it, and the spinner is
/// the actual defect — a user cannot tell an unreachable backend from a slow
/// one. So this asserts the loader is GONE as well as that the message and the
/// retry control are present, and the companion test asserts the loader is
/// still what an in-flight bootstrap shows, so the fix cannot be "delete the
/// splash".
library;

import 'package:ami_trade/app.dart';
import 'package:ami_trade/state/auth_providers.dart';
import 'package:ami_trade/widgets/hex/hex_pulse_loader.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

/// No network. `bootstrap()` is overridden to a no-op so the real
/// `/v1/auth/anon` call never fires; the state under test is injected instead.
class _StubAuthNotifier extends AuthNotifier {
  _StubAuthNotifier(Ref ref, AuthState initial) : super(ref) {
    state = initial;
  }

  int bootstrapCalls = 0;

  @override
  Future<void> bootstrap() async {
    bootstrapCalls++;
  }
}

/// Riverpod builds a provider lazily, so the stub does not exist until the
/// first `pumpWidget`. The box hands the test a handle it can read AFTER that,
/// rather than a `late` local that throws on the pump-only cases.
class _Box {
  _StubAuthNotifier? notifier;
}

(Widget, _Box) _harness(AuthState initial) {
  final box = _Box();
  final widget = ProviderScope(
    overrides: [
      authNotifierProvider.overrideWith((ref) {
        final n = _StubAuthNotifier(ref, initial);
        box.notifier = n;
        return n;
      }),
    ],
    child: const AmiTradeApp(),
  );
  return (widget, box);
}

void main() {
  testWidgets('a failed bootstrap renders the failure, not the splash',
      (t) async {
    final (widget, _) = _harness(
      const AuthState(loading: false, error: 'AMI is unreachable right now.'),
    );
    await t.pumpWidget(widget);
    await t.pump();

    expect(find.text('AMI is unreachable right now.'), findsOneWidget);
    expect(find.text('AMI couldn\'t be reached'), findsOneWidget);
    expect(find.text('TRY AGAIN'), findsOneWidget);
    // The load-bearing half: the spinner must be gone, not merely accompanied.
    expect(find.byType(HexPulseLoader), findsNothing);
  });

  testWidgets('the retry control re-runs the bootstrap', (t) async {
    final (widget, box) = _harness(
      const AuthState(loading: false, error: 'AMI is unreachable right now.'),
    );
    await t.pumpWidget(widget);
    await t.pump();

    expect(box.notifier!.bootstrapCalls, 0);
    await t.tap(find.text('TRY AGAIN'));
    await t.pump();
    expect(box.notifier!.bootstrapCalls, 1);
  });

  testWidgets('an in-flight bootstrap still shows the splash', (t) async {
    final (widget, _) = _harness(const AuthState(loading: true));
    await t.pumpWidget(widget);
    await t.pump();

    expect(find.byType(HexPulseLoader), findsOneWidget);
    expect(find.text('TRY AGAIN'), findsNothing);
  });

  testWidgets('a retry in flight shows the splash, not the stale error',
      (t) async {
    // The state immediately after TRY AGAIN: `bootstrap()` sets `loading` and
    // the PREVIOUS error is still on the state until the call resolves. Without
    // the `!auth.loading` half of the condition the user taps retry and nothing
    // visibly happens — the same failure message just stays put, which reads as
    // a dead button. This case is the reason the condition has two halves, and
    // it is asserted because dropping that half passed every other test here.
    final (widget, _) = _harness(
      const AuthState(loading: true, error: 'AMI is unreachable right now.'),
    );
    await t.pumpWidget(widget);
    await t.pump();

    expect(find.byType(HexPulseLoader), findsOneWidget);
    expect(find.text('AMI is unreachable right now.'), findsNothing);
    expect(find.text('TRY AGAIN'), findsNothing);
  });

  testWidgets('a bootstrap that has not started yet still shows the splash',
      (t) async {
    // `error == null && loading == false` is the pre-launch tick, before
    // `Future.microtask(bootstrap)` has run. Showing a failure here would be
    // the opposite defect: an error dressed as a fact nobody measured.
    final (widget, _) = _harness(const AuthState());
    await t.pumpWidget(widget);
    await t.pump();

    expect(find.byType(HexPulseLoader), findsOneWidget);
    expect(find.text('TRY AGAIN'), findsNothing);
  });
}
