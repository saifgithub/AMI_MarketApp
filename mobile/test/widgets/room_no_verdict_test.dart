/// CR098-MOBILE-VERDICT — the terminal verdict card under `NO_VERDICT`, and
/// the `opinions_not_included` closing disclosure that rides on every verdict.
///
/// `NO_VERDICT` (Amendment 2) is the PM declining to price a trade because the
/// session ran without a market read. It arrives with **every** level field
/// null — the crash surface this lane was opened for — and it must not read as
/// a rejection.
///
/// Everything here drives the **real** `RoomVerdict.fromJson` with the payload
/// `room_runner.py::_assemble_no_verdict` actually emits, then renders the
/// **real** `RoomScreen`. A fixture-built `RoomVerdict` would prove nothing
/// about the wire contract.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/room.dart';
import 'package:ami_trade/screens/room/room_screen.dart';
import 'package:ami_trade/state/room_providers.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

class _FixedRoomNotifier extends RoomNotifier {
  _FixedRoomNotifier(super.ref, super.ticker, RoomState fixed) {
    state = fixed;
  }
}

/// Verbatim from `room_runner.py::_NO_VERDICT_REASON`. Kept literal rather than
/// paraphrased because acceptance #7 asserts on this exact copy.
const _pmReason = 'No verdict — and that is deliberate.\n'
    'The fundamentals case for AAPL was argued in full, and it stands on its '
    'own.\n'
    'But entry, stop and target are price decisions, and this session ran '
    'without a market read. Issuing a position on that basis would be a guess '
    'presented as a call, and I won\'t put that on your book.\n'
    'The analysis holds. The trade doesn\'t — not until someone reads the tape.';

/// The wire payload as the backend emits it: `use_enum_values=True` so `action`
/// is the bare string, every level field explicitly null.
Map<String, dynamic> noVerdictPayload({
  List<String> withheld = const ['market_analyst'],
}) =>
    <String, dynamic>{
      'action': 'NO_VERDICT',
      'size_pct': null,
      'entry': null,
      'target': null,
      'stop': null,
      'time_horizon_days': null,
      'reason': _pmReason,
      'violations': <String>[],
      'overridden_from_llm': false,
      'opinions_not_included': withheld,
    };

Map<String, dynamic> approvePayload({
  List<String> withheld = const <String>[],
  bool includeOpinionsKey = true,
}) =>
    <String, dynamic>{
      'action': 'APPROVE',
      'size_pct': 2.5,
      'entry': 190.0,
      'target': 210.0,
      'stop': 180.0,
      'time_horizon_days': 30,
      'reason': 'Cleared — thesis and levels hold.',
      'violations': <String>[],
      'overridden_from_llm': false,
      if (includeOpinionsKey) 'opinions_not_included': withheld,
    };

