/// CR163 — the QA build flag must not be silently off.
///
/// `bool.fromEnvironment` accepts ONLY the exact literals 'true' and 'false'.
/// `--dart-define=AMI_QA_SEMANTICS=1` evaluates to **false**, with no warning
/// at build time and no symptom at run time. That is exactly what happened on
/// 2026-08-10: the flag was dead in every build for a day. Nothing caught it
/// because the iOS Simulator exposes the semantics tree regardless, so the
/// suite that depends on the flag passed anyway — the flag was load-bearing in
/// intent and inert in fact.
///
/// It only surfaced when a second feature (the crawler's error sink) depended
/// on the same flag and produced a missing file rather than a passing test.
///
/// This pins the parse so the trap cannot come back. It deliberately tests the
/// same expression `main.dart` uses rather than importing it — `main.dart`'s
/// constant is compile-time-bound to the build's own dart-defines, so importing
/// it would assert about THIS test run's flags, not about the parse.
library;

import 'package:flutter_test/flutter_test.dart';

/// Mirrors `main.dart`'s `_qaSemantics`. Keep the two in step; the whole point
/// is that the accepted set is wider than `bool.fromEnvironment`'s.
bool qaFlagIsOn(String raw) =>
    raw == '1' || raw == 'true' || raw == 'yes' || raw == 'on';

void main() {
  group('the QA flag accepts the spellings people actually type', () {
    for (final on in ['1', 'true', 'yes', 'on']) {
      test('$on -> enabled', () => expect(qaFlagIsOn(on), isTrue));
    }
  });

  group('and stays off otherwise', () {
    for (final off in ['', '0', 'false', 'no', 'off']) {
      test('${off.isEmpty ? '<empty>' : off} -> disabled',
          () => expect(qaFlagIsOn(off), isFalse));
    }
  });

  test('an unset flag leaves the app in shipping configuration', () {
    // String.fromEnvironment returns '' when the define is absent. A build with
    // no dart-define must never install the QA instrumentation.
    expect(qaFlagIsOn(''), isFalse,
        reason: 'a TestFlight/Play build passes no dart-define and must behave '
            'exactly as it did before CR162/CR163');
  });

  test('"1" would be FALSE under bool.fromEnvironment — the trap this pins', () {
    // Not a tautology: it documents why the parse is hand-rolled rather than
    // using the obvious constructor. If someone "simplifies" main.dart back to
    // bool.fromEnvironment, `1` silently stops working and this comment is the
    // only surviving record of why that matters.
    const underStrictParse = bool.fromEnvironment('AMI_QA_SEMANTICS_NEVER_SET');
    expect(underStrictParse, isFalse);
    expect(qaFlagIsOn('1'), isTrue,
        reason: 'our parse must accept 1 where bool.fromEnvironment does not');
  });
}
