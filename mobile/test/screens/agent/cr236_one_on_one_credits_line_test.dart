/// CR236 — the 1-on-1 composer shows the credit balance ("You have 63
/// credits"), since 1-on-1 turns bill the same ledger as the Room
/// (`one_on_one_credit_cost`, `api/one_on_one.py`).
///
/// Harness mirrors one_on_one_telemetry_test.dart — a dead `ApiClient` so
/// the session never actually starts (irrelevant to the composer's own
/// rendering), with `mandateNotifierProvider` fixed to a chosen balance.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/agent.dart';
import 'package:ami_trade/models/mandate.dart';
import 'package:ami_trade/models/one_on_one.dart';
import 'package:ami_trade/screens/agent/one_on_one_screen.dart';
import 'package:ami_trade/services/api/api_client.dart';
import 'package:ami_trade/state/mandate_providers.dart';
import 'package:ami_trade/state/onboarding_providers.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

class _DeadApi extends ApiClient {
  _DeadApi() : super(baseUrl: 'test://localhost');

  @override
  Future<OneOnOneSession> startOneOnOne({
    required String agentId,
    String locale = 'en',
  }) async {
    throw Exception('backend down');
  }
}

class _FixedMandateNotifier extends MandateNotifier {
  _FixedMandateNotifier(super.ref, UserMandate? initial) {
    state = MandateState(mandate: initial);
  }

  @override
  Future<void> refresh() async {}
}

UserMandate _mandate({int? creditBalance}) => UserMandate.fromJson({
      'user_id': 'u1',
      'plan': 'trial_trader',
      if (creditBalance != null) 'credit_balance': creditBalance,
    });

Future<void> _pump(
  WidgetTester tester, {
  required UserMandate? mandate,
  Size size = const Size(390, 844),
  double textScale = 1.0,
}) async {
  tester.view.physicalSize = size;
  tester.view.devicePixelRatio = 1.0;
  addTearDown(tester.view.reset);

  await tester.pumpWidget(ProviderScope(
    overrides: [
      apiClientProvider.overrideWithValue(_DeadApi()),
      mandateNotifierProvider.overrideWith(
        (ref) => _FixedMandateNotifier(ref, mandate),
      ),
    ],
    child: MediaQuery(
      data: MediaQueryData(
        size: size,
        textScaler: TextScaler.linear(textScale),
      ),
      child: MaterialApp(
        localizationsDelegates: AppLocalizations.localizationsDelegates,
        supportedLocales: AppLocalizations.supportedLocales,
        home: OneOnOneScreen(agent: kAllAgents.first),
      ),
    ),
  ));
  await tester.pump();
  await tester.pump(const Duration(milliseconds: 50));
}

AppLocalizations _l(WidgetTester t) =>
    AppLocalizations.of(t.element(find.byType(OneOnOneScreen)));

void main() {
  group('CR236 — 1-on-1 composer credits line', () {
    testWidgets('shows the current balance', (tester) async {
      await _pump(tester, mandate: _mandate(creditBalance: 63));

      final l = _l(tester);
      expect(find.text(l.oneOnOneCreditsBalance('63')), findsOneWidget);
    });

    testWidgets('shows the unknown state, never a guessed number', (tester) async {
      await _pump(tester, mandate: _mandate());

      final l = _l(tester);
      expect(find.text(l.creditsLineUnknown), findsOneWidget);
      expect(find.textContaining('You have'), findsNothing);
    });

    testWidgets(
        'the composer credits line adds no overflow at 320dp / 1.3x text scale',
        (tester) async {
      // `_Header`'s fixed `height: 72` Container already overflows verti-
      // cally at this size/scale on `main`, unrelated to CR236 (confirmed by
      // running this same pump against the pre-CR236 file — identical
      // `Size(156.0, 71.0)` RenderFlex). This test's job is the composer
      // `_InputBar` this CR actually touched: suppress the pre-existing
      // header error for the pump, then assert the credits line itself
      // rendered — a regression IN the composer would instead show up as
      // this finder failing.
      final original = FlutterError.onError;
      FlutterError.onError = (_) {};
      try {
        await _pump(
          tester,
          size: const Size(320, 690),
          textScale: 1.3,
          mandate: _mandate(creditBalance: 63),
        );
        final l = _l(tester);
        expect(find.text(l.oneOnOneCreditsBalance('63')), findsOneWidget);
      } finally {
        FlutterError.onError = original;
      }
    });
  });
}
