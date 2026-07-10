/// Floor home — shows the 12 agents as tappable hexes.
/// Locked agents show a dim/lock state; tapping surfaces "How to unlock" with
/// earn-path progress. The Concierge is always unlocked.
library;

import 'package:ami_trade/features/tour/floor_tour.dart';
import 'package:ami_trade/features/tour/tour_intro_sheet.dart';
import 'package:ami_trade/features/tour/tour_providers.dart';
import 'package:ami_trade/features/tour/tour_service.dart';
import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/agent.dart';
import 'package:ami_trade/models/lessons.dart';
import 'package:ami_trade/screens/agent/one_on_one_screen.dart';
import 'package:ami_trade/widgets/agent_action_sheet.dart';
import 'package:ami_trade/screens/floor/daily_challenge_card.dart';
import 'package:ami_trade/screens/league/league_card.dart';
import 'package:ami_trade/screens/lessons/lessons_screen.dart';
import 'package:ami_trade/screens/lessons/track_lessons_screen.dart';
import 'package:ami_trade/screens/room/convene_sheet.dart';
import 'package:ami_trade/state/daily_challenge_providers.dart';
import 'package:ami_trade/state/league_providers.dart';
import 'package:ami_trade/services/share/share_service.dart';
import 'package:ami_trade/state/lessons_providers.dart';
import 'package:ami_trade/state/onboarding_providers.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:ami_trade/widgets/hex/hex_avatar.dart';
import 'package:ami_trade/widgets/hex/hex_button.dart';
import 'package:ami_trade/widgets/hex/hex_mesh_overlay.dart';
import 'package:ami_trade/widgets/hex/hex_toast.dart';
import 'package:ami_trade/widgets/streak_chip.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_svg/flutter_svg.dart';
import 'package:tutorial_coach_mark/tutorial_coach_mark.dart';

class FloorScreen extends ConsumerStatefulWidget {
  const FloorScreen({super.key});

  @override
  ConsumerState<FloorScreen> createState() =>
      _FloorScreenState();
}

