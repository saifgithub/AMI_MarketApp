/// DEF114 — round-trips `unescapeSseText` against the *actual* backend
/// escape (`room.py`/`brief.py`/`one_on_one.py`:
/// `chunk.replace("\\", "\\\\").replace("\n", "\\n")`), so a passing suite
/// proves inversion, not just plausibility. The 13-case corpus below is the
/// one the Architect measured by hand in real Dart before laning this
/// defect — see `orchestration/dispatch/lanes/DEF114.assign.md` (D1).
///
/// The two sequential `replaceAll`s the parser shipped with (and the
/// swapped order the CR090 auditor mutation tried) both fail this corpus —
/// deliberately not asserted here as a "current behaviour" pin, since D1
/// settled that the current/swapped order is the bug, not the spec.
library;

import 'package:ami_trade/services/api/api_client.dart';
import 'package:flutter_test/flutter_test.dart';

/// The backend's exact escape, transcribed verbatim (not re-derived) so the
/// test proves this helper inverts the real wire format.
String _backendEscape(String chunk) =>
    chunk.replaceAll(r'\', r'\\').replaceAll('\n', r'\n');

void main() {
  group('DEF114 — unescapeSseText round-trips the backend escape', () {
    const cases = <String, String>{
      'plain newline': 'line one\nline two',
      'literal backslash-n in prose':
          r'the token \n means newline is coming',
      'windows path': r'C:\next\report',
      'double backslash (a\\b)': r'a\b',
      'trailing backslash': 'ends with \\',
      'backslash then real newline': 'before\\\nafter',
      'literal double-backslash-n': r'\\n',
      'repeated newlines': 'a\n\n\nb',
      'unicode and emoji': 'héllo 😀 wörld — 你好',
      'quotes and tabs': 'she said "hi"\tthere',
      'empty string': '',
      'lone backslash': '\\',
      'double newline': '\n\n',
    };

    cases.forEach((label, original) {
      test(label, () {
        final wire = _backendEscape(original);
        expect(unescapeSseText(wire), equals(original), reason: label);
      });
    });

    test('sanity: the corpus actually exercises escaping', () {
      // Guard against a no-op test corpus: at least one case must produce a
      // wire form different from its plaintext, or the round-trip proves
      // nothing about the escape/unescape pairing.
      final anyEscaped = cases.values.any((v) => _backendEscape(v) != v);
      expect(anyEscaped, isTrue);
    });
  });
}
