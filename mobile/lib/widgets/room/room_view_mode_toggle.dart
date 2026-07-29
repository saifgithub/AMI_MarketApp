/// CR106 — the 44pt sub-header strip: run metadata on the left, the
/// BOARD | TRANSCRIPT control on the right.
///
/// Not folded into the existing 88pt `_Header`: the back button plus
/// `THE ROOM · NVDA` already consume ~140pt there, and the toggle needs ~152pt
/// — it overflows in Arabic.
///
/// The control is one of exactly three places hexagonal geometry survives in
/// this feature (the others being the agent marks and the hero's outcome mark).
///
/// **DEF146 / CR117 — it used to match `ticker_chart.dart`'s period chips
/// verbatim, and that was the bug.** Those chips use
/// [CutCornerOctagonClipper], which is an octagon, applied per chip. Copying
/// that here produced two independently-cut objects with a gap and an outline
/// each — reported as *"the buttons are not hex design"*, with the outline's
/// clipped remnant reading as a stray divider. The AT:Designer's toggle
/// (`df515c35`) is **one continuous elongated hexagon**: angled cuts on the
/// outer edges only, a straight internal divider, no outline. That shape is
/// not producible by the octagon clipper at any `cornerCut`, which is why
/// CR117 had to exist before this defect could be fixed.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/state/room_view_mode_provider.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:ami_trade/theme/hex_clipper.dart';
import 'package:flutter/material.dart';

class RoomSubHeader extends StatelessWidget {
  const RoomSubHeader({
    super.key,
    required this.meta,
    required this.mode,
    required this.onModeChanged,
    this.showToggle = true,
  });

  /// Already-resolved text, or **null for no strip at all** (CR111).
  ///
  /// The Room shows `41s · 3 CREDITS`. The Journal used to show
  /// `MID TIER · MANDATE v7` — a *substitute*, because `duration_ms` and
  /// `credit_cost` were never serialised into the snapshot and entries already
  /// written never will be. Saiful ruled the substitute out rather than pick
  /// between two surfaces wearing different text in the same slot, or a corpus
  /// split by entry age. Nothing is backfilled: an inferred duration would be a
  /// guess wearing the authority of a record.
  final String? meta;

  final RoomViewMode mode;

  /// Wired straight to `setMode`, and nothing else in the feature is. A mode
  /// change caused by anything other than this control must not rewrite the
  /// stored preference (T-MODESIDE).
  final ValueChanged<RoomViewMode> onModeChanged;

  /// The toggle appears only once a verdict exists. While the run is streaming
  /// the screen is always in transcript mode — a comb filling in live reads as
  /// a running vote count (T-LIVE).
  final bool showToggle;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);

    // CR111 — with no strip AND no toggle there is nothing in this bar, and a
    // 44pt empty chrome band with a bottom border reads as a rendering fault.
    // Draw nothing rather than an empty frame.
    if (meta == null && !showToggle) return const SizedBox.shrink();

    return Container(
      height: 44,
      padding: const EdgeInsets.symmetric(horizontal: AmiSpacing.m),
      decoration: const BoxDecoration(
        color: AmiColors.glassChrome,
        border: Border(bottom: BorderSide(color: AmiColors.slate700)),
      ),
      child: Row(
        children: [
          Expanded(
            child: meta == null
                ? const SizedBox.shrink()
                : Text(
                    meta!,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: AmiTypography.labelMono
                        .copyWith(fontSize: 10, color: AmiColors.textLow),
                  ),
          ),
          if (showToggle)
            // DEF146 — ONE clip around BOTH halves. Clipping each segment
            // separately is what shipped, and it is why the report reads "the
            // buttons are not hex design": two independently-cut objects with
            // a gap between them are two chips, whatever their geometry. The
            // clip belongs to the control, not to its parts.
            ClipPath(
              clipper: const FlatTopHexagonBarClipper(endInset: 8),
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  _Segment(
                    label: l.roomViewModeBoard,
                    active: mode == RoomViewMode.board,
                    onTap: () => onModeChanged(RoomViewMode.board),
                  ),
                  // The Designer's straight vertical divider. Not a gap: a gap
                  // re-creates two objects, which is the defect in disguise.
                  Container(width: 1, height: 32, color: AmiColors.slate700),
                  _Segment(
                    label: l.roomViewModeTranscript,
                    active: mode == RoomViewMode.transcript,
                    onTap: () => onModeChanged(RoomViewMode.transcript),
                  ),
                ],
              ),
            ),
        ],
      ),
    );
  }
}

class _Segment extends StatelessWidget {
  const _Segment({
    required this.label,
    required this.active,
    required this.onTap,
  });

  final String label;
  final bool active;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Semantics(
      selected: active,
      button: true,
      child: GestureDetector(
        onTap: onTap,
        behavior: HitTestBehavior.opaque,
        // DEF146: no clipper and no border here. The parent clips the whole
        // bar; an outline drawn per half would trace two shapes inside one,
        // and the outer edges of that outline are clipped away anyway, so it
        // reads as a stray line down the middle — the "stray vertical
        // divider" in the report.
        //
        // Fill flip only, no sliding pill — the design system rules out motion
        // on text, and a 200ms crossfade of the fill reads as a state change
        // without dragging the label across the screen.
        child: AnimatedContainer(
          duration: AmiMotion.normal,
          curve: AmiMotion.easeOut,
          height: 32,
          padding: const EdgeInsets.symmetric(horizontal: 14),
          alignment: Alignment.center,
          color: active ? AmiColors.hexBlue : AmiColors.slate800,
          child: Text(
            label,
            style: AmiTypography.labelMono.copyWith(
              fontSize: 10,
              color: active ? Colors.white : AmiColors.textMed,
            ),
          ),
        ),
      ),
    );
  }
}
