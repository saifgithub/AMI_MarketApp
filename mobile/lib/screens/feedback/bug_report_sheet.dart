/// In-app bug report bottom sheet.
///
/// Triggered via:
///   - Long-press on the app version chip in Settings → bottom of the screen.
///   - Call `showBugReportSheet(context, ref)` from anywhere.
///
/// Auto-attaches: current GoRouter route, app version, platform. User
/// fills in: category (chip picker) + title + optional steps.
library;

import 'package:ami_trade/state/feedback_providers.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

const _kCategories = [
  ('ui_glitch', 'UI glitch'),
  ('wrong_data', 'Wrong data'),
  ('crash', 'App crashed'),
  ('performance', 'Slow / freeze'),
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

  @override
  void dispose() {
    _titleController.dispose();
    _stepsController.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (!(_formKey.currentState?.validate() ?? false)) return;
    final ok = await ref.read(feedbackNotifierProvider.notifier).submitBug(
          category: _category,
          title: _titleController.text.trim(),
          steps: _stepsController.text.trim().isEmpty
              ? null
              : _stepsController.text.trim(),
          route: widget.route,
        );
    if (ok && mounted) Navigator.of(context).pop();
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(feedbackNotifierProvider);
    final bottom = MediaQuery.of(context).viewInsets.bottom;

    return Padding(
      padding: EdgeInsets.fromLTRB(AmiSpacing.m, AmiSpacing.m, AmiSpacing.m, AmiSpacing.m + bottom),
      child: Form(
        key: _formKey,
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
            const SizedBox(height: AmiSpacing.m),
            Text('Report a bug', style: AmiTypography.h4),
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
    );
  }
}
