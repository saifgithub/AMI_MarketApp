/// DEF306 — what feature set is this build, said by the build itself.
///
/// `0.1.0+94` existed as two different Android apps: the Play AAB carried the
/// GAME tab, a cable-installed APK from a bare `flutter build apk` did not, and
/// both reported the same version string everywhere a human could look. The
/// founder reported a missing menu item, the register said the feature shipped
/// in `+89`, the Play artifact had it, the melehost rig's APK had it, and every
/// one of those facts pointed away from the answer. Attribution took an
/// `adb dumpsys` and a `libapp.so` extraction.
///
/// The version string cannot carry this: it comes from `pubspec.yaml` and is
/// identical across every producer. The compile-time gates are the thing that
/// actually differs, so the build states them next to its version.
///
/// This lives here, as a pure function of the flags rather than reading them
/// itself, for two reasons: `bool.fromEnvironment` is const-folded so a widget
/// test can only ever observe one value of it, and a label derived from the
/// same constant the gate uses cannot drift from what the binary does.
library;

/// The compile-time feature gates that are ON, as short uppercase labels.
///
/// Empty for a store binary — which is the point: the marker appears only when
/// the feature is genuinely present and reachable, so it can never advertise
/// something App Review would go looking for (guideline 2.3.1).
List<String> buildFeatureFlags({required bool gamesEnabled}) => [
      if (gamesEnabled) 'GAMES',
    ];

/// The one line shown under Settings: version, then whatever this binary
/// carries that another binary of the same version might not.
String buildIdentityLabel(String version, {required bool gamesEnabled}) {
  final flags = buildFeatureFlags(gamesEnabled: gamesEnabled);
  final base = 'AMI Trade v$version';
  return flags.isEmpty ? base : '$base · ${flags.join(' · ')}';
}
