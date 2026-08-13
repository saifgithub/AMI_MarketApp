/// CR173 slice 2 — YOUR FIRM, the depth layer the twelve moved to.
///
/// The roster did not leave the app; it left the *doorway*. Everything the
/// 12-hex wall on the Floor could do is here, one tap below the firm row, with
/// nothing removed: tap an unlocked agent for the `1-ON-1 / BRIEF` chooser
/// (D-024 — Brief Your Agent's locked block stays visible in that sheet,
/// acceptance #8), tap a locked one for the gateway-lesson path.
///
/// **This screen is CR159's, and CR159 has not been built.** §6 decision #4
/// re-scoped CR159's desk bands to be exactly this depth layer, but its row is
/// still `proposed` — so removing the wall from the Floor without a destination
/// would have orphaned 1-on-1, Brief Your Agent and the whole unlock path in
/// the same commit. What lands here is therefore the *shipped wall, re-homed*:
/// no invented structure, no desk bands, no seat metaphor. CR159 replaces this
/// body with its bands and keeps the route.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/agent.dart';
import 'package:ami_trade/models/lessons.dart';
import 'package:ami_trade/screens/agent/one_on_one_screen.dart';
import 'package:ami_trade/screens/lessons/lesson_reader_screen.dart';
import 'package:ami_trade/screens/lessons/lessons_screen.dart';
import 'package:ami_trade/state/lessons_providers.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:ami_trade/widgets/agent_action_sheet.dart';
import 'package:ami_trade/widgets/hex/ami_screen_header.dart';
import 'package:ami_trade/widgets/hex/hex_avatar.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

class YourFirmScreen extends ConsumerWidget {
  const YourFirmScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l = AppLocalizations.of(context);
    final state = ref.watch(lessonsNotifierProvider);
    final unlocked = state.unlockedAgentIds;
    final tradingAgents = kAllAgents.sublist(0, 12);

