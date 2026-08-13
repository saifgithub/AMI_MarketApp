/// The bottom nav's tabs, as a type rather than as an integer (CR133 §3).
///
/// **Why this exists.** Tabs were addressed by bare `int` literals scattered
/// across five screens — `state = 2, // Journal`, `if (next != 2)`,
/// `!= 0`. CR133 inserts [game] at index 2, and CR133 §3 measured what that
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
/// `HomeShell`'s `IndexedStack` indexes its children by [AmiTab.index]. The
/// declaration order and the child order are therefore one fact, asserted in
/// `home_shell_test.dart` rather than maintained by hand.
///
/// **[game] is declared here even in a build that cannot show it.** The
/// compile-time `AMI_GAMES` gate decides whether the tab is *rendered*, not
/// whether it exists as a value — `HomeShell` filters [visible] and every
/// index it uses is an index into that filtered list, never into
/// [AmiTab.values]. Making the enum itself conditional is not possible in
/// Dart, and faking it with a second enum would put the renumbering hazard
/// straight back. The store-binary guarantee is unaffected and stays where
/// CR109 put it: `app.dart` registers no `/games` route and the games screens
/// tree-shake out, so a gated-off build has nothing to reach.
library;

import 'package:ami_trade/features/games/games_gate.dart';

enum AmiTab {
  floor,
  portfolio,
  game,
  lessons,
  you;

  /// The tabs this binary actually renders, in bar order.
  ///
  /// With `AMI_GAMES` off this is four tabs and there is **no hole** — the bar
  /// sizes itself from `items.length`, so a gated-off build shows four wider
  /// cells rather than an empty cell or a "coming soon" promise sitting in
  /// prime real estate.
  static List<AmiTab> get visible => kGamesEnabled
      ? AmiTab.values
      : AmiTab.values.where((t) => t != AmiTab.game).toList(growable: false);
}
