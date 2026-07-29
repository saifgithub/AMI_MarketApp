/// CR111 — two scope reductions on CR106's Journal replay: the agent roster
/// and the metadata strip.
///
/// Saiful, on the entry screenshot: *"this section in the journal does not add
/// value. we can remove it."* Twelve full-width pills over six rows is a whole
/// phone screen of static labels sitting between the reader and the
/// `REJECT — Mandate violation` line they opened the entry to read.
///
/// **What measuring changed.** The CR was written expecting to edit the shared
/// `RoomBoard` view-model and to widen CR106 acceptance #10's parity allow-list
/// from three declared Room/Journal differences to four. Neither was needed:
/// the pills are `entry.agentsInvolved` rendered in the **generic journal entry
/// header**, which every entry type shares and which the board never sees, and
/// the strip is a value the Journal *passes in* rather than one the mapper
/// produces. So both changes are widget-level, both mappers are untouched, and
/// `room_board_parity_test.dart` still asserts exactly three differences.
///
/// The one thing the CR said to guard is the **roster gap** —
/// `opinions_not_included`, CR098's withheld-analyst disclosure. It renders
/// adjacently, so the obvious deletion takes both. It lives in `_RosterGap`
/// inside the board, which this change does not touch, and it is already
/// asserted by `room_board_parity_test.dart`'s *"the Journal carries the CR098
/// withheld disclosure"*. Not duplicated here.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/journal.dart';
import 'package:ami_trade/screens/journal/journal_detail_screen.dart';
import 'package:ami_trade/state/room_view_mode_provider.dart';
import 'package:ami_trade/widgets/room/room_view_mode_toggle.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

JournalEntry _entry(JournalEntryType type, List<String> agents) => JournalEntry(
      id: 'e1',
      userId: 'u1',
      entryType: type,
      title: 'NVDA',
      createdAt: DateTime.utc(2026, 7, 29),
      agentsInvolved: agents,
      tags: const [],
      payload: const {},
    );

Widget _host(Widget child) => MaterialApp(
      localizationsDelegates: AppLocalizations.localizationsDelegates,
      supportedLocales: AppLocalizations.supportedLocales,
      home: Scaffold(body: child),
    );

const _twelve = [
  'fundamentals', 'technicals', 'news', 'social', 'bull', 'bear',
  'trader', 'risk_conservative', 'risk_neutral', 'risk_aggressive',
  'pm', 'sharia',
];

void main() {
  group('CR111 — the Room run drops its agent pills', () {
    test('a room run shows none', () {
      expect(showsAgentPills(_entry(JournalEntryType.roomRun, _twelve)), isFalse,
          reason: 'for a Room run the answer to "which agents?" is "all of '
              'them", which the reader already knows');
    });

    test('every OTHER type keeps them — this is the load-bearing half', () {
      // Sweeping the enum rather than naming types one by one: a new entry type
      // must not silently join the suppression. The default is SHOW, because
      // showing a redundant pill is cheap and hiding the only clue to which
      // agent produced an entry is not.
      final others = JournalEntryType.values
          .where((t) => t != JournalEntryType.roomRun)
          .toList();
      final dropped =
          others.where((t) => !showsAgentPills(_entry(t, const ['bull'])));

      expect(dropped, isEmpty,
          reason: 'only roomRun is suppressed — these lost their pills too');
      expect(others.length, greaterThan(1),
          reason: 'vacuity: the enum must actually have other types');
    });

    test('an entry with no agents shows nothing regardless', () {
      for (final t in JournalEntryType.values) {
        expect(showsAgentPills(_entry(t, const [])), isFalse);
      }
    });

    test('the fixture is not vacuous — twelve agents really is twelve', () {
      expect(_twelve.length, 12);
      expect(_entry(JournalEntryType.roomRun, _twelve).agentsInvolved.length, 12);
    });
  });

  group('CR111 — the Journal drops the metadata strip, keeps the toggle', () {
    testWidgets('meta: null renders no strip text but still renders the toggle',
        (tester) async {
      await tester.pumpWidget(_host(const RoomSubHeader(
        meta: null,
        mode: RoomViewMode.board,
        onModeChanged: _noop,
      )));

      expect(find.textContaining('TIER'), findsNothing);
      expect(find.textContaining('MANDATE'), findsNothing);
      expect(find.byType(RoomSubHeader), findsOneWidget);
      // The toggle is the reason the bar survives at all.
      expect(find.byType(ClipPath), findsWidgets);
    });

    testWidgets('the live Room strip is untouched', (tester) async {
      // CR111 is Journal-side only. The Room keeps `41s · 3 CREDITS` — the
      // asymmetry is the point, not an inconsistency to tidy away later.
      await tester.pumpWidget(_host(const RoomSubHeader(
        meta: '41S · 3 CREDITS',
        mode: RoomViewMode.board,
        onModeChanged: _noop,
      )));
      expect(find.text('41S · 3 CREDITS'), findsOneWidget);
    });

    testWidgets('no strip AND no toggle draws nothing, not an empty band',
        (tester) async {
      // Reachable while a run has produced neither verdict nor transcript. A
      // 44pt chrome band with a bottom border and nothing in it reads as a
      // rendering fault — the same "clipped content with no cue" mistake as
      // DEF075, arrived at from the other direction.
      await tester.pumpWidget(_host(const RoomSubHeader(
        meta: null,
        showToggle: false,
        mode: RoomViewMode.board,
        onModeChanged: _noop,
      )));

      expect(tester.getSize(find.byType(RoomSubHeader)).height, 0);
    });

    testWidgets('a strip with no toggle still draws', (tester) async {
      await tester.pumpWidget(_host(const RoomSubHeader(
        meta: 'MID TIER',
        showToggle: false,
        mode: RoomViewMode.board,
        onModeChanged: _noop,
      )));
      expect(tester.getSize(find.byType(RoomSubHeader)).height, 44);
      expect(find.text('MID TIER'), findsOneWidget);
    });
  });
}

void _noop(RoomViewMode _) {}
