// CR177 UI — the Journal's compliance_block surface, screen + provider side:
//
//   * the BLOCKED filter chip exists, appended LAST (ROOM/TRADE front
//     placement is pinned by bug 1e645bca), and selecting it sends
//     entry_type=compliance_block on the wire;
//   * the detail screen offers NO win/loss/pending outcome editor for a
//     compliance_block entry — the backend writes outcome=None deliberately
//     ("a block has no win/loss and must never be rendered as either", CR177
//     §4) and the editor must not let the user stamp one — while every other
//     type (proven on sim_trade) keeps the chips, and the note field stays;
//   * a malformed payload (no blocked_by) falls through to the generic dump
//     rather than a confident typed card (CR040).

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/journal.dart';
import 'package:ami_trade/models/mandate.dart';
import 'package:ami_trade/screens/journal/journal_detail_screen.dart';
import 'package:ami_trade/screens/journal/journal_screen.dart';
import 'package:ami_trade/services/api/api_client.dart';
import 'package:ami_trade/state/journal_providers.dart';
import 'package:ami_trade/state/mandate_providers.dart';
import 'package:ami_trade/state/onboarding_providers.dart';
import 'package:ami_trade/widgets/journal/compliance_block_card.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

/// Records the `entryType` of every listJournal call so the test can prove
/// which filter actually reached the wire.
class _RecordingApiClient extends ApiClient {
  _RecordingApiClient() : super(baseUrl: 'test://localhost');

  final List<String?> entryTypeCallsSeen = [];

  @override
  Future<JournalListResponse> listJournal({
    required String userId,
    required String plan,
    String? entryType,
    String? ticker,
    String? q,
    int limit = 100,
  }) async {
    entryTypeCallsSeen.add(entryType);
    return const JournalListResponse(entries: [], total: 0, retentionDays: null);
  }
}

/// State set directly, no network — the `_FixedMandateNotifier` pattern from
/// journal_plan_trust_boundary_test.dart.
class _FixedMandateNotifier extends MandateNotifier {
  _FixedMandateNotifier(super.ref, UserMandate? initial) {
    state = MandateState(mandate: initial);
  }

  @override
  Future<void> refresh() async {}
}

class _ScriptedJournalNotifier extends JournalNotifier {
  _ScriptedJournalNotifier(super.ref, List<JournalEntry> entries) {
    state = JournalState(entries: entries, retentionLoaded: true);
  }

  @override
  Future<void> refresh({JournalEntryType? filterType, String? q}) async {}
}

UserMandate _mandate() => UserMandate(
      userId: 'u1',
      version: 1,
      displayName: 'Trader',
      locale: 'en',
      timezone: 'UTC',
      primaryGoal: 'long_term_wealth',
      horizon: 'long',
      path: 'long_horizon',
      riskScore: 3,
      riskComponents: const RiskComponents(
        drawdownResponse: 3,
        regretAsymmetry: 0,
        concentrationTolerance: 3,
      ),
      maxDrawdownPct: 30,
      learningStyle: 'quick',
      compliance: const ComplianceFlags(),
      plan: 'trial_trader',
      creditBalance: 75,
    );

JournalEntry _entry({
  required JournalEntryType type,
  Map<String, dynamic> payload = const {},
}) =>
    JournalEntry(
      id: 'e1',
      userId: 'u1',
      entryType: type,
      title: 'BLOCKED: BUY 5 BUD',
      createdAt: DateTime.utc(2026, 8, 18),
      agentsInvolved: const [],
      tags: const [],
      payload: payload,
    );

Widget _detailApp(JournalEntry entry) => ProviderScope(
      overrides: [
        journalNotifierProvider
            .overrideWith((ref) => _ScriptedJournalNotifier(ref, [entry])),
      ],
      child: MaterialApp(
        localizationsDelegates: AppLocalizations.localizationsDelegates,
        supportedLocales: AppLocalizations.supportedLocales,
        home: const JournalDetailScreen(entryId: 'e1'),
      ),
    );

Map<String, dynamic> _blockPayload() => {
      'blocked_by': 'concentration',
      'violations': ['VIOLATION-MARK breaches your concentration cap.'],
      'request': {
        'ticker': 'BUD',
        'side': 'BUY',
        'quantity': 5,
        'order_type': 'market',
      },
      'sharia_verdict': null,
      'classification_verdicts': const [],
      'advisories': const [],
      'source': 'ticket',
    };

void main() {
  setUp(() {
    SharedPreferences.setMockInitialValues({});
  });

  group('filter chip', () {
    test('BLOCKED chip exists and is appended last (bug 1e645bca pin)',
        () async {
      final l = await AppLocalizations.delegate.load(const Locale('en'));
      final filters = JournalScreen.filtersFor(l);
      expect(filters.last.type, JournalEntryType.complianceBlock);
      expect(filters.last.label, l.journalFilterBlocked);
      // ROOM/TRADE keep their pinned front placement right after ALL.
      expect(filters[1].type, JournalEntryType.roomRun);
      expect(filters[2].type, JournalEntryType.simTrade);
    });

    test('selecting the filter sends entry_type=compliance_block on the wire',
        () async {
      final fakeApi = _RecordingApiClient();
      final container = ProviderContainer(overrides: [
        apiClientProvider.overrideWithValue(fakeApi),
        mandateNotifierProvider.overrideWith(
          (ref) => _FixedMandateNotifier(ref, _mandate()),
        ),
      ]);
      addTearDown(container.dispose);

      final notifier = container.read(journalNotifierProvider.notifier);
      await pumpEventQueue();
      await notifier.setFilter(JournalEntryType.complianceBlock);

      expect(fakeApi.entryTypeCallsSeen, isNotEmpty);
      expect(fakeApi.entryTypeCallsSeen.last, 'compliance_block');
    });
  });

  group('detail screen', () {
    testWidgets(
        'compliance_block: typed card renders, outcome editor row hidden, '
        'note field stays', (tester) async {
      await tester.pumpWidget(_detailApp(_entry(
        type: JournalEntryType.complianceBlock,
        payload: _blockPayload(),
      )));
      await tester.pumpAndSettle();

      expect(find.byType(ComplianceBlockCard), findsOneWidget);
      // CR177 §4 — no WIN/LOSS/PENDING chips on a block, ever.
      expect(find.byType(ChoiceChip), findsNothing);
      // The note field is not part of the outcome and stays.
      expect(find.byType(TextField), findsOneWidget);
    });

    testWidgets('sim_trade still shows the three outcome chips',
        (tester) async {
      await tester.pumpWidget(
          _detailApp(_entry(type: JournalEntryType.simTrade)));
      await tester.pumpAndSettle();

      expect(find.byType(ChoiceChip), findsNWidgets(3));
    });

    testWidgets(
        'malformed compliance_block payload falls through to the generic dump',
        (tester) async {
      final malformed = Map<String, dynamic>.from(_blockPayload())
        ..remove('blocked_by');
      await tester.pumpWidget(_detailApp(_entry(
        type: JournalEntryType.complianceBlock,
        payload: malformed,
      )));
      await tester.pumpAndSettle();

      expect(find.byType(ComplianceBlockCard), findsNothing);
      // The generic dump labels every payload key uppercased — raw but
      // visible and honestly labelled (CR040).
      expect(find.text('VIOLATIONS'), findsOneWidget);
      expect(find.text('SOURCE'), findsOneWidget);
    });
  });
}
