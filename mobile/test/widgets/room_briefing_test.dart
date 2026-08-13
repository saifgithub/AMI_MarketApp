/// CR173 slice 1 §5.9 — the live Room, on screen.
///
/// `room_stage_test.dart` proves the narrative is *right*; this proves the
/// screen shows it, and that three things the surface could quietly lose are
/// still there:
///
///  - **the prose stays out** (CR112 acceptance #1). The whole complaint was a
///    wall of growing text. This surface renders headlines, and the transcript
///    the state is holding must not reach the tree.
///  - **the twelve are one tap away** (D-012, §5.7). Twelve agents hidden is a
///    design; twelve agents *gone* is a different product. Both routes are
///    tested — tap a desk, and the persisted WATCH THE FLOOR toggle.
///  - **the toggle writes the preference, once** (T-MODESIDE). CR106's rule
///    extends to the third value unchanged.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/screens/room/room_screen.dart';
import 'package:ami_trade/state/room_providers.dart';
import 'package:ami_trade/state/room_view_mode_provider.dart';
import 'package:ami_trade/widgets/room/room_briefing.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

class _FixedRoomNotifier extends RoomNotifier {
  _FixedRoomNotifier(super.ref, super.ticker, RoomState fixed) {
    state = fixed;
  }
}

AgentStance _spoke(String headline) =>
    AgentStance(stance: 'bull', headline: headline, recorded: true);

/// Mid-run: two analysts in, one working, the rest waiting.
const _prose =
    'The full multi-paragraph reasoning that the old live console streamed '
    'onto the screen a token at a time.';

RoomState _midRun() => RoomState(
      phase: 'ANALYSTS',
      activeAgent: 'news_analyst',
      streaming: true,
      order: const ['fundamentals_analyst', 'market_analyst', 'news_analyst'],
      transcript: const {
        'fundamentals_analyst': _prose,
        'market_analyst': _prose,
      },
      agentStances: {
        'fundamentals_analyst': _spoke('margins expanding, guidance intact'),
        'market_analyst': _spoke('consolidating under the 50-day'),
      },
    );

Future<ProviderContainer> _pump(
  WidgetTester t, {
  RoomState? state,
  RoomViewMode mode = RoomViewMode.board,
}) async {
  const ticker = 'AAPL';
  final container = ProviderContainer(overrides: [
    roomViewModeProvider
        .overrideWith((ref) => RoomViewModeNotifier.withoutHydration(mode)),
    roomNotifierProvider(ticker)
        .overrideWith((ref) => _FixedRoomNotifier(ref, ticker, state ?? _midRun())),
  ]);
  addTearDown(container.dispose);
  await t.pumpWidget(UncontrolledProviderScope(
    container: container,
    child: const MaterialApp(
      localizationsDelegates: AppLocalizations.localizationsDelegates,
      supportedLocales: AppLocalizations.supportedLocales,
      home: RoomScreen(ticker: ticker),
    ),
  ));
  await t.pump();
  return container;
}

