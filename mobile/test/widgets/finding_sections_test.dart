// CR136 M08 — stored Finding renders disclosure FIRST, then §F1–§F5, from payload only.

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/widgets/journal/finding_sections.dart';
import 'package:flutter/material.dart';
import 'package:flutter_markdown_plus/flutter_markdown_plus.dart';
import 'package:flutter_test/flutter_test.dart';

Widget _host(Widget child) => MaterialApp(
      localizationsDelegates: AppLocalizations.localizationsDelegates,
      supportedLocales: AppLocalizations.supportedLocales,
      home: Scaffold(body: SingleChildScrollView(child: child)),
    );

Map<String, dynamic> _payload({Map<String, dynamic>? sections}) => {
      'portfolio_id': 'p-1',
      'as_of': '2026-08-02',
      'engine_version': 'cr136.v1',
      'sections': sections ??
          const {
            'head': '> **Educational simulation. Not investment advice.** DISCLOSURE-MARK',
            'f1': '- F1-MARK headline',
            'f2': 'F2-MARK prose',
            'f3': 'F3-MARK method',
            'f4': 'F4-MARK summary',
            'f5': 'F5-MARK rules',
          },
    };

List<String> _rendered(WidgetTester tester) => tester
    .widgetList<MarkdownBody>(find.byType(MarkdownBody))
    .map((w) => w.data)
    .toList();

void main() {
  group('isRenderable', () {
    test('true on a complete stored payload', () {
      expect(FindingSections.isRenderable(_payload()), isTrue);
    });

    test('false when the disclosure is missing, empty or whitespace', () {
      for (final head in <String?>[null, '', '   ', '\n']) {
        final sections = Map<String, dynamic>.from(
          _payload()['sections'] as Map,
        );
        if (head == null) {
          sections.remove('head');
        } else {
          sections['head'] = head;
        }
        expect(
          FindingSections.isRenderable(_payload(sections: sections)),
          isFalse,
          reason: 'head=${head == null ? 'absent' : '"$head"'} — F19 forbids a '
              'disclosure-less Finding rendering as a report',
        );
      }
    });

    test('false when sections is missing entirely', () {
      expect(FindingSections.isRenderable(const {'as_of': '2026-08-02'}), isFalse);
    });

    test('an older top-level disclosure key still renders', () {
      final payload = <String, dynamic>{
        'disclosure': 'LEGACY-MARK',
        'sections': const {'f1': 'F1-MARK'},
      };
      expect(FindingSections.isRenderable(payload), isTrue);
    });
  });

  testWidgets('disclosure renders before §F1, then sections in order',
      (tester) async {
    await tester.pumpWidget(_host(FindingSections(payload: _payload())));

    final bodies = _rendered(tester);
    expect(bodies.length, 6);
    expect(bodies[0], contains('DISCLOSURE-MARK'),
        reason: 'F19 reversed the foot-of-report placement — a reader who '
            'stops halfway must not have stopped before the caveats');
    expect(bodies[1], contains('F1-MARK'));
    expect(bodies[2], contains('F2-MARK'));
    expect(bodies[3], contains('F3-MARK'));
    expect(bodies[4], contains('F4-MARK'));
    expect(bodies[5], contains('F5-MARK'));
  });

  testWidgets('a missing section is skipped, not substituted', (tester) async {
    final sections = Map<String, dynamic>.from(_payload()['sections'] as Map)
      ..remove('f3');
    await tester.pumpWidget(
      _host(FindingSections(payload: _payload(sections: sections))),
    );

    final bodies = _rendered(tester);
    expect(bodies.length, 5);
    expect(bodies[0], contains('DISCLOSURE-MARK'));
    expect(bodies[1], contains('F1-MARK'));
    expect(bodies[2], contains('F2-MARK'));
    expect(bodies[3], contains('F4-MARK'));
    expect(bodies[4], contains('F5-MARK'));
    expect(bodies.any((b) => b.contains('F3')), isFalse);
  });

  testWidgets('nothing is recomputed — the exact stored strings are shown',
      (tester) async {
    const stored = 'Annualised volatility 18.98%; the S&P 500 measured 15.10%.';
    await tester.pumpWidget(_host(FindingSections(
      payload: _payload(sections: {
        'head': 'DISCLOSURE-MARK',
        'f1': stored,
      }),
    )));

    final bodies = _rendered(tester);
    expect(bodies[1], stored,
        reason: 'an archived report reads as it did when filed — a client that '
            'reformatted a number would eventually disagree with its own copy');
  });
}
