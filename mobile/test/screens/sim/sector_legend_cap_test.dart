/// CR118 — the sector-allocation legend is capped and scrolls inside its card.
///
/// The bug this pins is forward-looking: the reporter's own portfolio is 89.3%
/// cash and fits fine. The legend rendered every sector inline, so the card's
/// height grew with diversification — the one behaviour the product actively
/// encourages. So every assertion here is measured against a **13-sector**
/// fixture (11 GICS sectors + Cash + Other), not the four in the screenshot.
///
/// The measurements are read off the render tree — `getSize` on the legend
/// viewport and on the card itself — rather than asserting that some widget
/// exists, because "it is capped" is a claim about height, and a `shrinkWrap`
/// list would satisfy a widget-existence check while silently re-expanding to
/// full content height.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/alpaca.dart';
import 'package:ami_trade/models/sim.dart';
import 'package:ami_trade/screens/sim/portfolio_screen.dart';
import 'package:ami_trade/state/alpaca_providers.dart';
import 'package:ami_trade/state/journal_providers.dart';
import 'package:ami_trade/state/sim_providers.dart';
import 'package:ami_trade/state/watchlist_providers.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

class _FixedSimNotifier extends SimNotifier {
  _FixedSimNotifier(super.ref, SimState fixed) {
    state = fixed;
  }
}

class _FixedWatchlistNotifier extends WatchlistNotifier {
  _FixedWatchlistNotifier(super.ref, WatchlistState fixed) {
    state = fixed;
  }
}

class _FixedJournalNotifier extends JournalNotifier {
  _FixedJournalNotifier(super.ref, JournalState fixed) {
    state = fixed;
  }
}

/// The 11 GICS sectors the backend classifies to, plus Cash and Other — the
/// realistic ceiling CR118 names, and roughly triple the shipped screenshot.
const _kThirteenSectors = <String>[
  'Cash',
  'Information Technology',
  'Health Care',
  'Financials',
  'Consumer Discretionary',
  'Communication Services',
  'Industrials',
  'Consumer Staples',
  'Energy',
  'Utilities',
  'Real Estate',
  'Materials',
  'Other',
];

SectorAllocation _allocation(int sectorCount) {
  final names = _kThirteenSectors.take(sectorCount).toList();
  final weight = 1.0 / names.length;
  return SectorAllocation(
    allocation: {for (final n in names) n: weight},
    totalValue: 100000,
    compliance: const SectorCompliance(
      maxSector: 0.1,
      maxSectorName: 'Cash',
      maxAllowed: 0.4,
      compliant: true,
    ),
  );
}

SimHolding _holding(int i) => SimHolding(
      ticker: 'H${i.toString().padLeft(3, '0')}',
      quantity: 10,
      avgCost: 50,
      mark: 55,
      value: 550,
      unrealisedPnl: 50,
      openedAt: DateTime(2026, 1, 1),
    );

Future<void> _pump(WidgetTester tester, {required int sectorCount}) async {
  tester.view.physicalSize = const Size(390, 844);
  tester.view.devicePixelRatio = 1.0;
  addTearDown(tester.view.reset);

  // Tear the previous tree down first. `ProviderScope`/`MaterialApp`/
  // `PortfolioScreen` are the same widget types across pumps, so Flutter would
  // otherwise reuse the element tree and Riverpod would serve the *previous*
  // allocation for a frame — which silently made the 4-sector case assert
  // against 13-sector state.
  await tester.pumpWidget(const SizedBox.shrink());

  await tester.pumpWidget(
    ProviderScope(
      overrides: [
        simNotifierProvider.overrideWith((ref) => _FixedSimNotifier(
              ref,
              SimState(
                portfolio: SimPortfolio(
                  userId: 'u1',
                  portfolioId: 'p1',
                  startingCapital: 100000,
                  currentCash: 31050,
                  holdings: List.generate(3, _holding),
                  totalValue: 100000,
                  drawdownPct: 1.0,
                  priceSource: 'yahoo',
                ),
                trades: const [],
              ),
            )),
        watchlistNotifierProvider.overrideWith(
            (ref) => _FixedWatchlistNotifier(ref, const WatchlistState())),
        journalNotifierProvider.overrideWith(
            (ref) => _FixedJournalNotifier(ref, const JournalState())),
        alpacaStatusProvider
            .overrideWith((ref) async => const AlpacaStatus(linked: false)),
        sectorAllocationProvider
            .overrideWith((ref) async => _allocation(sectorCount)),
      ],
      child: MaterialApp(
        localizationsDelegates: AppLocalizations.localizationsDelegates,
        supportedLocales: AppLocalizations.supportedLocales,
        home: const PortfolioScreen(),
      ),
    ),
  );
  await tester.pump();
  await tester.pump();
}

