/// DEF419 (mobile half) — the trade ticket sizes the mandate check against
/// the account that will actually receive the order, not always AMI's own
/// $10k sim portfolio.
///
/// Backend half (DEF419-BE, `b945142c`): `POST /v1/sim/preview` accepts an
/// optional `account` snapshot and runs `check_mandate_compliance` against
/// IT instead of the AMI sim portfolio when supplied. This file pins the
/// mobile wiring on top of that: ALPACA PAPER and BOTH fetch the linked
/// Alpaca account and pass it as the snapshot; a fetch failure degrades
/// loudly (CR040) rather than silently falling back to an AMI-sized check;
/// and BOTH runs its two legs independently — one account's rejection must
/// never veto the other's acceptance (Saiful: *"it may reject for ami and
/// approve for alpaca. Or vice versa. This is an expected condition"*).
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/features/sim/order_pricing.dart';
import 'package:ami_trade/models/alpaca.dart';
import 'package:ami_trade/models/sim.dart';
import 'package:ami_trade/screens/sim/trade_ticket_sheet.dart';
import 'package:ami_trade/services/alpaca/alpaca_client.dart';
import 'package:ami_trade/state/alpaca_providers.dart';
import 'package:ami_trade/state/sim_providers.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

/// A fixed Alpaca account, or a fetch failure on demand. `account()`/
/// `positions()` are the two calls [_fetchAlpacaSnapshot] makes; both must
/// fail together for the "unreadable account" branch, mirroring what an
/// offline device or a revoked credential actually does to both calls.
class _FixedAlpacaClient extends AlpacaClient {
  _FixedAlpacaClient({
    this.portfolio = const AlpacaPortfolio(
      cash: 5000,
      portfolioValue: 100000,
      equity: 100000,
      buyingPower: 5000,
    ),
    this.fixedPositions = const [],
    this.fails = false,
    this.paperLinked = true,
  });

  final AlpacaPortfolio portfolio;
  final List<AlpacaPosition> fixedPositions;
  final bool fails;

  /// DEF430 — this fake never touches `AlpacaCredentialStore` (no secure
  /// storage mock is registered in this file), so the real
  /// `isLinkedToPaperAccount()` would throw here. Defaults `true` because
  /// most of this suite is about which account a preview is sized against,
  /// not the paper/live host gate itself — `false` drives the
  /// "live-linked account" group below, which IS about that gate.
  final bool paperLinked;

  int accountCalls = 0;
  int positionsCalls = 0;
  final List<String> orderCalls = [];

  @override
  Future<bool> isLinkedToPaperAccount() async => paperLinked;

  @override
  Future<AlpacaPortfolio> account() async {
    accountCalls++;
    if (fails) throw const AlpacaException(null, 'not linked');
    return portfolio;
  }

  @override
  Future<List<AlpacaPosition>> positions() async {
    positionsCalls++;
    if (fails) throw const AlpacaException(null, 'not linked');
    return fixedPositions;
  }

  @override
  Future<AlpacaOrder> submitOrder({
    required String symbol,
    required String side,
    required double qty,
    required SimOrderType orderType,
    double? limitPrice,
    double? triggerPrice,
    SimOrderTif tif = SimOrderTif.day,
    AlpacaBracket? bracket,
  }) async {
    orderCalls.add('$side $qty $symbol');
    return AlpacaOrder(
      id: 'o1',
      symbol: symbol,
      side: side,
      qty: qty,
      status: 'accepted',
    );
  }
}

/// Per-account previews and AMI submits, both scriptable independently so a
/// test can prove one leg's rejection never touches the other's call count
/// or outcome. [previewResultFor] keys off whether the call carried an
/// `account` snapshot — the shape `_legAlpaca`/`_submitAlpacaOnly` always
/// pass one, and the plain AMI Sim path never does, so this stands in for
/// "which account was this preview actually checked against" without the
/// fake needing to parse the snapshot's contents.
class _ScriptedSim extends SimNotifier {
  _ScriptedSim(
    super.ref,
    SimState fixed, {
    this.previewWithAccount,
    this.previewWithoutAccount,
    this.submitResult,
  }) {
    state = fixed;
  }

