// CR136 M09 — six card states, partial chip, tile absence, CTA states.

import 'dart:async';

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/portfolio_health.dart';
import 'package:ami_trade/widgets/portfolio_health/health_chrome.dart';
import 'package:ami_trade/services/billing/purchase_models.dart';
import 'package:ami_trade/services/billing/purchase_service.dart';
import 'package:ami_trade/state/mandate_providers.dart';
import 'package:ami_trade/state/portfolio_health_providers.dart';
import 'package:ami_trade/state/purchase_providers.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:ami_trade/widgets/hex/accent_card.dart';
import 'package:ami_trade/widgets/hex/hex_button.dart';
import 'package:ami_trade/widgets/hex/hex_pulse_loader.dart';
import 'package:ami_trade/widgets/empty_state.dart';
import 'package:ami_trade/widgets/portfolio_health/health_card.dart';
import 'package:ami_trade/widgets/portfolio_health/risk_money_bars.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import '../support/portfolio_health_fixtures.dart';

/// Directional isolates, spelled as escapes: the card wraps every interpolated
/// numeric run, so an expected string that omits them silently never matches.
String _iso(String s) => '\u2066$s\u2069';

/// No RC offering — the paywall's degrade card. Enough to prove the sheet
/// opened without touching a platform channel.
class _NoOfferingService implements PurchaseService {
  @override
  bool get isConfigured => false;
  @override
  Future<PaywallOffering?> fetchOffering() async => null;
  @override
  Future<PurchaseOutcome> purchase(PaywallPackage pkg) async =>
      PurchaseOutcome.notConfigured;
  @override
  Future<PurchaseOutcome> restore() async => PurchaseOutcome.notConfigured;
}

class _QuietMandateNotifier extends MandateNotifier {
  _QuietMandateNotifier(super.ref);
  @override
  Future<void> refresh() async {}
}

Widget _harness({
  PortfolioHealth? health,
  bool loading = false,
  bool failing = false,
  bool disableAnimations = false,
  TextDirection direction = TextDirection.ltr,
}) =>
    ProviderScope(
      overrides: [
        purchaseServiceProvider.overrideWithValue(_NoOfferingService()),
        mandateNotifierProvider.overrideWith(_QuietMandateNotifier.new),
        portfolioHealthProvider.overrideWith((ref) {
          if (loading) return Completer<PortfolioHealth>().future;
          if (failing) throw Exception('transport');
          return health ?? healthFixture();
        }),
      ],
      child: MaterialApp(
        localizationsDelegates: AppLocalizations.localizationsDelegates,
        supportedLocales: AppLocalizations.supportedLocales,
        home: Directionality(
          textDirection: direction,
          child: Scaffold(
            body: SingleChildScrollView(
              child: Builder(
                builder: (context) => MediaQuery(
                  data: MediaQuery.of(context)
                      .copyWith(disableAnimations: disableAnimations),
                  child: const PortfolioHealthCard(),
                ),
              ),
            ),
          ),
        ),
      ),
    );

Future<void> _pump(
  WidgetTester tester, {
  PortfolioHealth? health,
  bool loading = false,
  bool failing = false,
  bool disableAnimations = false,
  TextDirection direction = TextDirection.ltr,
}) async {
  tester.view.physicalSize = const Size(390, 844);
  tester.view.devicePixelRatio = 1.0;
  addTearDown(tester.view.reset);

  await tester.pumpWidget(_harness(
    health: health,
    loading: loading,
    failing: failing,
    disableAnimations: disableAnimations,
    direction: direction,
  ));
  await tester.pump();
  await tester.pump(AmiMotion.fast);
}

/// Every colour the card actually paints or writes with, so an assertion about
/// amber cannot be satisfied by looking in the wrong place.
Set<Color> _colours(WidgetTester tester) {
  final out = <Color>{};
  for (final text in tester.widgetList<Text>(find.byType(Text))) {
    final c = text.style?.color;
    if (c != null) out.add(c);
  }
  for (final container in tester.widgetList<Container>(find.byType(Container))) {
    final d = container.decoration;
    if (d is BoxDecoration) {
      if (d.color != null) out.add(d.color!);
      final border = d.border;
      if (border is Border) out.add(border.top.color);
    }
  }
  return out;
}

