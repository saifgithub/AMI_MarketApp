/// CR172 §8 — the sell-to-open disclosure, shown BEFORE the user consents.
///
/// Saiful's ruling, 2026-08-20: the CR171 inform-not-block position extends to
/// options sell-to-open. So this dialog never refuses anything. It stands
/// between the YES button and the trade for exactly one reason — the notice
/// has to reach the person it is about, at the moment it is about them, and
/// `check_option_open` already put it in the payload for that purpose
/// ("an advisory that only reaches a log informs nobody", CR040).
///
/// **The body is the SERVER's text, rendered verbatim.** It reports a Sharia
/// position — gharar, and a premium received for an obligation rather than an
/// asset — and a client-side paraphrase of a ruling is a second, unverified
/// copy of a claim that then drifts from the first (DEF158, and the
/// `DayTraderDisclosureDialog` precedent it produced). Only the chrome — the
/// title and the two buttons — comes from the ARB.
///
/// The equity ticket shows its advisory AFTER the fill, because on that path
/// the server decides at submit and there is no earlier moment. Options
/// differ: AMI costs and checks the structure before the user is asked, so
/// the notice can precede the decision instead of explaining it. It should.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:flutter/material.dart';

class OptionDisclosureDialog extends StatelessWidget {
  const OptionDisclosureDialog({super.key, required this.advisories});

  /// The server's advisory sentences, in the order they arrived.
  final List<String> advisories;

  /// Resolves `true` only on an explicit acknowledgement. Cancel, back and a
  /// barrier dismiss all resolve to `false`/`null`, and the caller opens
  /// nothing on either.
  static Future<bool?> show(BuildContext context, List<String> advisories) {
    return showDialog<bool>(
      context: context,
      builder: (_) => OptionDisclosureDialog(advisories: advisories),
    );
  }

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    return AlertDialog(
      backgroundColor: AmiColors.slate800,
      title: Text(l.optionTicketDisclosureTitle, style: AmiTypography.h4),
      content: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            for (final a in advisories)
              Padding(
                padding: const EdgeInsets.only(bottom: AmiSpacing.s),
                child: Text(a, style: AmiTypography.body),
              ),
          ],
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.of(context).pop(false),
          child: Text(
            l.optionTicketDisclosureCancel,
            style: AmiTypography.labelMono.copyWith(
              color: AmiColors.textMed,
              fontSize: 12,
            ),
          ),
        ),
        ElevatedButton(
          style: ElevatedButton.styleFrom(
            backgroundColor: AmiColors.hexAmber,
            foregroundColor: AmiColors.slate900,
          ),
          onPressed: () => Navigator.of(context).pop(true),
          child: Text(
            l.optionTicketDisclosureAcknowledge,
            style: AmiTypography.labelMono
                .copyWith(color: AmiColors.slate900, fontSize: 12),
          ),
        ),
      ],
    );
  }
}