final _legend = find.byKey(const ValueKey('sector-legend'));

Size _cardSize(WidgetTester tester) {
  // The card is the nearest Container ancestor of the legend — measuring the
  // card and not just the legend is what proves the *footprint* is constant.
  final card = find
      .ancestor(of: _legend, matching: find.byType(Container))
      .last;
  return tester.getSize(card);
}

void main() {
  group('CR118 — the legend is capped, and the cap is a real height', () {
    testWidgets('the card footprint is identical at 4 sectors and at 13',
        (t) async {
      await _pump(t, sectorCount: 4);
      expect(_legend, findsOneWidget, reason: 'legend must render at all');
      final four = _cardSize(t);
      // Non-vacuity: prove the two pumps really rendered different data, or
      // "the height did not change" would pass on two identical renders.
      expect(find.descendant(of: _legend, matching: find.byType(ShaderMask)),
          findsNothing);

      await _pump(t, sectorCount: 13);
      final thirteen = _cardSize(t);
      expect(find.descendant(of: _legend, matching: find.byType(ShaderMask)),
          findsOneWidget);

      expect(thirteen.height, four.height,
          reason: 'the card grew with diversification — this is the defect');
    });

    testWidgets('the legend viewport is a fixed height, not shrink-wrapped',
        (t) async {
      await _pump(t, sectorCount: 13);
      final capped = t.getSize(_legend).height;

      // 13 rows at the 22pt row extent would be 286pt unclipped. A
      // `shrinkWrap: true` ListView would report exactly that while looking
      // correct in a 4-sector test.
      expect(capped, lessThan(13 * 22.0));
      expect(capped, 99.0);
    });

    testWidgets('no sector is lost — the 13th is reachable by scrolling',
        (t) async {
      await _pump(t, sectorCount: 13);
      // Capping is only acceptable because nothing is lost behind it.
      expect(find.descendant(of: _legend, matching: find.text('Cash')),
          findsOneWidget);
      expect(find.descendant(of: _legend, matching: find.text('Materials')),
          findsNothing,
          reason: 'the 12th sector should start below the cut');

      await t.drag(
          find.descendant(of: _legend, matching: find.byType(Scrollable)),
          const Offset(0, -400));
      await t.pump();

      expect(find.descendant(of: _legend, matching: find.text('Materials')),
          findsOneWidget,
          reason: 'a capped legend that cannot reach its tail hides holdings');
      expect(find.descendant(of: _legend, matching: find.text('Cash')),
          findsNothing,
          reason: 'the head scrolled away, so this really scrolled');
    });
  });

  group('CR118 — the cut is signposted, and only when there is a cut', () {
    testWidgets('13 sectors scroll and carry the fade; 4 do neither',
        (t) async {
      await _pump(t, sectorCount: 13);
      final scrollingList = t.widget<ListView>(
          find.descendant(of: _legend, matching: find.byType(ListView)));
      expect(scrollingList.physics, isA<ClampingScrollPhysics>());
      expect(find.descendant(of: _legend, matching: find.byType(ShaderMask)),
          findsOneWidget,
          reason: 'a clipped list with no cue reads as a rendering bug');

      await _pump(t, sectorCount: 4);
      final staticList = t.widget<ListView>(
          find.descendant(of: _legend, matching: find.byType(ListView)));
      expect(staticList.physics, isA<NeverScrollableScrollPhysics>(),
          reason: 'a fitting legend must not swallow the outer list drag');
      expect(find.descendant(of: _legend, matching: find.byType(ShaderMask)),
          findsNothing,
          reason: 'a fade with nothing hidden behind it is a lie');
    });

    testWidgets('the boundary is where the arithmetic says it is', (t) async {
      // 4 rows = 88 <= 99 viewport; 5 rows = 110 > 99. Pinned so a change to
      // either constant has to be deliberate.
      expect(sectorLegendScrolls(4), isFalse);
      expect(sectorLegendScrolls(5), isTrue);
      expect(sectorLegendScrolls(13), isTrue);
    });
  });
}
