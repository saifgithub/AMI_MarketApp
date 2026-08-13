/// CR180 — the one-time notice that the bottom nav was restructured.
///
/// CR133 moved the Journal and Settings off the bar and into `YOU`, and put
/// GAME where the Journal used to be. For a new user that is simply the app.
/// For everyone already using it, two things they know how to find are no
/// longer where they left them, and **nothing in the tour system would ever
/// have told them**: every section tour is gated on a `tour_*_seen` flag they
/// already carry, so the walkthrough is silent for exactly the population that
/// needs it.
///
/// That is CR040's shape pointed at the user's memory rather than at a config
/// value — the change is real, it is invisible, and the failure mode is
/// someone concluding a feature was removed.
///
/// **It names what they are looking for, not where it went.** "The Journal is
/// now in YOU" is a slot number in disguise; "Your Journal and Settings moved
/// together into YOU" tells someone hunting for either one that they are in the
/// same place. Same reasoning as CR133 §5: the useful thing is the destination,
/// not the route.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:flutter/material.dart';

class NavChangeSheet extends StatelessWidget {
  const NavChangeSheet({super.key});

  static Future<void> show(BuildContext context) => showModalBottomSheet<void>(
        context: context,
        backgroundColor: AmiColors.slate800,
        isScrollControlled: true,
        builder: (_) => const NavChangeSheet(),
      );

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    return SafeArea(
      child: Padding(
        padding: const EdgeInsets.fromLTRB(
          AmiSpacing.l, AmiSpacing.m, AmiSpacing.l, AmiSpacing.m,
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Center(
              child: Container(
                width: 36,
                height: 4,
                decoration: BoxDecoration(
                  color: AmiColors.slate600,
                  borderRadius: BorderRadius.circular(2),
                ),
              ),
            ),
            const SizedBox(height: AmiSpacing.l),
            Text(l.navChangeTitle, style: AmiTypography.h4),
            const SizedBox(height: AmiSpacing.s),
            Text(l.navChangeBody,
                style: AmiTypography.body.copyWith(color: AmiColors.textMed)),
            const SizedBox(height: AmiSpacing.m),
            _Line(icon: Icons.person_outline, text: l.navChangeYou),
            _Line(icon: Icons.insights_outlined, text: l.navChangeInsights),
            _Line(icon: Icons.emoji_events_outlined, text: l.navChangeGame),
            const SizedBox(height: AmiSpacing.l),
            SizedBox(
              width: double.infinity,
              child: ElevatedButton(
                style: ElevatedButton.styleFrom(
                  backgroundColor: AmiColors.hexCyan,
                  foregroundColor: AmiColors.slate900,
                  padding: const EdgeInsets.symmetric(vertical: 14),
                ),
                onPressed: () => Navigator.of(context).pop(),
                child: Text(l.navChangeGotIt,
                    style: AmiTypography.labelMono
                        .copyWith(color: AmiColors.slate900)),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _Line extends StatelessWidget {
  const _Line({required this.icon, required this.text});
  final IconData icon;
  final String text;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: AmiSpacing.s),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(icon, color: AmiColors.hexCyan, size: 18),
          const SizedBox(width: AmiSpacing.s),
          Expanded(child: Text(text, style: AmiTypography.body)),
        ],
      ),
    );
  }
}
