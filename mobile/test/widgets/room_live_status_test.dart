/// CR112 — the live convene renders per-agent STATUS + headline, never the
/// growing prose (bug report 583602ee: CR106 fixed the destination, the
/// live journey was left untouched and the complaint survived).
///
/// Load-bearing behaviours proven here:
///   1. No agent's prose reaches the tree while a run is live, even though
///      `state.transcript` holds it (acceptance #1).
///   2. Each roster seat renders `waiting` / `thinking` / `responded`
///      distinctly, driven off `state.activeAgent` / `state.transcript` /
///      `state.agentStances` (acceptance #2).
///   5. An agent whose turn never completed because the RUN itself broke
///      (stream error) reaches an `INTERRUPTED` terminal state — never a
///      silent `responded`, never an eternal `thinking` (acceptance #5).
///   6. A DEF125-truncated turn is marked, not a clean `responded`
///      (acceptance #6).
///   7. Growing `state.transcript` never auto-scrolls the page — the
///      behaviour is gone, not just the one call site (acceptance #7).
///   8. The headline renders on `responded`, read straight from
///      `state.agentStances` (acceptance #8).
///   9. The three `recorded`/`headline` states render as three DIFFERENT
///      widgets, never collapsing "stated nothing" into "neutral"
///      (acceptance #9 — the DEF059-class inversion this CR exists to
///      prevent, and the one Saiful reads first).
///
/// `RoomScreen` reads `roomNotifierProvider(ticker)` directly; this harness
/// overrides that family member with a notifier pre-seeded to a fixed
/// `RoomState` (never calling `start()`, so no real network/SSE stream is
/// touched) — same pattern as `room_live_data_notice_test.dart`.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/screens/room/room_screen.dart';
import 'package:ami_trade/state/room_providers.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

class _FixedRoomNotifier extends RoomNotifier {
  _FixedRoomNotifier(super.ref, super.ticker, RoomState fixed) {
    state = fixed;
  }

  /// Mutates state after the initial pump — used by the acceptance #7
  /// no-auto-scroll test to simulate the transcript growing mid-run.
  void push(RoomState next) => state = next;
}

Future<_FixedRoomNotifier> _pump(WidgetTester t, RoomState fixed) async {
  const ticker = 'AAPL';
  late _FixedRoomNotifier captured;
  await t.pumpWidget(
    ProviderScope(
      overrides: [
        roomNotifierProvider(ticker).overrideWith((ref) {
          captured = _FixedRoomNotifier(ref, ticker, fixed);
          return captured;
        }),
      ],
      child: MaterialApp(
        localizationsDelegates: AppLocalizations.localizationsDelegates,
        supportedLocales: AppLocalizations.supportedLocales,
        home: const RoomScreen(ticker: ticker),
      ),
    ),
  );
  await t.pump();
  return captured;
}

