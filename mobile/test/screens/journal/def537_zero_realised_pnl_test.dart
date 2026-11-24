// DEF537 — the Journal trade detail hid the Realised P&L row when the value was
// exactly zero, so a break-even close ("Closed 1155.KL — +RM0.00") read as if
// the P&L were unknown. A closed trade shows the row at zero, signed like every
// other P&L on screen; an open trade still shows none.

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

Future<void> _pump(WidgetTester t, Map<String, dynamic> trade) async {
  final entry = JournalEntry(
    id: 'e1',
    userId: 'u1',
    entryType: JournalEntryType.simTrade,
    title: 'Closed ${trade['ticker']}',
    createdAt: DateTime.utc(2026, 11, 24),
    agentsInvolved: const [],
    tags: const [],
    payload: {'trade': trade},
  );
  await t.pumpWidget(ProviderScope(
    overrides: [
      journalNotifierProvider
          .overrideWith((ref) => _ScriptedJournalNotifier(ref, [entry])),
    ],
    child: MaterialApp(
      localizationsDelegates: AppLocalizations.localizationsDelegates,
      supportedLocales: AppLocalizations.supportedLocales,
      home: const JournalDetailScreen(entryId: 'e1'),
    ),
  ));
  await t.pumpAndSettle();
}

void main() {
  setUp(() => SharedPreferences.setMockInitialValues({}));

  testWidgets('closed MY trade at zero shows +RM0.00', (t) async {
    await _pump(t, {
      'ticker': '1155.KL',
      'status': 'closed',
      'closed_price': 10.2,
      'realised_pnl': 0.0,
    });
    expect(find.text('REALISED P&L'), findsOneWidget);
    expect(find.text('+RM0.00'), findsOneWidget);
  });

  testWidgets('closed US trade at zero shows +\$0.00', (t) async {
    await _pump(t, {
      'ticker': 'AAPL',
      'status': 'closed',
      'closed_price': 190.0,
      'realised_pnl': 0,
    });
    expect(find.text('REALISED P&L'), findsOneWidget);
    expect(find.text('+\$0.00'), findsOneWidget);
  });

  testWidgets('closed non-zero P&L is unchanged', (t) async {
    await _pump(t, {
      'ticker': 'AAPL',
      'status': 'closed',
      'closed_price': 190.0,
      'realised_pnl': -12.5,
    });
    expect(find.text('REALISED P&L'), findsOneWidget);
    expect(find.text('-\$12.50'), findsOneWidget);
  });

  testWidgets('open trade shows no Realised P&L row', (t) async {
    await _pump(t, {
      'ticker': 'AAPL',
      'status': 'open',
      'realised_pnl': 0.0,
    });
    expect(find.text('REALISED P&L'), findsNothing);
  });
}
