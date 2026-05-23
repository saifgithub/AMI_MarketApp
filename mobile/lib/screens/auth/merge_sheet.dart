/// BL16 (AT:R38) — Account merge sheet.
///
/// Triggered from [SignInScreen] when an account-linking-Phase-1 adoption
/// fired (AuthVerifyResponse.adoptedFromUserId was non-null). Shows the
/// preview counts of what the orphan row holds and lets the user pick
/// [MERGE EVERYTHING] (re-keys the data into the adopting account) or
/// [KEEP SEPARATE] (closes the sheet, orphan stays in the DB for now).
///
/// This is the MVP scope (AT:R38). Followup work: per-bucket toggles
/// (journal yes, sim no), mandate-conflict resolution UI, and a
/// "Merged accounts" history section in Settings.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/merge.dart';
import 'package:ami_trade/state/onboarding_providers.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

/// Pushes the merge sheet as a modal bottom-sheet, fetches the preview
/// first, and returns once the user has chosen an action. Surfaces a
/// snackbar on the calling [BuildContext] on success / failure.
Future<void> showMergeSheet(
  BuildContext context,
  WidgetRef ref, {
  required String adoptedFromUserId,
}) async {
  final api = ref.read(apiClientProvider);
  MergePreview preview;
  try {
    preview = await api.previewMerge(fromUserId: adoptedFromUserId);
  } catch (_) {
    // Preview failed (network blip, 403/404 race) — silently swallow.
    // The user's sign-in still succeeded; we just couldn't surface the
    // merge offer. They can find it again later via Settings.
    return;
  }
  if (!context.mounted) return;
  await showModalBottomSheet<void>(
    context: context,
    isScrollControlled: true,
    backgroundColor: AmiColors.slate900,
    shape: const RoundedRectangleBorder(
      borderRadius: BorderRadius.vertical(top: Radius.circular(16)),
    ),
    builder: (_) => _MergeSheet(preview: preview),
  );
}

class _MergeSheet extends ConsumerStatefulWidget {
  const _MergeSheet({required this.preview});
  final MergePreview preview;

  @override
  ConsumerState<_MergeSheet> createState() => _MergeSheetState();
}

class _MergeSheetState extends ConsumerState<_MergeSheet> {
  bool _busy = false;

  Future<void> _confirm() async {
    setState(() => _busy = true);
    try {
      final api = ref.read(apiClientProvider);
      await api.executeMerge(fromUserId: widget.preview.fromUserId);
      if (!mounted) return;
      Navigator.of(context).pop();
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(
        content: Text(AppLocalizations.of(context).mergeSheetSuccess),
      ));
    } catch (_) {
      if (!mounted) return;
      setState(() => _busy = false);
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(
        content: Text(AppLocalizations.of(context).mergeSheetFailed),
      ));
    }
  }

  void _keepSeparate() {
    Navigator.of(context).pop();
  }

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final p = widget.preview;
    final lines = <String>[];
    if (p.journalEntries > 0) {
      lines.add(l.mergeSheetJournalEntries(p.journalEntries));
    }
    if (p.simTrades > 0) lines.add(l.mergeSheetSimTrades(p.simTrades));
    if (p.simWatchlists > 0) lines.add(l.mergeSheetWatchlist(p.simWatchlists));
    if (p.lessonsProgress > 0) lines.add(l.mergeSheetLessons(p.lessonsProgress));
    if (p.oneOnOneMessages > 0) {
      lines.add(l.mergeSheetOneOnOnes(p.oneOnOneMessages));
    }
    if (p.roomRuns > 0) lines.add(l.mergeSheetRoomRuns(p.roomRuns));
    if (p.mandateConflict) {
      lines.add(l.mergeSheetMandate);
    }

    return SafeArea(
      child: Padding(
        padding: const EdgeInsets.fromLTRB(
          AmiSpacing.m,
          AmiSpacing.m,
          AmiSpacing.m,
          AmiSpacing.l,
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Container(
              width: 36,
              height: 4,
              margin: const EdgeInsets.only(bottom: AmiSpacing.m),
              decoration: BoxDecoration(
                color: AmiColors.textLow,
                borderRadius: BorderRadius.circular(2),
              ),
            ),
            Text(
              l.mergeSheetTitle,
              style: AmiTypography.labelMono.copyWith(color: AmiColors.hexCyan),
            ),
            const SizedBox(height: AmiSpacing.s),
            Text(
              p.isEmpty ? l.mergeSheetEmptyBody : l.mergeSheetBody,
              style: AmiTypography.body,
            ),
            const SizedBox(height: AmiSpacing.m),
            if (lines.isNotEmpty) ...[
              Container(
                padding: const EdgeInsets.all(AmiSpacing.m),
                decoration: BoxDecoration(
                  color: AmiColors.slate800,
                  borderRadius: BorderRadius.circular(AmiRadii.card),
                  border: Border.all(color: AmiColors.slate700),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    for (final line in lines) ...[
                      Row(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          const Padding(
                            padding: EdgeInsets.only(top: 6, right: AmiSpacing.s),
                            child: Icon(Icons.circle,
                                size: 5, color: AmiColors.hexCyan),
                          ),
                          Expanded(
                            child: Text(line, style: AmiTypography.body),
                          ),
                        ],
                      ),
                      const SizedBox(height: AmiSpacing.xs),
                    ],
                  ],
                ),
              ),
              const SizedBox(height: AmiSpacing.l),
            ],
            if (p.isEmpty)
              SizedBox(
                height: 44,
                child: FilledButton(
                  onPressed: _busy ? null : _keepSeparate,
                  child: Text(l.mergeSheetClose),
                ),
              )
            else ...[
              SizedBox(
                height: 48,
                child: FilledButton(
                  onPressed: _busy ? null : _confirm,
                  style: FilledButton.styleFrom(
                    backgroundColor: AmiColors.hexCyan,
                    foregroundColor: AmiColors.slate900,
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(AmiRadii.card),
                    ),
                  ),
                  child: _busy
                      ? const SizedBox(
                          width: 18, height: 18,
                          child: CircularProgressIndicator(
                            strokeWidth: 2,
                            valueColor: AlwaysStoppedAnimation(Colors.black),
                          ),
                        )
                      : Text(l.mergeSheetConfirm),
                ),
              ),
              const SizedBox(height: AmiSpacing.s),
              SizedBox(
                height: 44,
                child: OutlinedButton(
                  onPressed: _busy ? null : _keepSeparate,
                  child: Text(l.mergeSheetKeepSeparate),
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
}
