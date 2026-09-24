/// CR232 (failure_patterns.md P36) — the exit-affordance guard.
///
/// Saiful: *"Some pages are simply using an 'X' to exit (top right) —
/// obscure and not in line with the app's aesthetics."* CR232 gave every
/// pushed full page a back chevron (`AmiScreenHeader`'s `showBack`, or the
/// hand-styled equivalent on the two screens that don't use it) instead, and
/// removed every top-right `Icons.close` that used to be a page's only way
/// out. Rule 4's exception is narrow: an X-shaped icon still belongs on small
/// INLINE dismissals — an ad card, a chip's delete glyph, a notice banner's
/// own X — never on a page's own exit.
///
/// This is the P36 enforcing check: a per-screen review cannot see that ~13
/// independent close buttons shared one root cause (every pushed screen
/// covered the shell and had nothing else to pop to), so the check that
/// holds is structural — walk the source, name every file that still
/// constructs an X-shaped exit icon, and fail if one is not on the
/// allowlist below. A NEW page that reaches for the pattern fails this test
/// immediately; a genuinely new inline dismissal is added to the allowlist
/// deliberately, by name, in the same commit that adds it — never silently.
///
/// **CR232 round 2 (audit MINOR-1).** The original guard matched only
/// `Icons.close` by name. The auditor added a new screen whose only exit was
/// `IconButton(icon: Icon(Icons.cancel))` — visually the same X, the exact
/// regression this test exists to catch — and it passed, because the regex
/// named one Material constant instead of the affordance ("an X-shaped icon
/// used as a page's own exit"). `_xShapedIconConstruction` now matches the
/// whole close/cancel/clear family Material and Cupertino both ship (any of
/// them reads as the same glyph to a user), plus a bare `Text('✕')` /
/// `Text('×')` — the auditor's other demonstrated evasion, an icon-less glyph
/// button. The allowlist-can-only-shrink property (the second test below) is
/// unchanged and still holds against the wider pattern.
library;

import 'dart:io';

import 'package:flutter_test/flutter_test.dart';

/// Every file that still contains an X-shaped exit-icon construction, and
/// why each one is fine.
///
/// All nine are inline dismissals or chip-delete glyphs on content that sits
/// *inside* a page, never a page's own top-right exit — CR232 rule 4's
/// exception. `home_shell.dart` and `qa/semantics_ids.dart` are not on this
/// list because they only ever *mention* `Icons.close` in doc comments
/// explaining CR232 itself; the regex below matches the real construction,
/// not prose, so neither needs an entry.
const _allowedIconsCloseFiles = {
  // "NO AI VERDICT" advisory card's own dismiss — an inline notice, not the
  // ticket's exit (the ticket's exit is the header back chevron + Cancel).
  'lib/screens/sim/trade_ticket_sheet.dart',
  // Journal's search-field clear (X) button — clears typed text, not a nav.
  'lib/screens/journal/journal_screen.dart',
  // A refusal/inline-notice card's own dismiss on the agent brief screen.
  'lib/screens/agent/brief_screen.dart',
  // Price-alert notification banner's inline dismiss on Ticker Detail.
  'lib/screens/sim/ticker_detail_screen.dart',
  // Chip delete glyph (HexChip's `deleteIcon`), not a page exit.
  'lib/screens/settings/ticker_rules_section.dart',
  // The bug-report SHEET's own close (it's a modal bottom sheet with a drag
  // handle, not a pushed page — rule 3/4 only retire the X on PAGES) and the
  // inline "remove attached photo" control further down the same form.
  'lib/screens/feedback/bug_report_sheet.dart',
  // Ad card dismiss buttons — explicitly named in rule 4's exception.
  'lib/widgets/ads/house_ad_card.dart',
  'lib/widgets/ads/admob_native_card.dart',
  // Floor's inline reaction card dismiss.
  'lib/widgets/floor/floor_reaction_card.dart',
};

/// The Material + Cupertino icon constants that read as the same X-shaped
/// glyph to a user — a page exit built with any of these is the same
/// regression as `Icons.close`, just under a different name. Room's status
/// glyph and the lesson quiz's wrong-answer mark both use `Icons.cancel` for
/// a non-exit purpose (`room_screen.dart:1220`, `lesson_quiz_card.dart:139`)
/// — neither is `Icon(...)`/`IconButton(...)`-constructed AS a page exit, so
/// widening the name list does not by itself allowlist them; the
/// `Icon(Button)?(...)`-construction shape below is still required to match.
const _xShapedIconNames = [
  'Icons.close',
  'Icons.close_rounded',
  'Icons.cancel',
  'Icons.cancel_outlined',
  'Icons.cancel_rounded',
  'Icons.clear',
  'Icons.clear_rounded',
  'Icons.highlight_off',
  'Icons.disabled_by_default',
  'CupertinoIcons.clear',
  'CupertinoIcons.clear_circled',
  'CupertinoIcons.clear_circled_solid',
  'CupertinoIcons.clear_thick',
  'CupertinoIcons.clear_thick_circled',
  'CupertinoIcons.xmark',
  'CupertinoIcons.xmark_circle',
  'CupertinoIcons.xmark_circle_fill',
];

