/// Placeholder Floor home — shows the 12 agents as tappable hexes.
/// Locked agents show a dim/lock state; tapping surfaces "How to unlock".
/// The Concierge is always unlocked.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/agent.dart';
import 'package:ami_trade/models/lessons.dart';
import 'package:ami_trade/screens/agent/one_on_one_screen.dart';
import 'package:ami_trade/screens/floor/daily_challenge_card.dart';
import 'package:ami_trade/screens/lessons/lessons_screen.dart';
import 'package:ami_trade/screens/room/convene_sheet.dart';
import 'package:ami_trade/state/lessons_providers.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:ami_trade/widgets/hex/hex_avatar.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

class FloorPlaceholderScreen extends ConsumerWidget {
  const FloorPlaceholderScreen({super.key});

  void _openAgent(BuildContext context, Agent agent) {
    Navigator.of(context).push(MaterialPageRoute(
      builder: (_) => OneOnOneScreen(agent: agent),
    ));
  }

  void _showLockedSheet(BuildContext context, WidgetRef ref, Agent agent) {
    final state = ref.read(lessonsNotifierProvider);
    // Gateway set = first 3 lessons (by id) that callout this agent. Mirrors
    // backend lessons_service.UNLOCK_REQUIRED_PER_AGENT so the UI shows the
    // exact lessons that gate the unlock — not the full 70+ enrichment set.
    const gatewaySize = 3;
    final calloutLessons = (state.catalogue?.tracks
                .expand((t) => t.lessons)
                .where((l) => l.agentCallouts.contains(agent.id))
                .toList() ??
            const <LessonMeta>[])
      ..sort((a, b) => a.id.compareTo(b.id));
    final requiredLessons = calloutLessons.take(gatewaySize).toList();
    final l = AppLocalizations.of(context);
    showModalBottomSheet<void>(
      context: context,
      backgroundColor: AmiColors.slate800,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(16)),
      ),
      builder: (_) => SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(AmiSpacing.l),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  HexAvatar(label: agent.abbreviation, color: agent.color, size: 56),
                  const SizedBox(width: AmiSpacing.m),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(agent.displayName.toUpperCase(),
                            style: AmiTypography.labelMono.copyWith(color: agent.color)),
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
                Text(
                  l.floorLockedNoLessons,
                  style: AmiTypography.body,
                )
              else ...[
                Text(
                  l.floorLockedEarnByLessons,
                  style: AmiTypography.body,
                ),
                const SizedBox(height: AmiSpacing.s),
                for (final lesson in requiredLessons)
                  Padding(
                    padding: const EdgeInsets.only(bottom: 4),
                    child: Row(
                      children: [
                        const Icon(Icons.school, size: 14, color: AmiColors.hexGreen),
                        const SizedBox(width: 6),
                        Expanded(child: Text(lesson.title, style: AmiTypography.body)),
                      ],
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
              const SizedBox(height: AmiSpacing.s),
              SizedBox(
                width: double.infinity,
                child: OutlinedButton(
                  style: OutlinedButton.styleFrom(
                    foregroundColor: AmiColors.hexBlue,
                    side: const BorderSide(color: AmiColors.hexBlue),
                  ),
                  onPressed: () => Navigator.of(context).pop(),
                  child: Text(l.floorLockedUpgradeSoon),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(lessonsNotifierProvider);
    final unlocked = state.unlockedAgentIds;
    final concierge = kAllAgents.last;
    final tradingAgents = kAllAgents.sublist(0, 12);
    final l = AppLocalizations.of(context);

    return Scaffold(
      backgroundColor: AmiColors.slate900,
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(AmiSpacing.m),
          child: Column(
            children: [
              const SizedBox(height: AmiSpacing.l),
              // ── Concierge centerpiece ──
              GestureDetector(
                onTap: () => _openAgent(context, concierge),
                child: HexAvatar(
                  label: concierge.abbreviation,
                  color: concierge.color,
                  size: 110,
                  status: HexAvatarStatus.recentCall,
                ),
              ),
              const SizedBox(height: AmiSpacing.s),
              Text(l.floorConciergeHeading, style: AmiTypography.labelMono),
              const SizedBox(height: AmiSpacing.xs),
              Text(
                l.floorConciergeTagline,
                style: AmiTypography.caption.copyWith(color: AmiColors.hexPink),
              ),
              const SizedBox(height: AmiSpacing.xl),

              // ── 12 trading agents grid ──
              Text(l.floorTeamHeading, style: AmiTypography.labelMono),
              const SizedBox(height: AmiSpacing.s),
              Text(
                l.floorUnlockedSummary(unlocked.length),
                style: AmiTypography.caption,
              ),
              const SizedBox(height: AmiSpacing.m),
              Wrap(
                spacing: AmiSpacing.m,
                runSpacing: AmiSpacing.l,
                alignment: WrapAlignment.center,
                children: [
                  for (final agent in tradingAgents)
                    _AgentTile(
                      agent: agent,
                      unlocked: unlocked.contains(agent.id),
                      onTap: () => unlocked.contains(agent.id)
                          ? _openAgent(context, agent)
                          : _showLockedSheet(context, ref, agent),
                    ),
                ],
              ),

              const SizedBox(height: AmiSpacing.xl),

              // ── Daily Challenge ──
              const DailyChallengeCard(),
              const SizedBox(height: AmiSpacing.l),

              // ── Convene the Room CTA ──
              SizedBox(
                width: double.infinity,
                child: ElevatedButton.icon(
                  style: ElevatedButton.styleFrom(
                    backgroundColor: AmiColors.hexGreen,
                    foregroundColor: AmiColors.slate900,
                    padding: const EdgeInsets.symmetric(vertical: AmiSpacing.m),
                  ),
                  icon: const Icon(Icons.bolt),
                  label: Text(l.floorConveneCta),
                  onPressed: () => ConveneSheet.show(context),
                ),
              ),
              const SizedBox(height: AmiSpacing.xs),
              Text(
                l.floorConveneCaption,
                style: AmiTypography.caption.copyWith(color: AmiColors.textLow),
              ),

              const SizedBox(height: AmiSpacing.xl),

              // ── Footer ──
              TextButton(
                onPressed: () =>
                    Navigator.of(context).pushReplacementNamed('/onboarding'),
                child: Text(
                  l.floorRestartOnboarding,
                  style: AmiTypography.caption.copyWith(color: AmiColors.hexBlue),
                ),
              ),
              const SizedBox(height: AmiSpacing.m),
              Text(
                l.floorFooter,
                style: AmiTypography.caption,
              ),
              const SizedBox(height: AmiSpacing.l),
            ],
          ),
        ),
      ),
    );
  }
}


class _AgentTile extends StatelessWidget {
  const _AgentTile({required this.agent, required this.unlocked, required this.onTap});
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