/// `dataMd` is the metric-value register: mono, 16pt. Nothing else in the card
/// may wear it, which is what makes "this state renders no value" checkable.
bool _rendersAMetricValue(WidgetTester tester) =>
    tester.widgetList<Text>(find.byType(Text)).any((t) =>
        t.style?.fontSize == AmiTypography.dataMd.fontSize &&
        t.style?.fontFamily == AmiTypography.dataMd.fontFamily);


/// A populated fixture whose top-3 risk rows are exactly [rows].
Map<String, dynamic> _blocksWithRisk(List<Map<String, dynamic>> rows) {
  final blocks = defaultBlocks();
  blocks['risk_contribution'] = blockJson(
    'risk_contribution',
    value: rows.first['risk_share'] as double,
    basis: 'invested_sleeve',
    extensions: {'per_holding': rows},
  );
  return blocks;
}

void main() {
  group('1 — populated', () {
    testWidgets('accent is hexBlue, tiles render, caption and CTA are present',
        (tester) async {
      await _pump(tester);

      final card = tester.widget<AccentCard>(find.byType(AccentCard));
      expect(card.accent, AmiColors.hexBlue,
          reason: 'amber means a mandate violation app-wide; a measurement is '
              'not a warning');

      expect(find.text('VOLATILITY'), findsOneWidget);
      expect(find.text('BETA'), findsOneWidget);
      expect(find.text('EFFECTIVE BETS'), findsOneWidget);
      expect(find.text('INVESTED WEIGHT CONCENTRATION'), findsOneWidget);

      // Tier-1 fractions, scaled exactly once: 0.1898 → 19.0 at 1 dp, beta is
      // a ratio at 2 dp, DR² at 1 dp.
      expect(find.text(_iso('19.0')), findsOneWidget);
      expect(find.text(_iso('1.07')), findsOneWidget);
      expect(find.text(_iso('2.4')), findsOneWidget);
      expect(find.text('S&P 500 ${_iso('15.1')}%'), findsOneWidget);
      expect(find.text(_iso('3.8')), findsOneWidget);

      expect(find.text('CASH · ${_iso('17')}% OF TOTAL BOOK'), findsOneWidget);
      expect(find.text('FULL FINDING'), findsOneWidget);
    });

    testWidgets('the bars are one tap away, and the caption comes with them',
        (tester) async {
      await _pump(tester);

      // Collapsed by default: the card measured 803pt fully expanded, a whole
      // screen on a tab CR120 budgets at three.
      expect(find.byType(RiskMoneyBars), findsNothing);
      expect(find.text('RISK VS MONEY'), findsOneWidget);
      expect(find.byIcon(Icons.expand_more), findsOneWidget);

      await tester.tap(find.text('RISK VS MONEY'));
      await tester.pump();

      expect(find.byType(RiskMoneyBars), findsOneWidget);
      expect(find.byIcon(Icons.expand_less), findsOneWidget);
      expect(
        find.text(
          'Shares of invested risk and invested money; cash is shown on its '
          'own line. Not a forecast and not a return.',
        ),
        findsOneWidget,
        reason: 'the amendment-1 caption is mandatory and verbatim, and it '
            'ships in the same block as the bars so no state can draw one '
            'without the other',
      );
      expect(find.text('RISK'), findsOneWidget);
      expect(find.text('MONEY'), findsOneWidget);
    });

    testWidgets('no number animates — the card fades, nothing counts up',
        (tester) async {
      await _pump(tester);
      final inCard = find.descendant(
        of: find.byType(AccentCard),
        matching: find.byType(AnimatedDefaultTextStyle),
      );
      expect(inCard, findsNothing);
      // A count-up needs a rebuilding tween somewhere inside the card.
      expect(
        find.descendant(
          of: find.byType(AccentCard),
          matching: find.byType(TweenAnimationBuilder<double>),
        ),
        findsNothing,
      );
    });
  });

  group('2 — insufficient', () {
    testWidgets('no result chrome, no metric value, neutral slate',
        (tester) async {
      await _pump(tester, health: healthFixture(blocks: insufficientBlocks()));

      expect(find.byType(AccentCard), findsNothing,
          reason: 'an error state must not be shaped like a result (07b)');
      expect(find.text('VOLATILITY'), findsNothing);
      expect(find.text('NOT ENOUGH HISTORY YET'), findsOneWidget);
      expect(
        find.text("Price history available to AMI's engine covers "
            '${_iso('47')} trading days; 126 needed.'),
        findsOneWidget,
      );
      expect(_colours(tester).contains(AmiColors.hexAmber), isFalse,
          reason: 'an absence of measurement is not a warning');
      expect(_rendersAMetricValue(tester), isFalse,
          reason: 'the 47/126 shortfall lives in the reason copy; no value may '
              'render in the metric register');
    });

    testWidgets('a dropped-weight cause names coverage, not the window',
        (tester) async {
      await _pump(
        tester,
        health: healthFixture(
          blocks: insufficientBlocks(cause: 'dropped_weight_exceeded'),
          coveredInvestedValue: 62000,
        ),
      );
      expect(
        find.text('Usable price history covers ${_iso('62')}% of invested '
            'value; AMI needs at least 80%.'),
        findsOneWidget,
      );
    });

    testWidgets('a gappy feed names the gap, not the book', (tester) async {
      // DEF213. 251 observations across 585 calendar days is the 40%-gaps arm
      // of that defect's own measurement: nothing was dropped, `partial` is
      // false, and the pre-guard engine published a σ overstated by 29.8% as a
      // clean measurement. The generic body would be TRUE here — AMI could not
      // measure — but it reads as a limit of the user's book, and this one is a
      // limit of the feed.
      await _pump(
        tester,
        health: healthFixture(
          blocks: insufficientBlocks(
            cause: 'sparse_grid',
            nObservations: 251,
            windowDays: 585,
          ),
        ),
      );
      expect(
        find.text("Price history available to AMI's engine has gaps: "
            '${_iso('251')} trading days spread across ${_iso('585')} '
            'calendar days.'),
        findsOneWidget,
      );
      expect(
        find.text("AMI could not measure this book's risk over the available "
            'window.'),
        findsNothing,
        reason: 'sparse_grid has pinned copy; falling to the generic body '
            'would lose the only fact the user can act on',
      );
      expect(_colours(tester).contains(AmiColors.hexAmber), isFalse,
          reason: 'a feed with holes is not a warning about the book');
      expect(_rendersAMetricValue(tester), isFalse,
          reason: 'the counts live in the reason copy; no value may render in '
              'the metric register');
    });

    testWidgets('an unpinned cause still says something', (tester) async {
      await _pump(
        tester,
        health:
            healthFixture(blocks: insufficientBlocks(cause: 'zero_variance')),
      );
      expect(
        find.text("AMI could not measure this book's risk over the available "
            'window.'),
        findsOneWidget,
        reason: 'a state with no explanation at all is the CR040 hole',
      );
    });
  });

  group('3 — refusal', () {
    testWidgets('amber title and body, no tiles and no values', (tester) async {
      await _pump(tester, health: PortfolioHealth.fromJson(refusalJson()));
      expect(find.text('LIVE MARKET DATA IS OFF'), findsOneWidget);
      expect(
        find.textContaining('will not compute these numbers from simulated'),
        findsOneWidget,
      );
      expect(_colours(tester).contains(AmiColors.hexAmber), isTrue,
          reason: 'an unavailable system is a real exclusion');
      expect(find.byType(AccentCard), findsNothing);
      expect(_rendersAMetricValue(tester), isFalse);
    });
  });

  group('4 — partial', () {
    testWidgets('populated, plus the chip, the excluded ticker and coverage',
        (tester) async {
      await _pump(
        tester,
        health: healthFixture(
          partial: true,
          droppedHoldings: const [
            {'ticker': 'RIVN', 'reason': 'short_history'},
          ],
          coveredInvestedValue: 87000,
        ),
      );
      expect(find.byType(AccentCard), findsOneWidget);
      expect(find.text('PARTIAL'), findsOneWidget);
      expect(
        find.text('Excludes ${_iso('RIVN')}. Numbers describe '
            '${_iso('87')}% of invested value.'),
        findsOneWidget,
      );
      final card = tester.widget<AccentCard>(find.byType(AccentCard));
      expect(card.accent, AmiColors.hexBlue,
          reason: 'the chip is amber; the accent never is');
    });
  });

  group('5 — empty', () {
    testWidgets('empty state with no CTA of its own', (tester) async {
      await _pump(tester, health: PortfolioHealth.fromJson(noHoldingsJson()));
      expect(find.byType(AmiEmptyState), findsOneWidget);
      expect(find.text('NO HOLDINGS TO MEASURE'), findsOneWidget);
      expect(find.byType(HexButton), findsNothing);
      expect(find.byType(ElevatedButton), findsNothing,
          reason: "the Positions tab's new-trader hint owns the trade CTA");
    });
  });

  group('6 — loading, and the transport failure beside it', () {
    testWidgets('loading shows the pulse loader and no card', (tester) async {
      await _pump(tester, loading: true);
      expect(find.byType(HexPulseLoader), findsOneWidget);
      expect(find.byType(AccentCard), findsNothing);
    });

    testWidgets('a failed fetch is slate with a retry, not an amber refusal',
        (tester) async {
      await _pump(tester, failing: true);
      expect(find.text("AMI's engine did not respond. Tap to retry."),
          findsOneWidget);
      expect(_colours(tester).contains(AmiColors.hexAmber), isFalse,
          reason: 'a failed fetch is not an engine refusal');
      expect(find.byType(InkWell), findsOneWidget);
    });
  });

  group('7 — a tile that is not there', () {
    testWidgets('t_over_n keeps vol and beta, drops bets and the bars',
        (tester) async {
      final blocks = defaultBlocks();
      blocks['effective_bets'] = blockJson(
        'effective_bets',
        sufficient: false,
        insufficientCause: 't_over_n',
        basis: 'invested_sleeve',
        nObservations: 130,
      );
      blocks['risk_contribution'] = blockJson(
        'risk_contribution',
        sufficient: false,
        insufficientCause: 't_over_n',
        basis: 'invested_sleeve',
        nObservations: 130,
      );
      await _pump(
        tester,
        health: healthFixture(blocks: blocks, riskyHoldingsCount: 22),
      );

      expect(find.text('VOLATILITY'), findsOneWidget);
      expect(find.text('BETA'), findsOneWidget);
      expect(find.text('EFFECTIVE BETS'), findsNothing,
          reason: 'sufficient:false ⇒ no tile — absent, not dashed');
      expect(find.byType(RiskMoneyBars), findsNothing);
      expect(find.text('RISK VS MONEY'), findsNothing,
          reason: 'no breakdown exists to expand, so there is nothing to tap');
      expect(
        find.text('${_iso('130')} aligned trading days across ${_iso('22')} '
            'holdings — too few for AMI to attribute risk reliably.'),
        findsOneWidget,
      );
    });

    testWidgets('a misaligned benchmark drops the beta tile and says why',
        (tester) async {
      final blocks = defaultBlocks();
      blocks['beta'] = blockJson(
        'beta',
        sufficient: false,
        insufficientCause: 'benchmark_misaligned',
      );
      await _pump(tester, health: healthFixture(blocks: blocks));
      expect(find.text('BETA'), findsNothing);
      expect(find.textContaining('did not align with this book'),
          findsOneWidget);
    });

    // M04 audit r1, MAJOR M1. A SPY feed outage is the ordinary Yahoo
    // rate-limit case, and it used to delete the beta tile with nothing in its
    // place: no note, no placeholder, no change in the card's chrome, so the
    // card still read as a complete measurement. The reader could not tell
    // "beta was not measured" from "beta does not apply to this book".
    testWidgets('a benchmark feed outage drops the beta tile and still says so',
        (tester) async {
      final blocks = defaultBlocks();
      blocks['beta'] = blockJson(
        'beta',
        sufficient: false,
        insufficientCause: kCauseFeedUnavailable,
      );
      await _pump(tester, health: healthFixture(blocks: blocks));
      expect(find.text('BETA'), findsNothing);
      expect(find.textContaining('could not measure this book\'s beta'),
          findsOneWidget);
      expect(find.textContaining('did not align with this book'), findsNothing,
          reason: 'a feed outage is not a misaligned benchmark — the generic '
              'note must not claim a cause the engine never reported');
    });

    // The same closure, one cause the engine cannot currently emit onto a
    // populated card. It is the branch, not the cause list, that has to hold.
    testWidgets('a cause the card has no copy for still gets a note',
        (tester) async {
      final blocks = defaultBlocks();
      blocks['beta'] = blockJson(
        'beta',
        sufficient: false,
        insufficientCause: 'a_cause_minted_after_this_build_shipped',
      );
      await _pump(tester, health: healthFixture(blocks: blocks));
      expect(find.text('BETA'), findsNothing);
      expect(find.textContaining('could not measure this book\'s beta'),
          findsOneWidget);
    });

    // M04 audit r2, MINOR m3. The same closure on the two blocks the r2 fix
    // volunteered beyond the finding: both reverted invisibly under the
    // auditor's MUT-H and MUT-I, so the behaviour was right and nothing held it
    // there. Neither state is reachable from the engine today — effective bets
    // has only `t_over_n` on a populated card, and any cause that makes
    // volatility insufficient makes all four core metrics insufficient and
    // switches the whole card to its insufficient state.
    testWidgets('effective bets insufficient for an unpinned cause still says so',
        (tester) async {
      final blocks = defaultBlocks();
      blocks['effective_bets'] = blockJson(
        'effective_bets',
        sufficient: false,
        insufficientCause: 'a_cause_minted_after_this_build_shipped',
      );
      await _pump(tester, health: healthFixture(blocks: blocks));
      expect(find.text('EFFECTIVE BETS'), findsNothing);
      expect(find.textContaining('how many independent bets'), findsOneWidget);
      expect(find.textContaining('aligned trading days'), findsNothing,
          reason: 'the T/N copy names a ratio the engine never reported');
    });

    testWidgets('volatility insufficient on a populated card still says so',
        (tester) async {
      final blocks = defaultBlocks();
      blocks['portfolio_volatility'] = blockJson(
        'portfolio_volatility',
        sufficient: false,
        insufficientCause: kCauseZeroVariance,
      );
      await _pump(tester, health: healthFixture(blocks: blocks));
      expect(find.text('VOLATILITY'), findsNothing);
      expect(find.textContaining('could not measure this book\'s volatility'),
          findsOneWidget);
      expect(find.text('BETA'), findsOneWidget,
          reason: 'the card must still be the POPULATED one — otherwise this '
              'asserts against the insufficient state and proves nothing');
    });

    // M04 audit r2, MINOR m2. `risk_contribution` gates the bars, the largest
    // element on the card, and had no note branch at all: the auditor pumped a
    // seventh share-basis cause and got a card whose bars were gone and whose
    // only note spoke to effective bets.
    testWidgets('risk attribution lost to an unpinned cause takes the bars '
        'and says why', (tester) async {
      final blocks = defaultBlocks();
      // The engine feeds both share-basis blocks from one variable, so they go
      // insufficient together with the same cause. Pumping only one would test
      // a state the wire cannot carry.
      for (final m in ['risk_contribution', 'effective_bets']) {
        blocks[m] = blockJson(
          m,
          sufficient: false,
          insufficientCause: 'a_share_cause_minted_after_this_build_shipped',
        );
      }
      await _pump(tester, health: healthFixture(blocks: blocks));
      expect(find.byType(RiskMoneyBars), findsNothing);
      expect(find.textContaining('how this book\'s risk splits'), findsOneWidget);
    });

    // The dedupe, asserted rather than assumed: on `t_over_n` both share-basis
    // blocks are insufficient with one cause and one note covers both, so the
    // note must appear ONCE — the reason every branch can stay keyed on
    // insufficiency without asking what another block's cause was.
    testWidgets('the shared T/N note is not printed twice', (tester) async {
      final blocks = defaultBlocks();
      for (final m in ['risk_contribution', 'effective_bets']) {
        blocks[m] = blockJson(
          m,
          sufficient: false,
          insufficientCause: kCauseTOverN,
          nObservations: 130,
        );
      }
      await _pump(tester, health: healthFixture(blocks: blocks));
      expect(find.byType(RiskMoneyBars), findsNothing);
      expect(find.textContaining('aligned trading days'), findsOneWidget);
      expect(find.textContaining('how this book\'s risk splits'), findsNothing,
          reason: 'the T/N copy already covers the bars; the generic note would '
              'be a second explanation of one fact');
    });
  });

  group('8 — Tier-2 max drawdown', () {
    testWidgets('absent from the wire renders nothing at all', (tester) async {
      await _pump(tester);
      expect(find.text('MAX DRAWDOWN'), findsNothing);
      expect(find.textContaining('daily snapshots so far'), findsNothing,
          reason: 'an absent block is silent — a note would imply a Tier-2 '
              'pipeline the wire never mentioned');
    });

    testWidgets('present but insufficient renders the note, not a tile',
        (tester) async {
      final blocks = defaultBlocks();
      blocks['realised_max_drawdown'] = blockJson(
        'realised_max_drawdown',
        sufficient: false,
        insufficientCause: 'short_window',
        nObservations: 9,
      );
      await _pump(tester, health: healthFixture(blocks: blocks));
      expect(find.text('MAX DRAWDOWN'), findsNothing);
      expect(
        find.text('${_iso('9')} daily snapshots so far; realised drawdown '
            'needs 21.'),
        findsOneWidget,
      );
    });

    testWidgets('sufficient renders the tile with its window, unscaled',
        (tester) async {
      final blocks = defaultBlocks();
      blocks['realised_max_drawdown'] = blockJson(
        'realised_max_drawdown',
        value: 19.69,
        windowDays: 90,
        nObservations: 62,
      );
      await _pump(tester, health: healthFixture(blocks: blocks));
      expect(find.text('MAX DRAWDOWN'), findsOneWidget);
      expect(find.text('${_iso('19.7')}%'), findsOneWidget,
          reason: 'already percent on the wire — scaling it again is the '
              '1969.00% bug M06 shipped');
      expect(
        find.text('TRAILING ${_iso('90')}-DAY WINDOW · REALISED'),
        findsOneWidget,
      );
    });
  });

  group('9 — the CTA', () {
    test('derivation at every boundary', () {
      HealthGateStatus g({
        String mode = 'plan',
        bool trialActive = false,
        bool planHasAccess = true,
        int dailyUsed = 0,
        int dailyCap = 2,
      }) =>
          HealthGateStatus.fromJson(gateJson(
            mode: mode,
            trialActive: trialActive,
            planHasAccess: planHasAccess,
            dailyUsed: dailyUsed,
            dailyCap: dailyCap,
          ));

      expect(deriveHealthCta(g(dailyUsed: 1)), HealthCtaState.generate);
      expect(deriveHealthCta(g(dailyUsed: 2)), HealthCtaState.dailyCap);
      expect(deriveHealthCta(g(dailyUsed: 3)), HealthCtaState.dailyCap);
      expect(deriveHealthCta(g(planHasAccess: false)), HealthCtaState.upgrade);
      expect(
        deriveHealthCta(
            g(mode: 'trial', trialActive: true, planHasAccess: false)),
        HealthCtaState.trial,
      );
      expect(
        deriveHealthCta(
            g(mode: 'trial', trialActive: true, planHasAccess: true)),
        HealthCtaState.generate,
        reason: 'a subscriber is not on trial',
      );
      expect(
        deriveHealthCta(
            g(mode: 'trial', trialActive: false, planHasAccess: false)),
        HealthCtaState.upgrade,
      );
      expect(
        deriveHealthCta(
            g(mode: 'open', trialActive: false, planHasAccess: false)),
        HealthCtaState.generate,
        reason: 'open mode gates nobody',
      );
      expect(
        deriveHealthCta(g(mode: 'open', planHasAccess: false, dailyUsed: 2)),
        HealthCtaState.dailyCap,
        reason: 'the daily cap applies in open mode too',
      );
    });

    testWidgets('the cap disables the button and states the numbers',
        (tester) async {
      await _pump(
        tester,
        health: healthFixture(gate: gateJson(dailyUsed: 2, dailyCap: 2)),
      );
      final button = tester.widget<HexButton>(find.byType(HexButton));
      expect(button.onPressed, isNull);
      expect(
        find.text('${_iso('2')} of ${_iso('2')} Findings used today. '
            'Available again tomorrow.'),
        findsOneWidget,
      );
    });

    testWidgets('the trial chip states both numbers', (tester) async {
      await _pump(
        tester,
        health: healthFixture(
          gate: gateJson(
            mode: 'trial',
            trialActive: true,
            planHasAccess: false,
            trialFindingsUsed: 2,
            trialFindingsBudget: 7,
            trialDaysLeft: 9,
          ),
        ),
      );
      expect(
        find.text('${_iso('5')} of ${_iso('7')} trial Findings left · '
            '${_iso('9')} days'),
        findsOneWidget,
      );
      expect(
        tester.widget<HexButton>(find.byType(HexButton)).onPressed,
        isNotNull,
      );
    });

    testWidgets('a closed gate offers plans and opens the sheet',
        (tester) async {
      await _pump(
        tester,
        health: healthFixture(gate: gateJson(planHasAccess: false)),
      );
      expect(
        find.text('Findings are included in Trader and Floor Manager plans.'),
        findsOneWidget,
      );
      await tester.tap(find.text('SEE PLANS'));
      await tester.pumpAndSettle();
      expect(find.text('Upgrade your desk'), findsOneWidget);
    });

    testWidgets('tiles are never gated', (tester) async {
      await _pump(
        tester,
        health: healthFixture(gate: gateJson(planHasAccess: false)),
      );
      expect(find.text('VOLATILITY'), findsOneWidget);
      await tester.tap(find.text('RISK VS MONEY'));
      await tester.pump();
      expect(find.byType(RiskMoneyBars), findsOneWidget,
          reason: 'Rev 4: only the written Finding is gated');
    });
  });

  group('10 — motion', () {
    testWidgets('reduced motion lands at full opacity on the first frame',
        (tester) async {
      tester.view.physicalSize = const Size(390, 844);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(tester.view.reset);

      await tester.pumpWidget(_harness(disableAnimations: true));
      await tester.pump();

      expect(tester.widget<Opacity>(find.byKey(healthFadeKey)).opacity, 1.0);
    });

    testWidgets('otherwise it fades once, over AmiMotion.fast', (tester) async {
      tester.view.physicalSize = const Size(390, 844);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(tester.view.reset);

      await tester.pumpWidget(_harness(loading: true));
      await tester.pump();
      expect(
        tester.widget<Opacity>(find.byKey(healthFadeKey)).opacity,
        lessThan(1.0),
        reason: 'the fade is real, not a no-op wrapper',
      );

      await tester.pump(AmiMotion.fast);
      expect(tester.widget<Opacity>(find.byKey(healthFadeKey)).opacity, 1.0);
    });
  });

  group('11 — RTL', () {
    testWidgets('the bar axis stays LTR and numbers carry isolates',
        (tester) async {
      await _pump(tester, direction: TextDirection.rtl);
      await tester.tap(find.text('RISK VS MONEY'));
      await tester.pump();

      final inner = tester.widget<Directionality>(
        find.descendant(
          of: find.byType(RiskMoneyBars),
          matching: find.byType(Directionality),
        ),
      );
      expect(inner.textDirection, TextDirection.ltr);

      final cash =
          tester.widgetList<Text>(find.textContaining('CASH ·')).single;
      expect(cash.data, contains('\u2066'),
          reason: 'CR106 T-BIDI: an unisolated numeric run reorders under RTL');
    });
  });

  group('12 — nothing to divide by', () {
    testWidgets('an empty covered sleeve draws no bars', (tester) async {
      await _pump(
        tester,
        health: healthFixture(
          investedValue: 0,
          coveredInvestedValue: 0,
          cashFraction: 1.0,
        ),
      );
      expect(find.byType(RiskMoneyBars), findsNothing,
          reason: 'never 0/0 — defence in depth behind the no_holdings path');
      expect(find.text('RISK VS MONEY'), findsNothing);
      expect(find.text('CASH · ${_iso('100')}% OF TOTAL BOOK'), findsOneWidget);
    });
  });

  group('13 — findings from the M09 audit', () {
    testWidgets('an all-positive book draws no negative caveat', (tester) async {
      await _pump(tester);
      await tester.tap(find.text('RISK VS MONEY'));
      await tester.pump();
      expect(
        find.text('A negative share means this holding offset risk over the '
            'window.'),
        findsNothing,
        reason: 'every share in the default fixture is positive',
      );
    });

    testWidgets('a drawn negative share carries its caveat', (tester) async {
      await _pump(
        tester,
        health: healthFixture(
          blocks: _blocksWithRisk(const [
            {'ticker': 'NVDA', 'invested_weight': 0.50, 'risk_share': 0.612},
            {'ticker': 'AAPL', 'invested_weight': 0.30, 'risk_share': 0.458},
            {'ticker': 'TLT', 'invested_weight': 0.20, 'risk_share': -0.0704},
          ]),
        ),
      );
      await tester.tap(find.text('RISK VS MONEY'));
      await tester.pump();
      expect(
        find.text('A negative share means this holding offset risk over the '
            'window.'),
        findsOneWidget,
      );
      expect(find.textContaining('-7%'), findsOneWidget,
          reason: 'the caveat explains a number the reader can see');
    });

    testWidgets('a negative share that rounds to 0% draws no caveat',
        (tester) async {
      await _pump(
        tester,
        health: healthFixture(
          blocks: _blocksWithRisk(const [
            {'ticker': 'NVDA', 'invested_weight': 0.50, 'risk_share': 0.700},
            {'ticker': 'AAPL', 'invested_weight': 0.30, 'risk_share': 0.304},
            {'ticker': 'TLT', 'invested_weight': 0.20, 'risk_share': -0.004},
          ]),
        ),
      );
      await tester.tap(find.text('RISK VS MONEY'));
      await tester.pump();
      expect(
        find.text('A negative share means this holding offset risk over the '
            'window.'),
        findsNothing,
        reason: 'the row prints 0%; a caveat about a negative number the '
            'reader cannot see explains nothing',
      );
    });

    testWidgets('a status this build does not know never renders as a result',
        (tester) async {
      for (final status in const ['', 'refused_stale_data', 'partially_ok']) {
        final json = healthJson()..['status'] = status;
        (json['metrics'] as Map)['status'] = status;
        await _pump(tester, health: PortfolioHealth.fromJson(json));

        expect(find.byType(AccentCard), findsNothing,
            reason: 'status "$status" is not one of the three pinned values, '
                'and a wire divergence must not wear the visual grammar of a '
                'real measurement (CR040)');
        expect(find.text('VOLATILITY'), findsNothing);
        expect(
          find.textContaining('does not recognise'),
          findsOneWidget,
          reason: 'the card says what happened rather than showing nothing',
        );
      }
    });

    testWidgets('a low-R² beta says what it means and never prints "R²"',
        (tester) async {
      final blocks = defaultBlocks();
      blocks['beta'] = blockJson(
        'beta',
        value: 0.94,
        lowExplanatoryPower: true,
        extensions: {'r_squared': 0.31},
      );
      await _pump(tester, health: healthFixture(blocks: blocks));

      expect(find.text('BETA'), findsOneWidget);
      expect(
        find.text('Market explains ${_iso('31')}% of daily moves'),
        findsOneWidget,
      );
      final copy = tester
          .widgetList<Text>(find.byType(Text))
          .map((t) => t.data ?? '')
          .join(' ');
      expect(copy.contains('R²'), isFalse,
          reason: 'amendment 7: the card is the §F1 register — the literal '
              'glyph belongs in the Finding, not on a tile');
    });

    testWidgets('a high-R² beta carries no explanatory note', (tester) async {
      await _pump(tester);
      expect(find.textContaining('Market explains'), findsNothing,
          reason: 'the default fixture has low_explanatory_power false');
    });

    testWidgets('an ETF in the book discloses what AMI did not look through',
        (tester) async {
      final blocks = defaultBlocks();
      blocks['weight_concentration'] = blockJson(
        'weight_concentration',
        value: 0.2650,
        basis: 'weights',
        backcast: false,
        containsEtfs: true,
        extensions: {'effective_n': 3.8, 'holdings_count': 6},
      );
      await _pump(tester, health: healthFixture(blocks: blocks));
      expect(find.text('ETF OVERLAP NOT COUNTED'), findsOneWidget);
    });

    testWidgets('no ETF, no chip', (tester) async {
      await _pump(tester);
      expect(find.text('ETF OVERLAP NOT COUNTED'), findsNothing);
    });

    testWidgets('no benchmark, no comparison line', (tester) async {
      await _pump(tester, health: healthFixture(benchmarkVolAnn: null));
      expect(find.text('VOLATILITY'), findsOneWidget,
          reason: 'the tile itself does not depend on the benchmark');
      expect(find.textContaining('S&P 500 \u2066'), findsNothing,
          reason: 'no comparison exists, so none is drawn — never "null%". '
              'The BETA tile\'s own unit line also says "S&P 500", so the '
              'assertion keys on the interpolated number that follows it');
    });
  });
}
