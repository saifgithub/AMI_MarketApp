// DEF476 (second occurrence of the DEF190 class) — failure_patterns.md P40.
//
// A button that means "go to Lessons" used to `Navigator.push(LessonsScreen)`
// onto the Floor tab's navigator: the nav bar stayed on FLOOR, tapping LESSONS
// then showed a different stack, and the user had two Lessons screens. The
// shell already offers the right move — write `activeTabProvider` — and
// `portfolio_screen.dart` / `home_shell.dart` use it.
//
// Structural guard: no source file may push a `LessonsScreen` route. The
// Lessons tab root is constructed once, in `home_shell.dart`, as a tab body
// (not a push). A deliberate exception is added to the allowlist below, by
// name, in the commit that adds it.

import 'dart:io';

import 'package:ami_trade/features/nav/ami_tab.dart';
import 'package:ami_trade/features/tour/tour_providers.dart';
import 'package:ami_trade/screens/floor/your_firm_screen.dart';
import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/agent.dart';
import 'package:ami_trade/screens/lessons/lessons_screen.dart';
import 'package:ami_trade/state/lessons_providers.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

const _allowedPushFiles = <String>{};

final _pushesLessons = RegExp(
  r'\.push(?:Replacement)?\s*(?:<[^>]*>)?\(\s*(?:const\s+)?'
  r'(?:MaterialPageRoute|CupertinoPageRoute)[^;]*?(?<![A-Za-z])LessonsScreen\s*\(',
  dotAll: true,
);

class _IdleLessonsNotifier extends LessonsNotifier {
  _IdleLessonsNotifier(super.ref);

  @override
  Future<void> refresh() async {}
}

void main() {
  test('no screen pushes LessonsScreen; they switch to the LESSONS tab', () {
    final offenders = <String>[];
    for (final f in Directory('lib')
        .listSync(recursive: true)
        .whereType<File>()
        .where((f) => f.path.endsWith('.dart'))) {
      final rel = f.path.replaceAll('\\', '/');
      if (rel.contains('/generated/') || _allowedPushFiles.contains(rel)) {
        continue;
      }
      if (_pushesLessons.hasMatch(f.readAsStringSync())) offenders.add(rel);
    }
    expect(offenders, isEmpty,
        reason: 'set activeTabProvider = AmiTab.lessons instead of pushing a '
            'second LessonsScreen over the Floor tab (DEF476 / P40)');
  });

  test('the allowlist is empty and can only stay that way unnoticed', () {
    expect(_allowedPushFiles, isEmpty);
  });

  testWidgets('locked-agent sheet GO TO LESSONS switches the tab, pushes nothing',
      (tester) async {
    final container = ProviderContainer(overrides: [
      lessonsNotifierProvider
          .overrideWith((ref) => _IdleLessonsNotifier(ref)),
    ]);
    addTearDown(container.dispose);

    await tester.pumpWidget(UncontrolledProviderScope(
      container: container,
      child: MaterialApp(
        localizationsDelegates: AppLocalizations.localizationsDelegates,
        supportedLocales: AppLocalizations.supportedLocales,
        home: Scaffold(
          body: Consumer(
            builder: (context, ref, _) => ElevatedButton(
              onPressed: () =>
                  showLockedSheet(context, ref, agentById('concierge')),
              child: const Text('open'),
            ),
          ),
        ),
      ),
    ));
    await tester.tap(find.text('open'));
    await tester.pumpAndSettle();

    await tester.ensureVisible(find.text('GO TO LESSONS'));
    await tester.tap(find.text('GO TO LESSONS'));
    await tester.pumpAndSettle();

    expect(container.read(activeTabProvider), AmiTab.lessons);
    expect(find.byType(LessonsScreen), findsNothing,
        reason: 'a pushed LessonsScreen leaves the nav bar on FLOOR');
  });
}
