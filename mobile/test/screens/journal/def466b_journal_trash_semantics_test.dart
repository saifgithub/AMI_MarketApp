/// DEF466 round 2 — the iPhone tree went dark after: Journal, swipe-delete,
/// UNDO, swipe again, TRASH, RESTORE. Replays that exact sequence against the
/// real YOU / Journal / Trash screens with semantics on (and again under
/// accessible navigation), asserting after every step that the visible
/// screen's labelled nodes are in the tree and that no error was raised while
/// the semantics tree was being built.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/journal.dart';
import 'package:ami_trade/models/mandate.dart';
import 'package:ami_trade/screens/you/insights_data.dart';
import 'package:ami_trade/screens/you/insights_providers.dart';
import 'package:ami_trade/screens/you/you_providers.dart';
import 'package:ami_trade/screens/you/you_screen.dart';
import 'package:ami_trade/services/api/api_client.dart';
import 'package:ami_trade/state/mandate_providers.dart';
import 'package:ami_trade/state/onboarding_providers.dart';
import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

JournalEntry _e(String id, String title) => JournalEntry(
      id: id,
      userId: 'u1',
      entryType: JournalEntryType.roomRun,
      title: title,
      createdAt: DateTime.utc(2026, 11, 19),
      agentsInvolved: const [],
      tags: const [],
    );

class _StatefulApi extends ApiClient {
  _StatefulApi({this.latency = Duration.zero})
      : super(baseUrl: 'test://localhost');

  final Duration latency;
  Future<void> _wait() => latency == Duration.zero
      ? Future<void>.value()
      : Future<void>.delayed(latency);

  final live = <JournalEntry>[
    for (var i = 0; i < 6; i++) _e('e$i', 'Room on MSFT $i'),
  ];
  final trash = <JournalEntry>[];

  @override
  Future<JournalListResponse> listJournal({
    required String userId,
    required String plan,
    String? entryType,
    String? ticker,
    String? q,
    int limit = 100,
  }) async {
    await _wait();
    return JournalListResponse(
        entries: List.of(live), total: live.length, retentionDays: null);
  }

  @override
  Future<void> deleteJournalEntry(
      {required String userId, required String entryId}) async {
    await _wait();
    final i = live.indexWhere((e) => e.id == entryId);
    if (i >= 0) trash.add(live.removeAt(i));
  }

  @override
  Future<void> restoreJournalEntry(
      {required String userId, required String entryId}) async {
    await _wait();
    final i = trash.indexWhere((e) => e.id == entryId);
    if (i >= 0) {
      live.add(trash.removeAt(i));
      live.sort((a, b) => a.id.compareTo(b.id));
    }
  }