  final SimPreviewResult? previewWithAccount;
  final SimPreviewResult? previewWithoutAccount;
  final SimSubmitResult? submitResult;

  final List<Map<String, dynamic>?> previewCalls = [];
  int submitCalls = 0;

  @override
  Future<SimPreviewResult?> preview({
    required String ticker,
    required String side,
    required double quantity,
    SimOrderType orderType = SimOrderType.market,
    double? limitPrice,
    double? triggerPrice,
    double? stop,
    double? target,
    String? verdictRef,
    Map<String, dynamic>? account,
  }) async {
    previewCalls.add(account);
    return account != null ? previewWithAccount : previewWithoutAccount;
  }

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
    submitCalls++;
    state = state.copyWith(lastSubmit: submitResult, clearLastSubmit: submitResult == null);
    return submitResult;
  }
}

SimPortfolio _portfolio() => SimPortfolio.fromJson({
      'user_id': 'u',
      'portfolio_id': 'p',
      'starting_capital': 10000,
      'current_cash': 10000,
      'holdings': const [],
      'total_value': 10000,
      'drawdown_pct': 0,
      'price_source': 'yfinance',
      'cash_committed': 0,
      'cash_available': 10000,
      'resting_order_count': 0,
      'shares_committed': const {},
      'shorts': const [],
      'closed_shorts': const [],
    });

SimSubmitResult _amiAccepted() => SimSubmitResult.fromJson({
      'ok': true,
      'trade': {
        'id': 't1', 'user_id': 'u', 'ticker': 'AAPL', 'side': 'buy',
        'quantity': 1.0, 'entry_price': 100.0, 'status': 'open',
        'opened_at': '2026-09-22T00:00:00Z',
      },
      'resting': false,
      'compliance': {'passed': true},
    });

SimSubmitResult _amiRejected() => SimSubmitResult.fromJson({
      'ok': false,
      'resting': false,
      'compliance': {
        'passed': false,
        'violations': ['position size 137.2% exceeds single-name cap 100.0%'],
        'blocked_by': 'single_name_cap',
      },
    });

