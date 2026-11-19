/// CR260 / CR267 WP-21b — the "How the Street rates it" card on the Verdict Board.
///
/// Pinned: the card shows when the user's setting is on and hides when it is
/// off; the backend's source label is always visible; missing Street data says
/// "No Street rating available" and never renders an empty or zero rating,
/// count or target; the wording stays educational; the setting persists and
/// defaults ON; the wire parses (JSON -> StreetComparison, live and Journal).
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/agent.dart';
import 'package:ami_trade/models/journal.dart';
import 'package:ami_trade/models/room.dart';
import 'package:ami_trade/models/room_board_mappers.dart';
import 'package:ami_trade/models/room_board.dart';
import 'package:ami_trade/screens/settings/street_comparison_setting.dart';
import 'package:ami_trade/state/street_comparison_provider.dart';
import 'package:ami_trade/widgets/room/room_board.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

const _label = 'Yahoo Finance via yfinance: sell-side analyst consensus';

RoomVoice _voice(String agentId) => RoomVoice(
      agentId: agentId,
      content: 'A contribution.',
      stance: 'for',
      conviction: 'high',
      stanceRecorded: true,
    );

StreetComparison _available({
  String rating = 'buy',
  String stance = 'buy',
  String action = 'PASS',
  String agreement = 'differ',
  bool approvedAgainstSell = false,
  int? count = 47,
  double? target = 312.5,
}) =>
    StreetComparison(
      status: 'available',
      sourceLabel: _label,
      streetRating: rating,
      streetStance: stance,
      analystCount: count,
      targetMean: target,
      asOf: '2026-11-18',
      roomAction: action,
      agreement: agreement,
      approvedAgainstStreetSell: approvedAgainstSell,
    );

const _unavailable = StreetComparison(
  status: 'unavailable',
  sourceLabel: _label,
  unavailableReason: 'no_rating',
  roomAction: 'PASS',
  agreement: 'not_comparable',
);

RoomBoardData _board(StreetComparison? c,
        {VerdictOutcome outcome = VerdictOutcome.pass}) =>
    RoomBoardData(
      ticker: 'AAPL',
      outcome: outcome,
      actionToken: outcome == VerdictOutcome.approve ? 'APPROVE' : 'PASS',
      reason: 'Synthesis defended; mandate clears.',
      streetComparison: c,
      voices: [for (final a in kCombVoices) _voice(a.id)],
    );

Future<void> _pump(WidgetTester t, RoomBoardData data,
    {required bool settingOn}) async {
  await t.pumpWidget(
    ProviderScope(
      overrides: [
        streetComparisonEnabledProvider.overrideWith(
            (ref) => StreetComparisonSettingNotifier.withoutHydration(settingOn)),
      ],
      child: MaterialApp(
        localizationsDelegates: AppLocalizations.localizationsDelegates,
        supportedLocales: AppLocalizations.supportedLocales,
        home: Scaffold(
          body: SingleChildScrollView(child: RoomBoard(data: data)),
        ),
      ),
    ),
  );
  await t.pumpAndSettle();
}

