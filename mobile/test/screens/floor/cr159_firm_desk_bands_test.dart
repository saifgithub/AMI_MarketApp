/// CR159 — Your Firm renders the roster as desk-banded tiers.
///
/// What this pins: every agent has a desk and every desk is seated; the bands
/// render top-to-bottom in hierarchy order with each agent in its own band;
/// locked / unlocked visuals and tap behaviour are the ones DEF520 and CR173
/// shipped; nothing overflows or scrolls sideways at 320pt or at 1.3x text; the
/// screen's semantics id is unchanged; and the Verdict Board's consensus comb
/// (`kCombVoices`) seats exactly the same agents as the bands (T-TWICE — two
/// renderers of one roster must agree on membership).
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/agent.dart';
import 'package:ami_trade/models/lessons.dart';
import 'package:ami_trade/qa/semantics_ids.dart';
import 'package:ami_trade/screens/floor/your_firm_screen.dart';
import 'package:ami_trade/state/lessons_providers.dart';
import 'package:ami_trade/widgets/agent_action_sheet.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

class _Lessons extends LessonsNotifier {
  _Lessons(super.ref, Set<String> unlocked) {
    state = LessonsState(activations: [
      for (final id in unlocked)
        AgentActivationRecord(
          userId: 'u',
          agentId: id,
          activationMethod: 'earn_path',
          activatedAt: DateTime(2026, 1, 1),
        ),
    ]);
  }
  @override
  Future<void> refresh() async {}
}

Future<void> _pump(
  WidgetTester t, {
  Set<String> unlocked = const {},
  double width = 390,
  double height = 844,
  double textScale = 1.0,
}) async {
  t.view.physicalSize = Size(width, height);
  t.view.devicePixelRatio = 1.0;
  addTearDown(t.view.reset);
  await t.pumpWidget(ProviderScope(
    overrides: [
      lessonsNotifierProvider.overrideWith((ref) => _Lessons(ref, unlocked)),
    ],
    child: MaterialApp(
      localizationsDelegates: AppLocalizations.localizationsDelegates,
      supportedLocales: AppLocalizations.supportedLocales,
      builder: (context, child) => MediaQuery(
        data: MediaQuery.of(context)
            .copyWith(textScaler: TextScaler.linear(textScale)),
        child: child!,
      ),
      home: const YourFirmScreen(),
    ),
  ));
  await t.pump();
}

Finder _tile(String agentId) =>
    find.widgetWithText(AgentTile, agentById(agentId).displayName);

double _top(WidgetTester t, Finder f) => t.getTopLeft(f).dy;

