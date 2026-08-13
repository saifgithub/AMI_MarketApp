/// CR178 — the INSIGHTS render.
///
/// The aggregation is tested in `insights_data_test.dart`. What is left to get
/// wrong is the presentation of it, and the two ways that matters are:
///
///   * **the window has to be on every card**, because this is the deepest
///     surface in the app (3.4 screens of scroll) and a reader who lands
///     mid-list would take an aggregate for all-time; and
///   * **NO VERDICT must not read as a rejection** — it has its own row, its
///     own disclosure, and deliberately not the reject colour, since colour is
///     the fastest way to say the opposite of what the words say.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/screens/you/insights_data.dart';
import 'package:ami_trade/screens/you/insights_providers.dart';
import 'package:ami_trade/screens/you/insights_section.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

Future<void> _pump(WidgetTester t, InsightsData data) async {
  t.view.physicalSize = const Size(390, 844);
  t.view.devicePixelRatio = 1.0;
  addTearDown(t.view.reset);
  await t.pumpWidget(ProviderScope(
    overrides: [insightsProvider.overrideWith((ref) async => data)],
    child: const MaterialApp(
      localizationsDelegates: AppLocalizations.localizationsDelegates,
      supportedLocales: AppLocalizations.supportedLocales,
      home: Scaffold(body: InsightsSection()),
    ),
  ));
  await t.pumpAndSettle();
}

void main() {
  testWidgets('an empty aggregate says what fills it — no zeroed cards',
      (t) async {
    await _pump(t, const InsightsData(entryCount: 0));
    expect(find.text('NOTHING TO AGGREGATE YET'), findsOneWidget);
    expect(find.text('HOW YOUR TRADES ENDED'), findsNothing);
    expect(find.text('WHAT YOUR PM DECIDED'), findsNothing);
    expect(find.text('0'), findsNothing,
        reason: 'CR040 — a figure that cannot be computed must not be rendered '
            'as one that can');
  });

  testWidgets('every card names its window, not just the top of the list',
      (t) async {
    await _pump(
      t,
      const InsightsData(
        entryCount: 40,
        trades: TradesCard(
            counts: {TradeEnding.won: 3, TradeEnding.manual: 2},
            unclassified: 0),
        verdicts: VerdictCard(
            counts: {VerdictOutcome.approve: 4}, noVerdictRecorded: 0),
        analysts: [AnalystCount(agentId: 'trader', count: 3)],
      ),
    );
    // Three cards → three window labels.
    expect(find.text('all 40 of your decisions'), findsNWidgets(3));
    expect(find.textContaining('last 100'), findsNothing,
        reason: 'telling a user with 40 entries that this is their last 100 is '
            'the same lie as an unlabelled all-time claim, pointing the other '
            'way');
  });

  testWidgets('at the cap the label says so', (t) async {
    await _pump(
      t,
      const InsightsData(
        entryCount: kInsightsWindow,
        trades: TradesCard(counts: {TradeEnding.won: 3}, unclassified: 0),
      ),
    );
    expect(find.text('your last 100 decisions'), findsOneWidget);
  });

  testWidgets('NO VERDICT gets its own row and its own disclosure',
      (t) async {
    await _pump(
      t,
      const InsightsData(
        entryCount: 10,
        verdicts: VerdictCard(
          counts: {VerdictOutcome.reject: 2, VerdictOutcome.noVerdict: 3},
          noVerdictRecorded: 0,
        ),
      ),
    );
    expect(find.text('rejected'), findsOneWidget);
    expect(find.text('no verdict'), findsOneWidget);
    expect(find.textContaining('NO VERDICT is not a rejection'), findsOneWidget,
        reason: 'CR098 — without this the row reads as a softer rejection');
  });

  testWidgets('the disclosure is absent when there is nothing to disclose',
      (t) async {
    await _pump(
      t,
      const InsightsData(
        entryCount: 10,
        verdicts: VerdictCard(
            counts: {VerdictOutcome.approve: 4}, noVerdictRecorded: 0),
      ),
    );
    expect(find.textContaining('NO VERDICT is not a rejection'), findsNothing);
  });

  testWidgets('runs that never reached a verdict are surfaced, not swallowed',
      (t) async {
    await _pump(
      t,
      const InsightsData(
        entryCount: 10,
        verdicts: VerdictCard(
            counts: {VerdictOutcome.approve: 4}, noVerdictRecorded: 2),
      ),
    );
    expect(find.textContaining('2 runs ended before a verdict'), findsOneWidget,
        reason: 'so the totals reconcile — a reader who counts 4 out of 6 runs '
            'and finds no explanation concludes the card is broken');
  });

  testWidgets('unclassified closes are disclosed on the trades card',
      (t) async {
    await _pump(
      t,
      const InsightsData(
        entryCount: 10,
        trades: TradesCard(
            counts: {TradeEnding.won: 3, TradeEnding.lost: 1},
            unclassified: 2),
      ),
    );
    expect(find.textContaining('could not be classified'), findsOneWidget);
  });

  testWidgets('the analysts card says what it is not', (t) async {
    await _pump(
      t,
      const InsightsData(
        entryCount: 10,
        analysts: [
          AnalystCount(agentId: 'bull_researcher', count: 4),
          AnalystCount(agentId: 'trader', count: 1),
        ],
      ),
    );
    expect(find.text('Bull Researcher'), findsOneWidget);
    expect(find.textContaining('all twelve speak every run'), findsOneWidget,
        reason: 'the obvious source would have reported participation and '
            'labelled it readership');
  });

  testWidgets('an agent this build does not know renders under its wire id',
      (t) async {
    // DEF210's rule: a wrong-but-plausible name is indistinguishable from a
    // right one.
    await _pump(
      t,
      const InsightsData(
        entryCount: 10,
        analysts: [AnalystCount(agentId: 'quant_analyst', count: 2)],
      ),
    );
    expect(find.text('quant_analyst'), findsOneWidget);
  });

  testWidgets('the challenge card always states that it is unweighted',
      (t) async {
    await _pump(
      t,
      const InsightsData(
        entryCount: 10,
        challenges: ChallengeCard(
          rows: [ChallengeRow(type: 'valuation', attempts: 6, correct: 4)],
          omittedTypes: 2,
        ),
      ),
    );
    expect(find.text('Valuation'), findsOneWidget);
    expect(find.text('4/6 correct'), findsOneWidget);
    expect(find.textContaining('Not weighted by difficulty'), findsOneWidget,
        reason: 'challenge rows carry a difficulty, so an unweighted '
            'comparison must say so');
    expect(find.textContaining('fewer than 5 attempts'), findsOneWidget);
  });

  testWidgets('a loosened limit is called loosened', (t) async {
    await _pump(
      t,
      const InsightsData(
        entryCount: 10,
        mandate: MandateCard(
          editCount: 3,
          moves: [
            LimitMove(field: 'max_drawdown_pct', from: 20, to: 40),
            LimitMove(field: 'sector_cap_pct', from: 40, to: 25),
          ],
        ),
      ),
    );
    expect(find.text('3 edits'), findsOneWidget);
    expect(find.text('Max drawdown'), findsOneWidget);
    expect(find.text('20 → 40'), findsOneWidget);
    expect(find.text('loosened'), findsOneWidget);
    expect(find.text('tightened'), findsOneWidget);
  });

  testWidgets('edits that moved no limit say so rather than showing a blank',
      (t) async {
    await _pump(
      t,
      const InsightsData(
        entryCount: 10,
        mandate: MandateCard(editCount: 2, moves: []),
      ),
    );
    expect(find.textContaining('No limit moved'), findsOneWidget);
  });
}
