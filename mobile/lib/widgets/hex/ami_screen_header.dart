/// The 64pt screen chrome every tab draws at its top (CR133 §7).
///
/// **Why this exists.** Four screens each carried a private `_Header` that
/// rendered the same thing — `Container(height: 64)`, `glassChrome`, a
/// `slate700` bottom border, a mono accent title, optional trailing actions.
/// Four independent renderers of one piece of chrome is the DEF098 class, and
/// hand-adding a fifth for `YOU` is exactly how it stays that way. CR133 adds
/// two more surfaces (`YOU`, and Settings as a pushed route needing a back
/// affordance), so the copy count was about to go from four to six.
///
/// **The right padding is derived, not passed.** The four originals disagreed:
/// Journal used `only(left: m, right: xs)` because an `IconButton` carries its
/// own 12pt of internal padding, while Portfolio used `symmetric(horizontal: m)`
/// with the *same* trailing `IconButton` and therefore sat 12pt further from the
/// edge. There was no rule to preserve — only two screens that drifted. The rule
/// is now here: a trailing action supplies its own inset, so the container gives
/// it `xs`; a bare title gets the full `m`.
///
/// Floor is deliberately not converted (CR133 §7, phase 3): it has no header at
/// all — its logo row sits inside a `SingleChildScrollView` and scrolls away —
/// so giving it one is a visible change to a screen this CR is not otherwise
/// touching.
library;

import 'package:ami_trade/theme/ami_theme.dart';
import 'package:flutter/material.dart';

class AmiScreenHeader extends StatelessWidget {
  const AmiScreenHeader({
    super.key,
    required this.title,
    required this.titleColor,
    this.subtitle,
    this.showBack = false,
    this.onBack,
    this.actions = const <Widget>[],
  });

  /// The translated heading. Rendered in `labelMono` at [titleColor].
  final String title;

  /// The screen's accent — `hexCyan` for Portfolio, `hexGreen` for Lessons,
  /// `hexBlue` for Journal and Settings. Required rather than defaulted: the
  /// accent identifies the screen, so a new one must choose.
  final Color titleColor;

  /// Optional caption immediately after the title (Settings' mandate version).
  final String? subtitle;

  /// Show a back chevron before the title. [onBack] defaults to `Navigator.pop`.
  final bool showBack;
  final VoidCallback? onBack;

  /// Trailing controls, right-aligned. Non-empty tightens the right inset —
  /// see the library comment.
  final List<Widget> actions;

  @override
  Widget build(BuildContext context) {
    return Container(
      height: 64,
      padding: EdgeInsets.only(
        left: AmiSpacing.m,
        right: actions.isEmpty ? AmiSpacing.m : AmiSpacing.xs,
      ),
      decoration: const BoxDecoration(
        color: AmiColors.glassChrome,
        border: Border(bottom: BorderSide(color: AmiColors.slate700)),
      ),
      child: Row(
        children: [
          if (showBack) ...[
            GestureDetector(
              onTap: onBack ?? () => Navigator.of(context).pop(),
              child: const Icon(Icons.arrow_back_ios_new,
                  size: 18, color: AmiColors.textMed),
            ),
            const SizedBox(width: AmiSpacing.m),
          ],
          Text(title,
              style: AmiTypography.labelMono.copyWith(color: titleColor)),
          if (subtitle != null) ...[
            const SizedBox(width: AmiSpacing.s),
            // Flexible, because the slot is shared and the only subtitle it
            // had until CR173 was Settings' `MANDATE v7`. A caller with an
            // ordinary sentence overflowed the row by 326px — the header did
            // not constrain what it renders, it was just never given anything
            // long. One ellipsis is a clipped subtitle; an unbounded Row is a
            // yellow-striped screen.
            Flexible(
              child: Text(subtitle!,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: AmiTypography.caption),
            ),
          ],
          const Spacer(),
          ...actions,
        ],
      ),
    );
  }
}
