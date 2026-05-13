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
  });

  final LessonMeta meta;
  final VoidCallback onRead;
  final VoidCallback onQuizOnly;

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
                  width: 36,
                  height: 36,
                  alignment: Alignment.center,
                  decoration: BoxDecoration(
                    color: AmiColors.slate900,
                    borderRadius: BorderRadius.circular(6),
                    border: Border.all(color: AmiColors.slate700),
                  ),
                  child: Text('L${meta.level}',
                      style: AmiTypography.labelMono.copyWith(fontSize: 11)),
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
                          Text(l.lessonsDurationMin(meta.durationMin),
                              style: AmiTypography.caption),
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
              ],
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
