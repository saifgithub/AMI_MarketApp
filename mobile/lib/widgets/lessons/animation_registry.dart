/// AnimationRegistry — maps `<Animation name="..." />` keys to asset paths.
///
/// A21 decouples lesson content from animation production: an MDX lesson can
/// reference an animation name today; if a Lottie file is bundled at the
/// matching key, the `AnimationBlock` widget plays it. If no asset exists yet,
/// the widget renders an `AmiHexPlaceholder` so the lesson still ships and a
/// later commit can drop the Lottie file in without touching content.
///
/// Add new entries here when you bundle a new animation. Keep keys lowercase
/// snake_case and stable — they're referenced by every translation of every
/// lesson that uses them.
library;

class AnimationRegistry {
  AnimationRegistry._();

  /// Asset map. Empty at A21 — no Lottie files are bundled yet. When you add
  /// `assets/animations/<name>.json` to pubspec, register it here.
  ///
  /// Example future entry:
  ///   'risk_pyramid': 'assets/animations/risk_pyramid.json',
  static const Map<String, String> _assets = <String, String>{};

  /// Return the asset path for `name`, or null if no animation is bundled.
  /// Callers should render the hex placeholder when this returns null.
  static String? assetFor(String name) => _assets[name.toLowerCase()];

  /// Whether the registry has a bundled asset for `name`. Convenience
  /// boolean for widgets that need a quick has-animation check before
  /// importing a Lottie playback dependency.
  static bool has(String name) => _assets.containsKey(name.toLowerCase());
}
