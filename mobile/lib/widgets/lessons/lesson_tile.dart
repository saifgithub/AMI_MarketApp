/// Shared lesson-row tile — used by the lessons hex landing and the
/// per-track lesson list.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/agent.dart';
import 'package:ami_trade/models/lessons.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:ami_trade/widgets/hex/hex_avatar.dart';
import 'package:flutter/material.dart';

class LessonTile extends StatelessWidget {
  const LessonTile({
    super.key,
    required this.meta,
    required this.onRead,
    required this.onQuizOnly,
    this.status,
  });

  final LessonMeta meta;
  final VoidCallback onRead;
  final VoidCallback onQuizOnly;
  final LessonStatus? status;

  @override
  Widget build(BuildContext context) {
    final callouts = meta.agentCallouts;
    final l = AppLocalizations.of(context);
    return Container(
      padding: const EdgeInsets.all(AmiSpacing.m),
      decoration: BoxDecoration(
        color: AmiColors.slate800,
        borderRadius: BorderRadius.circular(AmiRadii.card),
        border: Border.all(color: AmiColors.slate700),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          InkWell(
            onTap: onRead,
            child: Row(
              children: [
                Container(
                  // Padding-sized, not the old fixed 36×36: "TECH 12" doesn't
                  // fit in 36px. `minWidth` keeps short codes ("N&M 1") from
                  // collapsing so the titles still line up down the list.
                  constraints: const BoxConstraints(minWidth: 36, minHeight: 36),
                  padding: const EdgeInsets.symmetric(horizontal: 6),
                  alignment: Alignment.center,
                  decoration: BoxDecoration(
                    color: AmiColors.slate900,
                    borderRadius: BorderRadius.circular(6),
                    border: Border.all(color: AmiColors.slate700),
                  ),
                  // CR044 — lead each row with the group-scoped code ("TECH 12"),
                  // the identifier AMI and the user both say out loud. The level
                  // tier sits in the caption below.
                  child: Text(meta.codeLabel,
                      style: AmiTypography.labelMono.copyWith(
                          fontSize: 11, color: AmiColors.hexCyan)),
                ),
                const SizedBox(width: AmiSpacing.s),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(meta.title, style: AmiTypography.h4),
                      const SizedBox(height: 2),
                      Row(
                        children: [
                          Text('${l.lessonsDurationMin(meta.durationMin)} · L${meta.level}',
                              style: AmiTypography.caption),
                          // DEF068 — mark the lessons that actually move an
                          // agent-unlock gate. Without this a gateway lesson is
                          // indistinguishable from the dozens that merely name
                          // the agent, which is how a user could pass 50 lessons
                          // and still sit at 0 on three agents.
                          if (meta.isGateway) ...[
                            const SizedBox(width: AmiSpacing.s),
                            Container(
                              padding: const EdgeInsets.symmetric(
                                  horizontal: 5, vertical: 1),
                              decoration: BoxDecoration(
                                borderRadius: BorderRadius.circular(3),
                                border:
                                    Border.all(color: AmiColors.hexAmber, width: 1),
                              ),
                              child: Text(
                                l.lessonsUnlocksAgent,
                                style: AmiTypography.labelMono.copyWith(
                                    fontSize: 9, color: AmiColors.hexAmber),
                              ),
                            ),
                          ],
                          if (callouts.isNotEmpty) ...[
                            const SizedBox(width: AmiSpacing.s),
                            for (final id in callouts)
                              Padding(
                                padding: const EdgeInsets.only(right: 4),
                                child: HexAvatar(
                                  label: agentById(id).abbreviation,
                                  color: agentById(id).color,
                                  size: 20,
                                ),
                              ),
                          ],
                        ],
                      ),
                    ],
                  ),
                ),
                if (status != null)
                  _StatusBadge(status: status!),
              ],
            ),
          ),
          if (status?.isCompleted == true)
            Padding(
              padding: const EdgeInsets.only(bottom: AmiSpacing.xs),
              child: Text(
                l.lessonsTierCompleted,
                style: AmiTypography.labelMono.copyWith(
                    fontSize: 10, color: AmiColors.hexGreen),
              ),
            ),
          // DEF071 — mirror the COMPLETED label for started lessons. The list
          // floats in-progress lessons to the top, so their high canonical
          // badge number (e.g. EDGE 49) can sit above lower-numbered unstarted
          // ones; this label makes the pinned tile read as resumable, not
          // mis-sorted.
          if (status?.isInProgress == true)
            Padding(
              padding: const EdgeInsets.only(bottom: AmiSpacing.xs),
              child: Text(
                l.lessonsContinue,
                style: AmiTypography.labelMono.copyWith(
                    fontSize: 10, color: AmiColors.hexBlue),
              ),
            ),
          const SizedBox(height: AmiSpacing.s),
          Row(
            children: [
              Expanded(
                child: OutlinedButton(
                  onPressed: onRead,
                  style: OutlinedButton.styleFrom(
                    foregroundColor: AmiColors.hexGreen,
                    side: const BorderSide(color: AmiColors.hexGreen),
                    padding: const EdgeInsets.symmetric(vertical: 10),
                  ),
                  child: Text(l.actionRead, style: AmiTypography.labelMono),
                ),
              ),
              const SizedBox(width: AmiSpacing.s),
              Expanded(
                child: OutlinedButton(
                  onPressed: onQuizOnly,
                  style: OutlinedButton.styleFrom(
                    foregroundColor: AmiColors.hexAmber,
                    side: const BorderSide(color: AmiColors.hexAmber),
                    padding: const EdgeInsets.symmetric(vertical: 10),
                  ),
                  child: Text(l.actionQuizOnly, style: AmiTypography.labelMono),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _StatusBadge extends StatelessWidget {
  const _StatusBadge({required this.status});
  final LessonStatus status;

  @override
  Widget build(BuildContext context) {
    if (status.isCompleted) {
      return const Icon(Icons.check_circle, color: AmiColors.hexGreen, size: 20);
    }
    if (status.isInProgress) {
      return const Icon(Icons.radio_button_checked,
          color: AmiColors.hexBlue, size: 20);
    }
    return const SizedBox.shrink();
  }
}