void main() {
  group('desk data', () {
    test('every agent has a desk and every desk is seated', () {
      for (final d in AgentDesk.values) {
        expect(agentsOnDesk(d), isNotEmpty, reason: '$d has no agents');
      }
      expect(
          AgentDesk.values
              .expand(agentsOnDesk)
              .map((a) => a.id)
              .toSet()
              .length,
          kAllAgents.length);
    });

    test('desks seat the agents the CR names', () {
      List<String> ids(AgentDesk d) => agentsOnDesk(d).map((a) => a.id).toList();
      expect(ids(AgentDesk.officeOfCio), ['portfolio_manager']);
      expect(ids(AgentDesk.analyst), [
        'fundamentals_analyst',
        'market_analyst',
        'news_analyst',
        'social_media_analyst',
      ]);
      expect(ids(AgentDesk.research),
          ['bull_researcher', 'bear_researcher', 'research_manager']);
      expect(ids(AgentDesk.execution), ['trader']);
      expect(ids(AgentDesk.risk),
          ['aggressive_debator', 'conservative_debator', 'neutral_debator']);
      expect(ids(AgentDesk.concierge), ['concierge']);
      expect(kTradingAgents.length, 12);
    });

    test('bands and the consensus comb seat the same agents (T-TWICE)', () {
      final banded = {
        for (final d in AgentDesk.values)
          if (d != AgentDesk.officeOfCio && d != AgentDesk.concierge)
            ...agentsOnDesk(d).map((a) => a.id),
      };
      expect(kCombVoices.map((a) => a.id).toSet(), banded,
          reason: 'comb = every trading agent except the CIO (hero tile)');
    });
  });

  group('rendering', () {
    testWidgets('bands render top to bottom, each agent inside its band',
        (t) async {
      await _pump(t, unlocked: {for (final a in kTradingAgents) a.id});
      final analyst = _top(t, find.text('ANALYST DESK'));
      final research = _top(t, find.text('RESEARCH'));
      final execution = _top(t, find.text('EXECUTION'));
      final risk = _top(t, find.text('RISK'));
      final concierge = _top(t, find.textContaining('CONCIERGE'));
      final you = _top(t, find.text('YOU · CEO'));
      final cio = _top(t, _tile('portfolio_manager'));

      expect(you < cio, isTrue, reason: 'YOU sits above the CIO');
      expect(cio < analyst, isTrue, reason: 'the CIO sits above every desk');
      expect(analyst < research, isTrue);
      expect(research < execution, isTrue);
      expect(research < risk, isTrue);
      expect(execution == risk || (execution < concierge && risk < concierge),
          isTrue);
      expect(risk < concierge, isTrue);

      for (final id in agentsOnDesk(AgentDesk.analyst).map((a) => a.id)) {
        expect(_top(t, _tile(id)) > analyst && _top(t, _tile(id)) < research,
            isTrue,
            reason: '$id belongs in the analyst band');
      }
      for (final id in agentsOnDesk(AgentDesk.research).map((a) => a.id)) {
        expect(_top(t, _tile(id)) > research && _top(t, _tile(id)) < risk,
            isTrue,
            reason: '$id belongs in the research band');
      }
      expect(_top(t, _tile('trader')) > research, isTrue);
      for (final id in agentsOnDesk(AgentDesk.risk).map((a) => a.id)) {
        expect(_top(t, _tile(id)) > research && _top(t, _tile(id)) < concierge,
            isTrue,
            reason: '$id belongs in the risk band');
      }
      expect(_top(t, _tile('concierge')) > concierge, isTrue);
      expect(find.byType(AgentTile), findsNWidgets(13));
      expect(find.text('CONCIERGE — reports to you'), findsOneWidget);
    });

    testWidgets('band counts reflect unlocked seats', (t) async {
      await _pump(t, unlocked: {
        'fundamentals_analyst',
        'market_analyst',
        'bull_researcher',
      });
      expect(find.text('2/4'), findsOneWidget);
      expect(find.text('1/3'), findsOneWidget);
      expect(find.text('0/1'), findsOneWidget);
      expect(find.text('0/3'), findsOneWidget);
    });

    testWidgets('locked tiles keep the dimmed hex and lock glyph',
        (t) async {
      await _pump(t, unlocked: {'fundamentals_analyst'});
      expect(find.byIcon(Icons.lock_outline), findsNWidgets(11));
      final dim = t.widgetList<Opacity>(find.descendant(
          of: find.byType(AgentTile), matching: find.byType(Opacity)));
      expect(dim.where((o) => o.opacity == 0.35).length, 11);
      expect(dim.where((o) => o.opacity == 1.0).length, 2,
          reason: 'one unlocked analyst + the always-open Concierge');
    });

    testWidgets('semantics: the screen id is unchanged', (t) async {
      final h = t.ensureSemantics();
      await _pump(t);
      expect(
          find.semantics.byPredicate(
              (n) => n.identifier == ScreenIds.yourFirmScreen),
          findsOneWidget);
      h.dispose();
    });
  });

  group('taps', () {
    testWidgets('unlocked agent opens the 1-ON-1 / BRIEF chooser', (t) async {
      await _pump(t, unlocked: {'fundamentals_analyst'});
      await t.tap(find.text('FUND'));
      await t.pumpAndSettle();
      expect(find.byType(AgentActionSheet), findsOneWidget);
      expect(find.text('1-ON-1'), findsOneWidget);
    });

    testWidgets('locked agent opens the earn-path sheet', (t) async {
      await _pump(t);
      await t.tap(find.text('BULL'));
      await t.pumpAndSettle();
      expect(find.text('GO TO LESSONS'), findsOneWidget);
      expect(find.byType(AgentActionSheet), findsNothing);
    });
  });

  group('layout', () {
    for (final cfg in const [
      (320.0, 1.0),
      (320.0, 1.3),
      (390.0, 1.3),
    ]) {
      testWidgets('no overflow or sideways scroll at ${cfg.$1}pt, ${cfg.$2}x',
          (t) async {
        await _pump(t,
            unlocked: {'fundamentals_analyst'},
            width: cfg.$1,
            textScale: cfg.$2);
        expect(t.takeException(), isNull);
        for (final tile in t.widgetList<AgentTile>(find.byType(AgentTile))) {
          final r = t.getRect(find.byWidget(tile));
          expect(r.left >= 0 && r.right <= cfg.$1, isTrue,
              reason: '${tile.agent.id} spills past the screen: $r');
        }
        final scrollables = t.widgetList<SingleChildScrollView>(
            find.byType(SingleChildScrollView));
        expect(scrollables.every((s) => s.scrollDirection == Axis.vertical),
            isTrue);
      });
    }

    testWidgets('at 390pt the CIO topper and two bands sit above the fold',
        (t) async {
      await _pump(t, height: 844);
      expect(_top(t, find.text('RESEARCH')) < 844, isTrue);
      expect(_top(t, find.text('ANALYST DESK')) < 844, isTrue);
      expect(_top(t, _tile('portfolio_manager')) < 844, isTrue);
    });

    testWidgets('execution and risk share a band at 390pt, stack at 320pt',
        (t) async {
      await _pump(t, width: 390);
      expect(_top(t, find.text('EXECUTION')), _top(t, find.text('RISK')));
      await _pump(t, width: 320);
      expect(_top(t, find.text('EXECUTION')) < _top(t, find.text('RISK')),
          isTrue);
    });
  });
}
