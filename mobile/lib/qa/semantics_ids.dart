/// CR162 — the stable element-identifier contract between the app and the
/// black-box UAT harness (`qa/appium/`).
///
/// These strings are passed to `Semantics(identifier: …)`, which Flutter maps
/// to `resource-id` on Android and `accessibilityIdentifier` on iOS. They ship
/// in release builds and are never rendered — `identifier` is not a label, it
/// carries no text for a screen reader to speak.
///
/// Why this file exists rather than string literals at each call site: before
/// CR162 the harness located everything by *rendered text*, so
/// `qa/appium/config/locales.py` had to carry every EN/AR/MS string verbatim
/// just to tap a bottom-nav tab. Navigation was coupled to translation, and any
/// ARB copy edit could silently break the test suite. An identifier is
/// locale-independent by construction, so the harness navigates by ID and
/// asserts on text only where the text is the thing under test.
///
/// Convention: `ami.<area>.<thing>`, lowercase, dot-separated. Keep in sync
/// with `qa/appium/config/semantics_ids.py`; `mobile/test/qa/semantics_ids_test.dart`
/// fails if a nav identifier is dropped or renamed.
library;

import 'package:ami_trade/features/games/games_gate.dart';

/// Bottom-nav destinations. Order matches `home_shell.dart`'s `IndexedStack`.
///
/// CR133 restructured the bar: JOURNAL and SETTINGS are no longer destinations
/// (both moved inside `YOU` as segments), and GAME arrived. The old IDs are
/// deleted rather than left pointing at nothing — a stale ID the harness can
/// still ask for is worse than a missing one, because it fails on the device
/// days later instead of here.
class NavIds {
  const NavIds._();

  static const String floor = 'ami.nav.floor';
  static const String portfolio = 'ami.nav.portfolio';
  static const String game = 'ami.nav.game';
  static const String lessons = 'ami.nav.lessons';
  static const String you = 'ami.nav.you';

  /// Every destination **this binary renders**, in on-screen order — the
  /// harness asserts this exact set is addressable as its GO/NO-GO gate, so a
  /// dropped ID fails loudly on the Mac rather than as a confusing red device
  /// run days later.
  ///
  /// Conditional on the same compile-time gate the tab itself is, because the
  /// harness runs against store builds: an unconditional list would demand the
  /// harness find a GAME tab that a `--no-games` binary correctly does not
  /// have, and a gate that fires when nothing is wrong teaches the operator
  /// that firing does not mean stop.
  static const List<String> all = [
    floor,
    portfolio,
    if (kGamesEnabled) game,
    lessons,
    you,
  ];
}

/// The `YOU` tab's three segments (CR133 moved SETTINGS and JOURNAL here from
/// the bottom nav; INSIGHTS is new).
///
/// These need identifiers for the same reason the nav destinations do, and one
/// more besides. A segment's *rendered label* is a poor handle even in English:
/// the label sits on the button, so an exact-text wait is satisfied by the
/// control the moment the tab paints — before the pane behind it has rendered
/// anything. Waiting on the ID and then asserting on pane-specific content
/// separates "the segment exists" from "the pane is up", which is the race
/// `tests/test_portfolio.py` hit on the bottom nav.
///
/// Embedded panes drop their own `AmiScreenHeader` (YOU owns the header), so
/// there is no heading to wait on either — the harness must key off content
/// like SETTINGS' `MY MANDATE` section or JOURNAL's filter chips.
class YouIds {
  const YouIds._();

  static const String settings = 'ami.you.settings';
  static const String journal = 'ami.you.journal';
  static const String insights = 'ami.you.insights';

  /// In `YouSegment` order, which is the on-screen order of the segment bar.
  static const List<String> all = [settings, journal, insights];
}

/// Modal sheets. These are the DEF075 class — interactive elements that can end
/// up under the Android system nav bar or the iOS home indicator, which is the
/// one usability check CR080 was built to catch.
class SheetIds {
  const SheetIds._();

  static const String convene = 'ami.sheet.convene';
  static const String conveneCta = 'ami.sheet.convene.cta';
  static const String merge = 'ami.sheet.merge';
  static const String mergeCta = 'ami.sheet.merge.cta';
}

/// CR209 — the Concierge interview, the one surface the onboarding walk must
/// drive and the only one it had no identifier for.
///
/// The walk used to select an answer by geometry: "the bottom-most labelled
/// control". On iOS the bottom of the screen never belongs to the chips, and
/// three different controls were measured occupying that slot in three
/// consecutive runs — the keyboard's globe key (186 taps), the composer text
/// field (180), the send arrow (579). Excluding them one at a time cannot
/// converge, because the pool is the platform's, not ours.
///
/// [DEF346] is the sharp edge: giving the send button a VoiceOver label — a
/// correct accessibility fix — is what made the harness's `labelled_only`
/// filter stop excluding it, and `_live_chip`'s docstring still asserts the
/// arrow "has none". An accessibility improvement silently invalidated a test
/// heuristic. An identifier cannot rot that way: it is addressed by name, and
/// `mobile/test/qa/semantics_ids_test.dart` fails locally if it is dropped.
///
/// [answerChip] is deliberately NOT unique per chip. The harness needs "an
/// answer for the current turn", and `onboarding_screen.dart` renders only the
/// live turn's chips (`state.currentChips`), so every node carrying this id is
/// a valid answer. Numbering them would invent an ordering the interview does
/// not have — the chips are backend-authored and their count varies by turn.
class OnboardingIds {
  const OnboardingIds._();

  /// Every tappable answer chip of the current interview turn.
  static const String answerChip = 'ami.onboarding.answer_chip';

  /// The free-text composer and its send button. Named so the walk can exclude
  /// them **by name** rather than by guessing at geometry — the walk answers
  /// with chips and never types.
  static const String composer = 'ami.onboarding.composer';
  static const String send = 'ami.onboarding.send';
}

/// DEF375 — the first-run coach-mark tours.
///
/// Five tours (floor, portfolio, lessons, journal, you) all render through the
/// single `TourCard`, so one identifier addresses every one of them. They are
/// modal: until one is dismissed the tab behind it is unreachable, which on a
/// fresh install is every tab. That cost the iOS gate 7 of its 19 tests —
/// `test_portfolio_renders_heading` failed with the app parked on YOU behind
/// the *YOU* tour, never having reached Portfolio at all.
///
/// Only [skip] is named. `Next` walks the tour a step at a time and would make
/// dismissal depend on how many steps a tour happens to have; skip is one tap
/// whatever the tour, and the harness is not testing the tour's pagination.
class TourIds {
  const TourIds._();

  static const String skip = 'ami.tour.skip';
}
