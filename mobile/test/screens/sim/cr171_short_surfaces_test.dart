/// CR171 — the client half of shorting, at the places it can be wrong.
///
/// Two assertions here carry most of the weight:
///
///   * **The advisory renders.** `ComplianceBlock.advisories` reached the wire
///     in `dd8a4f3f` and nothing displayed it. Saiful's ruling is that a halal
///     mandate does not refuse a short — *"we will put a flag and notice to
///     inform the user, but we let the trade through"* — which makes rendering
///     the notice the entire feature. An advisory computed correctly, sent
///     correctly and shown to nobody is CR040's failure with an extra step.
///   * **A short is not reported as a resting order.** A short writes no trade
///     row by design (§3), and the sheet's confirmation read
///     `resting = result.resting || trade == null`, so every successful short
///     would have told the user their order was waiting at $0.00.
///
/// Everything drives the real widgets against real parsed models. Where a fact
/// crosses the wire it is built with `fromJson`, not with the constructor: a
/// constructor-built fixture proves the renderer and says nothing about whether
/// the field is read off the payload the server actually sends (DEF190).
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/features/sim/order_pricing.dart';
import 'package:ami_trade/models/sim.dart';
import 'package:ami_trade/screens/sim/trade_ticket_sheet.dart';
import 'package:ami_trade/state/sim_providers.dart';
import 'package:ami_trade/widgets/sim/short_positions_section.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

class _FixedSim extends SimNotifier {
  _FixedSim(super.ref, SimState fixed, {this.canned}) {
    state = fixed;
  }

  /// What `submit` answers with, so the sheet's real success path runs — the
  /// advisory panel is set inside `_submit`, and a test that hand-built the
  /// widget's state would prove nothing about whether `_submit` sets it.
  final SimSubmitResult? canned;

  @override
  Future<SimSubmitResult?> submit({
    required String ticker,
    required String side,
    required double quantity,
    SimOrderType orderType = SimOrderType.market,
    double? limitPrice,
    double? triggerPrice,
    SimOrderTif tif = SimOrderTif.day,
    double? stop,
    double? target,
    int? horizonDays,
    String? verdictRef,
  }) async {
    state = state.copyWith(lastSubmit: canned);
    return canned;
  }
}

/// Built the way the app builds it — off a payload shaped like the route's.
SimPortfolio _portfolioJson({
  List<Map<String, dynamic>> shorts = const [],
  List<Map<String, dynamic>> closedShorts = const [],
  double cash = 10000,
  double? cashCommitted,
  double? cashAvailable,
  int restingOrderCount = 0,
  Map<String, dynamic> sharesCommitted = const {},
}) =>
    SimPortfolio.fromJson({
      'user_id': 'u',
      'portfolio_id': 'p',
      'starting_capital': 10000,
      'current_cash': cash,
      'holdings': const [],
      'total_value': 10000,
      'drawdown_pct': 0,
      'price_source': 'yfinance',
      'cash_committed': cashCommitted ?? 0,
      'cash_available': cashAvailable ?? cash,
      'resting_order_count': restingOrderCount,
      'shares_committed': sharesCommitted,
      'shorts': shorts,
      'closed_shorts': closedShorts,
    });

Map<String, dynamic> _shortJson({
  double mark = 100,
  double? marginRatio = 1.5,
  double borrowAccrued = 0,
}) =>
    {
      'id': 's1',
      'ticker': 'AAPL',
      'quantity': 10.0,
      'entry_price': 100.0,
      'mark': mark,
      'leg_value': 500.0 + (100.0 - mark) * 10,
      'unrealised_pnl': (100.0 - mark) * 10,
      'cash_posted': 500.0,
      'collateral_posted': 1500.0,
      'borrow_rate_pct': 3.0,
      'borrow_rate_source': 'default',
      'borrow_accrued_total': borrowAccrued,
      'margin_ratio': marginRatio,
      'maintenance_margin': 1.3,
      'stop': null,
      'target': null,
      'opened_at': '2026-08-01T00:00:00Z',
    };

final _shortWithAdvisory = SimSubmitResult.fromJson({
  'ok': true,
  'trade': null,
  'resting': false,
  'short': {'action': 'short_open', 'ticker': 'AAPL', 'quantity': 1},
  'compliance': {
    'passed': true,
    'advisories': ['Short selling is widely held impermissible under Sharia.'],
  },
});