Future<_ScriptedSim> _pump(
  WidgetTester t, {
  SimPreviewResult? previewWithAccount,
  SimPreviewResult? previewWithoutAccount,
  SimSubmitResult? submitResult,
  required AlpacaClient alpacaClient,
  TradeDestination? tapDestination,
  SimOrderTif? tapTif,
}) async {
  await t.binding.setSurfaceSize(const Size(390, 1600));
  addTearDown(() => t.binding.setSurfaceSize(null));
  late _ScriptedSim sim;
  // A TIF pill other than DAY only renders for a resting order type
  // (`SimOrderType.canRest`), which itself only renders when the book
  // supports resting orders — same two-gate shape `cr233_ticket_order_
  // types_test.dart` already established.
  final needsLimit = tapTif != null;
  await t.pumpWidget(ProviderScope(
    overrides: [
      simNotifierProvider.overrideWith((ref) {
        sim = _ScriptedSim(
          ref,
          SimState(
              portfolio: _portfolio(),
              restingOrdersSupported: needsLimit),
          previewWithAccount: previewWithAccount,
          previewWithoutAccount: previewWithoutAccount,
          submitResult: submitResult,
        );
        return sim;
      }),
      alpacaLinkedProvider.overrideWith((ref) async => true),
      alpacaClientProvider.overrideWithValue(alpacaClient),
    ],
    child: MaterialApp(
      localizationsDelegates: AppLocalizations.localizationsDelegates,
      supportedLocales: AppLocalizations.supportedLocales,
      home: const TradeTicketSheet(tickerPrefill: 'AAPL'),
    ),
  ));
  for (var i = 0; i < 4; i++) {
    await t.pump(const Duration(milliseconds: 120));
  }
  if (needsLimit) {
    await t.tap(find.text('LIMIT').first);
    await t.pump(const Duration(milliseconds: 120));
    final field = find.ancestor(
      of: find.text('LIMIT PRICE'),
      matching: find.byType(TextField),
    );
    await t.enterText(field, '100');
    await t.pump(const Duration(milliseconds: 120));
  }
  if (tapDestination == TradeDestination.alpacaPaper) {
    await t.tap(find.text('ALPACA PAPER'));
    await t.pump(const Duration(milliseconds: 120));
  } else if (tapDestination == TradeDestination.both) {
    await t.tap(find.text('BOTH'));
    await t.pump(const Duration(milliseconds: 120));
  }
  if (tapTif == SimOrderTif.gtd30) {
    await t.tap(find.text('30 DAYS'));
    await t.pump(const Duration(milliseconds: 120));
  } else if (tapTif == SimOrderTif.gtd90) {
    await t.tap(find.text('90 DAYS'));
    await t.pump(const Duration(milliseconds: 120));
  }
  await t.tap(find.text('SUBMIT TRADE'));
  for (var i = 0; i < 8; i++) {
    await t.pump(const Duration(milliseconds: 120));
  }
  return sim;
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  setUp(() => SharedPreferences.setMockInitialValues({}));

  group('ALPACA PAPER sizes the check against the linked account', () {
    testWidgets('preview carries the fetched Alpaca account snapshot',
        (t) async {
      final alpaca = _FixedAlpacaClient(
        portfolio: const AlpacaPortfolio(
          cash: 20000,
          portfolioValue: 100000,
          equity: 100000,
          buyingPower: 20000,
        ),
        fixedPositions: const [
          AlpacaPosition(
              symbol: 'MSFT', qty: 10, marketValue: 4000, unrealizedPl: 0),
        ],
      );
      final sim = await _pump(
        t,
        alpacaClient: alpaca,
        previewWithAccount: const SimPreviewResult(accepted: true),
        tapDestination: TradeDestination.alpacaPaper,
      );

      expect(alpaca.accountCalls, 1);
      expect(alpaca.positionsCalls, 1);
      expect(sim.previewCalls, hasLength(1));
      final account = sim.previewCalls.single;
      expect(account, isNotNull,
          reason: 'ALPACA PAPER must preview WITH an account snapshot — '
              'previewing with none is the pre-DEF419 bug (checked against '
              "AMI's portfolio no matter the destination)");
      expect(account!['kind'], 'alpaca_paper');
      expect(account['equity'], 100000);
      expect(account['cash'], 20000);
      expect(account['positions'], [
        {'ticker': 'MSFT', 'qty': 10.0, 'market_value': 4000.0}
      ]);
      expect(sim.submitCalls, 0,
          reason: 'an accepted Alpaca-only preview places on Alpaca, never '
              "through AMI's own /submit");
      expect(alpaca.orderCalls, hasLength(1));
    });

    testWidgets(
        'a trade sized fine for the (larger) Alpaca account but rejected '
        "against AMI's own portfolio is ACCEPTED — the DEF419 report's own "
        'reproduction', (t) async {
      // The screenshot this DEF was filed from: ASML sized against a $10k
      // AMI sim account breached the single-name cap; against the actual,
      // larger Alpaca account it should not.
      final alpaca = _FixedAlpacaClient(
        portfolio: const AlpacaPortfolio(
          cash: 100000,
          portfolioValue: 100000,
          equity: 100000,
          buyingPower: 100000,
        ),
      );
      final sim = await _pump(
        t,
        alpacaClient: alpaca,
        previewWithAccount: const SimPreviewResult(accepted: true),
        previewWithoutAccount: SimPreviewResult(
          accepted: false,
          violations: const [
            'position size 137.2% exceeds single-name cap 100.0%'
          ],
          blockedBy: 'single_name_cap',
        ),
        tapDestination: TradeDestination.alpacaPaper,
      );

      expect(sim.previewCalls.single, isNotNull);
      expect(alpaca.orderCalls, hasLength(1),
          reason: 'checked against the real (larger) Alpaca account, this '
              'order clears the mandate and places');
      expect(find.textContaining('137.2%'), findsNothing,
          reason: 'the AMI-sized rejection sentence must not appear — this '
              'order was never checked against AMI');
    });
  });

  group('DEF419 round 2 — unmeasured_rules disclosure', () {
    // Single-leg ALPACA PAPER (unlike BOTH below) pops the sheet the instant
    // the order is accepted (`_submitAlpacaOnly`, "Navigator.of(context).pop()"
    // on `outcome.ok`) and reports through a SnackBar instead of the
    // `_destinationOutcomes` panel — in this widget-test harness (`home:`,
    // no pushed route to pop back to) that pop tears down the whole tree, so
    // there is nothing left to inspect text in once the call resolves. The
    // three cases below are therefore asserted the same way the file's own
    // pre-existing ALPACA-PAPER-accepted tests already do: by the OBSERVABLE
    // side effect (whether the order call fired), not by scraping
    // post-navigation text. The disclosure line's actual rendering (the
    // Text widget, the note plumbing, the "only on accepted" gating) is
    // proven by the BOTH case right below, which never pops and so stays
    // inspectable — same `_unmeasuredRulesNote` / `_DestinationOutcome.note`
    // code path either way.
    testWidgets(
        'ALPACA PAPER: an accepted preview with unmeasured_rules still '
        'places the order (disclosure never blocks)', (t) async {
      final alpaca = _FixedAlpacaClient();
      await _pump(
        t,
        alpacaClient: alpaca,
        previewWithAccount: const SimPreviewResult(
          accepted: true,
          unmeasuredRules: [
            UnmeasuredRule(
              rule: 'drawdown',
              reason: 'AMI has no NAV history for your Alpaca paper account.',
            ),
            UnmeasuredRule(
              rule: 'existing_open_risk',
              reason: 'AMI has no stop-loss data for your Alpaca positions.',
            ),
          ],
        ),
        tapDestination: TradeDestination.alpacaPaper,
      );

      expect(alpaca.orderCalls, hasLength(1),
          reason: 'accepted with two unmeasured rules — the order still '
              'places; disclosure is informational, never a block '
              '(Saiful, 2026-09-24: "disclose, don\'t block")');
    });

    testWidgets(
        'ALPACA PAPER: an accepted preview with NO unmeasured_rules also '
        'places the order (the AMI-checked path is unaffected)', (t) async {
      final alpaca = _FixedAlpacaClient();
      await _pump(
        t,
        alpacaClient: alpaca,
        previewWithAccount: const SimPreviewResult(accepted: true),
        tapDestination: TradeDestination.alpacaPaper,
      );

      expect(alpaca.orderCalls, hasLength(1));
    });

    testWidgets(
        'ALPACA PAPER: a REJECTED preview with unmeasured_rules never '
        'places an order — the violation, not the disclosure, decides',
        (t) async {
      final alpaca = _FixedAlpacaClient();
      await _pump(
        t,
        alpacaClient: alpaca,
        previewWithAccount: SimPreviewResult(
          accepted: false,
          violations: const ['exceeds single-name cap'],
          blockedBy: 'single_name_cap',
          unmeasuredRules: const [
            UnmeasuredRule(rule: 'drawdown', reason: 'no NAV history'),
          ],
        ),
        tapDestination: TradeDestination.alpacaPaper,
      );

      expect(alpaca.orderCalls, isEmpty);
      expect(find.textContaining('exceeds single-name cap'), findsOneWidget);
      expect(find.textContaining('Not checked for this account'),
          findsNothing,
          reason: 'unmeasured_rules is only rendered on the ACCEPTED path — '
              'this preview never even reaches _placeAlpacaOrder, so its '
              'note is never even constructed');
    });

    testWidgets(
        'BOTH: the Alpaca leg shows its own disclosure line alongside the '
        "AMI leg's own outcome, unaffected by the AMI leg", (t) async {
      final alpaca = _FixedAlpacaClient();
      await _pump(
        t,
        alpacaClient: alpaca,
        submitResult: _amiAccepted(),
        previewWithAccount: const SimPreviewResult(
          accepted: true,
          unmeasuredRules: [
            UnmeasuredRule(rule: 'drawdown', reason: 'no NAV history'),
          ],
        ),
        tapDestination: TradeDestination.both,
      );

      expect(alpaca.orderCalls, hasLength(1));
      expect(find.text('AMI SIM'), findsAtLeastNWidgets(1));
      expect(find.text('ALPACA PAPER'), findsAtLeastNWidgets(1));
      expect(find.textContaining('Not checked for this account'),
          findsOneWidget);
    });

    testWidgets(
        'BOTH: no unmeasured_rules on either leg means no disclosure line '
        'anywhere in the outcomes panel', (t) async {
      final alpaca = _FixedAlpacaClient();
      await _pump(
        t,
        alpacaClient: alpaca,
        submitResult: _amiAccepted(),
        previewWithAccount: const SimPreviewResult(accepted: true),
        tapDestination: TradeDestination.both,
      );

      expect(alpaca.orderCalls, hasLength(1));
      expect(find.text('AMI SIM'), findsAtLeastNWidgets(1));
      expect(find.text('ALPACA PAPER'), findsAtLeastNWidgets(1));
      expect(find.textContaining('Not checked for this account'),
          findsNothing,
          reason: 'the AMI leg never carries unmeasured_rules (it has no '
              'account_kind), and this Alpaca leg preview reported none — '
              'nothing to disclose on either outcome');
    });
  });

  group('CR233 round 2 (MINOR-1) — GTD-30/90 becomes GTC at Alpaca, disclosed',
      () {
    // Same BOTH-stays-inspectable rationale as the unmeasured_rules group
    // above: ALPACA-PAPER-only pops the sheet on acceptance, so BOTH is used
    // to actually read the disclosure text from the outcomes panel.
    testWidgets(
        'BOTH + 30-day TIF: the Alpaca leg discloses the GTC approximation',
        (t) async {
      final alpaca = _FixedAlpacaClient();
      await _pump(
        t,
        alpacaClient: alpaca,
        submitResult: _amiAccepted(),
        previewWithAccount: const SimPreviewResult(accepted: true),
        tapDestination: TradeDestination.both,
        tapTif: SimOrderTif.gtd30,
      );

      expect(alpaca.orderCalls, hasLength(1));
      expect(
          find.textContaining(
              'Alpaca has no 30/90-day expiry — this order stays open at '
              'Alpaca until filled or you cancel it.'),
          findsOneWidget);
    });

    testWidgets(
        'BOTH + 90-day TIF: the Alpaca leg discloses the GTC approximation',
        (t) async {
      final alpaca = _FixedAlpacaClient();
      await _pump(
        t,
        alpacaClient: alpaca,
        submitResult: _amiAccepted(),
        previewWithAccount: const SimPreviewResult(accepted: true),
        tapDestination: TradeDestination.both,
        tapTif: SimOrderTif.gtd90,
      );

      expect(alpaca.orderCalls, hasLength(1));
      expect(
          find.textContaining('Alpaca has no 30/90-day expiry'),
          findsOneWidget);
    });

    testWidgets(
        'BOTH + DAY TIF: no GTD disclosure — the approximation only applies '
        'to gtd30/gtd90', (t) async {
      final alpaca = _FixedAlpacaClient();
      await _pump(
        t,
        alpacaClient: alpaca,
        submitResult: _amiAccepted(),
        previewWithAccount: const SimPreviewResult(accepted: true),
        tapDestination: TradeDestination.both,
      );

      expect(alpaca.orderCalls, hasLength(1));
      expect(find.textContaining('Alpaca has no 30/90-day expiry'),
          findsNothing);
    });

    testWidgets(
        'BOTH + 30-day TIF + unmeasured_rules: both disclosure lines are '
        'shown together, not one overwriting the other', (t) async {
      final alpaca = _FixedAlpacaClient();
      await _pump(
        t,
        alpacaClient: alpaca,
        submitResult: _amiAccepted(),
        previewWithAccount: const SimPreviewResult(
          accepted: true,
          unmeasuredRules: [
            UnmeasuredRule(rule: 'drawdown', reason: 'no NAV history'),
          ],
        ),
        tapDestination: TradeDestination.both,
        tapTif: SimOrderTif.gtd30,
      );

      expect(alpaca.orderCalls, hasLength(1));
      expect(find.textContaining('Not checked for this account'),
          findsOneWidget);
      expect(find.textContaining('Alpaca has no 30/90-day expiry'),
          findsOneWidget);
    });
  });

  group('Alpaca fetch failure degrades loudly — never falls back to AMI',
      () {
    testWidgets(
        'ALPACA PAPER: an unreadable account sends no order and calls no preview',
        (t) async {
      final alpaca = _FixedAlpacaClient(fails: true);
      final sim = await _pump(
        t,
        alpacaClient: alpaca,
        previewWithAccount: const SimPreviewResult(accepted: true),
        previewWithoutAccount: const SimPreviewResult(accepted: true),
        tapDestination: TradeDestination.alpacaPaper,
      );

      expect(sim.previewCalls, isEmpty,
          reason: 'a snapshot that could not be fetched must never be '
              'replaced by no snapshot at all — previewing against AMI '
              'instead of the (unreadable) Alpaca account is the exact '
              'silent-fallback shape CR040 forbids');
      expect(alpaca.orderCalls, isEmpty,
          reason: 'no preview ran, so no order may be placed');
      expect(sim.submitCalls, 0,
          reason: "the AMI /submit path must not fire either — this is an "
              'Alpaca-only destination');
      // DEF442 — a null-status-code AlpacaException (no HTTP response, same
      // shape as a real network/timeout failure) now gets the specific
      // "couldn't reach Alpaca" line via `alpacaReadFailureMessage`, not the
      // old catch-all "couldn't read your account" text.
      expect(
        find.textContaining("Couldn't reach Alpaca"),
        findsOneWidget,
        reason: 'the failure must be loud and specific, not a generic '
            'error or a silently-accepted trade',
      );
      expect(find.textContaining('Order not sent'), findsOneWidget);
    });

    testWidgets(
        'BOTH: an unreadable Alpaca account still lets the AMI leg place '
        'independently', (t) async {
      final alpaca = _FixedAlpacaClient(fails: true);
      final sim = await _pump(
        t,
        alpacaClient: alpaca,
        submitResult: _amiAccepted(),
        tapDestination: TradeDestination.both,
      );

      expect(sim.submitCalls, 1,
          reason: "the AMI leg is independent of the Alpaca fetch and must "
              'still run');
      expect(sim.previewCalls, isEmpty,
          reason: 'no fallback preview against AMI for the failed Alpaca leg');
      expect(alpaca.orderCalls, isEmpty);
      expect(find.text('AMI SIM'), findsAtLeastNWidgets(1));
      expect(find.text('ALPACA PAPER'), findsAtLeastNWidgets(1));
      // DEF442 — see the ALPACA PAPER case above: a null-status-code failure
      // now reads as "couldn't reach Alpaca", not the old generic line.
      expect(
        find.textContaining("Couldn't reach Alpaca"),
        findsOneWidget,
      );
    });
  });

  group('DEF430 — a live-linked account never reaches the preview', () {
    testWidgets(
        'ALPACA PAPER: a live host sends no order, calls no preview, and '
        'never fetches the account at all', (t) async {
      final alpaca = _FixedAlpacaClient(paperLinked: false);
      final sim = await _pump(
        t,
        alpacaClient: alpaca,
        previewWithAccount: const SimPreviewResult(accepted: true),
        previewWithoutAccount: const SimPreviewResult(accepted: true),
        tapDestination: TradeDestination.alpacaPaper,
      );

      expect(alpaca.accountCalls, 0,
          reason: 'DEF430: a live account\'s summary must never even be '
              'fetched, let alone sent — the host check must short-circuit '
              'before any Alpaca call');
      expect(alpaca.positionsCalls, 0);
      expect(sim.previewCalls, isEmpty,
          reason: 'no preview may run against a live account\'s data');
      expect(alpaca.orderCalls, isEmpty);
      expect(sim.submitCalls, 0);
      // DEF439 round 1 MINOR-1 (carried from DEF430): this used to be the
      // same generic "Couldn't read your Alpaca paper account" text as an
      // offline/unlinked failure, which told a live-account user their
      // account was unreachable when it was in fact readable and simply
      // refused. The structural backstop this test drives directly (real UI
      // can no longer reach this state at all post-DEF439 — see
      // `alpacaLinkedProvider`) now says so specifically.
      expect(
        find.textContaining('AMI links Alpaca paper accounts only'),
        findsOneWidget,
        reason: 'a live account must say why it was refused, not look like '
            'an unreadable/offline account',
      );
    });

    testWidgets(
        'BOTH: a live Alpaca host still lets the AMI leg place '
        'independently, and still fetches nothing from Alpaca', (t) async {
      final alpaca = _FixedAlpacaClient(paperLinked: false);
      final sim = await _pump(
        t,
        alpacaClient: alpaca,
        submitResult: _amiAccepted(),
        tapDestination: TradeDestination.both,
      );

      expect(sim.submitCalls, 1,
          reason: 'the AMI leg is independent of the Alpaca host and must '
              'still run');
      expect(alpaca.accountCalls, 0);
      expect(alpaca.positionsCalls, 0);
      expect(sim.previewCalls, isEmpty);
      expect(alpaca.orderCalls, isEmpty);
    });
  });

  group('BOTH runs two independent legs', () {
    testWidgets(
        'AMI rejects, Alpaca accepts — the Alpaca leg still places (expected, per Saiful)',
        (t) async {
      final alpaca = _FixedAlpacaClient();
      final sim = await _pump(
        t,
        alpacaClient: alpaca,
        submitResult: _amiRejected(),
        previewWithAccount: const SimPreviewResult(accepted: true),
        tapDestination: TradeDestination.both,
      );

      expect(sim.submitCalls, 1);
      expect(sim.previewCalls, hasLength(1));
      expect(sim.previewCalls.single, isNotNull,
          reason: 'the Alpaca leg of BOTH must also size against the '
              'Alpaca account snapshot, not AMI');
      expect(alpaca.orderCalls, hasLength(1),
          reason: "AMI's rejection must not veto the Alpaca leg — the two "
              'accounts can legitimately disagree');
      expect(find.text('AMI SIM'), findsAtLeastNWidgets(1));
      expect(find.text('ALPACA PAPER'), findsAtLeastNWidgets(1));
      expect(find.textContaining('137.2%'), findsOneWidget,
          reason: "the AMI leg's own rejection sentence is shown under its "
              'own AMI SIM label');
    });

    testWidgets(
        'Alpaca rejects, AMI accepts — the AMI leg still places (the reverse direction)',
        (t) async {
      final alpaca = _FixedAlpacaClient();
      final sim = await _pump(
        t,
        alpacaClient: alpaca,
        submitResult: _amiAccepted(),
        previewWithAccount: const SimPreviewResult(
          accepted: false,
          violations: ['exceeds sector limit'],
          blockedBy: 'sector_limit',
        ),
        tapDestination: TradeDestination.both,
      );

      expect(sim.submitCalls, 1,
          reason: "the Alpaca leg's rejection must not veto the AMI leg");
      expect(alpaca.orderCalls, isEmpty,
          reason: 'a refused Alpaca preview must leave the Alpaca order call '
              'unmade');
      expect(find.text('AMI SIM'), findsAtLeastNWidgets(1));
      expect(find.text('ALPACA PAPER'), findsAtLeastNWidgets(1));
      expect(find.textContaining('exceeds sector limit'), findsOneWidget);
    });
  });
}
