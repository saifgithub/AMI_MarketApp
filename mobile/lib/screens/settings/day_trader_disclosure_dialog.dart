/// CR129 item 3 — the Day Trader disclosure dialog.
///
/// Shown BEFORE the preset is staged (inform, don't block — L3 draws no
/// ceiling on what a user may set, CR040 demands the change be loud). The
/// body is the SERVER-sent `mandate.dayTraderPreset.disclosure`, rendered
/// verbatim: it names what the preset removes, states plainly that
/// compliance, locale and halal/allow-blocklist rules are NOT removed, and
/// carries the Barber & Odean / Taiwan evidence. None of it is restated in
/// ARB copy — a client-side paraphrase would be a second copy of an
/// unverified-at-build-time claim (DEF158), drifting silently from the
/// server's. Chrome (title, buttons) is localized; the body is not.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:flutter/material.dart';

class DayTraderDisclosureDialog extends StatelessWidget {
  const DayTraderDisclosureDialog({super.key, required this.disclosure});

  /// The server-sent disclosure text, rendered verbatim.
  final String disclosure;

  /// Resolves true only on explicit confirm; false/null (cancel, barrier
  /// dismiss) leaves the mandate untouched.
  static Future<bool?> show(BuildContext context, String disclosure) {
    return showDialog<bool>(
      context: context,
      builder: (_) => DayTraderDisclosureDialog(disclosure: disclosure),
    );
  }

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    return AlertDialog(
      backgroundColor: AmiColors.slate800,
      title: Text(l.settingsDayTraderDisclosureTitle, style: AmiTypography.h4),
      content: SingleChildScrollView(
        child: Text(
          disclosure,
          key: const Key('dayTraderDisclosureBody'),
          style: AmiTypography.body,
        ),
      ),
      actions: [
        TextButton(
          key: const Key('dayTraderCancel'),
          onPressed: () => Navigator.of(context).pop(false),
          child: Text(l.settingsDayTraderCancel),
        ),
        TextButton(
          key: const Key('dayTraderConfirm'),
          onPressed: () => Navigator.of(context).pop(true),
          child: Text(
            l.settingsDayTraderConfirm,
            style: AmiTypography.labelMono.copyWith(color: AmiColors.hexAmber),
          ),
        ),
      ],
    );
  }
}
