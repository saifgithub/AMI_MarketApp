/// DEF520 (failure_patterns.md P42) — the dialog-pops-its-own-route guard.
///
/// DEF519: Brief rollback froze on a real phone because the confirm dialog's
/// buttons called `Navigator.of(context).pop(...)` with the OUTER page's
/// context. Every home tab runs its own nested Navigator (`home_shell.dart`)
/// and `showDialog` pushes onto the ROOT one, so that pop removed the tab's
/// page instead of the dialog; the dialog's future never completed and the
/// awaited action never ran. Nothing in a unit test or a review of the
/// closure looks wrong, because the code reads naturally.
///
/// This walks every `show*Dialog` / `show*Sheet` / `show*Popup` call under
/// `lib/`, takes the `builder:` closure, and fails if a pop inside it
/// (`Navigator.of(x).pop`, `.maybePop`, `.popUntil`, `Navigator.pop(x)` ...)
/// names an identifier that is not the builder's own context parameter or a
/// context parameter of a closure nested inside it (`Builder`,
/// `StatefulBuilder`). Push-family calls are not checked: pushing from the
/// page's context is the point of those.
///
/// A builder that is not an inline closure cannot be checked and also fails;
/// make it a closure, or pop from a widget class that owns its own `context`.
library;

import 'dart:io';

import 'package:flutter_test/flutter_test.dart';

const _showFns =
    'showDialog|showModalBottomSheet|showCupertinoDialog|showGeneralDialog|'
    'showCupertinoModalPopup|showAdaptiveDialog|showBottomSheet';

final _showCall = RegExp('\\b($_showFns)\\s*(<[^>(]*>)?\\s*\\(');

/// `Navigator.of(<id> ...)` followed by a pop-family call.
final _ofPop = RegExp(
    r'\bNavigator\s*\.\s*of\s*(?:<[^>(]*>)?\s*\(\s*([A-Za-z_]\w*)([^)]*)\)\s*\.\s*(?:pop|maybePop|popUntil|popAndPushNamed)\b');

/// `Navigator.pop(<id>, ...)` and friends.
final _staticPop = RegExp(
    r'\bNavigator\s*\.\s*(?:pop|maybePop|popUntil|popAndPushNamed)\s*(?:<[^>(]*>)?\s*\(\s*([A-Za-z_]\w*)');

/// `context.pop()` / `ctx.pop()` extension forms.
final _extPop = RegExp(r'\b(\w*(?:[cC]ontext|[cC]tx))\s*\.\s*(?:pop|maybePop)\s*\(');

/// Blanks comments and string contents (length preserved) so brace and paren
/// matching cannot be fooled by `)` inside a literal or a comment.
String _blank(String s) {
  final out = StringBuffer();
  var i = 0;
  while (i < s.length) {
    final c = s[i];
    final n = i + 1 < s.length ? s[i + 1] : '';
    if (c == '/' && n == '/') {
      while (i < s.length && s[i] != '\n') {
        out.write(' ');
        i++;
      }
    } else if (c == '/' && n == '*') {
      while (i < s.length && !(s[i] == '*' && i + 1 < s.length && s[i + 1] == '/')) {
        out.write(s[i] == '\n' ? '\n' : ' ');
        i++;
      }
      if (i < s.length) {
        out.write('  ');
        i += 2;
      }
    } else if (c == "'" || c == '"') {
      final raw = i > 0 && s[i - 1] == 'r';
      final triple = s.startsWith(c * 3, i);
      final q = triple ? c * 3 : c;
      out.write(q);
      i += q.length;
      while (i < s.length && !s.startsWith(q, i)) {
        if (s[i] == r'\' && !raw) {
          out.write('  ');
          i += 2;
          continue;
        }
        out.write(s[i] == '\n' ? '\n' : ' ');
        i++;
      }
      if (i < s.length) {
        out.write(q);
        i += q.length;
      }
    } else {
      out.write(c);
      i++;
    }
  }
  return out.toString();
}

int _matchClose(String s, int open) {
  const pairs = {'(': ')', '[': ']', '{': '}'};
  var depth = 0;
  for (var i = open; i < s.length; i++) {
    final c = s[i];
    if (pairs.containsKey(c)) {
      depth++;
    } else if (pairs.containsValue(c)) {
      depth--;
      if (depth == 0) return i;
    }
  }
  return -1;
}

