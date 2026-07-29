/// CR106 — the 44pt sub-header strip: run metadata on the left, the
/// BOARD | TRANSCRIPT control on the right.
///
/// Not folded into the existing 88pt `_Header`: the back button plus
/// `THE ROOM · NVDA` already consume ~140pt there, and the toggle needs ~152pt
/// — it overflows in Arabic.
///
/// The control is one of exactly three places hexagonal geometry survives in
/// this feature (the others being the agent marks and the hero's outcome mark),
/// and it matches `ticker_chart.dart`'s period chips verbatim at `cornerCut: 8`.
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

  /// Already-resolved text — the Room shows `41s · 3 CREDITS`, the Journal
  /// `MID TIER · MANDATE v7`, because the snapshot never serialised the first
  /// pair. One slot, two facts, resolved by the caller.
  final String meta;

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
            child: Text(
              meta,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: AmiTypography.labelMono
                  .copyWith(fontSize: 10, color: AmiColors.textLow),
            ),
          ),
          if (showToggle)
            Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                _Segment(
                  label: l.roomViewModeBoard,
                  active: mode == RoomViewMode.board,
                  onTap: () => onModeChanged(RoomViewMode.board),
                ),
                const SizedBox(width: 2),
                _Segment(
                  label: l.roomViewModeTranscript,
                  active: mode == RoomViewMode.transcript,
                  onTap: () => onModeChanged(RoomViewMode.transcript),
                ),
              ],
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
        child: ClipPath(
          clipper: const FlatTopHexagonClipper(cornerCut: 8),
          // Fill flip only, no sliding pill — the design system rules out
          // motion on text, and a 200ms crossfade of the fill reads as a state
          // change without dragging the label across the screen.
          child: AnimatedContainer(
            duration: AmiMotion.normal,
            curve: AmiMotion.easeOut,
            height: 32,
            padding: const EdgeInsets.symmetric(horizontal: 12),
            alignment: Alignment.center,
            decoration: BoxDecoration(
              color: active ? AmiColors.hexBlue : AmiColors.slate800,
              border: Border.all(
                color: active ? AmiColors.hexBlue : AmiColors.slate700,
              ),
            ),
            child: Text(
              label,
              style: AmiTypography.labelMono.copyWith(
                fontSize: 10,
                color: active ? Colors.white : AmiColors.textMed,
              ),
            ),
          ),
        ),
      ),
    );
  }
}
