/// Floor v0.2 — the landing surface, rebuilt as frame A′ (CR173 slice 2).
///
/// **What was wrong with the old one, measured** (research 01): 13 identity
/// marks at rest, 23 tap targets, the CONVENE button 1.63 folds down a 1178px
/// column. It opened by introducing twelve members of staff — answering *"who
/// works here?"* to a user who was asking *"what should I do?"*. Of 172 real
/// alpha users, 73% never took a core action.
///
/// A′ answers the question that was actually asked, in this order:
///
///   1. **the carousel** — how am I doing (portfolio) · what did my team decide
///   2. **one omnibox** — a ticker or a question, routed deterministically
///   3. **CONVENE THE ROOM** — the only primary on the screen
///   4. **the Daily Challenge** — the second hero
///   5. **YOUR FIRM** — the twelve, one tap down, with their seat count
///
/// **The twelve are intact** (D-012). They moved from the doorway to the depth
/// layer: `your_firm_screen.dart` carries the whole shipped wall, so 1-on-1,
/// Brief Your Agent and the unlock path all survive the move (acceptance #8).
/// Nothing else was orphaned either — the league card is gone by CR109
/// Amendment A's standing scope, the streak chip stays until CR109 re-homes it,
/// and `restart onboarding` moved into Settings, which is where the capability
/// map says it belongs now that CR133 put Settings inside YOU.
library;

import 'package:ami_trade/features/games/games_gate.dart';
import 'package:ami_trade/features/nav/ami_tab.dart';
import 'package:ami_trade/features/tour/floor_tour.dart';
import 'package:ami_trade/features/tour/tour_intro_sheet.dart';
import 'package:ami_trade/features/tour/tour_providers.dart';
import 'package:ami_trade/features/tour/tour_service.dart';
import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/agent.dart';
import 'package:ami_trade/screens/agent/one_on_one_screen.dart';
import 'package:ami_trade/screens/floor/daily_challenge_card.dart';
import 'package:ami_trade/screens/floor/floor_cards.dart';
import 'package:ami_trade/screens/floor/team_calls_screen.dart';
import 'package:ami_trade/screens/floor/your_firm_screen.dart';
import 'package:ami_trade/screens/room/convene_sheet.dart';
import 'package:ami_trade/screens/room/room_screen.dart';
import 'package:ami_trade/services/share/share_service.dart';
import 'package:ami_trade/state/daily_challenge_providers.dart';
import 'package:ami_trade/state/league_providers.dart';
import 'package:ami_trade/state/lessons_providers.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:ami_trade/widgets/floor/floor_carousel.dart';
import 'package:ami_trade/widgets/floor/floor_omnibox.dart';
import 'package:ami_trade/widgets/hex/hex_avatar.dart';
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
  ConsumerState<FloorScreen> createState() => _FloorScreenState();
}

