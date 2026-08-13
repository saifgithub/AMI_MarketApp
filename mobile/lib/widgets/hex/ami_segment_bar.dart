/// The full-width segmented control: one continuous flat-top hexagon, straight
/// internal dividers, fill flip only (CR133 §4, second use of CR120's idiom).
///
/// **Why this is shared rather than a fourth private copy.** Portfolio already
/// carried a private 3-segment version and the Room a private 2-segment one,
/// and both of them exist in their current form because of **DEF146**: the
/// first build clipped *each* segment separately, which produced two
/// independently-cut objects with a gap and an outline each, reported as
/// *"the buttons are not hex design"*. That fix is a property of the control —
/// one `ClipPath` around the whole bar, a 1pt `slate700` divider rather than a
/// gap, no per-segment border — and a property that lives in two hand-copied
/// widgets is one edit away from being a property of one of them. CR133 needs a
/// third instance for `YOU`, so it becomes a component.
///
/// The Room's toggle is deliberately **not** migrated: it is `MainAxisSize.min`
/// and shares a 44pt strip with run metadata, so it is a different control that
/// happens to share a clipper.
///
/// No sliding indicator and no swipe, per the design system: motion on text is
/// ruled out, and a fill crossfade reads as a state change without dragging the
/// label across the screen.
library;

import 'package:ami_trade/theme/ami_theme.dart';
import 'package:ami_trade/theme/hex_clipper.dart';
import 'package:flutter/material.dart';

class AmiSegment {
  const AmiSegment({
    required this.label,
    this.trailing,
    this.key,
    this.semanticsId,
  });

  /// The translated on-screen label.
  final String label;

  /// Optional adornment after the label — a live pip, a dirty marker.
  final Widget? trailing;

  /// Attached to this segment's cell, for a coach-mark target.
  final Key? key;

  /// Locale-independent automation handle (see `qa/semantics_ids.dart`).
  final String? semanticsId;
}

class AmiSegmentBar extends StatelessWidget {
  const AmiSegmentBar({
    super.key,
    required this.segments,
    required this.selected,
    required this.onSelect,
  });

  final List<AmiSegment> segments;

  /// Index into [segments]. Out-of-range simply renders nothing as active,
  /// which is what a caller mid-transition should look like.
  final int selected;

  final ValueChanged<int> onSelect;

  @override
  Widget build(BuildContext context) {
    return Container(
      height: 44,
      padding:
          const EdgeInsets.symmetric(horizontal: AmiSpacing.m, vertical: 6),
      decoration: const BoxDecoration(
        color: AmiColors.glassChrome,
        border: Border(bottom: BorderSide(color: AmiColors.slate700)),
      ),
      // DEF146 — ONE clip around every segment. The clip belongs to the
      // control, not to its parts.
      child: ClipPath(
        clipper: const FlatTopHexagonBarClipper(endInset: 8),
        child: Row(
          children: [
            for (var i = 0; i < segments.length; i++) ...[
              if (i > 0)
                // The Designer's straight vertical divider. Not a gap: a gap
                // re-creates two objects, which is DEF146 in disguise.
                Container(width: 1, height: 32, color: AmiColors.slate700),
              Expanded(
                key: segments[i].key,
                child: _Cell(
                  segment: segments[i],
                  active: i == selected,
                  onTap: () => onSelect(i),
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

class _Cell extends StatelessWidget {
  const _Cell({
    required this.segment,
    required this.active,
    required this.onTap,
  });

  final AmiSegment segment;
  final bool active;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Semantics(
      selected: active,
      button: true,
      identifier: segment.semanticsId,
      child: GestureDetector(
        onTap: onTap,
        behavior: HitTestBehavior.opaque,
        // DEF146 — no clipper, no border, no FittedBox here. The parent clips
        // the whole bar; shrinking the label to fit is CR108's failure over
        // again — the bar is sized so it does not have to.
        child: AnimatedContainer(
          duration: AmiMotion.normal,
          curve: AmiMotion.easeOut,
          height: 32,
          alignment: Alignment.center,
          color: active ? AmiColors.hexBlue : AmiColors.slate800,
          child: Row(
            mainAxisSize: MainAxisSize.min,
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Flexible(
                child: Text(
                  segment.label,
                  maxLines: 1,
                  softWrap: false,
                  overflow: TextOverflow.visible,
                  style: AmiTypography.labelMono.copyWith(
                    fontSize: 10,
                    color: active ? Colors.white : AmiColors.textMed,
                  ),
                ),
              ),
              if (segment.trailing != null) ...[
                const SizedBox(width: 4),
                segment.trailing!,
              ],
            ],
          ),
        ),
      ),
    );
  }
}
