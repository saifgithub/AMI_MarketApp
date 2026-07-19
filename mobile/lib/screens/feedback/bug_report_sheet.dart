/// In-app bug report bottom sheet.
///
/// Triggered via:
///   - Long-press on the app version chip in Settings → bottom of the screen.
///   - Call `showBugReportSheet(context, ref)` from anywhere.
///
/// Auto-attaches: current GoRouter route, app version, platform. User
/// fills in: category (chip picker) + title + optional steps.
library;

import 'dart:io';

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/state/feedback_providers.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:ami_trade/widgets/hex/hex_toast.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:image_picker/image_picker.dart';

const _kCategories = [
  ('ui_glitch', 'UI glitch'),
  ('wrong_data', 'Wrong data'),
  ('crash', 'App crashed'),
  ('performance', 'Slow / freeze'),
  ('feature_request', 'Feature request'),
  ('other', 'Other'),
];

/// Convenience helper — call from any widget.
Future<void> showBugReportSheet(BuildContext context, WidgetRef ref) {
  final route = ModalRoute.of(context)?.settings.name ?? 'unknown';
  return showModalBottomSheet<void>(
    context: context,
    isScrollControlled: true,
    backgroundColor: AmiColors.slate800,
    shape: const RoundedRectangleBorder(
      borderRadius: BorderRadius.vertical(top: Radius.circular(16)),
    ),
    builder: (_) => _BugReportSheet(route: route),
  );
}

class _BugReportSheet extends ConsumerStatefulWidget {
  const _BugReportSheet({required this.route});
  final String route;

  @override
  ConsumerState<_BugReportSheet> createState() => _BugReportSheetState();
}

class _BugReportSheetState extends ConsumerState<_BugReportSheet> {
  String _category = 'ui_glitch';
  final _titleController = TextEditingController();
  final _stepsController = TextEditingController();
  final _formKey = GlobalKey<FormState>();
  final _picker = ImagePicker();
  XFile? _attachment;

  @override
  void dispose() {
    _titleController.dispose();
    _stepsController.dispose();
    super.dispose();
  }

  Future<void> _pickFrom(ImageSource source) async {
    try {
      final f = await _picker.pickImage(
        source: source,
        imageQuality: 85,
        maxWidth: 2400,
      );
      if (f != null && mounted) setState(() => _attachment = f);
    } catch (_) {
      // Permission denied or picker dismissed — swallow; the report can
      // still go without a photo.
    }
  }

