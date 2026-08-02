// CR136 M09 — Finding order, section labels, F3 ledger, error panels.

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/portfolio_health.dart';
import 'package:ami_trade/screens/sim/portfolio_health_finding_screen.dart';
import 'package:ami_trade/services/billing/purchase_models.dart';
import 'package:ami_trade/services/billing/purchase_service.dart';
import 'package:ami_trade/state/mandate_providers.dart';
import 'package:ami_trade/state/portfolio_health_providers.dart';
import 'package:ami_trade/state/purchase_providers.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:ami_trade/widgets/hex/hex_pulse_loader.dart';
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_markdown_plus/flutter_markdown_plus.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import '../support/portfolio_health_fixtures.dart';

String _iso(String s) => '\u2066$s\u2069';

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

DioException _refusal(int status, Map<String, dynamic> detail) {
  final options = RequestOptions(path: '/v1/portfolio/health/u1/finding');
  return DioException(
    requestOptions: options,
    response: Response<Map<String, dynamic>>(
      requestOptions: options,
      statusCode: status,
      data: {'detail': detail},
    ),
  );
}

Future<void> _pump(
  WidgetTester tester, {
  HealthFinding? finding,
  Object? error,
}) async {
  tester.view.physicalSize = const Size(390, 844);
  tester.view.devicePixelRatio = 1.0;
  addTearDown(tester.view.reset);

  await tester.pumpWidget(ProviderScope(
    overrides: [
      purchaseServiceProvider.overrideWithValue(_NoOfferingService()),
      mandateNotifierProvider.overrideWith(_QuietMandateNotifier.new),
      healthFindingProvider.overrideWith((ref) {
        if (error != null) throw error;
        return finding ?? HealthFinding.fromJson(findingJson());
      }),
    ],
    child: MaterialApp(
      localizationsDelegates: AppLocalizations.localizationsDelegates,
      supportedLocales: AppLocalizations.supportedLocales,
      home: const PortfolioHealthFindingScreen(),
    ),
  ));
  await tester.pump();
  await tester.pump(AmiMotion.fast);
}

List<String> _bodies(WidgetTester tester) => tester
    .widgetList<MarkdownBody>(find.byType(MarkdownBody))
    .map((w) => w.data)
    .toList();

