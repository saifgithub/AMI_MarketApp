/// CR043 — the resolution toast fires once per report and no more.
///
/// The load-bearing case is the second one: a provider rebuild must not
/// re-show a message whose ack hasn't round-tripped yet, or a user with one
/// fixed bug gets told about it repeatedly.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/feedback.dart';
import 'package:ami_trade/screens/feedback/bug_resolution_toasts.dart';
import 'package:ami_trade/state/feedback_providers.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

BugResolutionUpdate _update(String id, String title, {String? note}) =>
    BugResolutionUpdate(id: id, title: title, resolutionNote: note);

Widget _harness(List<BugResolutionUpdate> updates) {
  return ProviderScope(
    overrides: [
      feedbackUpdatesProvider.overrideWith((ref) async => updates),
    ],
    child: MaterialApp(
      localizationsDelegates: AppLocalizations.localizationsDelegates,
      supportedLocales: AppLocalizations.supportedLocales,
      home: const Scaffold(
        body: BugResolutionToasts(child: SizedBox.expand()),
      ),
    ),
  );
}

/// Pump past the settle delay, the toast's slide-in, its hold and the gap.
Future<void> _drainOne(WidgetTester t) async {
  await t.pump(const Duration(milliseconds: 1500));
  await t.pump(const Duration(milliseconds: 400));
}

void main() {
  testWidgets('a resolved report toasts the reporter with its title',
      (t) async {
    await t.pumpWidget(_harness([_update('id-1', 'Quiz has no answers')]));
    await t.pump();
    await _drainOne(t);

    expect(find.textContaining('Quiz has no answers'), findsOneWidget);
    expect(t.takeException(), isNull);

    await t.pump(const Duration(seconds: 8));
  });

  testWidgets('the resolution note is shown under the headline', (t) async {
    await t.pumpWidget(_harness([
      _update('id-1', 'Quiz has no answers',
          note: 'The quiz now accepts your answer.'),
    ]));
    await t.pump();
    await _drainOne(t);

    expect(
      find.textContaining('The quiz now accepts your answer.'),
      findsOneWidget,
    );

    await t.pump(const Duration(seconds: 8));
  });

  testWidgets('a rebuild does not re-show an already-queued report',
      (t) async {
    await t.pumpWidget(_harness([_update('id-1', 'Only once')]));
    await t.pump();
    await _drainOne(t);
    expect(find.textContaining('Only once'), findsOneWidget);

    // Force a rebuild while the first toast is still on screen. Without the
    // _seen guard this enqueues a duplicate.
    await t.pumpWidget(_harness([_update('id-1', 'Only once')]));
    await t.pump();
    await _drainOne(t);

    expect(find.textContaining('Only once'), findsOneWidget);
    await t.pump(const Duration(seconds: 12));
  });

  testWidgets('no updates means no toast', (t) async {
    await t.pumpWidget(_harness([]));
    await t.pump();
    await _drainOne(t);

    expect(find.byType(Overlay), findsWidgets);
    expect(find.textContaining('Fixed:'), findsNothing);
    expect(t.takeException(), isNull);
  });
}
