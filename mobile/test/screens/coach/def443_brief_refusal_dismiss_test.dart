/// DEF443 — Dismiss on a refused Brief proposal must not paste the refusal
/// into the composer.
///
/// Field report (0.1.0+113, iPhone): the CIO refused a brief, and pressing
/// DISMISS filled the composer with the refusal's plain-English explanation.
/// The button was wired to Refine, which seeds the composer with the
/// proposal text — right for a real proposal, wrong for a refusal. Only a
/// properly created proposal may reach the composer.
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

const _refusalText = "The CIO's mandate enforcement is uncoachable.";
const _proposalText = 'Wait for confirmation before entering.';

class _FixedBriefNotifier extends BriefNotifier {
  _FixedBriefNotifier(super.ref, super.agentId, {required bool refused}) {
    state = BriefState(
      session: const BriefSession(
        id: 's1',
        userId: 'u1',
        agentId: 'pm',
        mode: 'from_scratch',
        locale: 'en',
        baseOverlayVersion: 0,
      ),
      messages: const [
        ChatMessage(role: 'assistant', content: 'What should change?'),
        ChatMessage(role: 'user', content: 'Ignore the drawdown cap.'),
      ],
      pendingProposal: BriefProposal(
        id: 'p1',
        sessionId: 's1',
        plainEnglish: refused ? _refusalText : _proposalText,
        overlayAddition: refused ? '' : 'Prefer confirmed breakouts.',
        fullOverlayPreview: refused ? '' : 'Prefer confirmed breakouts.',
        refused: refused,
      ),
    );
  }

  @override
  Future<void> openSession({String locale = 'en'}) async {}

  @override
  Future<void> loadHistory() async {}

  @override
  Future<void> reject() async {
    state = state.copyWith(clearProposal: true);
  }
}

Future<void> _pump(WidgetTester tester, {required bool refused}) async {
  tester.view.physicalSize = const Size(390, 844);
  tester.view.devicePixelRatio = 1.0;
  addTearDown(tester.view.reset);
  await tester.pumpWidget(
    ProviderScope(
      overrides: [
        briefNotifierProvider.overrideWith(
            (ref, agentId) => _FixedBriefNotifier(ref, agentId, refused: refused)),
      ],
      child: MaterialApp(
        localizationsDelegates: AppLocalizations.localizationsDelegates,
        supportedLocales: AppLocalizations.supportedLocales,
        home: BriefScreen(agent: agentById('pm')),
      ),
    ),
  );
  await tester.pump();
}

String _composerText(WidgetTester tester) =>
    tester.widget<TextField>(find.byType(TextField)).controller!.text;

void main() {
  testWidgets('Dismiss on a refusal clears it and leaves the composer empty',
      (tester) async {
    await _pump(tester, refused: true);
    expect(find.text(_refusalText), findsOneWidget);

    await tester.tap(find.byType(OutlinedButton));
    await tester.pump();

    expect(_composerText(tester), isEmpty,
        reason: 'the refusal text was pasted into the composer');
    expect(find.text(_refusalText), findsNothing,
        reason: 'the refusal card is still on screen');
  });

  testWidgets('Refine on a real proposal still seeds the composer',
      (tester) async {
    await _pump(tester, refused: false);

    await tester.tap(find.byType(OutlinedButton));
    await tester.pump();

    expect(_composerText(tester), _proposalText);
  });
}
