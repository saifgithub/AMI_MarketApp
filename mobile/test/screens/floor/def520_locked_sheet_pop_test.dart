/// DEF520 — the locked-agent sheet pops its own route, inside a nested Navigator.
///
/// `showLockedSheet` (your_firm_screen.dart) is the one dialog/sheet site the
/// DEF520 sweep found popping with the OUTER page's context rather than the
/// builder's. It opens with `useRootNavigator: false`, so the outer context
/// resolved to the same Navigator and the pop happened to work; the site is
/// moved onto the builder's own context so it cannot depend on that. The
/// harness is the DEF519 shape: the page lives in a nested Navigator under
/// MaterialApp, as every home tab does (home_shell.dart).
library;

import 'package:ami_trade/features/nav/ami_tab.dart';
import 'package:ami_trade/features/tour/tour_providers.dart';
import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/agent.dart';
import 'package:ami_trade/models/lessons.dart';
import 'package:ami_trade/screens/floor/your_firm_screen.dart';
import 'package:ami_trade/state/lessons_providers.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

class _Lessons extends LessonsNotifier {
  _Lessons(super.ref, AgentUnlockRequirement req) {
    state = LessonsState(unlockRequirements: {req.agentId: req});
  }
  @override
  Future<void> refresh() async {}
}

Future<ProviderContainer> _pump(WidgetTester t) async {
  t.view.physicalSize = const Size(390, 844);
  t.view.devicePixelRatio = 1.0;
  addTearDown(t.view.reset);
  final agent = agentById('fundamentals_analyst');
  final req = AgentUnlockRequirement(
    agentId: agent.id,
    unlocked: false,
    required_: const [
      GatewayLessonStatus(
          lessonId: 'L1', code: 'F-01', title: 'First lesson', track: 'foundations', passed: false),
    ],
    passedCount: 0,
    remainingCount: 1,
  );
  final container = ProviderContainer(overrides: [
    lessonsNotifierProvider.overrideWith((ref) => _Lessons(ref, req)),
  ]);
  addTearDown(container.dispose);
  await t.pumpWidget(UncontrolledProviderScope(
    container: container,
    child: MaterialApp(
      localizationsDelegates: AppLocalizations.localizationsDelegates,
      supportedLocales: AppLocalizations.supportedLocales,
      home: Scaffold(
        body: Navigator(
          onGenerateRoute: (_) => MaterialPageRoute<void>(
            builder: (ctx) => Consumer(
              builder: (ctx, ref, _) => Scaffold(
                body: Center(
                  child: ElevatedButton(
                    onPressed: () => showLockedSheet(ctx, ref, agent),
                    child: const Text('open sheet'),
                  ),
                ),
              ),
            ),
          ),
        ),
      ),
    ),
  ));
  await t.tap(find.text('open sheet'));
  await t.pumpAndSettle();
  expect(find.text('GO TO LESSONS'), findsOneWidget);
  return container;
}

void main() {
  testWidgets('GO TO LESSONS closes the sheet and switches tab', (t) async {
    final container = await _pump(t);

    await t.ensureVisible(find.text('GO TO LESSONS'));
    await t.tap(find.text('GO TO LESSONS'));
    await t.pumpAndSettle();

    expect(find.text('GO TO LESSONS'), findsNothing,
        reason: 'the sheet stayed on screen');
    expect(find.text('open sheet'), findsOneWidget,
        reason: 'the page under the sheet must survive');
    expect(container.read(activeTabProvider), AmiTab.lessons);
  });
}