class _FloorScreenState extends ConsumerState<FloorScreen> {
  // Three coach-mark targets, down from five (§5.10). The Concierge hex and the
  // agent wall they used to point at are not on this screen any more.
  final _carouselKey = GlobalKey();
  final _omniboxKey = GlobalKey();
  final _firmKey = GlobalKey();

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
    if (ref.read(activeTabProvider) != AmiTab.floor) return;
    final service = ref.read(tourServiceProvider);
    if (await service.hasSeen(TourSection.floor)) return;
    await service.markSeen(TourSection.floor);
    if (!mounted) return;
    final start = await showModalBottomSheet<bool>(
      context: context,
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
        carouselKey: _carouselKey,
        omniboxKey: _omniboxKey,
        firmKey: _firmKey,
      ),
      hideSkip: true,
      colorShadow: Colors.black,
      opacityShadow: 0.88,
      pulseEnable: false,
      beforeFocus: (target) async {
        // Ensure the target is in view before the spotlight focuses on it. If
        // the tooltip is positioned ABOVE the target, scroll the target toward
        // the bottom of the viewport so there's room above for the tooltip.
        final ctx = target.keyTarget?.currentContext;
        if (ctx == null) return;
        final contents = target.contents ?? const [];
        final tooltipAbove =
            contents.isNotEmpty && contents.first.align == ContentAlign.top;
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

  void _convene(String ticker) {
    Navigator.of(context).push(MaterialPageRoute<void>(
      builder: (_) => RoomScreen(ticker: ticker),
    ));
  }

  void _ask(String text) {
    // D-015 — the Concierge takes the question and routes analysis to the firm;
    // it does not answer it itself. Carrying the text here rather than
    // answering it on the Floor is what keeps that boundary intact.
    Navigator.of(context).push(MaterialPageRoute<void>(
      builder: (_) =>
          OneOnOneScreen(agent: kAllAgents.last, initialMessage: text),
    ));
  }

  @override
  Widget build(BuildContext context) {
    // Listen for Floor becoming the active tab after the user switches away
    // and back.
    ref.listen<AmiTab>(activeTabProvider, (prev, next) async {
      if (next != AmiTab.floor) return;
      final service = ref.read(tourServiceProvider);
      if (await service.hasSeen(TourSection.floor)) return;
      await service.markSeen(TourSection.floor);
      if (!mounted) return;
      final start = await showModalBottomSheet<bool>(
        context: context,
        backgroundColor: AmiColors.slate800,
        shape: const RoundedRectangleBorder(
          borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
        ),
        builder: (_) => const TourIntroSheet(),
      );
      if (start != true || !mounted) return;
      _runFloorTour();
    });

    final l = AppLocalizations.of(context);
    final me = ref.watch(leagueMeProvider).valueOrNull;
    final todayFilled =
        ref.watch(dailyChallengeTodayProvider).valueOrNull?.myAttempt != null;
    final unlocked = ref.watch(lessonsNotifierProvider).unlockedAgentIds;

    return Scaffold(
      backgroundColor: AmiColors.slate900,
      body: Stack(
        children: [
          const Positioned.fill(child: HexMeshOverlay()),
          SafeArea(
            child: SingleChildScrollView(
              padding: const EdgeInsets.all(AmiSpacing.m),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Row(
                    children: [
                      SvgPicture.asset('assets/logo_hex.svg',
                          height: 26, semanticsLabel: 'AMI'),
                      const Spacer(),
                      // Stays until CR109 re-homes it (§3). Its "keep your
                      // streak" copy is re-cut there too, not here.
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
                  const SizedBox(height: AmiSpacing.s),

                  // 1 — the answer cards.
                  SizedBox(
                    key: _carouselKey,
                    child: FloorCarousel(
                      cards: [
                        // Rule 2: portfolio leads. Rule 3: nothing behind it is
                        // load-bearing — the portfolio has its own tab and the
                        // calls have their own screen.
                        const FloorCard(
                            id: 'portfolio', child: PortfolioAnswerCard()),
                        FloorCard(
                          id: 'calls',
                          child: const TeamCallsAnswerCard(),
                          onTap: () =>
                              Navigator.of(context).push(MaterialPageRoute<void>(
                            builder: (_) => const TeamCallsScreen(),
                          )),
                        ),
                        // SECTOR WATCH is card 3 and ships when the News
                        // analyst's live feed does (§3). Two real cards beat
                        // three with one empty.
                      ],
                    ),
                  ),
                  const SizedBox(height: AmiSpacing.m),

                  // 2 + 3 — one box, one primary.
                  FloorOmnibox(
                    fieldKey: _omniboxKey,
                    onConvene: _convene,
                    onAsk: _ask,
                    onPick: () => ConveneSheet.show(context),
                  ),
                  const SizedBox(height: AmiSpacing.m),

                  // 4 — the second hero.
                  const DailyChallengeCard(),
                  const SizedBox(height: AmiSpacing.m),

                  // 5 — the twelve, one tap down.
                  _FirmRow(
                    key: _firmKey,
                    unlockedCount: unlocked.length,
                    onTap: () =>
                        Navigator.of(context).push(MaterialPageRoute<void>(
                      builder: (_) => const YourFirmScreen(),
                    )),
                  ),

                  const SizedBox(height: AmiSpacing.l),
                  // CR109 Amendment F — the long-press into the dark-launched
                  // game. `kGamesEnabled` is a const `bool.fromEnvironment`, so
                  // with the define off the compiler folds this branch away and
                  // a store binary carries neither the gesture nor the route.
                  if (kGamesEnabled)
                    GestureDetector(
                      onLongPress: () =>
                          Navigator.of(context).pushNamed('/games'),
                      child: Text(l.floorFooter,
                          textAlign: TextAlign.center,
                          style: AmiTypography.caption),
                    )
                  else
                    Text(l.floorFooter,
                        textAlign: TextAlign.center,
                        style: AmiTypography.caption),
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

/// The firm row — a live seat count and a way in.
///
/// **The count is load-bearing** (§5.7, from research 08 §8.4): it is the one
/// thing on this screen that says the firm is twelve people and that some of
/// them are still locked. Dropping it turns the row into a menu item and
/// changes the design — the acceptance says so explicitly, and says a re-review
/// is required if it goes.
class _FirmRow extends StatelessWidget {
  const _FirmRow({
    super.key,
    required this.unlockedCount,
    required this.onTap,
  });

  final int unlockedCount;
  final VoidCallback onTap;

  static const _seats = 12;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    // Three marks, not twelve: enough to say "a firm", not enough to be a
    // roster. These are the three families, in the order the run uses them.
    const faces = ['fundamentals_analyst', 'research_manager', 'neutral_debator'];
    return InkWell(
      onTap: onTap,
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: AmiSpacing.s),
        child: Row(
          children: [
            for (final id in faces)
              Padding(
                padding: const EdgeInsets.only(right: 4),
                child: HexAvatar(
                    label: '', color: agentById(id).color, size: 24),
              ),
            const SizedBox(width: AmiSpacing.s),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(l.floorFirmHeading,
                      style: AmiTypography.labelMono
                          .copyWith(fontSize: 10, color: AmiColors.hexCyan)),
                  const SizedBox(height: 1),
                  Text(l.floorFirmSeats(unlockedCount, _seats),
                      style: AmiTypography.caption
                          .copyWith(color: AmiColors.textMed)),
                ],
              ),
            ),
            const Icon(Icons.chevron_right,
                color: AmiColors.textLow, size: 18),
          ],
        ),
      ),
    );
  }
}
