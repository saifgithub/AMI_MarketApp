/// CR226 — the text-scale clamp on fixed-height chrome.
///
/// `app.dart` sets no `builder:` and `textScaler` is set nowhere in the app
/// except `share_service.dart`'s offscreen PNG export (pinned to 1.0 there,
/// correctly — a share card is a fixed-size image, not a live layout). So
/// Flutter's default applies everywhere else: the OS font-size setting
/// multiplies every `fontSize`, unbounded — iOS Dynamic Type reaches ~3.1×,
/// Android's slider 2.0×. Fine for body/lesson text, which can reflow and
/// scroll. Not fine for the app's fixed-height chrome — `ami_screen_header.dart`
/// and `hex_bottom_nav.dart` are both `height: 64`, `ticker_tape.dart` is
/// 28dp — which does not grow with it, so at 2× a 12pt title renders at 24pt
/// inside a box built for 12pt.
///
/// The fix is scoped, not global: clamping `textScaler` app-wide would
/// defeat the OS accessibility setting for the screens where it matters
/// most (lesson content, agent dialogue). [clampChrome] wraps ONLY the three
/// chrome widgets `CR226_adaptive_banner_slot.md` names — the bottom nav,
/// the screen header, and the ticker tape — each individually, at their own
/// mount points, so body content one level up or down the tree is
/// unaffected. `MediaQuery.withClampedTextScaling` is the one call this
/// wraps; the constant lives here so all three call sites (and the widget
/// test asserting no overflow at 1.0×/2.0×/3.1×) read the same bound.
library;

import 'package:flutter/widgets.dart';

/// Recommended bound from the CR226 doc: chrome stays legible up to 1.3×
/// (still larger than the 1.0× baseline every screenshot and design review
/// was done against) without the fixed-height boxes overflowing.
const double kChromeMaxTextScaleFactor = 1.3;

/// Wraps [child] so any `Text` inside it never scales past
/// [kChromeMaxTextScaleFactor], regardless of the OS setting. Scaling BELOW
/// the bound (a user who sets smaller-than-default text) passes through
/// unclamped — this only ever prevents chrome overflow, never fights a user
/// who wants smaller text.
Widget clampChromeTextScale({required Widget child}) {
  return MediaQuery.withClampedTextScaling(
    maxScaleFactor: kChromeMaxTextScaleFactor,
    child: child,
  );
}
