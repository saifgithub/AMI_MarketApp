// DEF469 — Journal entry detail: the OUTCOME label + WIN / LOSS / PENDING
// chips sat in a non-wrapping Row, so at a 360dp phone width with larger
// system text the PENDING chip ran past the card's right edge (tester report
// bug 11223a2a, Android). The row is now a Wrap: every chip must stay inside
// the screen and nothing may throw a RenderFlex overflow.

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/journal.dart';
import 'package:ami_trade/screens/journal/journal_detail_screen.dart';
import 'package:ami_trade/state/journal_providers.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

class _ScriptedJournalNotifier extends JournalNotifier {
  _ScriptedJournalNotifier(super.ref, List<JournalEntry> entries) {
    state = JournalState(entries: entries, retentionLoaded: true);
  }

  @override
  Future<void> refresh({JournalEntryType? filterType, String? q}) async {}
}

JournalEntry _entry() => JournalEntry(
      id: 'e1',
      userId: 'u1',
      entryType: JournalEntryType.simTrade,
      title: 'BUY 5 BUD',
      createdAt: DateTime.utc(2026, 8, 18),
      agentsInvolved: const [],
      tags: const [],
      payload: const {},
    );

Widget _app(Locale locale) => ProviderScope(
      overrides: [
        journalNotifierProvider
            .overrideWith((ref) => _ScriptedJournalNotifier(ref, [_entry()])),
      ],
      child: MaterialApp(
        locale: locale,
        localizationsDelegates: AppLocalizations.localizationsDelegates,
        supportedLocales: AppLocalizations.supportedLocales,
        home: const JournalDetailScreen(entryId: 'e1'),
      ),
    );

void main() {
  setUp(() => SharedPreferences.setMockInitialValues({}));

  for (final locale in const [Locale('en'), Locale('ar'), Locale('ms')]) {
    for (final scale in const [1.3, 2.0]) {
      testWidgets(
          'outcome chips stay on-screen at 360dp, ${locale.languageCode}, '
          '${scale}x text', (tester) async {
        tester.view.physicalSize = const Size(360, 780);
        tester.view.devicePixelRatio = 1.0;
        tester.platformDispatcher.textScaleFactorTestValue = scale;
        addTearDown(tester.view.reset);
        addTearDown(tester.platformDispatcher.clearTextScaleFactorTestValue);

        await tester.pumpWidget(_app(locale));
        await tester.pumpAndSettle();

        final chips = find.byType(ChoiceChip);
        expect(chips, findsNWidgets(3));
        for (var i = 0; i < 3; i++) {
          final r = tester.getRect(chips.at(i));
          expect(r.left, greaterThanOrEqualTo(0));
          expect(r.right, lessThanOrEqualTo(360),
              reason: 'chip $i runs off the right edge: $r');
        }
        expect(tester.takeException(), isNull);
      });
    }
  }
}