/// End (exclusive) of an expression body that starts at [from]: the first
/// top-level `,` / `;` or the closing bracket of the enclosing group.
int _exprEnd(String s, int from, int limit) {
  var depth = 0;
  for (var i = from; i < limit; i++) {
    final c = s[i];
    if (c == '(' || c == '[' || c == '{') {
      depth++;
    } else if (c == ')' || c == ']' || c == '}') {
      if (depth == 0) return i;
      depth--;
    } else if ((c == ',' || c == ';') && depth == 0) {
      return i;
    }
  }
  return limit;
}

List<String> _paramNames(String params) {
  final names = <String>[];
  for (var p in params.split(',')) {
    p = p.replaceAll(RegExp(r'[{}\[\]]'), ' ').split('=').first.trim();
    if (p.isEmpty) continue;
    final m = RegExp(r'([A-Za-z_]\w*)$').firstMatch(p);
    if (m != null) names.add(m.group(1)!);
  }
  return names;
}

class _Closure {
  _Closure(this.names, this.start, this.end);
  final List<String> names;
  final int start;
  final int end;
}

/// Closure literals inside [s] between [from] and [to]: `(a, b) => ...` or
/// `(a, b) { ... }`, with the range their parameters are in scope for.
List<_Closure> _closuresIn(String s, int from, int to) {
  final found = <_Closure>[];
  for (var i = from; i < to; i++) {
    if (s[i] != '(') continue;
    final close = _matchClose(s, i);
    if (close < 0 || close >= to) continue;
    var j = close + 1;
    while (j < to && s[j].trim().isEmpty) {
      j++;
    }
    final isArrow = s.startsWith('=>', j);
    final isBlock = j < to && s[j] == '{';
    if (!isArrow && !isBlock) continue;
    var k = i - 1;
    while (k >= from && s[k].trim().isEmpty) {
      k--;
    }
    final prev = k >= from ? s[k] : '';
    if (RegExp(r'\w').hasMatch(prev)) continue;
    final bodyStart = isArrow ? j + 2 : j;
    final end = isArrow ? _exprEnd(s, bodyStart, to) : _matchClose(s, j);
    found.add(_Closure(_paramNames(s.substring(i + 1, close)), i, end < 0 ? to : end));
  }
  return found;
}

class Violation {
  Violation(this.line, this.what);
  final int line;
  final String what;
  @override
  String toString() => 'line $line: $what';
}

List<Violation> scanSource(String raw) {
  final s = _blank(raw);
  final violations = <Violation>[];
  int lineOf(int o) => '\n'.allMatches(raw.substring(0, o)).length + 1;

  for (final m in _showCall.allMatches(s)) {
    final open = m.end - 1;
    final close = _matchClose(s, open);
    if (close < 0) continue;
    final args = s.substring(open + 1, close);
    final rootDefault = !RegExp(r'useRootNavigator\s*:\s*false').hasMatch(args);

    final b = RegExp(r'\b(?:builder|pageBuilder)\s*:\s*').firstMatch(args);
    if (b == null) {
      violations.add(Violation(lineOf(m.start), '${m.group(1)} has no builder: argument to check'));
      continue;
    }
    final bStart = open + 1 + b.end;
    if (s[bStart] != '(') {
      violations.add(Violation(
          lineOf(m.start), '${m.group(1)} builder is not an inline closure, cannot verify its pops'));
      continue;
    }
    final pClose = _matchClose(s, bStart);
    var j = pClose + 1;
    while (s[j].trim().isEmpty) {
      j++;
    }
    final names = _paramNames(s.substring(bStart + 1, pClose));
    final bodyStart = s.startsWith('=>', j) ? j + 2 : j;
    final bodyEnd = s.startsWith('=>', j) ? _exprEnd(s, bodyStart, close) : _matchClose(s, j);
    final nested = _closuresIn(s, bodyStart, bodyEnd);

    bool inScope(String id, int at) =>
        names.contains(id) || nested.any((c) => c.start < at && at < c.end && c.names.contains(id));

    void check(RegExpMatch pm, String id, String rest) {
      if (inScope(id, pm.start)) return;
      if (rootDefault && RegExp(r'rootNavigator\s*:\s*true').hasMatch(rest)) return;
      violations.add(Violation(
          lineOf(pm.start),
          '${m.group(1)} (line ${lineOf(m.start)}) pops with `$id`, not the builder context '
          '(${names.isEmpty ? 'builder ignores its context' : names.join(', ')})'));
    }

    for (final pm in _ofPop.allMatches(s, bodyStart).takeWhile((e) => e.start < bodyEnd)) {
      check(pm, pm.group(1)!, pm.group(2) ?? '');
    }
    for (final pm in _staticPop.allMatches(s, bodyStart).takeWhile((e) => e.start < bodyEnd)) {
      check(pm, pm.group(1)!, '');
    }
    for (final pm in _extPop.allMatches(s, bodyStart).takeWhile((e) => e.start < bodyEnd)) {
      check(pm, pm.group(1)!, '');
    }
  }
  return violations;
}