void main() {
  testWidgets('the app bar names the document', (tester) async {
    await _pump(tester);
    expect(find.text('Portfolio Health'), findsOneWidget);
  });

  testWidgets('loading shows the pulse loader', (tester) async {
    await tester.pumpWidget(ProviderScope(
      overrides: [
        healthFindingProvider.overrideWith((ref) => Future.any([])),
      ],
      child: MaterialApp(
        localizationsDelegates: AppLocalizations.localizationsDelegates,
        supportedLocales: AppLocalizations.supportedLocales,
        home: const PortfolioHealthFindingScreen(),
      ),
    ));
    await tester.pump();
    expect(find.byType(HexPulseLoader), findsOneWidget);
  });

  testWidgets('the disclosure renders first, then §F1–§F5 in order',
      (tester) async {
    await _pump(tester);
    final bodies = _bodies(tester);
    expect(bodies.length, 6,
        reason: 'M08 pins the MarkdownBody count and order; the M09 headers '
            'are Text widgets and must not change it');
    expect(bodies[0], contains('HEAD-MARK'));
    expect(bodies[1], 'F1-MARK');
    expect(bodies[2], 'F2-MARK');
    expect(bodies[3], 'F3-MARK');
    expect(bodies[4], 'F4-MARK');
    expect(bodies[5], 'F5-MARK');
  });

  testWidgets('each section carries its label, and the disclosure carries none',
      (tester) async {
    await _pump(tester);
    expect(find.text('F1 · HEADLINES'), findsOneWidget);
    expect(find.text('F2 · EXECUTIVE SUMMARY'), findsOneWidget);
    expect(find.text('F3 · DETAILED ANALYSIS'), findsOneWidget);
    expect(find.text('F4 · CONCLUSION'), findsOneWidget);
    expect(find.text('F5 · WHAT THE NUMBERS POINT TO'), findsOneWidget);
    expect(find.textContaining('Recommendations'), findsNothing,
        reason: 'amendment 6: AMI is a simulator and does not advise');
  });

  testWidgets('§F3 sits in the recessed ledger and the others do not',
      (tester) async {
    await _pump(tester);

    Color? fillAround(String marker) {
      final container = find
          .ancestor(
            of: find.byWidgetPredicate(
              (w) => w is MarkdownBody && w.data == marker,
            ),
            matching: find.byType(Container),
          )
          .evaluate()
          .map((e) => e.widget as Container)
          .firstWhere(
            (c) => c.decoration is BoxDecoration,
            orElse: () => Container(),
          );
      final d = container.decoration;
      return d is BoxDecoration ? d.color : null;
    }

    expect(fillAround('F3-MARK'), AmiColors.slate900,
        reason: 'the numbers section carries a different document register');
    expect(fillAround('F2-MARK'), isNot(AmiColors.slate900));
  });

  testWidgets('nothing is recomputed — stored strings render verbatim',
      (tester) async {
    const stored = 'Annualised volatility 18.98%; the S&P 500 measured 15.10%.';
    await _pump(
      tester,
      finding: HealthFinding.fromJson(findingJson(sections: const {
        'head': 'HEAD-MARK',
        'f1': stored,
      })),
    );
    expect(_bodies(tester)[1], stored);
  });

  testWidgets('a Finding without its disclosure does not render as a report',
      (tester) async {
    await _pump(
      tester,
      finding: HealthFinding.fromJson(findingJson(sections: const {
        'f1': 'F1-MARK',
      })),
    );
    expect(find.byType(MarkdownBody), findsNothing,
        reason: 'F19: an archived report outlives every caveat that was true '
            'when it was written, so it never renders without them');
    expect(find.text("AMI's engine did not respond. Tap to retry."),
        findsOneWidget);
  });

  group('refusal panels key on the server code, not the status alone', () {
    testWidgets('409 is amber and names the engine refusal', (tester) async {
      await _pump(
        tester,
        error: _refusal(409, {
          'code': 'portfolio_health_unavailable',
          'reason': 'refused_mock_data',
        }),
      );
      expect(
        find.text('AMI cannot generate a Finding right now — live market data '
            'is off.'),
        findsOneWidget,
      );
      final border = tester
          .widgetList<Container>(find.byType(Container))
          .map((c) => c.decoration)
          .whereType<BoxDecoration>()
          .map((d) => d.border)
          .whereType<Border>()
          .map((b) => b.top.color)
          .toSet();
      expect(border.contains(AmiColors.hexAmber), isTrue);
    });

    testWidgets('402 offers plans and opens the sheet', (tester) async {
      await _pump(
        tester,
        error: _refusal(402, {'code': 'portfolio_health_gate_closed'}),
      );
      expect(
        find.text('Findings are included in Trader and Floor Manager plans.'),
        findsOneWidget,
      );
      await tester.tap(find.text('SEE PLANS'));
      await tester.pumpAndSettle();
      expect(find.text('Upgrade your desk'), findsOneWidget);
    });

    testWidgets("429 quotes the server's own gate numbers", (tester) async {
      await _pump(
        tester,
        error: _refusal(429, {
          'code': 'portfolio_health_daily_cap_reached',
          'gate': gateJson(dailyUsed: 2, dailyCap: 2),
        }),
      );
      expect(
        find.text('${_iso('2')} of ${_iso('2')} Findings used today. '
            'Available again tomorrow.'),
        findsOneWidget,
        reason: 'the request that was refused is the authority on why, not the '
            "card's older copy of the gate",
      );
      expect(find.text('SEE PLANS'), findsNothing,
          reason: 'a cap is not an entitlement problem — offering an upgrade '
              'here sells a subscriber something they already have');
    });

    testWidgets('anything else is a transport panel with a retry',
        (tester) async {
      await _pump(tester, error: Exception('socket'));
      expect(find.text("AMI's engine did not respond. Tap to retry."),
          findsOneWidget);
      expect(find.byType(InkWell), findsOneWidget);
    });

    testWidgets('an unrecognised server code degrades to the same panel',
        (tester) async {
      await _pump(
        tester,
        error: _refusal(400, {'code': 'portfolio_health_something_new'}),
      );
      expect(find.text("AMI's engine did not respond. Tap to retry."),
          findsOneWidget,
          reason: 'a code this build does not know is still visibly a failure, '
              'never a blank screen');
    });
  });
}