void main() {
  group('setting gate', () {
    testWidgets('shown when the setting is on', (t) async {
      await _pump(t, _board(_available()), settingOn: true);
      expect(t.takeException(), isNull);
      expect(find.text('HOW THE STREET RATES IT'), findsOneWidget);
      expect(find.text('Buy'), findsOneWidget);
      expect(find.text('47'), findsOneWidget);
      expect(find.text('\$312.50'), findsOneWidget);
      expect(find.text('THE ROOM PASSED'), findsWidgets);
    });

    testWidgets('hidden when the setting is off', (t) async {
      await _pump(t, _board(_available()), settingOn: false);
      expect(find.text('HOW THE STREET RATES IT'), findsNothing);
      expect(find.textContaining('Source:'), findsNothing);
      expect(find.text('Buy'), findsNothing);
    });

    testWidgets('a run with no comparison shows no card, setting on or off',
        (t) async {
      await _pump(t, _board(null), settingOn: true);
      expect(find.text('HOW THE STREET RATES IT'), findsNothing);
    });

    testWidgets('a board without a comparison needs no ProviderScope',
        (t) async {
      await t.pumpWidget(
        MaterialApp(
          localizationsDelegates: AppLocalizations.localizationsDelegates,
          supportedLocales: AppLocalizations.supportedLocales,
          home: Scaffold(
            body: SingleChildScrollView(child: RoomBoard(data: _board(null))),
          ),
        ),
      );
      await t.pumpAndSettle();
      expect(t.takeException(), isNull);
    });
  });

  group('source label', () {
    testWidgets('the backend label is visible verbatim, with the as-of date',
        (t) async {
      await _pump(t, _board(_available()), settingOn: true);
      expect(find.text('Source: $_label'), findsOneWidget);
      expect(find.text('Rating read on 2026-11-18'), findsOneWidget);
    });

    testWidgets('the label stays visible when the rating is unavailable',
        (t) async {
      await _pump(t, _board(_unavailable), settingOn: true);
      expect(find.text('Source: $_label'), findsOneWidget);
    });

    testWidgets('a missing label is shown as missing, not hidden', (t) async {
      final noLabel = StreetComparison.fromJson({
        'status': 'available',
        'street_rating': 'buy',
        'street_stance': 'buy',
        'room_action': 'PASS',
        'agreement': 'differ',
      });
      await _pump(t, _board(noLabel), settingOn: true);
      expect(find.text('Source: not stated'), findsOneWidget);
    });
  });

  group('missing data', () {
    testWidgets('says so, and renders no rating, count or target',
        (t) async {
      await _pump(t, _board(_unavailable), settingOn: true);
      expect(find.text('HOW THE STREET RATES IT'), findsOneWidget);
      expect(find.text('No Street rating available for this run.'),
          findsOneWidget);
      expect(find.text('STREET RATING'), findsNothing);
      expect(find.text('ANALYSTS'), findsNothing);
      expect(find.text('MEAN TARGET'), findsNothing);
      expect(find.textContaining('\$0'), findsNothing);
    });

    testWidgets('an "available" block with no stance is still unavailable',
        (t) async {
      final broken = StreetComparison.fromJson({
        'status': 'available',
        'source_label': _label,
        'room_action': 'PASS',
        'agreement': 'differ',
      });
      expect(broken.isAvailable, isFalse);
      await _pump(t, _board(broken), settingOn: true);
      expect(find.text('No Street rating available for this run.'),
          findsOneWidget);
    });

    testWidgets('a missing count or target omits the row, never shows 0',
        (t) async {
      await _pump(t, _board(_available(count: null, target: null)),
          settingOn: true);
      expect(find.text('STREET RATING'), findsOneWidget);
      expect(find.text('ANALYSTS'), findsNothing);
      expect(find.text('MEAN TARGET'), findsNothing);
    });
  });

  group('wording', () {
    testWidgets('a reasoned pass on a Street-Buy name is not an error',
        (t) async {
      await _pump(t, _board(_available()), settingOn: true);
      expect(
        find.textContaining('Passing on a name the Street rates Buy can be a reasoned call'),
        findsOneWidget,
      );
      expect(find.textContaining('worth checking'), findsNothing);
    });

    testWidgets('approving a Street-Sell name is called out, neutrally',
        (t) async {
      await _pump(
        t,
        _board(
          _available(
              rating: 'sell',
              stance: 'sell',
              action: 'APPROVE',
              approvedAgainstSell: true),
          outcome: VerdictOutcome.approve,
        ),
        settingOn: true,
      );
      expect(find.textContaining('approved a name the Street rates Sell'),
          findsOneWidget);
      expect(find.text('Sell'), findsOneWidget);
    });

    testWidgets('agreement is stated', (t) async {
      await _pump(
          t,
          _board(_available(
              rating: 'sell', stance: 'sell', agreement: 'agree')),
          settingOn: true);
      expect(
          find.text('The Room\'s call and the Street rating point the same way.'),
          findsOneWidget);
    });

    testWidgets('no user-facing text says "the AI" or gives advice',
        (t) async {
      await _pump(t, _board(_available()), settingOn: true);
      for (final w in t.widgetList<Text>(find.byType(Text))) {
        final s = (w.data ?? '').toLowerCase();
        expect(s.contains('the ai'), isFalse, reason: s);
        expect(s.contains('you should'), isFalse, reason: s);
        expect(s.contains('buy now'), isFalse, reason: s);
      }
    });
  });

  group('the setting', () {
    setUp(() => SharedPreferences.setMockInitialValues({}));

    test('defaults ON and persists only when the user changes it', () async {
      final c = ProviderContainer();
      addTearDown(c.dispose);
      expect(c.read(streetComparisonEnabledProvider), isTrue);
      await Future<void>.delayed(Duration.zero);
      final prefs = await SharedPreferences.getInstance();
      expect(prefs.containsKey(streetComparisonPrefsKey), isFalse);
      await c.read(streetComparisonEnabledProvider.notifier).setEnabled(false);
      expect(c.read(streetComparisonEnabledProvider), isFalse);
      expect(prefs.getBool(streetComparisonPrefsKey), isFalse);
    });

    test('a stored OFF is restored on the next launch', () async {
      SharedPreferences.setMockInitialValues({streetComparisonPrefsKey: false});
      final c = ProviderContainer();
      addTearDown(c.dispose);
      c.read(streetComparisonEnabledProvider);
      await Future<void>.delayed(const Duration(milliseconds: 20));
      expect(c.read(streetComparisonEnabledProvider), isFalse);
    });

    testWidgets('the Settings switch flips the provider', (t) async {
      final c = ProviderContainer();
      addTearDown(c.dispose);
      await t.pumpWidget(
        UncontrolledProviderScope(
          container: c,
          child: MaterialApp(
            localizationsDelegates: AppLocalizations.localizationsDelegates,
            supportedLocales: AppLocalizations.supportedLocales,
            home: const Scaffold(body: StreetComparisonSetting()),
          ),
        ),
      );
      await t.pumpAndSettle();
      expect(find.text('Show how the Street rates it'), findsOneWidget);
      expect(c.read(streetComparisonEnabledProvider), isTrue);
      await t.tap(find.byKey(const ValueKey('street-comparison-switch')));
      await t.pumpAndSettle();
      expect(c.read(streetComparisonEnabledProvider), isFalse);
    });
  });

  group('wire', () {
    test('a verdict JSON parses the comparison', () {
      final v = RoomVerdict.fromJson({
        'action': 'APPROVE',
        'reason': 'r',
        'street_comparison': {
          'status': 'available',
          'source_label': _label,
          'street_rating': 'underperform',
          'street_stance': 'sell',
          'analyst_count': 31,
          'target_mean': 88.4,
          'as_of': '2026-11-18',
          'room_action': 'APPROVE',
          'room_stance': 'approve',
          'agreement': 'differ',
          'approved_against_street_sell': true,
          'reasons_from_narrow_answers': <String>[],
        },
      });
      final c = v.streetComparison!;
      expect(c.isAvailable, isTrue);
      expect(c.differs, isTrue);
      expect(c.approvedAgainstStreetSell, isTrue);
      expect(c.analystCount, 31);
      expect(c.targetMean, 88.4);
      expect(c.reasonsFromNarrowAnswers, isEmpty);
    });

    test('the Journal replays the stored comparison, and an old entry has none',
        () {
      JournalEntry entry(Map<String, dynamic> verdict) => JournalEntry(
            id: 'e1',
            userId: 'u1',
            entryType: JournalEntryType.roomRun,
            title: 'Room on NVDA',
            createdAt: DateTime.utc(2026, 11, 18),
            agentsInvolved: const [],
            tags: const ['room'],
            ticker: 'NVDA',
            payload: {
              'verdict': verdict,
              'transcript': const [
                {'agent_id': 'bull_researcher', 'content': 'x', 'stance': 'FOR'},
              ],
            },
          );
      final withIt = boardFromJournalEntry(entry({
        'action': 'PASS',
        'reason': 'r',
        'street_comparison': {
          'status': 'unavailable',
          'source_label': _label,
          'room_action': 'PASS',
          'agreement': 'not_comparable',
        },
      }))!;
      expect(withIt.streetComparison, isNotNull);
      expect(withIt.streetComparison!.isAvailable, isFalse);
      final old = boardFromJournalEntry(entry({'action': 'PASS', 'reason': 'r'}))!;
      expect(old.streetComparison, isNull);
    });

    test('a verdict with no key has no comparison', () {
      final v = RoomVerdict.fromJson({'action': 'PASS', 'reason': 'r'});
      expect(v.streetComparison, isNull);
    });
  });
}
