/// CR109 Amendment F — the dark-launch gate for The Game.
///
/// The game is built and shipping into the same app as everything else, but
/// no user may reach it yet. The gate is a COMPILE-TIME constant rather than
/// a runtime feature flag, and that distinction is the whole design:
///
///   * A runtime flag still ships the route in every binary. App Review
///     guideline 2.3.1 names hidden and undocumented features, and a flag
///     someone can flip is exactly the kind of control CR040 says not to
///     rely on ("prompt instructions are not controls" — the same logic
///     applies to booleans a caller can set).
///   * `bool.fromEnvironment` is const-folded, so with the flag off the
///     conditional route entry in `app.dart` is not merely unreachable —
///     the compiler removes it, and the games screens tree-shake out with
///     nothing referencing them.
///
/// So the store binary contains no games route at all, which is why CR109
/// needs no server-side kill switch or user allowlist to stay dark. Saiful,
/// rejecting both: *"why bother? so long as no one can reach it, the
/// additional control adds complication with no upside."*
///
/// Turned on only for Saiful's own cable-installed release builds, on both
/// platforms, by `scripts/install_iphone.sh` and `scripts/install_android.sh`.
/// `scripts/build_testflight.sh` and `scripts/build_playstore.sh` deliberately
/// do NOT pass it, so every store binary stays dark.
///
///     flutter build ios --release --dart-define=AMI_GAMES=1
///
/// Deleting this gate is what "shipping the game" will mean; until then, a
/// widget test asserts `/games` is absent from the route map when it is off.
library;

const bool kGamesEnabled = bool.fromEnvironment(
  'AMI_GAMES',
  defaultValue: false,
);