  @override
  Future<JournalListResponse> listJournalTrash(
          {required String userId, int limit = 100}) async {
    await _wait();
    return JournalListResponse(
        entries: List.of(trash), total: trash.length, retentionDays: null);
  }
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

/// Every label in the semantics tree, including hidden-by-merge descendants.
Set<String> _labels(WidgetTester t) {
  final out = <String>{};
  void walk(SemanticsNode n) {
    if (n.label.isNotEmpty) out.add(n.label);
    if (n.tooltip.isNotEmpty) out.add(n.tooltip);
    n.visitChildren((c) {
      walk(c);
      return true;
    });
  }

  // ignore: deprecated_member_use
  final root = t.binding.pipelineOwner.semanticsOwner?.rootSemanticsNode;
  expect(root, isNotNull, reason: 'semantics owner has no root node');
  walk(root!);
  return out;
}

void _expectLabels(WidgetTester t, String step, Iterable<Pattern> wanted) {
  final labels = _labels(t);
  for (final w in wanted) {
    expect(labels.any((l) => l.contains(w)), isTrue,
        reason: '[$step] semantics tree is missing "$w". Tree: $labels');
  }
}

void main() {
  setUp(() => SharedPreferences.setMockInitialValues({}));

  for (final (accessible, slow) in [
    (false, false),
    (true, false),
    (false, true),
    (true, true),
  ]) {
    testWidgets(
        'DEF466b — delete, UNDO, delete, TRASH, RESTORE keeps the semantics '
        'tree populated (accessibleNavigation: $accessible, '
        'slow network: $slow)', (t) async {
      Future<void> settle() async {
        for (var i = 0; i < (slow ? 12 : 1); i++) {
          await t.pump(const Duration(milliseconds: 100));
        }
        await t.pumpAndSettle();
      }

      t.view.physicalSize = const Size(390, 1000);
      t.view.devicePixelRatio = 1.0;
      addTearDown(t.view.reset);
      final handle = t.ensureSemantics();
      final api = _StatefulApi(
          latency: slow ? const Duration(milliseconds: 400) : Duration.zero);

      final collected = <FlutterErrorDetails>[];
      final previous = FlutterError.onError;
      FlutterError.onError = collected.add;
      addTearDown(() => FlutterError.onError = previous);

      final container = ProviderContainer(overrides: [
        apiClientProvider.overrideWithValue(api),
        mandateNotifierProvider.overrideWith((ref) => _FixedMandate(ref)),
        insightsProvider
            .overrideWith((ref) async => const InsightsData(entryCount: 0)),
      ]);
      addTearDown(container.dispose);

      await t.pumpWidget(UncontrolledProviderScope(
        container: container,
        child: MaterialApp(
          localizationsDelegates: AppLocalizations.localizationsDelegates,
          supportedLocales: AppLocalizations.supportedLocales,
          builder: (context, child) => MediaQuery(
            data: MediaQuery.of(context)
                .copyWith(accessibleNavigation: accessible),
            child: child!,
          ),
          home: const YouScreen(),
        ),
      ));
      await settle();
      final l = AppLocalizations.of(t.element(find.byType(YouScreen)));

      void check(String step, Iterable<Pattern> wanted) {
        expect(t.takeException(), isNull, reason: '[$step] exception');
        expect(collected, isEmpty,
            reason: '[$step] FlutterError: ${collected.map((d) => d.exceptionAsString())}');
        _expectLabels(t, step, wanted);
      }

      container.read(youSegmentProvider.notifier).state = YouSegment.journal;
      await settle();
      check('journal open', [
        l.journalTrashHeading,
        l.journalFilterAll,
        l.journalFilterRoom,
        'Room on MSFT 0',
      ]);

      // tap every filter chip, then search
      for (final chip in [
        l.journalFilterRoom,
        l.journalFilterTrade,
        l.journalFilterOneOnOne,
        l.journalFilterAll,
      ]) {
        await t.tap(find.widgetWithText(ChoiceChip, chip));
        await settle();
      }
      await t.enterText(find.byType(TextField).first, 'MSFT');
      await settle();
      check('after chips + search', [l.journalTrashHeading, 'Room on MSFT 0']);

      Future<void> swipe(String title) async {
        await t.fling(find.text(title), const Offset(-600, 0), 2000);
        await settle();
      }

      await swipe('Room on MSFT 0');
      check('after swipe 1', [l.journalEntryDeleted, l.journalUndo, 'Room on MSFT 1']);

      await t.tap(find.text(l.journalUndo));
      await settle();
      check('after UNDO', [l.journalTrashHeading, 'Room on MSFT 0']);

      await swipe('Room on MSFT 0');
      check('after swipe 2', [l.journalEntryDeleted, 'Room on MSFT 1']);

      await t.tap(find.byTooltip(l.journalTrashHeading));
      await settle();
      check('trash open', [
        l.journalTrashHeading,
        l.journalRestoreEntry,
        MaterialLocalizations.of(t.element(find.byType(Scaffold).last))
            .backButtonTooltip,
      ]);

      await t.tap(find.text(l.journalRestoreEntry));
      await t.pump();
      await t.pump(const Duration(milliseconds: 500));
      await settle();
      check('after RESTORE', [
        l.journalTrashHeading,
        MaterialLocalizations.of(t.element(find.byType(Scaffold).last))
            .backButtonTooltip,
      ]);

      await t.tap(find.byTooltip(
          MaterialLocalizations.of(t.element(find.byType(Scaffold).last))
              .backButtonTooltip));
      await settle();
      check('back on journal', [l.journalTrashHeading, 'Room on MSFT 0']);

      container.read(youSegmentProvider.notifier).state = YouSegment.settings;
      await settle();
      check('settings', [l.settingsTabUpper]);

      // let every snackbar timer run out
      await t.pump(const Duration(seconds: 20));
      await settle();
      check('after timers', [l.settingsTabUpper]);

      handle.dispose();
    });
  }
}