void main() {
  group('scanner (so the guard cannot go inert)', () {
    test('flags the pre-DEF519 shape: builder ignores its context, pops outer', () {
      const src = '''
void f(BuildContext context) {
  showDialog<bool>(
    context: context,
    builder: (_) => AlertDialog(
      actions: [TextButton(onPressed: () => Navigator.of(context).pop(false), child: Text('x'))],
    ),
  );
}
''';
      expect(scanSource(src), hasLength(1));
    });

    test('flags a builder param that is not the one popped', () {
      const src = '''
void f(BuildContext context) {
  showModalBottomSheet<void>(
    context: context,
    builder: (sheetCtx) {
      return TextButton(onPressed: () { Navigator.pop(context); }, child: Text('x'));
    },
  );
}
''';
      expect(scanSource(src), hasLength(1));
    });

    test('accepts the builder context and a nested Builder context', () {
      const src = '''
void f(BuildContext context) {
  showDialog<void>(
    context: context,
    builder: (dialogContext) => Column(children: [
      TextButton(onPressed: () => Navigator.of(dialogContext).pop(), child: Text('a')),
      Builder(builder: (inner) => TextButton(
          onPressed: () => Navigator.pop(inner), child: Text('b'))),
      TextButton(onPressed: () => Navigator.of(context).push(route), child: Text('c')),
    ]),
  );
}
''';
      expect(scanSource(src), isEmpty);
    });

    test('a nested closure param is only in scope inside that closure', () {
      const src = '''
void f(BuildContext context) {
  showDialog<void>(
    context: context,
    builder: (_) => Column(children: [
      Builder(builder: (context) => Text('x')),
      TextButton(onPressed: () => Navigator.of(context).pop(), child: Text('y')),
    ]),
  );
}
''';
      expect(scanSource(src), hasLength(1));
    });

    test('a pop named only in a comment or string is not a violation', () {
      const src = r'''
void f(BuildContext context) {
  showDialog<void>(
    context: context,
    // old: Navigator.of(context).pop()
    builder: (ctx) => Text('Navigator.of(context).pop()'),
  );
}
''';
      expect(scanSource(src), isEmpty);
    });

    test('a non-closure builder is refused rather than waved through', () {
      const src = '''
void f(BuildContext context) {
  showDialog<void>(context: context, builder: _build);
}
''';
      expect(scanSource(src), hasLength(1));
    });
  });

  group('lib/ (DEF520)', () {
    final files = Directory('lib')
        .listSync(recursive: true)
        .whereType<File>()
        .where((f) => f.path.endsWith('.dart'))
        .toList();

    test('every dialog / sheet builder pops with its own context', () {
      final bad = <String>[];
      var sites = 0;
      for (final f in files) {
        final src = f.readAsStringSync();
        sites += _showCall.allMatches(_blank(src)).length;
        for (final v in scanSource(src)) {
          bad.add('${f.path}:${v.line}  ${v.what}');
        }
      }
      expect(sites, greaterThan(40),
          reason: 'the scan found too few show* calls; the pattern has gone inert');
      expect(bad, isEmpty,
          reason: 'DEF519/P42: a dialog or sheet that pops with the OUTER context pops '
              "the tab's nested-Navigator page, not itself. Use the builder's own "
              'context (dialogContext / sheetContext).\n${bad.join('\n')}');
    });
  });
}
