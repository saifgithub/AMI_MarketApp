/// DEF342 — Brief Your Agent's bottom controls must clear the Android
/// system nav.
///
/// Field screenshot (0.1.0+77, android_gms): the TRADER — PROPOSAL view's
/// Accept/Reject row and the composer under it sat behind the system
/// navigation bar. The screen's top-level SafeArea reads MediaQuery.padding,
/// and under Android edge-to-edge that channel reported zero while
/// viewPadding still carried the nav-bar inset — so this harness simulates
/// exactly that split (viewPadding.bottom = 48, padding = 0) and pins that
/// every bottom-anchored control still clears the 48pt nav band.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/agent.dart';
import 'package:ami_trade/models/brief.dart';
import 'package:ami_trade/models/one_on_one.dart';
import 'package:ami_trade/screens/agent/brief_screen.dart';
import 'package:ami_trade/state/brief_providers.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

/// Pre-seeded to a live session with a pending proposal; every network entry
/// point is a no-op so the provider's own `openSession()` microtask cannot
/// touch the API from a test.
class _FixedBriefNotifier extends BriefNotifier {
  _FixedBriefNotifier(super.ref, super.agentId) {
    state = BriefState(
      session: const BriefSession(
        id: 's1',
        userId: 'u1',
        agentId: 'trader',
        mode: 'from_scratch',
        locale: 'en',
        baseOverlayVersion: 0,
      ),
      messages: const [
        ChatMessage(role: 'assistant', content: 'What should change?'),
        ChatMessage(role: 'user', content: 'Be more patient on entries.'),
      ],
      pendingProposal: const BriefProposal(
        id: 'p1',
        sessionId: 's1',
        plainEnglish: 'Wait for confirmation before entering.',
        overlayAddition: 'Prefer confirmed breakouts over anticipation.',
        fullOverlayPreview: 'Prefer confirmed breakouts over anticipation.',
        refused: false,
      ),
    );
  }

  @override
  Future<void> openSession({String locale = 'en'}) async {}

  @override
  Future<void> loadHistory() async {}
}

void main() {
  testWidgets(
      'proposal actions and composer clear a 48pt bottom viewPadding '
      'even when the padding channel reports zero', (tester) async {
    tester.view.physicalSize = const Size(390, 844);
    tester.view.devicePixelRatio = 1.0;
    // The Android edge-to-edge split from the field report: the nav bar is
    // present in viewPadding but absent from padding, so SafeArea alone
    // protects nothing.
    tester.view.viewPadding = const FakeViewPadding(bottom: 48);
    tester.view.padding = FakeViewPadding.zero;
    addTearDown(tester.view.reset);

    final agent = agentById('trader');
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          briefNotifierProvider.overrideWith(
              (ref, agentId) => _FixedBriefNotifier(ref, agentId)),
        ],
        child: MaterialApp(
          localizationsDelegates: AppLocalizations.localizationsDelegates,
          supportedLocales: AppLocalizations.supportedLocales,
          home: BriefScreen(agent: agent),
        ),
      ),
    );
    await tester.pump();

    const navTop = 844.0 - 48.0;
    // The composer is the bottom-most control on every state of this screen;
    // if it clears the nav band, everything stacked above it does too.
    expect(tester.getRect(find.byType(TextField)).bottom,
        lessThanOrEqualTo(navTop),
        reason: 'composer sits behind the system nav');
    // And the reported subject itself: the proposal's action row.
    for (final button in [
      find.byType(ElevatedButton), // Accept
      find.byType(OutlinedButton), // Refine
      find.byType(TextButton), // Reject
    ]) {
      expect(tester.getRect(button).bottom, lessThanOrEqualTo(navTop),
          reason: 'proposal action behind the system nav');
    }
    expect(tester.takeException(), isNull);
  });
}
