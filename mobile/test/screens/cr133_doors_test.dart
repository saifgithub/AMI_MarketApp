/// CR133 §5 + §6 — the two places CR133 replaces directions with a door.
///
/// Both are the same failure in different clothes: the app knew where the user
/// needed to go and told them to walk there instead of taking them.
///
///   * §5 — the blocked trade ticket rendered *"Change what is enforced via
///     Settings → My Mandate"* at the exact moment a compliance breach had just
///     stopped the trade. CR133 moves that path, so it was about to be wrong as
///     well as unhelpful. Renaming it was rejected: *"always make it easier for
///     the user!"*
///   * §6 — the only way to file a bug report was to scroll past thirteen
///     sections of Settings and long-press an **unlabelled grey version
///     string**, while `bug_report_sheet.dart` documents "call this from
///     anywhere" and had exactly one caller.
///
/// These assert against the shipped source rather than by driving the screens,
/// because both surfaces need a large amount of live state to render (a
/// rejected submit with violations; a loaded mandate plus thirteen sections)
/// and the property under test is "the control exists and is wired", not
/// "the screen lays out".
library;

import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';

void main() {
  group('§5 — the blocked trade ticket offers the mandate, not directions', () {
    final source = File('lib/screens/sim/trade_ticket_sheet.dart')
        .readAsStringSync();

    test('the violations block renders the OPEN MY MANDATE control', () {
      expect(source, contains('l.tradeTicketOpenMandate'),
          reason: 'the button that turns the instruction into a control');
      expect(source, contains('SettingsScreen()'),
          reason: 'and it must actually push the mandate — a label that goes '
              'nowhere is worse than the sentence it replaced');
    });

    test('the copy states the outcome and names no path', () {
      final arb = jsonDecode(File('lib/l10n/app_en.arb').readAsStringSync())
          as Map<String, dynamic>;
      final body = arb['tradeTicketChangeMandate'] as String;
      expect(body, isNot(contains('→')));
      expect(body.toLowerCase(), isNot(contains('settings')),
          reason: 'CR133 moves Settings under YOU; a string that names the '
              'path goes stale silently, in three locales, at three '
              'different times');
      expect(arb['tradeTicketOpenMandate'], 'OPEN MY MANDATE');
    });

    test('this is the pattern the app already ships', () {
      // `floorLockedGoToLessons` is already a button rather than directions.
      // Pinned so a future "simplification" back to a sentence has to argue
      // with a precedent rather than with a preference.
      final arb = jsonDecode(File('lib/l10n/app_en.arb').readAsStringSync())
          as Map<String, dynamic>;
      expect(arb['floorLockedGoToLessons'], 'GO TO LESSONS');
    });
  });

  group('§6 — the bug-report door is labelled', () {
    final source =
        File('lib/screens/settings/settings_screen.dart').readAsStringSync();

    test('HELP carries a labelled entry, not only the long-press', () {
      expect(source, contains('settingsReportProblem'),
          reason: 'the labelled door — the long-press on an unlabelled grey '
              'version chip is not a door a tester can find');
      expect('showBugReportSheet(context, ref)'.allMatches(source).length,
          greaterThanOrEqualTo(2),
          reason: 'two callers now: the new labelled row and the version '
              "chip's long-press, which is kept because some muscle memory "
              'exists and it costs nothing');
    });

    test('the label is a real string, in every locale', () {
      for (final locale in const ['en', 'ar', 'ms']) {
        final arb =
            jsonDecode(File('lib/l10n/app_$locale.arb').readAsStringSync())
                as Map<String, dynamic>;
        expect(arb['settingsReportProblem'], isNotNull,
            reason: 'a missing key renders English mid-screen (DEF137)');
        expect((arb['settingsReportProblem'] as String).trim(), isNotEmpty);
      }
    });
  });
}