void main() {
  // CR106 added a BOARD | TRANSCRIPT toggle whose default is BOARD, so a
  // finished run no longer opens on `_VerdictCard`. This file's subject is
  // `_VerdictCard`, which is still a real and reachable surface — so it now
  // declares the mode it is testing instead of relying on the default.
  //
  // The board is NOT left unguarded: `room_board_test.dart` re-asserts every
  // invariant below against the hero tile, and `room_board_parity_test.dart`
  // asserts the Journal renders it identically. Between them the NO_VERDICT
  // treatment is pinned on all three surfaces — which is one more than CR098
  // shipped with, and is why the Journal was free to contradict the Room
  // (DEF143) in the first place.
  setUp(() => SharedPreferences.setMockInitialValues(
        {'ami_room_view_mode': 'transcript'},
      ));

  Future<void> pumpVerdict(WidgetTester t, RoomVerdict v) async {
    const ticker = 'AAPL';
    await t.pumpWidget(
      ProviderScope(
        overrides: [
          roomNotifierProvider(ticker).overrideWith(
            (ref) => _FixedRoomNotifier(
              ref,
              ticker,
              RoomState(
                done: true,
                runId: 'run-1',
                order: const ['fundamentals_analyst'],
                transcript: const {
                  'fundamentals_analyst': 'Margins are expanding.',
                },
                verdict: v,
              ),
            ),
          ),
        ],
        child: MaterialApp(
          localizationsDelegates: AppLocalizations.localizationsDelegates,
          supportedLocales: AppLocalizations.supportedLocales,
          home: const RoomScreen(ticker: ticker),
        ),
      ),
    );
    // RoomScreen animates a scroll on every build; without settling, the
    // harness fails on a pending timer for reasons unrelated to the card.
    await t.pumpAndSettle();
  }

  List<String> renderedTexts(WidgetTester t) => t
      .widgetList<Text>(find.byType(Text))
      .map((w) => w.data ?? '')
      .where((s) => s.isNotEmpty)
      .toList();

  /// The verdict card's own status icon — the only 28px Icon on the screen.
  Icon verdictIcon(WidgetTester t) => t
      .widgetList<Icon>(find.byType(Icon))
      .firstWhere((i) => i.size == 28);

  group('acceptance #3/#4 — all-null levels render, and render as ABSENT', () {
    testWidgets('renders through the real parse path without throwing',
        (t) async {
      final v = RoomVerdict.fromJson(noVerdictPayload());
      expect(v.action, 'NO_VERDICT');
      expect(v.sizePct, isNull);
      expect(v.entry, isNull);
      expect(v.target, isNull);
      expect(v.stop, isNull);
      expect(v.timeHorizonDays, isNull);

      await pumpVerdict(t, v);
      expect(t.takeException(), isNull);
      expect(find.textContaining('No verdict'), findsOneWidget);
    });

    testWidgets('no level row is rendered at all — not "—", not "0" (D1)',
        (t) async {
      await pumpVerdict(t, RoomVerdict.fromJson(noVerdictPayload()));
      final texts = renderedTexts(t);

      // The metric labels themselves must be absent — an empty-looking row is
      // as bad as a wrong one. A zero-size position shown in a training
      // simulator is worse than an error.
      //
      // Matched EXACTLY, not by substring: the PM's own copy says "But entry,
      // stop and target are price decisions", so a `contains` check here fails
      // on the very paragraph that proves the card is behaving.
      for (final label in const [
        'TICKER',
        'SIZE',
        'ENTRY',
        'STOP',
        'TARGET',
        'HORIZON',
      ]) {
        expect(texts.where((s) => s == label), isEmpty,
            reason: '$label row leaked into a NO_VERDICT card');
      }
      expect(texts.contains('—'), isFalse);
      expect(texts.where((s) => s == '0' || s == '0.0%' || s == '\$0.00'),
          isEmpty);
    });

    testWidgets('no trade ticket CTA — there is no trade to place', (t) async {
      await pumpVerdict(t, RoomVerdict.fromJson(noVerdictPayload()));
      expect(find.byType(ElevatedButton), findsNothing);
    });
  });

  group('NO_VERDICT must not read as a rejection', () {
    testWidgets('neutral accent + neutral icon, never the reject pair',
        (t) async {
      await pumpVerdict(t, RoomVerdict.fromJson(noVerdictPayload()));
      final icon = verdictIcon(t);
      expect(icon.color, AmiColors.slate500,
          reason: 'amber here tells the user their thesis was turned down');
      expect(icon.icon, isNot(Icons.cancel));
    });

    testWidgets('a real REJECT still gets the reject treatment', (t) async {
      // Guards the above from being satisfied by neutering the whole card.
      final reject = RoomVerdict.fromJson({
        ...approvePayload(),
        'action': 'REJECT',
        'reason': 'Breaches your concentration limit.',
      });
      await pumpVerdict(t, reject);
      final icon = verdictIcon(t);
      expect(icon.color, AmiColors.hexAmber);
      expect(icon.icon, Icons.cancel);
    });

    testWidgets('the raw wire enum never reaches the user', (t) async {
      await pumpVerdict(t, RoomVerdict.fromJson(noVerdictPayload()));
      final texts = renderedTexts(t);
      expect(texts.where((s) => s.contains('NO_VERDICT')), isEmpty,
          reason: 'the underscored enum token is not user-facing copy');
      expect(find.textContaining('NO VERDICT'), findsOneWidget);
    });
  });

  group('acceptance #5/#6 — the disclosure is on EVERY action (D3/D4)', () {
    testWidgets('renders on an APPROVE with Social withheld', (t) async {
      final v = RoomVerdict.fromJson(
          approvePayload(withheld: ['social_media_analyst']));
      expect(v.isApprove, isTrue);
      await pumpVerdict(t, v);

      expect(find.text('Not in the room'), findsOneWidget);
      expect(find.textContaining('Social'), findsWidgets,
          reason: 'an APPROVE reached without Social must still disclose it');
      // And the APPROVE half of the card is untouched.
      expect(find.byType(ElevatedButton), findsOneWidget);
    });

    testWidgets('empty list renders nothing — no heading, no stray divider',
        (t) async {
      await pumpVerdict(t, RoomVerdict.fromJson(approvePayload()));
      final texts = renderedTexts(t);
      expect(texts.contains('Not in the room'), isFalse);
      expect(texts.where((s) => s.contains('without their input')), isEmpty);
    });

    testWidgets(
        'empty list is identical to the field being absent from the wire',
        (t) async {
      await pumpVerdict(t, RoomVerdict.fromJson(approvePayload()));
      final withEmptyList = renderedTexts(t);

      await pumpVerdict(
          t, RoomVerdict.fromJson(approvePayload(includeOpinionsKey: false)));
      final withNoKey = renderedTexts(t);

      // D4: every existing user sees this card until a threshold is set, so
      // the new field must be invisible in the common case.
      expect(withEmptyList, withNoKey);
    });

    testWidgets('an unresolvable agent id renders as itself, never as a name',
        (t) async {
      // `agentById` falls back to the Concierge for an unknown id — in a
      // disclosure that would name the WRONG analyst as absent.
      final v =
          RoomVerdict.fromJson(noVerdictPayload(withheld: ['future_analyst']));
      await pumpVerdict(t, v);
      // Twice, correctly: once as its own bullet, once inside the CTA — with
      // one withheld analyst it is also the blocking one.
      expect(find.text('• future_analyst'), findsOneWidget);
      expect(find.text('Include the future_analyst →'), findsOneWidget);
      expect(find.textContaining('Concierge'), findsNothing);
    });
  });

  group('acceptance #7/#8 — the PM never sells, the CTA is app chrome', () {
    testWidgets('nothing in the PM voice mentions plans, upgrades or pricing',
        (t) async {
      await pumpVerdict(t, RoomVerdict.fromJson(noVerdictPayload()));

      // The reason is rendered verbatim — assert on the widget, so that
      // concatenating chrome into the PM's voice fails here.
      final reason = t
          .widgetList<Text>(find.byType(Text))
          .map((w) => w.data ?? '')
          .firstWhere((s) => s.startsWith('No verdict'));
      expect(reason, _pmReason);

      final lower = reason.toLowerCase();
      for (final banned in const [
        'upgrade',
        'plan',
        'credit',
        'floor pass',
        'trader',
        'floor manager',
        '\$',
        'subscri',
      ]) {
        expect(lower.contains(banned), isFalse,
            reason: 'PM copy must never sell — found "$banned"');
      }
    });

    testWidgets('the CTA exists, names the blocking analyst, and is chrome',
        (t) async {
      await pumpVerdict(t, RoomVerdict.fromJson(noVerdictPayload()));

      final cta = find.widgetWithText(OutlinedButton, 'Include the Market Analyst →');
      expect(cta, findsOneWidget);

      // Chrome, not speech: it is a button, and it sits outside the reason
      // block rather than inside the PM's paragraph.
      final reasonText = find.text(_pmReason);
      expect(reasonText, findsOneWidget);
      expect(
        find.descendant(of: find.byType(OutlinedButton), matching: reasonText),
        findsNothing,
      );
      expect(find.byType(Divider), findsWidgets);
    });

    testWidgets('no CTA on an ordinary APPROVE', (t) async {
      await pumpVerdict(t, RoomVerdict.fromJson(approvePayload()));
      expect(find.textContaining('Include the'), findsNothing);
    });
  });

  group('acceptance #9 — the enum grows; unknown actions must not crash', () {
    testWidgets('an unseen action renders, raw, without throwing', (t) async {
      final v = RoomVerdict.fromJson({
        ...approvePayload(),
        'action': 'DEFERRED_PENDING_EARNINGS',
        'size_pct': null,
        'entry': null,
        'target': null,
        'stop': null,
        'time_horizon_days': null,
      });
      await pumpVerdict(t, v);
      expect(t.takeException(), isNull);
      expect(find.textContaining('DEFERRED_PENDING_EARNINGS'), findsOneWidget);
    });

    testWidgets('a malformed opinions list does not take down the card',
        (t) async {
      // `cast<String>()` would defer the type error to first read — i.e. into
      // build(). `whereType` drops the bad entry instead.
      final v = RoomVerdict.fromJson({
        ...noVerdictPayload(),
        'opinions_not_included': <dynamic>['market_analyst', 7, null],
      });
      expect(v.opinionsNotIncluded, ['market_analyst']);
      await pumpVerdict(t, v);
      expect(t.takeException(), isNull);
    });
  });
}
