import 'package:ami_trade/qa/semantics_ids.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:ami_trade/theme/hex_clipper.dart';
import 'package:flutter/material.dart';

/// Horizontal scrollable row of chip suggestions the Concierge offers
/// (e.g., "Save for retirement", "10+ years"). Tapping = submitting that answer.
class ChipRow extends StatelessWidget {
  const ChipRow({
    super.key,
    required this.chips,
    required this.onSelected,
  });

  final List<String> chips;
  final ValueChanged<String> onSelected;

  @override
  Widget build(BuildContext context) {
    if (chips.isEmpty) return const SizedBox.shrink();
    return SizedBox(
      height: 48,
      child: ListView.separated(
        scrollDirection: Axis.horizontal,
        padding: const EdgeInsets.symmetric(horizontal: AmiSpacing.m),
        itemCount: chips.length,
        separatorBuilder: (_, __) => const SizedBox(width: AmiSpacing.s),
        itemBuilder: (context, i) =>
            _Chip(label: chips[i], onTap: () => onSelected(chips[i])),
      ),
    );
  }
}

class _Chip extends StatelessWidget {
  const _Chip({required this.label, required this.onTap});
  final String label;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    // DEF249: without `button: true` this is announced as static text, so a
    // VoiceOver user on the very first onboarding question gets no signal that
    // the chips are tappable at all. Android's bridge marks any tappable node
    // `clickable` regardless, which is why this went unnoticed until the app
    // was driven on iOS, where a node is a button only if Flutter says so.
    // No `label:` here — the child Text already supplies one, and setting both
    // concatenates them, so VoiceOver announces the chip twice.
    // CR209: the identifier is what the UAT walk selects on. Without it the
    // walk had to guess "bottom-most labelled control", which on iOS is the
    // keyboard, the composer or the send arrow — never this. `identifier` is
    // not a label and is never spoken, so it does not disturb DEF249's
    // announcement above.
    return Semantics(
      button: true,
      identifier: OnboardingIds.answerChip,
      child: GestureDetector(
        onTap: onTap,
        child: ClipPath(
          clipper: const CutCornerOctagonClipper(cornerCut: 8),
          child: Container(
            padding: const EdgeInsets.symmetric(
                horizontal: AmiSpacing.m, vertical: 10),
            decoration: BoxDecoration(
              color: Colors.transparent,
              border: Border.all(color: AmiColors.hexBlue, width: 1),
            ),
            alignment: Alignment.center,
            child: Text(
              label,
              style: AmiTypography.body.copyWith(
                color: AmiColors.hexBlue,
                fontSize: 13,
                fontWeight: FontWeight.w500,
              ),
            ),
          ),
        ),
      ),
    );
  }
}
