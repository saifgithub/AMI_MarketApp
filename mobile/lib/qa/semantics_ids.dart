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
