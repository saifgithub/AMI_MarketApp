/// CR109 Amendment F — the dark-launch gate.
///
/// This test is the entire basis of the dark launch: `/games` must be
/// structurally absent from the app's route map whenever the `AMI_GAMES`
/// dart-define is off, which it is for every store binary
/// (`build_testflight.sh` / `build_playstore.sh` deliberately never pass it
/// — see `features/games/games_gate.dart`). Every test suite in this repo
/// runs with no `--dart-define`, so `kGamesEnabled` is `false` here exactly
/// as it is in a shipped build; that is what makes this assertion mean
/// anything rather than merely testing itself.
library;

import 'package:ami_trade/app.dart';
import 'package:ami_trade/features/games/games_gate.dart';
import 'package:ami_trade/models/onboarding.dart';
import 'package:ami_trade/services/api/api_client.dart';
import 'package:ami_trade/state/onboarding_providers.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

/// Same shape as `widget_test.dart`'s `_FakeApiClient` — enough canned
/// onboarding responses that `AmiTradeApp` renders without making a real
/// HTTP call. This test only inspects the static `routes:` map, so nothing
/// here needs to actually resolve.
class _FakeApiClient extends ApiClient {
  _FakeApiClient() : super(baseUrl: 'test://localhost');

  @override
  Future<StartOnboardingResponse> startOnboarding({
    required String locale,
    required String timezone,
  }) async {
    return StartOnboardingResponse(
      sessionId: 'fake-session',
      welcomeMessage: const OnboardingMessage(
        author: ChatAuthorRemote.concierge,
        content: 'Welcome (test)',
        step: 'welcome',
      ),
      firstQuestion: const OnboardingMessage(
        author: ChatAuthorRemote.concierge,
        content: 'First question (test)',
        step: 'q1_goal',
      ),
    );
  }

  @override
  Future<bool> health() async => true;
}

void main() {
  testWidgets(
    'AMI_GAMES off: /games is absent from the route map',
    (tester) async {
      // No --dart-define is ever passed to `flutter test` for this suite,
      // so this mirrors a store build exactly. If this ever reads true, the
      // dark launch is already broken before the rest of the test runs.
      expect(
        kGamesEnabled,
        isFalse,
        reason: 'this suite must run with AMI_GAMES off, the same as every '
            'store binary — a true here means the test itself is no longer '
            'proving what CR109 Amendment F requires',
      );

      await tester.pumpWidget(
        ProviderScope(
          overrides: [apiClientProvider.overrideWithValue(_FakeApiClient())],
          child: const AmiTradeApp(),
        ),
      );
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 50));

      final app = tester.widget<MaterialApp>(find.byType(MaterialApp));
      final routes = app.routes;
      expect(routes, isNotNull);

      // The rest of the map is untouched — proves this is inspecting the
      // real route table, not an empty one that would trivially lack a key.
      expect(routes!.containsKey('/onboarding'), isTrue);
      expect(routes.containsKey('/floor'), isTrue);
      expect(routes.containsKey('/dev-preview'), isTrue);

      expect(
        routes.containsKey('/games'),
        isFalse,
        reason: 'kGamesEnabled=false must const-fold the conditional entry '
            "out of the routes map entirely — the route isn't merely "
            'unregistered at runtime, it must never exist in the built app '
            '(CR109 Amendment F, CR109.md §0)',
      );
    },
  );
}