    return Scaffold(
      backgroundColor: AmiColors.slate900,
      body: SafeArea(
        child: Column(
          children: [
            AmiScreenHeader(
              title: l.floorFirmHeading,
              titleColor: AmiColors.hexCyan,
              subtitle: l.floorFirmSeats(unlocked.length, tradingAgents.length),
              showBack: true,
            ),
            Expanded(
              child: SingleChildScrollView(
                padding: const EdgeInsets.all(AmiSpacing.m),
                child: Column(
                  children: [
                    Text(l.floorUnlockedSummary(unlocked.length),
                        textAlign: TextAlign.center,
                        style: AmiTypography.caption),
                    const SizedBox(height: AmiSpacing.m),
                    Wrap(
                      spacing: AmiSpacing.m,
                      runSpacing: AmiSpacing.l,
                      alignment: WrapAlignment.center,
                      children: [
                        for (final agent in tradingAgents)
                          AgentTile(
                            agent: agent,
                            unlocked: unlocked.contains(agent.id),
                            onTap: () => unlocked.contains(agent.id)
                                ? openAgent(context, agent)
                                : showLockedSheet(context, ref, agent),
                          ),
                      ],
                    ),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// The Concierge skips the sheet — it has no Brief surface, so 1-on-1 is the
/// only path. The other 12 get the `1-ON-1 / BRIEF` chooser.
void openAgent(BuildContext context, Agent agent) {
  if (agent.family == AgentFamily.concierge) {
    Navigator.of(context).push(MaterialPageRoute(
      builder: (_) => OneOnOneScreen(agent: agent),
    ));
    return;
  }
  AgentActionSheet.show(context, agent);
}

void showLockedSheet(BuildContext context, WidgetRef ref, Agent agent) {
  final state = ref.read(lessonsNotifierProvider);
  // DEF068 — the gateway set comes from the server. This used to filter the
  // catalogue on `agentCallouts` and take the first 3 by id, duplicating a
  // backend constant; the two then had to be kept in step by hand, and the
  // gate is 5 now. `required_` also carries per-lesson `passed`, so the
  // checklist no longer joins against `lessonStatuses` either.
  final requirement = state.unlockRequirements[agent.id];
  final requiredLessons =
      requirement?.required_ ?? const <GatewayLessonStatus>[];
  final l = AppLocalizations.of(context);
  showModalBottomSheet<void>(
    context: context,
    backgroundColor: AmiColors.slate800,
    // DEF075 — scroll-controlled + scrollable so the "GO TO LESSONS" CTA isn't
    // overflowed past the 9/16 cap (and under the nav bar) when an agent has a
    // full 5-lesson gateway list.
    isScrollControlled: true,
    shape: const RoundedRectangleBorder(
      borderRadius: BorderRadius.vertical(top: Radius.circular(16)),
    ),
    builder: (_) => SafeArea(
      child: SingleChildScrollView(
        child: Padding(
          padding: const EdgeInsets.all(AmiSpacing.l),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  HexAvatar(
                      label: agent.abbreviation, color: agent.color, size: 56),
                  const SizedBox(width: AmiSpacing.m),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(agent.displayName.toUpperCase(),
                            style: AmiTypography.labelMono
                                .copyWith(color: agent.color)),
                        const SizedBox(height: 2),
                        Text(agent.tagline, style: AmiTypography.body),
                      ],
                    ),
                  ),
                ],
              ),
              const SizedBox(height: AmiSpacing.l),
              Text(l.floorLockedHowTo, style: AmiTypography.labelMono),
              const SizedBox(height: AmiSpacing.s),
              if (requiredLessons.isEmpty)
                Text(l.floorLockedNoLessons, style: AmiTypography.body)
              else ...[
                Text(l.floorLockedEarnByLessons(requiredLessons.length),
                    style: AmiTypography.body),
                const SizedBox(height: 2),
                // CR053 — each row used to just name the lesson and do nothing
                // on tap (§4.2 #1, the single biggest friction point here).
                Text(l.floorLockedTapHint, style: AmiTypography.caption),
                const SizedBox(height: AmiSpacing.s),
                for (final lesson in requiredLessons)
                  InkWell(
                    onTap: () {
                      Navigator.of(context).pop();
                      Navigator.of(context).push(MaterialPageRoute<void>(
                        builder: (_) =>
                            LessonReaderScreen(lessonId: lesson.lessonId),
                      ));
                    },
                    child: Padding(
                      padding: const EdgeInsets.only(bottom: 4),
                      child: Row(
                        children: [
                          Icon(
                            lesson.passed ? Icons.check_circle : Icons.school,
                            size: 14,
                            color: lesson.passed
                                ? AmiColors.hexGreen
                                : AmiColors.textLow,
                          ),
                          const SizedBox(width: 6),
                          // CR044 — lead with the code so the user can actually
                          // go find it, and so this reads the same way AMI says
                          // it.
                          Text(
                            lesson.code,
                            style: AmiTypography.labelMono.copyWith(
                                fontSize: 11, color: AmiColors.hexCyan),
                          ),
                          const SizedBox(width: 6),
                          Expanded(
                              child: Text(lesson.title,
                                  style: AmiTypography.body)),
                        ],
                      ),
                    ),
                  ),
              ],
              const SizedBox(height: AmiSpacing.l),
              SizedBox(
                width: double.infinity,
                child: ElevatedButton(
                  style: ElevatedButton.styleFrom(
                    backgroundColor: AmiColors.hexGreen,
                    foregroundColor: AmiColors.slate900,
                  ),
                  onPressed: () {
                    Navigator.of(context).pop();
                    Navigator.of(context).push(MaterialPageRoute<void>(
                      builder: (_) => const LessonsScreen(),
                    ));
                  },
                  child: Text(l.floorLockedGoToLessons),
                ),
              ),
              // B4: the dead "UPGRADE TO SKIP — coming soon" button is gone. In
              // its place, real earn-path progress that jumps straight into the
              // next unfinished gateway lesson's reader (CR053).
              if (requiredLessons.isNotEmpty) ...[
                const SizedBox(height: AmiSpacing.s),
                Builder(builder: (_) {
                  final completed = requirement?.passedCount ?? 0;
                  final next = requiredLessons.firstWhere(
                    (m) => !m.passed,
                    orElse: () => requiredLessons.first,
                  );
                  return SizedBox(
                    width: double.infinity,
                    child: OutlinedButton.icon(
                      style: OutlinedButton.styleFrom(
                        foregroundColor: AmiColors.hexBlue,
                        side: const BorderSide(color: AmiColors.hexBlue),
                      ),
                      icon: const Icon(Icons.trending_up, size: 16),
                      // CR053 §4.2 #2 — deep-link straight to the next
                      // unfinished gateway lesson instead of the track list the
                      // user then had to search.
                      onPressed: () {
                        Navigator.of(context).pop();
                        Navigator.of(context).push(MaterialPageRoute<void>(
                          builder: (_) =>
                              LessonReaderScreen(lessonId: next.lessonId),
                        ));
                      },
                      label: Text(l.floorLockedProgress(
                          completed, requiredLessons.length)),
                    ),
                  );
                }),
              ],
            ],
          ),
        ),
      ),
    ),
  );
}

class AgentTile extends StatelessWidget {
  const AgentTile({
    super.key,
    required this.agent,
    required this.unlocked,
    required this.onTap,
  });

  final Agent agent;
  final bool unlocked;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: 88,
      child: Column(
        children: [
          Stack(
            alignment: Alignment.center,
            children: [
              Opacity(
                opacity: unlocked ? 1.0 : 0.35,
                child: HexAvatar(
                  label: agent.abbreviation,
                  color: agent.color,
                  size: 72,
                  onTap: onTap,
                ),
              ),
              if (!unlocked)
                IgnorePointer(
                  child: Container(
                    width: 72,
                    height: 72,
                    alignment: Alignment.center,
                    child: const Icon(Icons.lock_outline,
                        color: AmiColors.textLow, size: 22),
                  ),
                ),
            ],
          ),
          const SizedBox(height: 6),
          Text(
            agent.displayName,
            textAlign: TextAlign.center,
            maxLines: 2,
            overflow: TextOverflow.ellipsis,
            style: AmiTypography.caption.copyWith(
              fontSize: 10,
              color: unlocked ? AmiColors.textMed : AmiColors.textLow,
            ),
          ),
        ],
      ),
    );
  }
}