Map<String, dynamic> _closedShortJson({String reason = 'margin'}) => {
      'id': 'c1',
      'ticker': 'AAPL',
      'quantity': 10.0,
      'entry_price': 100.0,
      'close_price': 145.0,
      'close_reason': reason,
      'realised_pnl': -450.0,
      'borrow_accrued_total': 1.23,
      'closed_at': '2026-08-13T00:00:00Z',
    };

Future<void> _pump(
  WidgetTester t,
  Widget child, {
  required SimState sim,
  SimSubmitResult? canned,
}) async {
  await t.binding.setSurfaceSize(const Size(390, 1400));
  addTearDown(() => t.binding.setSurfaceSize(null));
  await t.pumpWidget(ProviderScope(
    overrides: [
      simNotifierProvider
          .overrideWith((ref) => _FixedSim(ref, sim, canned: canned)),
    ],
    child: MaterialApp(
      localizationsDelegates: AppLocalizations.localizationsDelegates,
      supportedLocales: AppLocalizations.supportedLocales,
      home: Scaffold(body: SingleChildScrollView(child: child)),
    ),
  ));
  // Explicit pumps, not pumpAndSettle: the ticket leaves pending Dio timers
  // against no server and settle would never return.
  for (var i = 0; i < 4; i++) {
    await t.pump(const Duration(milliseconds: 120));
  }
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  setUp(() => SharedPreferences.setMockInitialValues({}));

  group('the halal advisory reaches the person it is about', () {
    test('it is parsed off the compliance block on a trade that SUCCEEDED',
        () {
      final r = SimSubmitResult.fromJson({
        'ok': true,
        'trade': null,
        'resting': false,
        'short': {
          'action': 'short_open',
          'ticker': 'AAPL',
          'quantity': 5,
          'realised_pnl': null,
        },
        'compliance': {
          'passed': true,
          'violations': <String>[],
          'advisories': ['Short selling is widely held impermissible…'],
        },
      });
      expect(r.ok, isTrue);
      expect(r.advisories, hasLength(1),
          reason: 'the notice rides on the OK branch — that is the whole '
              'ruling: the trade proceeds and the user is told');
      expect(r.violations, isEmpty,
          reason: 'an advisory is a third state, not a soft violation');
    });

    testWidgets('the sheet holds itself open and shows it', (t) async {
      // Driven through the real `_submit`. The panel is keyed off state the
      // widget sets for itself, so a hand-built `_pendingAdvisories` would
      // prove the renderer and say nothing about whether submitting reaches
      // it — which is exactly the gap that let the field ship unrendered.
      await _pump(
        t,
        const TradeTicketSheet(tickerPrefill: 'AAPL'),
        sim: SimState(portfolio: _portfolioJson()),
        canned: _shortWithAdvisory,
      );
      await t.enterText(find.widgetWithText(TextField, 'AAPL'), 'AAPL');
      await t.pump();
      await t.tap(find.text('SUBMIT TRADE'));
      for (var i = 0; i < 6; i++) {
        await t.pump(const Duration(milliseconds: 120));
      }

      expect(find.text('NOTICE'), findsOneWidget,
          reason: 'the trade PROCEEDED — this is a notice, never a refusal');
      expect(find.textContaining('impermissible'), findsOneWidget);
      expect(find.text('GOT IT'), findsOneWidget);
      expect(find.text('SAFETY FLOOR BLOCKED'), findsNothing,
          reason: 'Saiful ruled the trade goes through; reusing the refusal '
              'banner would say the opposite of what happened');
    });

    testWidgets('the trade cannot be repeated while the notice is unread',
        (t) async {
      await _pump(
        t,
        const TradeTicketSheet(tickerPrefill: 'AAPL'),
        sim: SimState(portfolio: _portfolioJson()),
        canned: _shortWithAdvisory,
      );
      await t.enterText(find.widgetWithText(TextField, 'AAPL'), 'AAPL');
      await t.pump();
      await t.tap(find.text('SUBMIT TRADE'));
      for (var i = 0; i < 6; i++) {
        await t.pump(const Duration(milliseconds: 120));
      }
      final cta = t.widget<ElevatedButton>(
        find.ancestor(
          of: find.text('SUBMIT TRADE'),
          matching: find.byType(ElevatedButton),
        ),
      );
      expect(cta.onPressed, isNull,
          reason: 'a live submit button under an unread notice is a second '
              'trade one tap away');
    });
  });

  group('a short is never reported as something else', () {
    test('the short branch is read off the response, not inferred', () {
      final r = SimSubmitResult.fromJson({
        'ok': true,
        'trade': null,
        'resting': false,
        'short': {
          'action': 'short_open',
          'ticker': 'AAPL',
          'quantity': 10,
          'realised_pnl': null,
        },
        'compliance': {'passed': true},
      });
      expect(r.isShortOpen, isTrue);
      expect(r.resting, isFalse,
          reason: 'inferring resting from a null trade told every successful '
              'short it was waiting at \$0.00');
      expect(r.shortTicker, 'AAPL');
      expect(r.shortQuantity, 10);
    });

    test('a cover carries its realised P&L', () {
      final r = SimSubmitResult.fromJson({
        'ok': true,
        'trade': null,
        'resting': false,
        'short': {
          'action': 'short_cover',
          'ticker': 'AAPL',
          'quantity': 10,
          'realised_pnl': 125.5,
        },
        'compliance': {'passed': true},
      });
      expect(r.isShortCover, isTrue);
      expect(r.shortRealisedPnl, 125.5);
    });

    test('an ordinary resting order is untouched by the short branch', () {
      final r = SimSubmitResult.fromJson({
        'ok': true,
        'trade': null,
        'resting': true,
        'order': {
          'id': 'o1',
          'ticker': 'AAPL',
          'side': 'buy',
          'quantity': 10,
          'order_type': 'limit',
          'state': 'working',
          'tif': 'day',
          'limit_price': 190,
        },
        'compliance': {'passed': true},
      });
      expect(r.resting, isTrue);
      expect(r.shortAction, isNull);
    });
  });

  group('the open short book', () {
    testWidgets('renders the leg, the borrow and the margin', (t) async {
      await _pump(
        t,
        const ShortPositionsSection(),
        sim: SimState(
          portfolio: _portfolioJson(
            shorts: [_shortJson(mark: 110, borrowAccrued: 2.47)],
          ),
        ),
      );
      expect(find.text('SHORT POSITIONS'), findsOneWidget);
      expect(find.text('SHORT'), findsOneWidget);
      // The LEG, not quantity x mark. At a mark of 110 the position is down
      // $100 on cash of $500, so the leg is $400 — a market-value reading
      // would render $1,100 and it would be the larger number.
      expect(find.text('\$400.00'), findsOneWidget);
      expect(find.textContaining('\$1,100'), findsNothing,
          reason: 'quantity x mark grows as a short goes AGAINST the user');
      expect(find.textContaining('Borrow cost so far \$2.47'), findsOneWidget,
          reason: 'the borrow comes out of cash, not out of the leg — without '
              'this line a short looks free to hold');
      expect(find.textContaining('3.00%/yr'), findsOneWidget);
      expect(find.textContaining('Margin 1.50'), findsOneWidget);
      expect(find.textContaining('1.30'), findsOneWidget,
          reason: 'the threshold travels with the ratio; the client must not '
              'carry its own copy');
    });

    testWidgets('a position near the buy-in level says so', (t) async {
      await _pump(
        t,
        const ShortPositionsSection(),
        sim: SimState(
          portfolio: _portfolioJson(
            shorts: [_shortJson(mark: 130, marginRatio: 1.35)],
          ),
        ),
      );
      expect(find.textContaining('AMI closes this position for you'),
          findsOneWidget,
          reason: 'there is no grace period and no notification — the close '
              'simply happens, so the only warning is this one');
    });

    testWidgets('a comfortable position does not cry wolf', (t) async {
      await _pump(
        t,
        const ShortPositionsSection(),
        sim: SimState(
          portfolio: _portfolioJson(shorts: [_shortJson(marginRatio: 1.5)]),
        ),
      );
      expect(find.textContaining('AMI closes this position for you'),
          findsNothing);
    });

    testWidgets('a null ratio renders no ratio rather than a stand-in',
        (t) async {
      await _pump(
        t,
        const ShortPositionsSection(),
        sim: SimState(
          portfolio: _portfolioJson(shorts: [_shortJson(marginRatio: null)]),
        ),
      );
      expect(find.textContaining('Margin'), findsNothing);
      expect(find.text('SHORT'), findsOneWidget,
          reason: 'the rest of the row still renders — one uncomputable '
              'number must not take the position off the screen');
    });

    testWidgets('COVER opens the ticket fixed to buy the whole position',
        (t) async {
      await _pump(
        t,
        const ShortPositionsSection(),
        sim: SimState(portfolio: _portfolioJson(shorts: [_shortJson()])),
      );
      await t.tap(find.text('COVER'));
      for (var i = 0; i < 4; i++) {
        await t.pump(const Duration(milliseconds: 120));
      }
      expect(find.textContaining('buys back the whole position'), findsOneWidget,
          reason: 'the server takes a cover whole or not at all, so the '
              'quantity is stated rather than left as a field whose only '
              'other value is a refusal');
      expect(find.widgetWithText(TextField, 'AAPL'), findsOneWidget);
    });

    testWidgets('nothing renders on a portfolio that has never shorted',
        (t) async {
      await _pump(t, const ShortPositionsSection(),
          sim: SimState(portfolio: _portfolioJson()));
      expect(find.text('SHORT POSITIONS'), findsNothing,
          reason: 'an empty heading on every portfolio in the app is the '
              'placeholder CR040 forbids');
    });
  });

  group('the close the user did not ask for', () {
    testWidgets('a margin close names AMI as the actor', (t) async {
      await _pump(
        t,
        const ShortPositionsSection(),
        sim: SimState(
          portfolio: _portfolioJson(closedShorts: [_closedShortJson()]),
        ),
      );
      expect(find.text('RECENTLY CLOSED SHORTS'), findsOneWidget);
      expect(find.textContaining('AMI bought back 10 AAPL'), findsOneWidget);
      expect(find.textContaining('margin fell below'), findsOneWidget);
      expect(find.textContaining('−\$450.00'), findsOneWidget);
    });

    test('every reason gets its own sentence', () {
      // Not a rendering detail: "you covered this" read about a forced buy-in
      // teaches the wrong lesson about the mechanic that just took the
      // decision away.
      SimClosedShort parse(String reason) =>
          SimClosedShort.fromJson(_closedShortJson(reason: reason));
      expect(parse('margin').wasForced, isTrue);
      expect(parse('user').wasForced, isFalse);
      expect(parse('stop').wasForced, isFalse);
    });
  });

  group('CR170 §6 — what the resting book has spoken for', () {
    test('the four fields are read off the payload', () {
      final p = _portfolioJson(
        cash: 1000,
        cashCommitted: 600,
        cashAvailable: 400,
        restingOrderCount: 2,
        sharesCommitted: {'aapl': 5.0},
      );
      expect(p.cashCommitted, 600);
      expect(p.cashAvailable, 400);
      expect(p.restingOrderCount, 2);
      expect(p.sharesCommittedFor('AAPL'), 5,
          reason: 'the map is keyed however the server cased it');
    });

    test('an over-committed book is visible, not clamped away', () {
      // The server deliberately does not floor `cash_available` at zero, and
      // the games lane's identically-named getter DOES clamp. Copying that
      // clamp here would hide the one condition the field exists to show.
      final p = _portfolioJson(
        cash: 1000,
        cashCommitted: 1500,
        cashAvailable: -500,
        restingOrderCount: 3,
      );
      expect(p.cashAvailable, -500);
      expect(p.isOverCommitted, isTrue);
    });

    test('a pre-CR170 payload still parses, with an empty book', () {
      final p = SimPortfolio.fromJson({
        'user_id': 'u',
        'portfolio_id': 'p',
        'starting_capital': 10000,
        'current_cash': 10000,
        'holdings': const [],
        'total_value': 10000,
        'drawdown_pct': 0,
      });
      expect(p.cashCommitted, 0);
      expect(p.cashAvailable, 10000);
      expect(p.shorts, isEmpty);
      expect(p.closedShorts, isEmpty);
    });
  });
}
