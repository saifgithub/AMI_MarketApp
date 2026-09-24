/// DEF420 — the app's first shared width-class helper.
///
/// Saiful, on the Standings restyle: *"really it should be adaptive to the
/// different screen size surely?"* Before this there was no app-wide
/// responsive convention to reuse (checked: no breakpoint constant, no
/// `LayoutBuilder`-derived width class, no max-content-width anywhere in
/// `mobile/lib`). The one adjacent precedent, `AnchoredAdBanner`
/// (`widgets/ads/anchored_ad_banner.dart`), measures its own width via
/// `LayoutBuilder` for a single purpose (AdMob's `AdSize` wants an exact dp
/// int) and is not a general-purpose class — it has no notion of
/// compact/medium/expanded at all.
///
/// This is deliberately small and general so other screens can adopt it
/// later — it does not know anything about Standings, ads, or any other
/// screen's content.
///
/// Breakpoints follow Material 3's window size classes
/// (https://m3.material.io/foundations/layout/applying-layout/window-size-classes):
/// compact < 600dp (the overwhelming majority of phones, portrait and most
/// landscape), medium 600–840dp (large/unfolded phones, small tablets in
/// portrait), expanded > 840dp (tablets, foldables unfolded, landscape
/// tablets). Only three classes — M3 also defines large/extra-large for
/// desktop-class widths, which this app does not target (mobile-first per
/// CLAUDE.md's tech stack decision).
library;

import 'package:flutter/widgets.dart';

/// Material 3 window size class, derived from available WIDTH only (M3 also
/// has a height axis; this app's screens scroll vertically, so width is the
/// axis that actually changes layout shape here).
enum AmiWindowWidthClass {
  compact,
  medium,
  expanded;

  bool get isCompact => this == AmiWindowWidthClass.compact;
  bool get isMedium => this == AmiWindowWidthClass.medium;
  bool get isExpanded => this == AmiWindowWidthClass.expanded;

  /// True on medium or expanded — the common "is there more room than a
  /// phone-portrait screen" check a caller reaches for most often.
  bool get isAtLeastMedium => this != AmiWindowWidthClass.compact;
}

abstract final class AmiBreakpoints {
  /// Below this: compact. M3's own compact/medium boundary.
  static const double medium = 600;

  /// Below this: medium. Above: expanded. M3's own medium/expanded boundary.
  static const double expanded = 840;

  /// The width a single-column reading layout is constrained to on
  /// medium/expanded windows, centred, so a leaderboard row or a status card
  /// does not stretch into an unreadably long line on a tablet. Not tied to
  /// either breakpoint value above — this is a typography/reading-measure
  /// choice, not a device-class one.
  static const double maxContentWidth = 640;
}

AmiWindowWidthClass windowWidthClassOf(double widthDp) {
  if (widthDp >= AmiBreakpoints.expanded) return AmiWindowWidthClass.expanded;
  if (widthDp >= AmiBreakpoints.medium) return AmiWindowWidthClass.medium;
  return AmiWindowWidthClass.compact;
}

/// Wraps [child] in a [LayoutBuilder] and hands the resolved
/// [AmiWindowWidthClass] (plus the exact width) to [builder]. Width-derived
/// (`constraints.maxWidth`), not `MediaQuery.sizeOf` — the same reasoning
/// `AnchoredAdBanner`'s doc comment gives: the constraint is what this
/// widget actually has to lay out into (safe-area insets, a split-pane
/// ancestor, a constrained parent), where the full `MediaQuery` size is the
/// whole screen and can overstate what is actually available here.
class AmiWindowSizeBuilder extends StatelessWidget {
  const AmiWindowSizeBuilder({super.key, required this.builder});

  final Widget Function(
    BuildContext context,
    AmiWindowWidthClass windowClass,
    double widthDp,
  ) builder;

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        final widthDp = constraints.maxWidth;
        return builder(context, windowWidthClassOf(widthDp), widthDp);
      },
    );
  }
}

/// Centres [child] and caps it at [maxWidth] (default
/// [AmiBreakpoints.maxContentWidth]) — the standard "readable column on a
/// wide window" wrapper. A no-op (returns [child] unchanged) below the cap,
/// so it costs nothing on the compact windows almost every session runs in.
class AmiContentWidthConstraint extends StatelessWidget {
  const AmiContentWidthConstraint({
    super.key,
    required this.child,
    this.maxWidth = AmiBreakpoints.maxContentWidth,
  });

  final Widget child;
  final double maxWidth;

  @override
  Widget build(BuildContext context) {
    return Align(
      alignment: Alignment.topCenter,
      child: ConstrainedBox(
        constraints: BoxConstraints(maxWidth: maxWidth),
        child: child,
      ),
    );
  }
}
