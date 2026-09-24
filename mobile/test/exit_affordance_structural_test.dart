/// CR232 (failure_patterns.md P36) — the exit-affordance guard.
///
/// Saiful: *"Some pages are simply using an 'X' to exit (top right) —
/// obscure and not in line with the app's aesthetics."* CR232 gave every
/// pushed full page a back chevron (`AmiScreenHeader`'s `showBack`, or the
/// hand-styled equivalent on the two screens that don't use it) instead, and
/// removed every top-right `Icons.close` that used to be a page's only way
/// out. Rule 4's exception is narrow: `Icons.close` still belongs on small
/// INLINE dismissals — an ad card, a chip's delete glyph, a notice banner's
/// own X — never on a page's own exit.
///
/// This is the P36 enforcing check: a per-screen review cannot see that ~13
/// independent close buttons shared one root cause (every pushed screen
/// covered the shell and had nothing else to pop to), so the check that
/// holds is structural — walk the source, name every file that still uses
/// `Icons.close`, and fail if one is not on the allowlist below. A NEW page
/// that reaches for `Icons.close` as its exit fails this test immediately;
/// a genuinely new inline dismissal is added to the allowlist deliberately,
/// by name, in the same commit that adds it — never silently.
///
/// Mirrors `ads_structural_test.dart`'s discovery method: walk `lib/`, no
/// separately-maintained list of files to scan (only of files to exempt).
library;

import 'dart:io';

import 'package:flutter_test/flutter_test.dart';

/// Every file that still contains `Icons.close`, and why each one is fine.
///
/// All nine are inline dismissals or chip-delete glyphs on content that sits
/// *inside* a page, never a page's own top-right exit — CR232 rule 4's
/// exception. `home_shell.dart` and `qa/semantics_ids.dart` are not on this
/// list because they only ever *mention* `Icons.close` in doc comments
/// explaining CR232 itself; the regex below matches the real `Icon(...)`
/// construction, not prose, so neither needs an entry.
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

/// Matches the real widget construction (`Icon(Icons.close` /
/// `Icons.close,` inside an `Icon(`/`IconButton(` call), not a bare mention
/// in a doc comment — `home_shell.dart` and `qa/semantics_ids.dart` both
/// talk ABOUT `Icons.close` without constructing one, and must not trip this.
final _iconsCloseConstruction = RegExp(r'Icon(?:Button)?\(\s*[\s\S]{0,80}?Icons\.close');

void main() {
  test('Icons.close is used only for inline dismissals, never a page exit',
      () {
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
        if (_iconsCloseConstruction.hasMatch(src)) {
          offenders.add(path);
        }
      }
    }
    expect(offenders, isEmpty,
        reason: 'CR232 (failure_patterns.md P36): a pushed full page must '
            'exit via AmiScreenHeader\'s back chevron (or the hand-styled '
            'equivalent for the two screens that don\'t use it), never a '
            'top-right Icons.close. If this is a genuine new INLINE '
            'dismissal (an ad card, a chip delete, a notice banner), add it '
            'to _allowedIconsCloseFiles by name in the same commit — do not '
            'widen the allowlist to unblock an unrelated change:\n'
            '${offenders.join('\n')}');
  });

  test('the allowlist itself has no stale entries', () {
    // The inverse check: every allowlisted file must still actually contain
    // an Icons.close construction. An entry that no longer needs its
    // exemption is a silent hole the next real regression could hide behind.
    final stale = <String>[];
    for (final path in _allowedIconsCloseFiles) {
      final f = File(path);
      if (!f.existsSync()) {
        stale.add('$path (file no longer exists)');
        continue;
      }
      if (!_iconsCloseConstruction.hasMatch(f.readAsStringSync())) {
        stale.add('$path (no longer constructs Icons.close)');
      }
    }
    expect(stale, isEmpty,
        reason: 'These allowlist entries are stale — remove them so the '
            'allowlist only ever names files that actually need the '
            'exemption:\n${stale.join('\n')}');
  });
}