class _FloorScreenState
    extends ConsumerState<FloorScreen> {
  // GlobalKeys for coach-mark targets
  final _conciergeKey = GlobalKey();
  final _agentKey0 = GlobalKey();
  final _agentKey4 = GlobalKey();
  final _challengeKey = GlobalKey();
  final _conveneKey = GlobalKey();

  @override
  void initState() {
    super.initState();
    // Floor is tab 0 — active from the start. Check immediately after layout.
    WidgetsBinding.instance.addPostFrameCallback((_) async {
      await _maybeShowTour();
    });
  }

  Future<void> _maybeShowTour() async {
    if (!mounted) return;
    // Only fire when Floor is the active tab (guards against IndexedStack
    // running initState for all tabs simultaneously on first build).
    if (ref.read(activeTabIndexProvider) != 0) return;
    final service = ref.read(tourServiceProvider);
    if (await service.hasSeen(TourSection.floor)) return;
    await service.markSeen(TourSection.floor);
    if (!mounted) return;
    final ctx = context;
    final start = await showModalBottomSheet<bool>(
      context: ctx,
      backgroundColor: AmiColors.slate800,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (_) => const TourIntroSheet(),
    );
    if (start != true || !mounted) return;
    _runFloorTour();
  }

  void _runFloorTour() {
    final l = AppLocalizations.of(context);
    TutorialCoachMark(
      targets: buildFloorTargets(
        l: l,
        conciergeKey: _conciergeKey,
        agentKey0: _agentKey0,
        agentKey4: _agentKey4,
        challengeKey: _challengeKey,
        conveneKey: _conveneKey,
        onTryConvene: () {
          if (mounted) ConveneSheet.show(context);
        },
      ),
      hideSkip: true,
      colorShadow: Colors.black,
      opacityShadow: 0.88,
      pulseEnable: false,
      beforeFocus: (target) async {
        // Ensure the target is in view before the spotlight focuses on it.
        // If the tooltip is positioned ABOVE the target, scroll the target
        // toward the bottom of the viewport so there's room above for the
        // tooltip (otherwise the tooltip ends up off-screen).
        final ctx = target.keyTarget?.currentContext;
        if (ctx == null) return;
        final contents = target.contents ?? const [];
        final tooltipAbove = contents.isNotEmpty &&
            contents.first.align == ContentAlign.top;
        await Scrollable.ensureVisible(
          ctx,
          duration: const Duration(milliseconds: 350),
          alignment: tooltipAbove ? 0.85 : 0.15,
        );
      },
      onFinish: () {
        if (!mounted) return;
        HexToast.show(
          context,
          AppLocalizations.of(context).tourCompletionFloor,
          accent: AmiColors.hexGreen,
          icon: Icons.check_circle_outline,
        );
      },
    ).show(context: context);
  }

  void _openAgent(BuildContext context, Agent agent) {
    // Concierge skips the sheet — it has no Brief surface, so 1-on-1 is the
    // only path. The other 12 agents get the [1-ON-1] / [BRIEF] chooser.
    if (agent.family == AgentFamily.concierge) {
      Navigator.of(context).push(MaterialPageRoute(
        builder: (_) => OneOnOneScreen(agent: agent),
      ));
      return;
    }
    AgentActionSheet.show(context, agent);
  }

  void _showLockedSheet(BuildContext context, WidgetRef ref, Agent agent) {
    final state = ref.read(lessonsNotifierProvider);
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
                        Icon(
                          state.isLessonCompleted(lesson.id)
                              ? Icons.check_circle
                              : Icons.school,
                          size: 14,
                          color: state.isLessonCompleted(lesson.id)
                              ? AmiColors.hexGreen
                              : AmiColors.textLow,
                        ),
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
              // B4: the dead "UPGRADE TO SKIP — coming soon" button is gone.
              // In its place, real earn-path progress that jumps to the next
              // unfinished gateway lesson's track.
              if (requiredLessons.isNotEmpty) ...[
                const SizedBox(height: AmiSpacing.s),
                Builder(builder: (_) {
                  final completed = requiredLessons
                      .where((m) => state.isLessonCompleted(m.id))
                      .length;
                  final next = requiredLessons.firstWhere(
                    (m) => !state.isLessonCompleted(m.id),
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
                      onPressed: () {
                        Navigator.of(context).pop();
                        Navigator.of(context).push(MaterialPageRoute<void>(
                          builder: (_) => TrackLessonsScreen(trackId: next.track),
                        ));
                      },
                      label: Text(
                        l.floorLockedProgress(completed, requiredLessons.length),
                      ),
                    ),
                  );
                }),
              ],
            ],
          ),
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    // Listen for Floor becoming the active tab after the user switches away and back.
    ref.listen<int>(activeTabIndexProvider, (prev, next) async {
      if (next != 0) return;
      final service = ref.read(tourServiceProvider);
      if (await service.hasSeen(TourSection.floor)) return;
      await service.markSeen(TourSection.floor);
      if (!mounted) return;
      final ctx = context;
      final start = await showModalBottomSheet<bool>(
        context: ctx,
        backgroundColor: AmiColors.slate800,
        shape: const RoundedRectangleBorder(
          borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
        ),
        builder: (_) => const TourIntroSheet(),
      );
      if (start != true || !mounted) return;
      _runFloorTour();
    });

    final state = ref.watch(lessonsNotifierProvider);
    final unlocked = state.unlockedAgentIds;
    final concierge = kAllAgents.last;
    final tradingAgents = kAllAgents.sublist(0, 12);
    final l = AppLocalizations.of(context);
    final me = ref.watch(leagueMeProvider).valueOrNull;
    final todayFilled =
        ref.watch(dailyChallengeTodayProvider).valueOrNull?.myAttempt != null;

    return Scaffold(
      backgroundColor: AmiColors.slate900,
      body: Stack(
        children: [
          const Positioned.fill(child: HexMeshOverlay()),
          SafeArea(
            child: SingleChildScrollView(
              padding: const EdgeInsets.all(AmiSpacing.m),
              child: Column(
                children: [
                  // ── C5 logo (left) + B2 streak chip (right) ──
                  Row(
                    children: [
                      SvgPicture.asset(
                        'assets/logo_hex.svg',
                        height: 26,
                        semanticsLabel: 'AMI',
                      ),
                      const Spacer(),
                      if (me != null && me.streak.current > 0)
                        StreakChip(
                          count: me.streak.current,
                          todayFilled: todayFilled,
                          onTap: () => ShareService.shareStreak(
                            context,
                            days: me.streak.current,
                            accent: AmiColors.hexGreen,
                          ),
                        ),
                    ],
                  ),
                  const SizedBox(height: AmiSpacing.l),
                  // ── Concierge centerpiece ──
                  GestureDetector(
                    key: _conciergeKey,
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
                      for (var i = 0; i < tradingAgents.length; i++)
                        _AgentTile(
                          key: i == 0
                              ? _agentKey0
                              : i == 4
                                  ? _agentKey4
                                  : null,
                          agent: tradingAgents[i],
                          unlocked: unlocked.contains(tradingAgents[i].id),
                          onTap: () => unlocked.contains(tradingAgents[i].id)
                              ? _openAgent(context, tradingAgents[i])
                              : _showLockedSheet(context, ref, tradingAgents[i]),
                        ),
                    ],
                  ),

                  const SizedBox(height: AmiSpacing.xl),

                  // ── Daily Challenge ──
                  SizedBox(
                    key: _challengeKey,
                    child: const DailyChallengeCard(),
                  ),
                  const SizedBox(height: AmiSpacing.l),

                  // ── Weekly League (C3) ──
                  const LeagueCard(),
                  const SizedBox(height: AmiSpacing.l),

                  // ── Convene the Room CTA ──
                  SizedBox(
                    key: _conveneKey,
                    child: HexButton(
                      label: l.floorConveneCta,
                      color: AmiColors.hexGreen,
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
                    onPressed: () async {
                      await ref
                          .read(onboardingNotifierProvider.notifier)
                          .reset();
                      if (!context.mounted) return;
                      Navigator.of(context).pushReplacementNamed('/onboarding');
                    },
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
        ],
      ),
    );
  }
}


class _AgentTile extends StatelessWidget {
  const _AgentTile({
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