void main() {
  setUp(() => SharedPreferences.setMockInitialValues({}));

  testWidgets('the live default is the briefing, not the twelve', (t) async {
    await _pump(t);
    expect(find.byType(RoomBriefing), findsOneWidget);
    // The four desks, by name.
    expect(find.textContaining('ANALYST DESK'), findsOneWidget);
    expect(find.text('RESEARCH DEBATE'), findsOneWidget);
    expect(find.text('RISK REVIEW'), findsOneWidget);
    expect(find.text('PM VERDICT'), findsOneWidget);
  });

  testWidgets('the desk count says how many of the desk have reported',
      (t) async {
    await _pump(t);
    expect(find.textContaining('2/4 REPORTED'), findsOneWidget);
  });

  testWidgets('the prose does not reach the tree', (t) async {
    // CR112 acceptance #1, on the surface that replaced the one it was written
    // for. `state.transcript` holds it; the briefing must not render it.
    await _pump(t);
    expect(find.textContaining('multi-paragraph', findRichText: true), findsNothing);
    expect(find.textContaining('margins expanding', findRichText: true), findsOneWidget,
        reason: 'the headline is the one line per member that IS shown');
  });

  testWidgets('a desk that has not started explains itself instead of counting',
      (t) async {
    await _pump(t);
    expect(find.textContaining('Bull and Bear argue it out'), findsOneWidget);
    expect(find.textContaining('RESEARCH DEBATE · '), findsNothing,
        reason: '0/3 REPORTED on a desk nobody has reached is noise dressed '
            'as data');
  });

  testWidgets('tapping a desk opens its members, standing-by seats included',
      (t) async {
    await _pump(t);
    // Collapsed, the waiting analysts are not on screen — that is the whole
    // point of the surface.
    expect(find.textContaining('Social Media Analyst', findRichText: true), findsNothing);
    await t.tap(find.textContaining('ANALYST DESK'));
    await t.pump();
    expect(find.textContaining('Social Media Analyst', findRichText: true), findsOneWidget,
        reason: 'the twelve are hidden, not gone (D-012)');
    expect(find.textContaining('Fundamentals Analyst', findRichText: true), findsOneWidget);
  });

  testWidgets('one desk open at a time', (t) async {
    await _pump(t);
    await t.tap(find.textContaining('ANALYST DESK'));
    await t.pump();
    await t.tap(find.text('RISK REVIEW'));
    await t.pump();
    expect(find.textContaining('Social Media Analyst', findRichText: true), findsNothing,
        reason: 'four rows all open is the twelve-row wall this replaced');
    expect(find.textContaining('Neutral Debator', findRichText: true), findsOneWidget);
  });

  testWidgets('WATCH THE FLOOR restores the shipped roster and persists',
      (t) async {
    final container = await _pump(t);
    expect(find.byType(RoomBriefing), findsOneWidget);

    await t.tap(find.text('WATCH THE FLOOR'));
    await t.pump();

    expect(find.byType(RoomBriefing), findsNothing);
    // All twelve seats, the shipped roster.
    expect(find.text('Portfolio Manager'), findsOneWidget);
    expect(find.text('Social Media Analyst'), findsOneWidget);
    expect(container.read(roomViewModeProvider), RoomViewMode.floor);

    await t.pump(); // let setMode's SharedPreferences write settle
    final prefs = await SharedPreferences.getInstance();
    expect(prefs.getString(roomViewModePrefsKey), 'floor',
        reason: '§5.7 — the choice persisting is load-bearing; dropping it '
            'changes the design and needs a re-review');
  });

  testWidgets('BRIEFING comes back, and the run is not disturbed', (t) async {
    final container = await _pump(t, mode: RoomViewMode.floor);
    expect(find.byType(RoomBriefing), findsNothing);
    await t.tap(find.text('BRIEFING'));
    await t.pump();
    expect(find.byType(RoomBriefing), findsOneWidget);
    expect(container.read(roomViewModeProvider), RoomViewMode.board);
  });

  testWidgets('a stalled desk says so rather than spinning forever', (t) async {
    // DEF059 — the run stopped with news_analyst mid-turn. The row must not
    // read as a desk still working.
    await _pump(
      t,
      state: RoomState(
        phase: 'ANALYSTS',
        activeAgent: 'news_analyst',
        streaming: false,
        order: const ['fundamentals_analyst', 'news_analyst'],
        agentStances: {'fundamentals_analyst': _spoke('margins expanding')},
      ),
    );
    expect(find.textContaining('INTERRUPTED', findRichText: true), findsWidgets);
  });

  testWidgets('the settled screen is untouched by this CR', (t) async {
    // "This CR ends where CR106 begins." A finished run with the default mode
    // shows the Verdict Board, and no stage row appears anywhere.
    await _pump(
      t,
      state: const RoomState(done: true, streaming: false),
    );
    expect(find.byType(RoomBriefing), findsNothing);
    expect(find.text('BOARD'), findsOneWidget);
    expect(find.text('BRIEFING'), findsNothing);
    expect(find.text('ANALYST DESK'), findsNothing);
  });

  testWidgets('a floor user still settles to the Board', (t) async {
    // CR173 Amendment B, stated as a test because it is the one consequence of
    // squeezing two bits into three values: WATCH THE FLOOR must not silently
    // replace the settled screen this user has always seen.
    await _pump(
      t,
      state: const RoomState(done: true, streaming: false),
      mode: RoomViewMode.floor,
    );
    expect(find.text('BOARD'), findsOneWidget);
    expect(
      t.widget<Semantics>(find
          .ancestor(
              of: find.text('BOARD'), matching: find.byType(Semantics))
          .first)
          .properties
          .selected,
      isTrue,
      reason: 'neither settled segment selected is how a three-value enum '
          'read with a two-value comparison fails',
    );
  });
}
