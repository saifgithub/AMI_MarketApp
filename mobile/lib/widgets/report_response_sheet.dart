/// CR278 (CR267 WP-36) - the long-press action on an AMI response.
///
/// Long-pressing a Room turn, the verdict, or a chat reply opens this one-row
/// sheet; its row opens the existing bug-report sheet pre-filled for that
/// response ([showBugReportSheet] with a [ResponseReportTarget]). A confirm
/// step on purpose: a long-press is also how a user tries to select text, and
/// it must not drop them straight into a form.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/response_report.dart';
import 'package:ami_trade/qa/semantics_ids.dart';
import 'package:ami_trade/screens/feedback/bug_report_sheet.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:ami_trade/widgets/sheet_insets.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

Future<void> showReportResponseActions(
  BuildContext context,
  WidgetRef ref,
  ResponseReportTarget target,
) async {
  final report = await showModalBottomSheet<bool>(
    context: context,
    useRootNavigator: false,
    backgroundColor: AmiColors.slate800,
    shape: const RoundedRectangleBorder(
      borderRadius: BorderRadius.vertical(top: Radius.circular(16)),
    ),
    builder: (sheetCtx) => Padding(
      padding: EdgeInsets.only(bottom: sheetBottomInset(MediaQuery.of(sheetCtx))),
      child: Semantics(
        identifier: RoomFeedbackIds.reportResponse,
        child: ListTile(
          key: const Key('reportResponseTile'),
          leading: const Icon(Icons.flag_outlined, color: AmiColors.textHigh),
          title: Text(AppLocalizations.of(sheetCtx).reportResponseAction,
              style: AmiTypography.body),
          onTap: () => Navigator.of(sheetCtx).pop(true),
        ),
      ),
    ),
  );
  if (report == true && context.mounted) {
    await showBugReportSheet(context, ref, response: target);
  }
}