  Future<void> _showAttachOptions() async {
    final source = await showModalBottomSheet<ImageSource>(
      context: context,
      backgroundColor: AmiColors.slate800,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(16)),
      ),
      builder: (sheetCtx) => SafeArea(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            ListTile(
              leading: const Icon(Icons.photo_camera_outlined,
                  color: AmiColors.textHigh),
              title: Text('Take photo', style: AmiTypography.body),
              onTap: () => Navigator.of(sheetCtx).pop(ImageSource.camera),
            ),
            ListTile(
              leading: const Icon(Icons.photo_library_outlined,
                  color: AmiColors.textHigh),
              title: Text('Choose from library', style: AmiTypography.body),
              onTap: () => Navigator.of(sheetCtx).pop(ImageSource.gallery),
            ),
          ],
        ),
      ),
    );
    if (source != null) await _pickFrom(source);
  }

  String? _mimeFor(XFile f) {
    final lower = f.path.toLowerCase();
    if (lower.endsWith('.png')) return 'image/png';
    if (lower.endsWith('.jpg') || lower.endsWith('.jpeg')) return 'image/jpeg';
    if (lower.endsWith('.heic')) return 'image/heic';
    if (lower.endsWith('.heif')) return 'image/heif';
    if (lower.endsWith('.webp')) return 'image/webp';
    if (lower.endsWith('.gif')) return 'image/gif';
    return f.mimeType;
  }

  Future<void> _submit() async {
    if (!(_formKey.currentState?.validate() ?? false)) return;
    // Grab the root navigator/overlay context before the sheet pops — after
    // pop() this widget's own context is defunct and the toast would have
    // no Overlay to insert into.
    final rootContext = Navigator.of(context, rootNavigator: true).context;
    final l = AppLocalizations.of(context);
    final ok = await ref.read(feedbackNotifierProvider.notifier).submitBug(
          category: _category,
          title: _titleController.text.trim(),
          steps: _stepsController.text.trim().isEmpty
              ? null
              : _stepsController.text.trim(),
          route: widget.route,
          attachmentPath: _attachment?.path,
          attachmentMime: _attachment == null ? null : _mimeFor(_attachment!),
        );
    if (!ok || !mounted) return;
    final shortId = ref.read(feedbackNotifierProvider).shortId;
    Navigator.of(context).pop();
    if (shortId == null || !rootContext.mounted) return;
    HexToast.show(
      rootContext,
      l.bugReportThanks(shortId),
      accent: AmiColors.hexGreen,
      icon: Icons.check_circle_outline,
      duration: const Duration(seconds: 4),
    );
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(feedbackNotifierProvider);
    final bottom = MediaQuery.of(context).viewInsets.bottom;

    return Padding(
      padding: EdgeInsets.fromLTRB(AmiSpacing.m, AmiSpacing.m, AmiSpacing.m, AmiSpacing.m + bottom),
      child: Form(
        key: _formKey,
        // SingleChildScrollView so the photo + submit buttons stay reachable
        // when the keyboard is open and pushes the form taller than the sheet.
        child: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Center(
              child: Container(
                width: 36, height: 4,
                decoration: BoxDecoration(
                  color: AmiColors.slate600,
                  borderRadius: BorderRadius.circular(2),
                ),
              ),
            ),
            const SizedBox(height: AmiSpacing.s),
            Row(
              children: [
                Expanded(child: Text('Report a bug', style: AmiTypography.h4)),
                // 44pt tap target (Apple HIG minimum) — earlier GestureDetector
                // wrapped a 20px icon, giving a 20×20 hit area that testers
                // couldn't reliably trigger (bugs 6fd4144d + a19871c3).
                IconButton(
                  icon: const Icon(Icons.close, size: 24,
                      color: AmiColors.textMed),
                  tooltip: 'Close',
                  onPressed: () => Navigator.of(context).pop(),
                  constraints: const BoxConstraints(
                    minWidth: 44, minHeight: 44,
                  ),
                  padding: EdgeInsets.zero,
                  visualDensity: VisualDensity.compact,
                ),
              ],
            ),
            const SizedBox(height: AmiSpacing.xs),
            Text(
              'v${ref.watch(appVersionProvider).valueOrNull ?? '…'} · ${widget.route}',
              style: AmiTypography.caption.copyWith(color: AmiColors.slate500),
            ),
            const SizedBox(height: AmiSpacing.m),
            // Category chips
            Wrap(
              spacing: AmiSpacing.xs,
              runSpacing: AmiSpacing.xs,
              children: [
                for (final (value, label) in _kCategories)
                  ChoiceChip(
                    label: Text(label),
                    selected: _category == value,
                    onSelected: (_) => setState(() => _category = value),
                    selectedColor: AmiColors.hexBlue,
                    backgroundColor: AmiColors.slate700,
                    labelStyle: AmiTypography.caption.copyWith(
                      color: _category == value
                          ? AmiColors.textHigh
                          : AmiColors.slate500,
                    ),
                    side: BorderSide.none,
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(6),
                    ),
                  ),
              ],
            ),
            const SizedBox(height: AmiSpacing.m),
            TextFormField(
              controller: _titleController,
              style: AmiTypography.body,
              maxLength: 200,
              decoration: InputDecoration(
                hintText: 'Short description',
                hintStyle: AmiTypography.body.copyWith(color: AmiColors.slate500),
                filled: true,
                fillColor: AmiColors.slate700,
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(8),
                  borderSide: BorderSide.none,
                ),
                counterStyle: AmiTypography.caption.copyWith(color: AmiColors.slate500),
              ),
              validator: (v) =>
                  (v == null || v.trim().isEmpty) ? 'Required' : null,
            ),
            const SizedBox(height: AmiSpacing.s),
            TextFormField(
              controller: _stepsController,
              style: AmiTypography.body,
              maxLength: 1000,
              maxLines: 3,
              decoration: InputDecoration(
                hintText: 'Steps to reproduce (optional)',
                hintStyle: AmiTypography.body.copyWith(color: AmiColors.slate500),
                filled: true,
                fillColor: AmiColors.slate700,
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(8),
                  borderSide: BorderSide.none,
                ),
                counterStyle: AmiTypography.caption.copyWith(color: AmiColors.slate500),
              ),
            ),
            const SizedBox(height: AmiSpacing.s),
            _AttachmentRow(
              attachment: _attachment,
              onPick: _showAttachOptions,
              onClear: () => setState(() => _attachment = null),
            ),
            if (state.error != null) ...[
              const SizedBox(height: AmiSpacing.xs),
              Text(
                'Failed to send — please try again',
                style: AmiTypography.caption.copyWith(color: AmiColors.hexRed),
              ),
            ],
            const SizedBox(height: AmiSpacing.m),
            SizedBox(
              width: double.infinity,
              child: FilledButton(
                onPressed: state.submitting ? null : _submit,
                style: FilledButton.styleFrom(
                  backgroundColor: AmiColors.hexBlue,
                  foregroundColor: AmiColors.textHigh,
                  padding: const EdgeInsets.symmetric(vertical: AmiSpacing.s),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(8),
                  ),
                ),
                child: state.submitting
                    ? const SizedBox(
                        height: 20, width: 20,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : const Text('Send report'),
              ),
            ),
          ],
        ),
        ),
      ),
    );
  }
}


/// Renders either an "Attach photo" affordance or a 56px thumbnail with a
/// clear (×) button. Tapping the affordance opens a camera/library picker.
class _AttachmentRow extends StatelessWidget {
  const _AttachmentRow({
    required this.attachment,
    required this.onPick,
    required this.onClear,
  });

  final XFile? attachment;
  final VoidCallback onPick;
  final VoidCallback onClear;

  @override
  Widget build(BuildContext context) {
    if (attachment == null) {
      return OutlinedButton.icon(
        onPressed: onPick,
        icon: const Icon(Icons.add_photo_alternate_outlined, size: 18),
        label: const Text('Attach photo'),
        style: OutlinedButton.styleFrom(
          foregroundColor: AmiColors.textMed,
          side: const BorderSide(color: AmiColors.slate700),
          padding: const EdgeInsets.symmetric(
            horizontal: AmiSpacing.m, vertical: AmiSpacing.s,
          ),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(8),
          ),
        ),
      );
    }
    return Row(
      children: [
        ClipRRect(
          borderRadius: BorderRadius.circular(6),
          child: Image.file(
            File(attachment!.path),
            width: 56, height: 56, fit: BoxFit.cover,
          ),
        ),
        const SizedBox(width: AmiSpacing.s),
        Expanded(
          child: Text(
            attachment!.name,
            style: AmiTypography.caption.copyWith(color: AmiColors.textMed),
            overflow: TextOverflow.ellipsis,
          ),
        ),
        IconButton(
          icon: const Icon(Icons.close, size: 18, color: AmiColors.textLow),
          tooltip: 'Remove',
          onPressed: onClear,
        ),
      ],
    );
  }
}
