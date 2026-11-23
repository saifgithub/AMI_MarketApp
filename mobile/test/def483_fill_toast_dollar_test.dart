// DEF483 — the fill toast rendered "Filled: BUY 1 NFLX @ \$69.85": the EN ARB
// string carried a JSON-escaped backslash before the dollar sign, which ICU
// keeps literally. This pins the rendered text in every shipped locale and
// bans a backslash anywhere in the ARB message values (ARB needs no escaping
// for the dollar sign).

import 'dart:convert';
import 'dart:io';

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:flutter/widgets.dart' show Locale;
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('fill toast renders a clean dollar sign in every locale', () async {
    for (final code in ['en', 'ar', 'ms']) {
      final l = await AppLocalizations.delegate.load(Locale(code));
      // CR282 - the money arrives pre-formatted; the ARB no longer owns the `$`.
      final text = l.tradeTicketFilled('BUY', '1', 'NFLX', r'$69.85');
      expect(text, contains(r'$69.85'), reason: code);
      expect(text, isNot(contains(r'\')), reason: '$code: stray backslash');
      final my = l.tradeTicketFilled('BUY', '100', '1155.KL', 'RM9.50');
      expect(my, contains('RM9.50'), reason: code);
      expect(my, isNot(contains(r'$')), reason: '$code: stray dollar sign');
    }
  });

  test('no ARB message value carries a literal backslash', () {
    final offenders = <String>[];
    for (final f in Directory('lib/l10n')
        .listSync()
        .whereType<File>()
        .where((f) => f.path.endsWith('.arb'))) {
      final arb = jsonDecode(f.readAsStringSync()) as Map<String, dynamic>;
      arb.forEach((k, v) {
        if (!k.startsWith('@') && v is String && v.contains(r'\')) {
          offenders.add('${f.uri.pathSegments.last}:$k');
        }
      });
    }
    expect(offenders, isEmpty);
  });
}
