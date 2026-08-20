// CR177 UI — ComplianceBlockCard renders the stored refusal payload verbatim:
// the rule, ALL the violations (the list card's summary only carries the
// first), the refusal path, and the verdicts that drove it. isRenderable gates
// the detail screen's typed branch, so a payload without blocked_by provably
// falls to the generic dump.

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/widgets/journal/compliance_block_card.dart';
import 'package:ami_trade/widgets/sharia_verdict_banner.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

Widget _host(Widget child) => MaterialApp(
      localizationsDelegates: AppLocalizations.localizationsDelegates,
      supportedLocales: AppLocalizations.supportedLocales,
      home: Scaffold(body: SingleChildScrollView(child: child)),
    );

/// Verbatim shape of `sim_trade_effects.record_compliance_block`'s payload
/// (sim_trade_effects.py:163-186).
Map<String, dynamic> _payload({
  Object? blockedBy = 'concentration',
  Object? source = 'resting_order',
  Object? shariaVerdict = const {
    'status': 'screened_out',
    'ticker': 'BUD',
    'standard': 'AAOIFI',
    'source': 'S&P 500 Sharia Industry Exclusions Index (via SPUS)',
    'as_of': '2026-08-01',
  },
}) =>
    {
      if (blockedBy != null) 'blocked_by': blockedBy,
      'violations': [
        'VIOLATION-ONE this trade breaches your concentration cap.',
        'VIOLATION-TWO position would exceed 25% of the portfolio.',
      ],
      'request': {
        'ticker': 'BUD',
        'side': 'BUY',
        'quantity': 5,
        'order_type': 'limit',
      },
      'sharia_verdict': shariaVerdict,
      'classification_verdicts': [
        {
          'status': 'pass',
          'ticker': 'BUD',
          'kind': 'sector',
          'source': 'GICS',
          'as_of': '2026-08-01',
        },
      ],
      'advisories': ['ADVISORY-MARK earnings within your horizon.'],
      if (source != null) 'source': source,
    };

void main() {
  group('isRenderable', () {
    test('true when blocked_by is a non-empty string', () {
      expect(ComplianceBlockCard.isRenderable(_payload()), isTrue);
    });

    test('false when blocked_by is absent, empty, blank or not a string', () {
      expect(ComplianceBlockCard.isRenderable(_payload(blockedBy: null)),
          isFalse);
      expect(ComplianceBlockCard.isRenderable(_payload(blockedBy: '')),
          isFalse);
      expect(ComplianceBlockCard.isRenderable(_payload(blockedBy: '  ')),
          isFalse);
      expect(ComplianceBlockCard.isRenderable(_payload(blockedBy: 7)),
          isFalse);
    });
  });

  testWidgets('renders rule, ALL violations, source and advisories',
      (tester) async {
    await tester.pumpWidget(_host(ComplianceBlockCard(payload: _payload())));

    // The load-bearing field, uppercased raw slug — CR177 §4.
    expect(find.text('CONCENTRATION'), findsOneWidget);
    // ALL violations, not just violations[0] (the list card already shows
    // the first as the entry summary; the detail must show every one).
    expect(find.textContaining('VIOLATION-ONE'), findsOneWidget);
    expect(find.textContaining('VIOLATION-TWO'), findsOneWidget);
    // Refusal-path mapping: resting_order → the localized label.
    expect(find.text('Resting order — refused at fill'), findsOneWidget);
    expect(find.text('SAFETY FLOOR — TRADE BLOCKED'), findsOneWidget);
    expect(find.text('LIMIT'), findsOneWidget);
    expect(find.textContaining('ADVISORY-MARK'), findsOneWidget);
    // Classification verdict provenance line from the raw map.
    expect(find.text('sector · pass · GICS · 2026-08-01'), findsOneWidget);
  });

  testWidgets('ShariaVerdictBanner shown when the payload carries a verdict',
      (tester) async {
    await tester.pumpWidget(_host(ComplianceBlockCard(payload: _payload())));
    expect(find.byType(ShariaVerdictBanner), findsOneWidget);
  });

  testWidgets('ShariaVerdictBanner absent when sharia_verdict is null',
      (tester) async {
    await tester.pumpWidget(
        _host(ComplianceBlockCard(payload: _payload(shariaVerdict: null))));
    expect(find.byType(ShariaVerdictBanner), findsNothing);
  });

  testWidgets('unknown source slug renders raw, never guessed into a label',
      (tester) async {
    await tester.pumpWidget(_host(
        ComplianceBlockCard(payload: _payload(source: 'future_path'))));
    expect(find.text('future_path'), findsOneWidget);
    expect(find.text('Resting order — refused at fill'), findsNothing);
    expect(find.text('Trade ticket'), findsNothing);
  });
}
