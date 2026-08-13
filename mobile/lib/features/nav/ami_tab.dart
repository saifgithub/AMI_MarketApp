/// The bottom nav's tabs, as a type rather than as an integer (CR133 §3).
///
/// **Why this exists.** Tabs were addressed by bare `int` literals scattered
/// across five screens — `state = 2, // Journal`, `if (next != 2)`,
/// `!= 0`. CR133 inserts `game` at index 2, and CR133 §3 measured what that
/// would have done:
///
///   * `portfolio_screen.dart`'s Portfolio History "Review in Journal" would
///     have opened **the game**;
///   * `journal_screen.dart`'s coach-mark tour would have fired on **the game
///     tab**, once, and marked itself seen forever.
///
/// Three of the five literals keep working through a reorder, **so a smoke
/// test passes** — the DEF190 class exactly, and the same shape as DEF284
/// where the broken case was the one branch nobody exercised.
///
/// A named value cannot silently mean a different tab after a reorder. Every
/// call site becomes a compile error the moment the set changes, and
/// `flutter analyze` coming back clean is the proof — not a reviewer's
/// attention. Inserting a tab later is then one line here instead of a
/// renumbering nobody can verify by reading.
///
/// **Order is meaningful**: it is the left-to-right order of the bar, and
/// `HomeShell`'s `IndexedStack` indexes its children by `AmiTab.index`. The
/// declaration order and the child order are therefore one fact, asserted in
/// `home_shell_test.dart` rather than maintained by hand.
library;

enum AmiTab {
  floor,
  portfolio,
  journal,
  lessons,
  settings,
}
