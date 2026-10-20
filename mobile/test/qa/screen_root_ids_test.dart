/// CR264 — guards the screen-identity and icon-label contract the exhaustive
/// UAT crawl depends on.
///
/// Pure Dart: reads source files, no widget tree. Three checks:
///
/// 1. Every `*_screen.dart` / `*_sheet.dart` under `lib/screens/`, plus the
///    listed standalone surfaces under `lib/widgets/` and `lib/features/`,
///    roots itself in `Semantics(identifier: ScreenIds.…)` (or a literal
///    `ami.screen.` id).
/// 2. `ScreenIds`, its `all` list, and the Python mirror
///    (`qa/appium/config/semantics_ids.py::SCREEN_IDS`) agree, ids are unique,
///    and every id is actually used in lib/.
/// 3. Every `IconButton(` in lib/ passes `tooltip:`, and no `InkWell` /
///    `GestureDetector` whose child is a bare `Icon` (optionally inside one
///    `Padding`) lacks a `Semantics(` immediately around it.
///
/// Limits of the heuristic in (3): it is source-text, not semantics-tree
/// based. It does not see icon-only controls built from other widgets
/// (`Container` + `Icon`, `HexButton` with an icon and no label, custom
/// painters), a `tooltip:` that is an empty string, or a `Semantics` that is
/// further than ~250 characters before the gesture widget. Check (1) only
/// proves the id is present in the file, not that it wraps the live root.
library;

import 'dart:io';

import 'package:ami_trade/qa/semantics_ids.dart';
import 'package:flutter_test/flutter_test.dart';

const _extraSurfaces = <String>[
  'lib/widgets/paywall/upgrade_paywall.dart',
  'lib/widgets/watchlist_sheet.dart',
  'lib/widgets/agent_action_sheet.dart',
  'lib/widgets/sim/option_reprice_sheet.dart',
  'lib/widgets/sim/option_proposal_ticket.dart',
  'lib/widgets/sim/option_disclosure_dialog.dart',
  'lib/widgets/confirm_restart_onboarding.dart',
  'lib/widgets/games/no_rules_disclosure.dart',
  'lib/widgets/ads/house_ad_interstitial.dart',
  'lib/features/tour/nav_change_sheet.dart',
  'lib/features/tour/tour_intro_sheet.dart',
];

List<File> _dartFiles(String dir) => Directory(dir)
    .listSync(recursive: true)
    .whereType<File>()
    .where((f) => f.path.endsWith('.dart'))
    .toList();

