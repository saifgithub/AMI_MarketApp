/// DEF152 — the confirmation gate in front of "restart onboarding".
///
/// The control was a bare `TextButton` in the Floor footer, caption-sized and
/// in `hexBlue`, i.e. it read as a link rather than as a consequential one. A
/// tester hit it by accident and had to sit through the whole interview again.
/// The cost the gate protects against is that lost time.
///
/// DEF158 corrected what the gate CLAIMS. It originally said restarting
/// "clears the mandate your interview produced"; traced end to end, nothing
/// clears it — so for exactly the users who had a mandate to lose, the dialog
/// described a wipe that never happened. The body now states what is true for
/// both populations. Do not reinstate destructive language here without a
/// mechanism that actually replaces the mandate.
///
/// It lives in its own file rather than inline in `floor_screen.dart` for one
/// reason: the screen needs a dozen providers to pump, so an inline dialog is
/// effectively untestable, and an untested guard on a destructive action is
/// how the guard quietly stops working. Here it is a unit.
///
/// Returns `true` only on an explicit confirm — a dismissed barrier, a back
/// gesture and a cancel all return `false`, because `showDialog` resolves to
/// `null` for every one of those and `null != true`.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:flutter/material.dart';

Future<bool> confirmRestartOnboarding(BuildContext context) async {
  final l = AppLocalizations.of(context);
  final confirmed = await showDialog<bool>(
    context: context,
    builder: (ctx) => AlertDialog(
      backgroundColor: AmiColors.slate800,
      title: Text(
        l.floorRestartOnboardingConfirmTitle,
        style: AmiTypography.labelMono.copyWith(color: AmiColors.hexCyan),
      ),
      content: Text(
        l.floorRestartOnboardingConfirmBody,
        style: AmiTypography.body,
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.of(ctx).pop(false),
          child: Text(l.actionCancel),
        ),
        TextButton(
          onPressed: () => Navigator.of(ctx).pop(true),
          child: Text(
            l.floorRestartOnboardingConfirmCta,
            style: const TextStyle(color: AmiColors.hexRed),
          ),
        ),
      ],
    ),
  );
  return confirmed == true;
}
