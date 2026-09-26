/// DEF446 — the onboarding error screen must not claim "can't reach the
/// backend" over a request that reached the backend and was rejected.
///
/// Live-reported 2026-09-26: a new user in Saudi Arabia (routed through
/// Cloudflare's `ruh02` PoP, confirmed in the tunnel logs — not the
/// unrelated APAC subsea-cable incident) hit a `409 Conflict` on
/// `POST /v1/onboarding/answer`, most likely a double-tap or a resumed
/// session, while the backend, Postgres, the LLM gateway, and the
/// Cloudflare tunnel all measured healthy at that exact moment. The screen
/// showed the cloud-off icon and "CAN'T REACH THE BACKEND" regardless —
/// `_ErrorView` paired a static connectivity title with `friendlyError`'s
/// honestly-different body text ("that request wasn't accepted…"),
/// contradicting itself in the same box. This pins that the title now
/// follows the same classification the body already uses.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/screens/onboarding/onboarding_screen.dart';
import 'package:ami_trade/services/api/api_client.dart';
import 'package:ami_trade/state/onboarding_providers.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

class _ErroredOnboarding extends OnboardingNotifier {
  _ErroredOnboarding(String message, bool isConnectivity)
      : super(ApiClient(baseUrl: 'http://unused.invalid')) {
    state = OnboardingState(
      phase: OnboardingPhase.error,
      errorMessage: message,
      errorIsConnectivity: isConnectivity,
    );
  }

  // The screen's initState calls start() on every mount, and `error` is the
  // one phase that does NOT hit start()'s "already in progress" guard (it is
  // meant to let a real retry fire). Overridden here to a no-op so the fixed
  // error state this test pins is not immediately raced by a real network
  // call against 'http://unused.invalid'.
  @override
  Future<void> start({required String locale, required String timezone}) async {}
}

Future<void> _pump(WidgetTester t, String message, bool isConnectivity) async {
  await t.binding.setSurfaceSize(const Size(390, 720));
  addTearDown(() => t.binding.setSurfaceSize(null));

  await t.pumpWidget(ProviderScope(
    overrides: [
      onboardingNotifierProvider
          .overrideWith((ref) => _ErroredOnboarding(message, isConnectivity)),
    ],
    child: MaterialApp(
      localizationsDelegates: AppLocalizations.localizationsDelegates,
      supportedLocales: AppLocalizations.supportedLocales,
      home: const OnboardingScreen(),
    ),
  ));
  await t.pump();
}

void main() {
  testWidgets(
      'a rejected request (409-shaped) shows "request not accepted", '
      'not "can\'t reach the backend"', (t) async {
    await _pump(
      t,
      "Couldn't send your answer — that request wasn't accepted. Check "
          'the details before trying again.',
      false,
    );

    expect(find.text('REQUEST NOT ACCEPTED'), findsOneWidget);
    expect(find.text("CAN'T REACH THE BACKEND"), findsNothing);
    expect(find.byIcon(Icons.cloud_off), findsNothing);
  });

  testWidgets('a genuine connectivity failure still shows the cloud-off copy',
      (t) async {
    await _pump(
      t,
      "Couldn't send your answer — couldn't reach the server. Check your "
          'connection and try again.',
      true,
    );

    expect(find.text("CAN'T REACH THE BACKEND"), findsOneWidget);
    expect(find.text('REQUEST NOT ACCEPTED'), findsNothing);
    expect(find.byIcon(Icons.cloud_off), findsOneWidget);
  });
}
