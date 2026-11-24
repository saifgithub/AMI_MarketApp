// DEF542 — a closed trade's Realised P&L is NET of fees (the backend nets it)
// and a Fees row shows what the round trip paid. A zero-fee close (US) shows no
// Fees row at all. A Bursa break-even round trip reads -RM16.42 / RM16.42.

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

  testWidgets('Bursa round trip: net -RM16.42 and a Fees row of RM16.42',
      (t) async {
    await _pump(t, {
      'ticker': '6888.KL',
      'status': 'closed',
      'closed_price': 1.61,
      'realised_pnl': -16.42,
      'fees': 16.42,
    });
    expect(find.text('REALISED P&L'), findsOneWidget);
    expect(find.text('-RM16.42'), findsOneWidget);
    expect(find.text('FEES'), findsOneWidget);
    expect(find.text('RM16.42'), findsOneWidget);
  });

  testWidgets('zero-fee US close shows no Fees row', (t) async {
    await _pump(t, {
      'ticker': 'AAPL',
      'status': 'closed',
      'closed_price': 190.0,
      'realised_pnl': 0.0,
    });
    expect(find.text('REALISED P&L'), findsOneWidget);
    expect(find.text('+\$0.00'), findsOneWidget);
    expect(find.text('FEES'), findsNothing);
  });

  testWidgets('fees of 0 shows no Fees row', (t) async {
    await _pump(t, {
      'ticker': 'AAPL',
      'status': 'closed',
      'closed_price': 190.0,
      'realised_pnl': 5.0,
      'fees': 0,
    });
    expect(find.text('FEES'), findsNothing);
  });

  testWidgets('a US fee is shown in dollars', (t) async {
    await _pump(t, {
      'ticker': 'AAPL',
      'status': 'closed',
      'closed_price': 190.0,
      'realised_pnl': 9.0,
      'fees': 2.0,
    });
    expect(find.text('FEES'), findsOneWidget);
    expect(find.text('\$2.00'), findsOneWidget);
  });
}
