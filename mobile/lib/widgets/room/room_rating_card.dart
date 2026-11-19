/// CR278 (CR267 WP-36) - the dismissible Beta card under a finished Room's
/// verdict: "Did the verdict and its reasons make sense?" with a thumbs-up and
/// a thumbs-down, plus the "Report this response" link for the verdict itself.
///
/// It sits in the scrolling column, never in a dialog or a gate: nothing in the
/// Room waits for it, the X hides it, and a failed save is a quiet line on the
/// card. The answer is stored server-side against the Room id (one per Room,
/// changeable - tapping the other thumb replaces it).
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/qa/semantics_ids.dart';
import 'package:ami_trade/state/room_rating_providers.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

class RoomRatingCard extends ConsumerWidget {
  const RoomRatingCard({super.key, required this.runId, this.onReport});

  final String runId;

  /// Opens the bug sheet about the verdict. Null hides the link.
  final VoidCallback? onReport;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final s = ref.watch(roomRatingProvider(runId));
    if (s.dismissed) return const SizedBox.shrink();
    final l = AppLocalizations.of(context);
    final notifier = ref.read(roomRatingProvider(runId).notifier);
    return Semantics(
      identifier: RoomFeedbackIds.ratingCard,
      container: true,
      explicitChildNodes: true,
      child: Container(
        key: const Key('roomRatingCard'),
        margin: const EdgeInsets.only(top: AmiSpacing.s),
        padding: const EdgeInsets.fromLTRB(
            AmiSpacing.m, AmiSpacing.s, AmiSpacing.xs, AmiSpacing.s),
        decoration: BoxDecoration(
          color: AmiColors.slate800,
          border: Border.all(color: AmiColors.slate700),
          borderRadius: BorderRadius.circular(AmiRadii.card),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Expanded(
                  child: Text(l.roomRatingQuestion, style: AmiTypography.body),
                ),
                Semantics(
                  identifier: RoomFeedbackIds.ratingDismiss,
                  child: IconButton(
                    key: const Key('roomRatingDismiss'),
                    icon: const Icon(Icons.close,
                        size: 20, color: AmiColors.textMed),
                    tooltip: l.roomRatingDismiss,
                    onPressed: notifier.dismiss,
                    constraints:
                        const BoxConstraints(minWidth: 44, minHeight: 44),
                    padding: EdgeInsets.zero,
                  ),
                ),
              ],
            ),
            Wrap(
              spacing: AmiSpacing.s,
              runSpacing: AmiSpacing.xs,
              children: [
                _Thumb(
                  id: RoomFeedbackIds.thumbUp,
                  widgetKey: const Key('roomRatingUp'),
                  icon: Icons.thumb_up_alt_outlined,
                  selectedIcon: Icons.thumb_up_alt,
                  label: l.roomRatingYes,
                  selected: s.helpful == true,
                  busy: s.submitting,
                  onTap: () => notifier.rate(true),
                ),
                _Thumb(
                  id: RoomFeedbackIds.thumbDown,
                  widgetKey: const Key('roomRatingDown'),
                  icon: Icons.thumb_down_alt_outlined,
                  selectedIcon: Icons.thumb_down_alt,
                  label: l.roomRatingNo,
                  selected: s.helpful == false,
                  busy: s.submitting,
                  onTap: () => notifier.rate(false),
                ),
              ],
            ),
            if (s.failed)
              Padding(
                padding: const EdgeInsets.only(top: AmiSpacing.xs),
                child: Text(
                  l.roomRatingFailed,
                  style: AmiTypography.caption
                      .copyWith(color: AmiColors.hexAmber),
                ),
              )
            else if (s.helpful != null)
              Padding(
                padding: const EdgeInsets.only(top: AmiSpacing.xs),
                child: Text(
                  l.roomRatingThanks,
                  style: AmiTypography.caption
                      .copyWith(color: AmiColors.textLow),
                ),
              ),
            if (onReport != null)
              Semantics(
                identifier: RoomFeedbackIds.reportResponse,
                child: TextButton.icon(
                  key: const Key('roomRatingReport'),
                  onPressed: onReport,
                  icon: const Icon(Icons.flag_outlined, size: 16),
                  label: Text(l.reportResponseAction),
                  style: TextButton.styleFrom(
                    foregroundColor: AmiColors.textMed,
                    padding: EdgeInsets.zero,
                    minimumSize: const Size(44, 36),
                    alignment: Alignment.centerLeft,
                    tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                  ),
                ),
              ),
          ],
        ),
      ),
    );
  }
}

class _Thumb extends StatelessWidget {
  const _Thumb({
    required this.id,
    required this.widgetKey,
    required this.icon,
    required this.selectedIcon,
    required this.label,
    required this.selected,
    required this.busy,
    required this.onTap,
  });

  final String id;
  final Key widgetKey;
  final IconData icon;
  final IconData selectedIcon;
  final String label;
  final bool selected;
  final bool busy;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Semantics(
      identifier: id,
      child: OutlinedButton.icon(
        key: widgetKey,
        onPressed: busy ? null : onTap,
        icon: Icon(selected ? selectedIcon : icon, size: 18),
        label: Text(label),
        style: OutlinedButton.styleFrom(
          foregroundColor: selected ? AmiColors.hexGreen : AmiColors.textMed,
          side: BorderSide(
              color: selected ? AmiColors.hexGreen : AmiColors.slate600),
          minimumSize: const Size(44, 44),
        ),
      ),
    );
  }
}
