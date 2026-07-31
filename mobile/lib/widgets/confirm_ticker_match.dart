/// CR128 — the "did you mean X?" confirmation gate shared by Convene the
/// Room, trade submit, and watchlist add.
///
/// Bug report `ab1d5664`: none of those three flows checked that a typed
/// ticker actually existed. A typo either got a fabricated mock price (trade)
/// or ran a full 12-agent Room debate and spent real credits on nothing
/// (Room convene) before anything noticed. The fix is a shared existence
/// check (`ApiClient.validateTicker`) plus this dialog for the one case that
/// needs a human decision: a close-but-not-exact match, where the reporter's
/// own acceptance criterion was "display a bit about the company and get
/// confirmation" before proceeding.
///
/// Lives in its own file for the same reason `confirm_restart_onboarding.dart`
/// does — a dialog inline in three different screens is untestable as a
/// unit, and an untested confirmation gate is how it quietly stops guarding.
///
/// Returns the accepted ticker only on explicit confirm; a dismissed
/// barrier, a back gesture, and Cancel all resolve to `null` — `showDialog`
/// resolves to `null` for every one of those, and the caller must treat
/// `null` as "abort, no side effects" exactly like the empty-ticker case it
/// already handles.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:flutter/material.dart';

Future<String?> confirmTickerMatch(
  BuildContext context, {
  required String typed,
  required String suggestedTicker,
  required String suggestedCompanyName,
  required String exchange,
}) async {
  final l = AppLocalizations.of(context);
  final confirmed = await showDialog<bool>(
    context: context,
    builder: (ctx) => AlertDialog(
      backgroundColor: AmiColors.slate800,
      title: Text(
        l.tickerConfirmTitle(suggestedTicker),
        style: AmiTypography.labelMono.copyWith(color: AmiColors.hexCyan),
      ),
      content: Text(
        l.tickerConfirmBody(typed, suggestedCompanyName, exchange),
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
            l.tickerConfirmCta(suggestedTicker),
            style: const TextStyle(color: AmiColors.hexCyan),
          ),
        ),
      ],
    ),
  );
  return confirmed == true ? suggestedTicker : null;
}
