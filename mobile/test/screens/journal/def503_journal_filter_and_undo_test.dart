/// DEF503 — three Journal bugs from AMI-DL-3 (E5-JRNL-01).
///
///   a. Tapping ALL fetched the full list but the previous chip stayed
///      highlighted (`copyWith(filterType: null)` meant "unchanged").
///   b. A search ran under whatever the fetch last used, not under the chip on
///      screen, because background `refresh()` calls fetched unfiltered while
///      leaving the chip highlighted; and an older, slower response could land
///      after a newer one.
///   c. The "Entry removed / UNDO" bar never closed: Flutter keeps a SnackBar
///      with an action open under accessible navigation (TalkBack / the
///      automation service a device lab drives the phone with), and it
///      followed the user to other screens.
///
/// The fake API filters the way the backend does (entry_type AND q), so what
/// the list shows is what the request asked for.
library;

import 'dart:async';

import 'package:ami_trade/features/nav/ami_tab.dart';
import 'package:ami_trade/features/tour/tour_providers.dart';
import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/journal.dart';
import 'package:ami_trade/models/mandate.dart';
import 'package:ami_trade/screens/journal/journal_screen.dart';
import 'package:ami_trade/screens/you/you_providers.dart';
import 'package:ami_trade/services/api/api_client.dart';
import 'package:ami_trade/state/journal_providers.dart';
import 'package:ami_trade/state/mandate_providers.dart';
import 'package:ami_trade/state/onboarding_providers.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

JournalEntry _e(String id, JournalEntryType t, String title) => JournalEntry(
      id: id,
      userId: 'u1',
      entryType: t,
      title: title,
      createdAt: DateTime.utc(2026, 11, 19),
      agentsInvolved: const [],
      tags: const [],
    );

final _all = [
  _e('1', JournalEntryType.roomRun, 'Room on NFLX'),
  _e('2', JournalEntryType.simTrade, 'BUY 1 NFLX'),
  _e('3', JournalEntryType.complianceBlock, 'BLOCKED: BUY MSFT'),
  _e('4', JournalEntryType.oneOnOne, 'Ask on NFLX margins'),
  _e('5', JournalEntryType.oneOnOne, 'Ask on AAPL services'),
];

class _FilteringApi extends ApiClient {
  _FilteringApi() : super(baseUrl: 'test://localhost');

  final calls = <({String? type, String? q})>[];

  /// When set, the next call waits for it (to force out-of-order responses).
  Completer<void>? holdNext;

  @override
  Future<JournalListResponse> listJournal({
    required String userId,
    required String plan,
    String? entryType,
    String? ticker,
    String? q,
    int limit = 100,
  }) async {
    calls.add((type: entryType, q: q));
    final gate = holdNext;
    holdNext = null;
    if (gate != null) await gate.future;
    final rows = _all.where((e) {
      if (entryType != null && e.entryType!.wire != entryType) return false;
      if (q != null && !e.title.toLowerCase().contains(q.toLowerCase())) {
        return false;
      }
      return true;
    }).toList();
    return JournalListResponse(entries: rows, total: rows.length, retentionDays: null);
  }

  @override
  Future<void> deleteJournalEntry({
    required String userId,
    required String entryId,
  }) async {}
}

class _FixedMandate extends MandateNotifier {
  _FixedMandate(super.ref) {
    state = MandateState(
      mandate: UserMandate.fromJson({'user_id': 'u1', 'plan': 'trial_trader'}),
    );
  }
  @override
  Future<void> refresh() async {}
}

ProviderContainer _container(_FilteringApi api) {
  final c = ProviderContainer(overrides: [
    apiClientProvider.overrideWithValue(api),
    mandateNotifierProvider.overrideWith((ref) => _FixedMandate(ref)),
  ]);
  addTearDown(c.dispose);
  return c;
}

