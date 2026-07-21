/// CR050 — the email 6-digit-code claim is demoted behind a "Use email
/// instead" disclosure so the primary sign-in surface stays one-tap.
///
/// The load-bearing assertion is that the email card is NOT rendered on first
/// paint (only the small disclosure link is), and that tapping the link
/// reveals it. If the card ever renders by default again, the "tighten login"
/// intent has regressed.
///
/// Note: the per-platform Apple/Google button is gated on `Platform.isIOS` /
/// `Platform.isAndroid`, which are both false on the macOS test host, so this
/// test does not assert the federated button (that's covered by on-device
/// verification). The email-disclosure branch is platform-independent.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/screens/auth/sign_in_screen.dart';
import 'package:ami_trade/state/auth_providers.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

/// Anonymous auth state with no network. The real provider factory schedules
/// `bootstrap()` (which hits /v1/auth/anon); we override the factory and
/// no-op bootstrap so nothing touches the API. `user` stays null → the screen
/// renders the anonymous claim controls.
class _StubAuthNotifier extends AuthNotifier {
  _StubAuthNotifier(Ref ref) : super(ref);

  @override
  Future<void> bootstrap() async {}
}

Widget _harness() {
  return ProviderScope(
    overrides: [
      authNotifierProvider.overrideWith((ref) => _StubAuthNotifier(ref)),
    ],
    child: const MaterialApp(
      localizationsDelegates: AppLocalizations.localizationsDelegates,
      supportedLocales: AppLocalizations.supportedLocales,
      home: SignInScreen(),
    ),
  );
}

void main() {
  testWidgets('email claim is hidden behind the disclosure by default',
      (t) async {
    await t.pumpWidget(_harness());
    await t.pump();

    // The demoted disclosure link is present...
    expect(find.text('Use email instead'), findsOneWidget);
    // ...but the email card itself is not (its header + inputs are absent).
    expect(find.text('OR CONTINUE WITH EMAIL'), findsNothing);
    expect(find.byType(TextField), findsNothing);
    expect(find.text('SEND CODE'), findsNothing);
    expect(t.takeException(), isNull);
  });

  testWidgets('tapping "Use email instead" reveals the email claim card',
      (t) async {
    await t.pumpWidget(_harness());
    await t.pump();

    await t.tap(find.text('Use email instead'));
    await t.pump();

    // The card is now shown and the disclosure link is gone.
    expect(find.text('OR CONTINUE WITH EMAIL'), findsOneWidget);
    expect(find.text('SEND CODE'), findsOneWidget);
    expect(find.text('Use email instead'), findsNothing);
    expect(t.takeException(), isNull);
  });
}
