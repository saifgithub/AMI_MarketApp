/// DEF346 — the Concierge composer's send arrow must expose an accessibility
/// label. Before the fix it was a bare `IconButton(Icons.arrow_upward)`:
/// VoiceOver announced "button" with no name, and the CR163 crawler skipped
/// the control because an unlabelled control cannot be proven safe to tap.
/// The label and the visual tooltip must come from the same l10n key, so the
/// assertions here resolve the expected text through AppLocalizations rather
/// than hardcoding copy.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/screens/onboarding/onboarding_screen.dart';
import 'package:ami_trade/services/api/api_client.dart';
import 'package:ami_trade/state/onboarding_providers.dart';
import 'package:ami_trade/widgets/chat/chat_bubble.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

/// Seeds `inConversation` so the composer renders. The inherited `start()`
/// hits its "already in progress" guard and returns without any network call.
class _FixedOnboarding extends OnboardingNotifier {
  _FixedOnboarding() : super(ApiClient(baseUrl: 'http://unused.invalid')) {
    state = const OnboardingState(
      phase: OnboardingPhase.inConversation,
      sessionId: 'test-session',
      lines: [
        ChatLine(id: 'l1', author: ChatAuthor.concierge, content: 'Hello'),
      ],
    );
  }
}

Future<void> _pump(WidgetTester t) async {
  await t.binding.setSurfaceSize(const Size(390, 720));
  addTearDown(() => t.binding.setSurfaceSize(null));

  await t.pumpWidget(ProviderScope(
    overrides: [
      onboardingNotifierProvider.overrideWith((ref) => _FixedOnboarding()),
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
  testWidgets('composer send button exposes the l10n semantics label',
      (tester) async {
    final semantics = tester.ensureSemantics();

    await _pump(tester);
    final l = await AppLocalizations.delegate.load(const Locale('en'));

    expect(find.bySemanticsLabel(l.onboardingSendAnswerTooltip),
        findsOneWidget);

    semantics.dispose();
  });

  testWidgets('send label is the tooltip — one key drives both',
      (tester) async {
    await _pump(tester);
    final l = await AppLocalizations.delegate.load(const Locale('en'));

    final button = tester.widget<IconButton>(find.byType(IconButton));
    expect(button.tooltip, l.onboardingSendAnswerTooltip);
  });
}