void main() {
  setUp(() => SharedPreferences.setMockInitialValues({}));

  group('DEF503 a — the ALL chip clears the previous chip', () {
    test('setFilter(null) leaves no filter in state', () async {
      final api = _FilteringApi();
      final c = _container(api);
      final n = c.read(journalNotifierProvider.notifier);
      await pumpEventQueue();

      await n.setFilter(JournalEntryType.oneOnOne);
      expect(c.read(journalNotifierProvider).filterType, JournalEntryType.oneOnOne);
      expect(c.read(journalNotifierProvider).entries, hasLength(2));

      await n.setFilter(null);
      expect(c.read(journalNotifierProvider).filterType, isNull);
      expect(c.read(journalNotifierProvider).entries, hasLength(5));
      expect(api.calls.last.type, isNull);
    });

    testWidgets('the ALL chip, not 1-ON-1, is the selected one after tapping ALL',
        (tester) async {
      final api = _FilteringApi();
      await tester.pumpWidget(ProviderScope(
        overrides: [
          apiClientProvider.overrideWithValue(api),
          mandateNotifierProvider.overrideWith((ref) => _FixedMandate(ref)),
        ],
        child: MaterialApp(
          localizationsDelegates: AppLocalizations.localizationsDelegates,
          supportedLocales: AppLocalizations.supportedLocales,
          home: const Scaffold(body: JournalScreen(embedded: true)),
        ),
      ));
      await tester.pumpAndSettle();
      final l = AppLocalizations.of(tester.element(find.byType(JournalScreen)));

      bool selected(String label) => tester
          .widget<ChoiceChip>(find.widgetWithText(ChoiceChip, label))
          .selected;

      await tester.tap(find.widgetWithText(ChoiceChip, l.journalFilterOneOnOne));
      await tester.pumpAndSettle();
      expect(selected(l.journalFilterOneOnOne), isTrue);
      expect(selected(l.journalFilterAll), isFalse);

      await tester.tap(find.widgetWithText(ChoiceChip, l.journalFilterAll));
      await tester.pumpAndSettle();
      expect(selected(l.journalFilterAll), isTrue);
      expect(selected(l.journalFilterOneOnOne), isFalse);
    });
  });

  group('DEF503 b — search respects the chip', () {
    test('search under a chip sends both entry_type and q, and only that '
        'type comes back', () async {
      final api = _FilteringApi();
      final c = _container(api);
      final n = c.read(journalNotifierProvider.notifier);
      await pumpEventQueue();

      await n.setFilter(JournalEntryType.oneOnOne);
      await n.search('NFLX');

      expect(api.calls.last, (type: 'one_on_one', q: 'NFLX'));
      final titles =
          c.read(journalNotifierProvider).entries.map((e) => e.title).toList();
      expect(titles, ['Ask on NFLX margins']);
    });

    test('a background refresh() keeps the chip and the search text', () async {
      final api = _FilteringApi();
      final c = _container(api);
      final n = c.read(journalNotifierProvider.notifier);
      await pumpEventQueue();
      await n.setFilter(JournalEntryType.oneOnOne);
      await n.search('NFLX');

      // MandateNotifier / the Room / a trade fill all call it bare.
      await n.refresh();

      expect(api.calls.last, (type: 'one_on_one', q: 'NFLX'));
      expect(c.read(journalNotifierProvider).filterType, JournalEntryType.oneOnOne);
      expect(c.read(journalNotifierProvider).entries, hasLength(1));
    });

    test('clearing the search keeps the chip', () async {
      final api = _FilteringApi();
      final c = _container(api);
      final n = c.read(journalNotifierProvider.notifier);
      await pumpEventQueue();
      await n.setFilter(JournalEntryType.oneOnOne);
      await n.search('NFLX');
      await n.search('');

      expect(api.calls.last, (type: 'one_on_one', q: null));
      expect(c.read(journalNotifierProvider).entries, hasLength(2));
    });

    test('a slow older response cannot overwrite the newer filter', () async {
      final api = _FilteringApi();
      final c = _container(api);
      final n = c.read(journalNotifierProvider.notifier);
      await pumpEventQueue();

      final gate = Completer<void>();
      api.holdNext = gate; // the ALL fetch below stalls
      final slow = n.setFilter(null);
      await pumpEventQueue();
      await n.setFilter(JournalEntryType.simTrade);
      gate.complete();
      await slow;

      expect(c.read(journalNotifierProvider).filterType, JournalEntryType.simTrade);
      expect(c.read(journalNotifierProvider).entries.map((e) => e.id), ['2']);
    });
  });

  group('DEF503 c — the UNDO bar closes itself', () {
    Future<void> pumpJournal(WidgetTester tester, {required bool accessible}) async {
      final api = _FilteringApi();
      await tester.pumpWidget(ProviderScope(
        overrides: [
          apiClientProvider.overrideWithValue(api),
          mandateNotifierProvider.overrideWith((ref) => _FixedMandate(ref)),
        ],
        child: MaterialApp(
          localizationsDelegates: AppLocalizations.localizationsDelegates,
          supportedLocales: AppLocalizations.supportedLocales,
          builder: (context, child) => MediaQuery(
            data: MediaQuery.of(context)
                .copyWith(accessibleNavigation: accessible),
            child: child!,
          ),
          home: const Scaffold(body: JournalScreen(embedded: true)),
        ),
      ));
      await tester.pumpAndSettle();
    }

    Future<void> swipeFirstRow(WidgetTester tester) async {
      await tester.fling(find.text('Room on NFLX'), const Offset(-600, 0), 2000);
      await tester.pumpAndSettle();
    }

    testWidgets('closes after its duration under normal navigation',
        (tester) async {
      await pumpJournal(tester, accessible: false);
      await swipeFirstRow(tester);
      final l = AppLocalizations.of(tester.element(find.byType(JournalScreen)));
      expect(find.text(l.journalEntryDeleted), findsOneWidget);

      await tester.pump(const Duration(seconds: 5));
      await tester.pumpAndSettle();
      expect(find.text(l.journalEntryDeleted), findsNothing);
    });

    testWidgets(
        'closes under accessible navigation too (Flutter alone never would)',
        (tester) async {
      await pumpJournal(tester, accessible: true);
      await swipeFirstRow(tester);
      final l = AppLocalizations.of(tester.element(find.byType(JournalScreen)));
      expect(find.text(l.journalEntryDeleted), findsOneWidget);

      // Still up after the normal window: a switch/voice user needs longer.
      await tester.pump(const Duration(seconds: 5));
      expect(find.text(l.journalEntryDeleted), findsOneWidget);

      await tester.pump(const Duration(seconds: 5));
      await tester.pumpAndSettle();
      expect(find.text(l.journalEntryDeleted), findsNothing);
    });

    testWidgets('is closed when the user leaves the Journal segment',
        (tester) async {
      final api = _FilteringApi();
      await tester.pumpWidget(ProviderScope(
        overrides: [
          apiClientProvider.overrideWithValue(api),
          mandateNotifierProvider.overrideWith((ref) => _FixedMandate(ref)),
          activeTabProvider.overrideWith((ref) => AmiTab.you),
          youSegmentProvider.overrideWith((ref) => YouSegment.journal),
        ],
        child: MaterialApp(
          localizationsDelegates: AppLocalizations.localizationsDelegates,
          supportedLocales: AppLocalizations.supportedLocales,
          builder: (context, child) => MediaQuery(
            data: MediaQuery.of(context).copyWith(accessibleNavigation: true),
            child: child!,
          ),
          home: const Scaffold(body: JournalScreen(embedded: true)),
        ),
      ));
      await tester.pumpAndSettle();
      await swipeFirstRow(tester);
      final l = AppLocalizations.of(tester.element(find.byType(JournalScreen)));
      expect(find.text(l.journalEntryDeleted), findsOneWidget);

      ProviderScope.containerOf(tester.element(find.byType(JournalScreen)))
          .read(youSegmentProvider.notifier)
          .state = YouSegment.settings;
      await tester.pumpAndSettle();
      expect(find.text(l.journalEntryDeleted), findsNothing);
    });
  });
}