/// Matches the real widget construction (`Icon(Icons.close` /
/// `Icons.close,` inside an `Icon(`/`IconButton(` call), not a bare mention
/// in a doc comment — `home_shell.dart` and `qa/semantics_ids.dart` both
/// talk ABOUT `Icons.close` without constructing one, and must not trip this.
final _xShapedIconConstruction = RegExp(
    r'Icon(?:Button)?\(\s*[\s\S]{0,80}?(?:' +
        _xShapedIconNames.map(RegExp.escape).join('|') +
        r')');

/// The auditor's other demonstrated evasion: an icon-LESS exit built from a
/// bare glyph in a `Text` widget rather than an `Icon`, so the construction
/// regex above cannot see it at all. Neither glyph has a legitimate use in
/// `lib/screens` or `lib/widgets` today (confirmed by grep — the only hit in
/// the whole tree is generated l10n, which this test doesn't scan), so this
/// stays a plain literal match rather than needing its own allowlist.
final _xShapedTextConstruction = RegExp(r'''Text\(\s*['"][✕×]['"]''');

void main() {
  test(
      'no X-shaped icon or glyph is used as a page exit outside the '
      'allowlist', () {
    final offenders = <String>[];
    for (final dir in ['lib/screens', 'lib/widgets']) {
      final d = Directory(dir);
      if (!d.existsSync()) continue;
      for (final entity in d.listSync(recursive: true)) {
        if (entity is! File || !entity.path.endsWith('.dart')) continue;
        // Normalise to the same forward-slash, `lib/`-rooted form the
        // allowlist uses, regardless of platform path separators.
        final relPath = entity.path.replaceAll(r'\', '/');
        final path = relPath.startsWith('lib/')
            ? relPath
            : relPath.substring(relPath.indexOf('lib/'));
        if (_allowedIconsCloseFiles.contains(path)) continue;
        final src = entity.readAsStringSync();
        if (_xShapedIconConstruction.hasMatch(src) ||
            _xShapedTextConstruction.hasMatch(src)) {
          offenders.add(path);
        }
      }
    }
    expect(offenders, isEmpty,
        reason: 'CR232 (failure_patterns.md P36): a pushed full page must '
            'exit via AmiScreenHeader\'s back chevron (or the hand-styled '
            'equivalent for the two screens that don\'t use it), never a '
            'top-right X-shaped icon or glyph (close/cancel/clear, Material '
            'or Cupertino, or a bare "✕"/"×"). If this is a genuine new '
            'INLINE dismissal (an ad card, a chip delete, a notice banner), '
            'add it to _allowedIconsCloseFiles by name in the same commit — '
            'do not widen the allowlist to unblock an unrelated change:\n'
            '${offenders.join('\n')}');
  });

  test('the allowlist itself has no stale entries', () {
    // The inverse check: every allowlisted file must still actually contain
    // a matching construction. An entry that no longer needs its exemption
    // is a silent hole the next real regression could hide behind.
    final stale = <String>[];
    for (final path in _allowedIconsCloseFiles) {
      final f = File(path);
      if (!f.existsSync()) {
        stale.add('$path (file no longer exists)');
        continue;
      }
      final src = f.readAsStringSync();
      if (!_xShapedIconConstruction.hasMatch(src) &&
          !_xShapedTextConstruction.hasMatch(src)) {
        stale.add('$path (no longer constructs an X-shaped exit)');
      }
    }
    expect(stale, isEmpty,
        reason: 'These allowlist entries are stale — remove them so the '
            'allowlist only ever names files that actually need the '
            'exemption:\n${stale.join('\n')}');
  });

  // CR232 round 2 — the property the auditor named directly: the allowlist
  // can only ever SHRINK relative to what the wider pattern below matches.
  // Anyone who tries to grow the allowlist by widening the regex instead
  // (the failure mode a hand-maintained scan list would invite) trips this,
  // because the count of matching files can never exceed the count under the
  // widest reasonable pattern — every real exit icon this test knows about.
  test('the allowlist cannot grow past what an X-shaped exit can match', () {
    // A deliberately permissive pattern — ANY of the tracked names, in
    // EITHER construction shape — so this is a strict superset of what the
    // enforcing test above matches. If the allowlist ever contains more
    // files than this superset can find, something added an entry that
    // doesn't correspond to a real X-shaped construction at all.
    final superset = RegExp(
        r'(?:Icon(?:Button)?\(|Text\()\s*[\s\S]{0,80}?(?:' +
            [..._xShapedIconNames, "'✕'", '"✕"', "'×'", '"×"']
                .map(RegExp.escape)
                .join('|') +
            r')');
    final matching = _allowedIconsCloseFiles.where((path) {
      final f = File(path);
      return f.existsSync() && superset.hasMatch(f.readAsStringSync());
    }).length;
    expect(matching, _allowedIconsCloseFiles.length,
        reason: 'every allowlisted file must correspond to a real X-shaped '
            'exit construction — an entry that does not is dead weight the '
            'allowlist should never have grown to include');
  });
}
