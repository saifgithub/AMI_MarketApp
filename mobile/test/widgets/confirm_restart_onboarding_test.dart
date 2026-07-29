/// DEF152 — "restart onboarding" wiped the mandate on one tap, no dialog, no
/// undo, from a caption-sized link sitting a short scroll under the Convene
/// CTA. A tester hit it by accident and had to redo the whole interview.
///
/// Two halves, and they fail differently:
///
/// 1. **The dialog behaves.** Cancel and dismissal must be indistinguishable
///    from "no" — `showDialog` resolves `null` for a barrier tap and a back
///    gesture, and a guard that treats `null` as consent is worse than none.
/// 2. **The call site still uses it.** A dialog nothing calls is not a guard.
///    That tie is exactly what nothing in the type system holds, so it is
///    asserted here against the source, the same shape as DEF151's
///    cross-language contract test.
library;

import 'dart:io';

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/widgets/confirm_restart_onboarding.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

/// Drives the dialog from a real button press so the `BuildContext` is a
/// descendant of `Navigator`, as it is on the Floor.
Widget _harness(void Function(bool) onResult) {
  return MaterialApp(
    localizationsDelegates: AppLocalizations.localizationsDelegates,
    supportedLocales: AppLocalizations.supportedLocales,
    home: Scaffold(
      body: Builder(
        builder: (context) => TextButton(
          onPressed: () async =>
              onResult(await confirmRestartOnboarding(context)),
          child: const Text('open'),
        ),
      ),
    ),
  );
}

void main() {
  group('DEF152 — the restart-onboarding confirmation', () {
    testWidgets('CANCEL does not confirm', (t) async {
      bool? result;
      await t.pumpWidget(_harness((r) => result = r));
      await t.tap(find.text('open'));
      await t.pumpAndSettle();

      expect(find.byType(AlertDialog), findsOneWidget,
          reason: 'the destructive action must not run unannounced');

      await t.tap(find.text('CANCEL'));
      await t.pumpAndSettle();
      expect(result, isFalse);
      expect(find.byType(AlertDialog), findsNothing);
    });

    testWidgets('RESTART confirms', (t) async {
      bool? result;
      await t.pumpWidget(_harness((r) => result = r));
      await t.tap(find.text('open'));
      await t.pumpAndSettle();

      await t.tap(find.text('RESTART'));
      await t.pumpAndSettle();
      expect(result, isTrue);
    });

    testWidgets('dismissing the dialog is a NO, not a yes', (t) async {
      // The load-bearing case. `showDialog` resolves to `null` when the
      // barrier is tapped or the user swipes back; anything that reads that
      // as consent has re-created the defect behind a dialog.
      bool? result;
      await t.pumpWidget(_harness((r) => result = r));
      await t.tap(find.text('open'));
      await t.pumpAndSettle();

      await t.tapAt(const Offset(10, 10)); // the barrier, outside the dialog
      await t.pumpAndSettle();
      expect(result, isFalse);
      expect(find.byType(AlertDialog), findsNothing);
    });

    testWidgets('the body names the real cost', (t) async {
      // Not a bare "are you sure?". The control's placement and styling carry
      // no signal that it costs anything, so the copy has to carry all of it.
      await t.pumpWidget(_harness((_) {}));
      await t.tap(find.text('open'));
      await t.pumpAndSettle();

      final l = AppLocalizations.of(
          t.element(find.byType(AlertDialog)) as BuildContext);
      expect(find.text(l.floorRestartOnboardingConfirmTitle), findsOneWidget);
      expect(find.text(l.floorRestartOnboardingConfirmBody), findsOneWidget);

      final body = l.floorRestartOnboardingConfirmBody.toLowerCase();
      expect(body, contains('interview'),
          reason: 'the cost is sitting through the interview again');
      expect(body, contains('mandate'),
          reason: 'the mandate is what the user thinks is at stake, so the '
              'copy has to address it one way or the other');
    });

    testWidgets('DEF158 — the body does not promise a wipe that never happens',
        (t) async {
      // The original copy said restarting "clears the mandate your interview
      // produced". Nothing clears it: reset() only drops a SharedPreferences
      // flag, _bind_onboarding_session refuses to overwrite an existing
      // mandate (pinned backend-side by
      // test_def060_onboarding_claim_mandate.py::
      // test_claim_does_not_clobber_an_existing_mandate), and the readback
      // preview is never PATCHed. So the promise was false for exactly the
      // users who had a mandate to lose. This test exists to stop the
      // destructive phrasing coming back without the mechanism behind it.
      await t.pumpWidget(_harness((_) {}));
      await t.tap(find.text('open'));
      await t.pumpAndSettle();

      final l = AppLocalizations.of(
          t.element(find.byType(AlertDialog)) as BuildContext);
      final body = l.floorRestartOnboardingConfirmBody.toLowerCase();

      for (final claim in const [
        'clears the mandate',
        'clear your mandate',
        'deletes the mandate',
        'delete your mandate',
        'erases the mandate',
        'resets your mandate',
      ]) {
        expect(body, isNot(contains(claim)),
            reason: 'the app must not claim an outcome it does not deliver — '
                'if restart is ever made to actually replace the mandate, '
                'change the mechanism first, then this test, then the copy');
      }

      expect(body, contains('settings'),
          reason: 'having told the user restart will not change the mandate, '
              'the copy must name the control that does');
    });
  });

  group('DEF152 — the guard is still wired to the call site', () {
    final source =
        File('lib/screens/floor/floor_screen.dart').readAsStringSync();

    test('the Floor resets onboarding in exactly one place', () {
      expect(RegExp(r'\.reset\(\)').allMatches(source).length, 1,
          reason: 'a second unguarded door is the defect again, elsewhere');
    });

    test('the confirm gates the reset, and can abort it', () {
      final confirm = source.indexOf('confirmRestartOnboarding(context)');
      final reset = source.indexOf('.reset()');
      expect(confirm, greaterThan(-1),
          reason: 'the dialog was removed from the call site');
      expect(confirm, lessThan(reset),
          reason: 'confirming AFTER the wipe is not confirming');
      expect(source, contains('if (!await confirmRestartOnboarding(context)) return;'),
          reason: 'the early return is the whole guard — without it the '
              'dialog is decoration and the reset runs either way');
    });
  });
}