/// Index just past the bracket matching the one at [open], skipping strings
/// and `//` comments.
int _matchEnd(String s, int open) {
  var depth = 0;
  var i = open;
  while (i < s.length) {
    final c = s[i];
    if (c == '/' && s.startsWith('//', i)) {
      final nl = s.indexOf('\n', i);
      i = nl < 0 ? s.length : nl;
      continue;
    }
    if (c == "'" || c == '"') {
      if (s.startsWith(c * 3, i)) {
        i = s.indexOf(c * 3, i + 3) + 3;
        continue;
      }
      i++;
      while (s[i] != c) {
        if (s[i] == r'\') i++;
        i++;
      }
      i++;
      continue;
    }
    if ('([{'.contains(c)) depth++;
    if (')]}'.contains(c)) {
      depth--;
      if (depth == 0) return i + 1;
    }
    i++;
  }
  throw StateError('unbalanced brackets');
}

/// The expression text of the depth-1 named argument [name] in a call body
/// `Ctor( … )`, or null.
String? _topLevelArg(String call, String name) {
  var depth = 0;
  for (var i = 0; i < call.length; i++) {
    final c = call[i];
    if (c == '/' && call.startsWith('//', i)) {
      i = call.indexOf('\n', i);
      continue;
    }
    if (c == "'" || c == '"') {
      if (call.startsWith(c * 3, i)) {
        i = call.indexOf(c * 3, i + 3) + 2;
        continue;
      }
      i++;
      while (call[i] != c) {
        if (call[i] == r'\') i++;
        i++;
      }
      continue;
    }
    if ('([{'.contains(c)) depth++;
    if (')]}'.contains(c)) depth--;
    if (depth == 1 && call.startsWith('$name:', i) && i > 0) {
      final prev = call[i - 1];
      if (RegExp(r'[\s(,]').hasMatch(prev)) {
        return call.substring(i + name.length + 1).trimLeft();
      }
    }
  }
  return null;
}

bool _isBareIcon(String expr) {
  var e = expr.replaceFirst(RegExp(r'^const\s+'), '');
  if (e.startsWith('Icon(')) return true;
  if (e.startsWith('Padding(')) {
    final call = e.substring(0, _matchEnd(e, e.indexOf('(')));
    final child = _topLevelArg(call, 'child');
    return child != null && _isBareIcon(child);
  }
  return false;
}

void main() {
  test('every screen / sheet / listed surface carries a root screen id', () {
    final files = <File>[
      ..._dartFiles('lib/screens').where((f) =>
          f.path.endsWith('_screen.dart') ||
          f.path.endsWith('_sheet.dart') ||
          f.path.endsWith('_dialog.dart')),
      ..._extraSurfaces.map(File.new),
    ];
    expect(files, isNotEmpty);
    final missing = <String>[];
    for (final f in files) {
      expect(f.existsSync(), isTrue, reason: '${f.path} listed but missing');
      final src = f.readAsStringSync();
      if (!src.contains('ScreenIds.') && !src.contains('ami.screen.')) {
        missing.add(f.path);
      }
    }
    expect(missing, isEmpty,
        reason: 'CR264: these surfaces have no root '
            'Semantics(identifier: ScreenIds.…): $missing. The exhaustive '
            'crawl cannot tell which screen it is on without one.');
  });

  test('ScreenIds is unique, fully used, and mirrored in Python', () {
    final all = ScreenIds.all;
    expect(all.toSet().length, all.length, reason: 'duplicate ScreenIds');
    final src = _dartFiles('lib')
        .where((f) => !f.path.endsWith('qa/semantics_ids.dart'))
        .map((f) => f.readAsStringSync())
        .join('\n');
    final decl = File('lib/qa/semantics_ids.dart').readAsStringSync();
    final consts = RegExp(r"static const String (\w+) = 'ami\.screen\.([\w.]+)'")
        .allMatches(decl)
        .toList();
    expect(consts.map((m) => m.group(1)).toSet().length, all.length,
        reason: 'ScreenIds.all is out of step with the declared constants');
    for (final m in consts) {
      expect(src.contains('ScreenIds.${m.group(1)}'), isTrue,
          reason: 'ScreenIds.${m.group(1)} is declared but never used');
    }
    final py = File('../qa/appium/config/semantics_ids.py').readAsStringSync();
    final pyIds = RegExp(r'"(ami\.screen\.[\w.]+)"')
        .allMatches(py)
        .map((m) => m.group(1)!)
        .toSet();
    final dartIds = consts.map((m) => 'ami.screen.${m.group(2)}').toSet();
    expect(pyIds, dartIds,
        reason: 'qa/appium/config/semantics_ids.py SCREEN_IDS drifted from '
            'ScreenIds — keep the mirror in sync.');
  });

  test('every IconButton has a tooltip; bare-icon gestures are labelled', () {
    final badButtons = <String>[];
    final badGestures = <String>[];
    for (final f in _dartFiles('lib')) {
      final s = f.readAsStringSync();
      for (final m in RegExp(r'\bIconButton\(').allMatches(s)) {
        final call = s.substring(m.start, _matchEnd(s, m.end - 1));
        if (!call.contains('tooltip:')) {
          badButtons.add('${f.path}:${s.substring(0, m.start).split('\n').length}');
        }
      }
      for (final m in RegExp(r'\b(InkWell|GestureDetector)\(').allMatches(s)) {
        final call = s.substring(m.start, _matchEnd(s, m.end - 1));
        final child = _topLevelArg(call, 'child');
        if (child == null || !_isBareIcon(child)) continue;
        final before = s.substring(m.start < 250 ? 0 : m.start - 250, m.start);
        if (!before.contains('Semantics(') && !before.contains('label:')) {
          badGestures
              .add('${f.path}:${s.substring(0, m.start).split('\n').length}');
        }
      }
    }
    expect(badButtons, isEmpty,
        reason: 'CR264: IconButton without tooltip: $badButtons');
    expect(badGestures, isEmpty,
        reason: 'CR264: icon-only tap target without Semantics label: '
            '$badGestures');
  });
}