void main() {
  const proseThatMustNeverRenderLive =
      'The balance sheet shows margins expanding well past consensus, and '
      'the free cash flow conversion looks unusually strong this quarter.';

  group('acceptance #1 — no prose live, even though state carries it', () {
    testWidgets('transcript is non-empty in state but absent from the tree',
        (t) async {
      const seeded = RoomState(
        streaming: true,
        order: ['fundamentals_analyst'],
        activeAgent: 'fundamentals_analyst',
        transcript: {'fundamentals_analyst': proseThatMustNeverRenderLive},
      );
      await _pump(t, seeded);

      // Proven against the state actually fed to the widget, not a copy —
      // the text is genuinely IN state.transcript, and still never rendered.
      expect(seeded.transcript['fundamentals_analyst'],
          proseThatMustNeverRenderLive);
      expect(find.textContaining(proseThatMustNeverRenderLive), findsNothing);
      // Not even a fragment of it — a truncated *render* of the prose would
      // still be the prose leaking, just less of it.
      expect(find.textContaining('margins expanding'), findsNothing);
      expect(t.takeException(), isNull);
    });
  });

  group('acceptance #2 — waiting / thinking / responded render distinctly',
      () {
    testWidgets('a mixed roster shows all three, correctly attributed',
        (t) async {
      await _pump(
        t,
        const RoomState(
          streaming: true,
          order: ['fundamentals_analyst'],
          activeAgent: 'fundamentals_analyst',
          transcript: {
            'fundamentals_analyst': 'partial thought still streaming',
            'market_analyst': 'full text that must never appear on screen',
          },
          agentStances: {
            'market_analyst': AgentStance(recorded: true, headline: null),
          },
        ),
      );

      // Waiting: 10 of the 12 roster seats never started.
      expect(find.text('STANDING BY'), findsNWidgets(10));
      // Responded: exactly one agent (market_analyst) has an agentStances
      // entry — its check mark is the ONLY one on screen.
      expect(find.byIcon(Icons.check), findsOneWidget);
      // Thinking: fundamentals_analyst is active while streaming, so it is
      // neither STANDING BY nor checked off — no INTERRUPTED mark either.
      expect(find.byIcon(Icons.error_outline), findsNothing);
      expect(find.textContaining('full text that must never appear'),
          findsNothing);
      expect(t.takeException(), isNull);
    });
  });

  group('acceptance #5 — an interrupted turn is a distinct terminal state',
      () {
    testWidgets(
        'an agent mid-turn when the stream itself breaks reads INTERRUPTED, '
        'never responded and never stuck thinking', (t) async {
      await _pump(
        t,
        const RoomState(
          streaming: false,
          reconnecting: false,
          done: false,
          error: 'connection dropped',
          order: ['fundamentals_analyst'],
          activeAgent: 'fundamentals_analyst',
          transcript: {'fundamentals_analyst': 'cut off mid-sentence'},
          // No agentStances entry — agent_done never arrived for this agent.
        ),
      );

      expect(find.text('INTERRUPTED'), findsOneWidget);
      // Two error_outline icons: the top `_ErrorBanner` (state.error) plus
      // this roster row's own terminal mark — both honest, neither hiding
      // the other.
      expect(find.byIcon(Icons.error_outline), findsNWidgets(2));
      // Not rendered as a clean completion.
      expect(find.byIcon(Icons.check), findsNothing);
      expect(t.takeException(), isNull);
    });

    testWidgets('reconnecting keeps an in-flight turn OUT of interrupted',
        (t) async {
      // A dropped socket that is still attempting recovery must not flash
      // INTERRUPTED before the recovery poll has had its chance to land the
      // real final state — that would be a false alarm, not honesty.
      await _pump(
        t,
        const RoomState(
          streaming: false,
          reconnecting: true,
          order: ['fundamentals_analyst'],
          activeAgent: 'fundamentals_analyst',
          transcript: {'fundamentals_analyst': 'cut off mid-sentence'},
        ),
      );

      expect(find.text('INTERRUPTED'), findsNothing);
      expect(t.takeException(), isNull);
    });
  });

  group('acceptance #6 — a truncated turn does not read as clean', () {
    testWidgets('a DEF125-marked contribution carries a visible mark',
        (t) async {
      await _pump(
        t,
        const RoomState(
          streaming: true,
          order: ['fundamentals_analyst'],
          transcript: {
            'fundamentals_analyst':
                'Solid quarter so far [AMI: this contribution hit its '
                    'length limit and stops mid-thought]',
          },
          agentStances: {
            'fundamentals_analyst': AgentStance(recorded: true),
          },
        ),
      );

      expect(find.text('⬢'), findsOneWidget);
      expect(t.takeException(), isNull);
    });

    testWidgets('an ordinary completed turn carries no mark', (t) async {
      await _pump(
        t,
        const RoomState(
          streaming: true,
          order: ['fundamentals_analyst'],
          transcript: {'fundamentals_analyst': 'Solid quarter, no issues.'},
          agentStances: {
            'fundamentals_analyst': AgentStance(recorded: true),
          },
        ),
      );

      expect(find.text('⬢'), findsNothing);
      expect(t.takeException(), isNull);
    });
  });

  group('acceptance #7 — no auto-scroll on transcript growth', () {
    testWidgets(
        'the scroll offset never moves as agents finish and the roster '
        'grows past the viewport', (t) async {
      await t.binding.setSurfaceSize(const Size(400, 500));
      addTearDown(() => t.binding.setSurfaceSize(null));

      var current = const RoomState(streaming: true);
      final notifier = await _pump(t, current);
      await t.pump();

      final scrollable = findScrollable(t);
      expect(scrollable.position.pixels, 0.0);

      // Simulate agents finishing one by one — exactly the sequence that
      // used to fire `ref.listen<int>(...transcript.length...)` and animate
      // to the bottom on every token.
      for (final id in const [
        'fundamentals_analyst',
        'market_analyst',
        'news_analyst',
        'social_media_analyst',
        'bull_researcher',
        'bear_researcher',
      ]) {
        current = current.copyWith(
          order: [...current.order, id],
          transcript: {
            ...current.transcript,
            id: 'a full contribution long enough that the old code would '
                'have scrolled to reveal it',
          },
          agentStances: {
            ...current.agentStances,
            id: const AgentStance(recorded: true, headline: 'Ships now.'),
          },
        );
        notifier.push(current);
        await t.pump();
      }
      // NOT pumpAndSettle: the still-`streaming` footer runs an unending
      // pulse animation (`HexPulseLoader`), so settling never completes. A
      // few explicit frames are enough to let any `animateTo` (the old
      // behaviour) actually play out.
      for (var i = 0; i < 10; i++) {
        await t.pump(const Duration(milliseconds: 50));
      }

      // Still at the top — nothing ever called animateTo.
      expect(scrollable.position.pixels, 0.0);
      expect(t.takeException(), isNull);
    });
  });

  group('acceptance #8 — the headline renders on responded', () {
    testWidgets('read straight from state.agentStances, no new parsing',
        (t) async {
      await _pump(
        t,
        const RoomState(
          streaming: true,
          agentStances: {
            'fundamentals_analyst': AgentStance(
              recorded: true,
              headline: 'Margins beat consensus by 300bps.',
            ),
          },
        ),
      );

      expect(find.text('Margins beat consensus by 300bps.'), findsOneWidget);
      expect(t.takeException(), isNull);
    });
  });

  group(
      'acceptance #9 — the three recorded/headline states render '
      'distinguishably from EACH OTHER', () {
    testWidgets(
        'no-stances-this-run, stated-nothing, and a real headline are three '
        'different renderings — not one collapsed into another', (t) async {
      await _pump(
        t,
        const RoomState(
          streaming: true,
          agentStances: {
            // (a) recorded == false: this run carries no stances at all for
            // this agent. Must show status only — no headline row.
            'fundamentals_analyst': AgentStance(recorded: false),
            // (b) recorded == true, headline == null: finished and stated
            // no view. Must read as an explicit "not stated", never blank
            // and never the same as (a).
            'market_analyst': AgentStance(recorded: true, headline: null),
            // (c) recorded == true, headline present.
            'news_analyst': AgentStance(
              recorded: true,
              headline: 'Headlines skew bullish into earnings.',
            ),
          },
        ),
      );

      // All three responded (agentStances carries a key for each) — three
      // check marks regardless of what each one recorded.
      expect(find.byIcon(Icons.check), findsNWidgets(3));

      // (b) renders the explicit NOT STATED label...
      expect(find.text('NOT STATED'), findsOneWidget);
      // ...(c) renders its own headline verbatim...
      expect(find.text('Headlines skew bullish into earnings.'),
          findsOneWidget);
      // ...and (a) renders NEITHER — proving it is a third, distinct state,
      // not a silent duplicate of (b). If (a) also rendered "NOT STATED"
      // this count would be 2, which is exactly the DEF059-class inversion
      // (stated-nothing collapsed into never-recorded) acceptance #9 exists
      // to catch.
      expect(find.text('NOT STATED'), findsOneWidget);
      expect(t.takeException(), isNull);
    });
  });

  group('DEF174 — per-agent status reaches the accessibility tree', () {
    testWidgets(
        'thinking and responded each carry a semantic label naming the '
        'agent and its state', (t) async {
      final handle = t.ensureSemantics();

      await _pump(
        t,
        const RoomState(
          streaming: true,
          order: ['fundamentals_analyst'],
          activeAgent: 'fundamentals_analyst',
          transcript: {
            'fundamentals_analyst': 'partial thought still streaming',
          },
          agentStances: {
            'news_analyst': AgentStance(recorded: true, headline: null),
          },
        ),
      );

      // `thinking` used to be a colour-changing dot with zero semantics —
      // the exact gap DEF174 reports. A screen-reader-visible label naming
      // both the agent and the state must exist for it now.
      expect(
        find.bySemanticsLabel('Fundamentals Analyst: thinking…'),
        findsOneWidget,
      );
      // `responded` was an Icon(Icons.check) with no semantic label at all.
      expect(
        find.bySemanticsLabel('News Analyst: responded'),
        findsOneWidget,
      );
      // `waiting` (STANDING BY) is covered too, for a roster seat neither
      // active nor recorded — proving the label tracks every branch, not
      // just the two that were silent before the fix.
      expect(
        find.bySemanticsLabel('Trader: standing by'),
        findsOneWidget,
      );
      expect(t.takeException(), isNull);
      handle.dispose();
    });

    testWidgets('interrupted carries its own distinct semantic label',
        (t) async {
      final handle = t.ensureSemantics();

      await _pump(
        t,
        const RoomState(
          streaming: false,
          reconnecting: false,
          done: false,
          error: 'connection dropped',
          order: ['fundamentals_analyst'],
          activeAgent: 'fundamentals_analyst',
          transcript: {'fundamentals_analyst': 'cut off mid-sentence'},
        ),
      );

      expect(
        find.bySemanticsLabel('Fundamentals Analyst: INTERRUPTED'),
        findsOneWidget,
      );
      expect(t.takeException(), isNull);
      handle.dispose();
    });
  });
}

/// Small helper — the live roster's `SingleChildScrollView` is the only
/// scrollable on this screen while a run is live (no board/board-toggle
/// exists yet), so the first `Scrollable` found is unambiguous.
ScrollableState findScrollable(WidgetTester t) =>
    t.state<ScrollableState>(find.byType(Scrollable).first);
