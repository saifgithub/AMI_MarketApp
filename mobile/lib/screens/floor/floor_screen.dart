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
/// Nothing else was orphaned either — the league card and the streak chip are
/// both gone by CR109 Amendment A's standing scope (slice 7 took the chip with
/// the reputation streak that fed it), and `restart onboarding` moved into
/// Settings, which is where the capability map says it belongs now that CR133
/// put Settings inside YOU.
library;

import 'package:ami_trade/features/nav/ami_tab.dart';
import 'package:ami_trade/features/tour/ami_tour_overlay.dart';
import 'package:ami_trade/features/tour/floor_tour.dart';
import 'package:ami_trade/features/tour/tour_intro_sheet.dart';
import 'package:ami_trade/features/tour/tour_providers.dart';
import 'package:ami_trade/features/tour/tour_service.dart';
import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/agent.dart';
import 'package:ami_trade/screens/agent/one_on_one_screen.dart';
import 'package:ami_trade/screens/floor/daily_challenge_card.dart';
import 'package:ami_trade/screens/floor/floor_cards.dart';
import 'package:ami_trade/screens/floor/floor_providers.dart';
import 'package:ami_trade/screens/floor/team_calls_screen.dart';
import 'package:ami_trade/screens/floor/your_firm_screen.dart';
import 'package:ami_trade/screens/room/convene_sheet.dart';
import 'package:ami_trade/screens/room/room_screen.dart';
import 'package:ami_trade/services/telemetry/telemetry_emitter.dart';
import 'package:ami_trade/state/inbox_providers.dart';
import 'package:ami_trade/state/lessons_providers.dart';
import 'package:ami_trade/state/onboarding_providers.dart';
import 'package:ami_trade/state/telemetry_providers.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:ami_trade/widgets/floor/floor_carousel.dart';
import 'package:ami_trade/widgets/floor/floor_omnibox.dart';
import 'package:ami_trade/widgets/floor/floor_reaction_card.dart';
import 'package:ami_trade/widgets/hex/hex_avatar.dart';
import 'package:ami_trade/widgets/hex/hex_mesh_overlay.dart';
import 'package:ami_trade/widgets/hex/hex_toast.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_svg/flutter_svg.dart';

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

  /// CR173 §5.12 — whether to ask how this surface feels. Resolved once, after
  /// layout, so it never delays the first frame.
  bool _askReaction = false;

  @override
  void initState() {
    super.initState();
    // Floor is tab 0 — active from the start. Check immediately after layout.
    WidgetsBinding.instance.addPostFrameCallback((_) async {
      await _maybeShowTour();
      final ask = await registerFloorVisit();
      if (mounted && ask) setState(() => _askReaction = true);
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
    // DEF382 — the `beforeFocus` + `Scrollable.ensureVisible` that used to sit
    // here now lives in `showAmiTour`, verbatim: 350ms, alignment 0.85 when the
    // card sits above the target and 0.15 when below.
    showAmiTour(
      context: context,
      steps: buildFloorTargets(
        l: l,
        carouselKey: _carouselKey,
        omniboxKey: _omniboxKey,
        firmKey: _firmKey,
      ),
      onFinish: () {
        if (!mounted) return;
        HexToast.show(
          context,
          AppLocalizations.of(context).tourCompletionFloor,
          accent: AmiColors.hexGreen,
          icon: Icons.check_circle_outline,
        );
      },
    );
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
    final unlocked = ref.watch(lessonsNotifierProvider).unlockedAgentIds;
    // CR184 — the NOT ACTIONED card collapses (is omitted, not blanked) when
    // nothing is outstanding: loading, error and empty all read as "no card",
    // because acceptance #4 forbids a blank card and "everything actioned"
    // needs no permanent one.
    final hasUnactioned =
        ref.watch(unactionedCallsProvider).valueOrNull?.isNotEmpty ?? false;

    return Scaffold(
      backgroundColor: AmiColors.slate900,
      body: Stack(
        children: [
          const Positioned.fill(child: HexMeshOverlay()),
          SafeArea(
            child: SingleChildScrollView(
              // DEF297 — the second way down for the keyboard, and the one a
              // thumb reaches for first. `onTapOutside` on the field handles a
              // tap; this handles the drag, which is what a user does when the
              // keyboard is covering the thing they wanted to read.
              keyboardDismissBehavior:
                  ScrollViewKeyboardDismissBehavior.onDrag,
              padding: const EdgeInsets.all(AmiSpacing.m),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Row(
                    children: [
                      SvgPicture.asset('assets/logo_hex.svg',
                          height: 26, semanticsLabel: 'AMI'),
                      const Spacer(),
                      // CR102 — the inbox bell. Badge only when unread > 0;
                      // absent on load error (the badge may be absent, the
                      // inbox screen may not lie).
                      const _InboxBell(),
                      // CR109 slice 7 — the streak chip stood here, pending a
                      // re-homing that was never specified. The streak it drew
                      // was the reputation game's, retired by Amendment A, and
                      // its only feed was `GET /v1/league/me`. It goes with them
                      // rather than being re-homed onto nothing.
                    ],
                  ),
                  const SizedBox(height: AmiSpacing.s),

                  // §5.12 — the interim capture path, above the fold but below
                  // the chrome, and gone for good once answered or dismissed.
                  if (_askReaction)
                    FloorReactionCard(
                        onDone: () => setState(() => _askReaction = false)),

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
                        // CR183 — card 3. onTap stays null: the real home is
                        // the leader's TickerDetail, and the leader is only
                        // known async, so the tap is wired inside the body.
                        const FloorCard(
                            id: 'sector', child: SectorWatchAnswerCard()),
                        // CR184 — card 4, collapsed when nothing is
                        // unactioned. Its second home is the calls screen
                        // (rule 3), same as card 2.
                        if (hasUnactioned)
                          FloorCard(
                            id: 'unactioned',
                            child: const UnactionedCallsCard(),
                            onTap: () => Navigator.of(context)
                                .push(MaterialPageRoute<void>(
                              builder: (_) => const TeamCallsScreen(),
                            )),
                          ),
                      ],
                    ),
                  ),
                  const SizedBox(height: AmiSpacing.m),

                  // 2 + 3 — one box, one primary.
                  FloorOmnibox(
                    // DEF298 — the same CR128 gate the Convene sheet and the
                    // trade ticket use. Third field, one gate.
                    validate: (t) =>
                        ref.read(apiClientProvider).validateTicker(t),
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
                    onTap: () {
                      // CR181 — depth segment. Recorded at the only push
                      // site the firm screen has (it is a stateless wall);
                      // one tap = one event. Fire-and-forget.
                      ref
                          .read(telemetryProvider)
                          .record(TelemetryEvents.firmOpen);
                      Navigator.of(context).push(MaterialPageRoute<void>(
                        builder: (_) => const YourFirmScreen(),
                      ));
                    },
                  ),

                  const SizedBox(height: AmiSpacing.l),
                  // CR182 — the CR109 Amendment F long-press into the game is
                  // GONE. Saiful, 2026-08-14: "Remove the hidden 'long press on
                  // ami-trade' link to the game. we no longer need it."
                  //
                  // Only the gesture is removed. `kGamesEnabled` and the
                  // `/games` route registration stay exactly as CR109 built
                  // them, so the compile-time gate is untouched — but with no
                  // entry point anywhere in the UI the route is now unreachable
                  // in every build, which also empties DEF296's exposure in
                  // practice rather than by promise. A future way back into the
                  // game needs a new door, deliberately.
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
      child: Container(
        // CR182 — the row was the shortest tappable thing on the Floor and the
        // only route to the twelve agents the whole product is about. The
        // footer's hidden long-press is gone, so the space it was conceding is
        // free; 64pt also clears the 48pt one-handed thumb minimum, which
        // `vertical: AmiSpacing.s` around a 24pt avatar did not.
        constraints: const BoxConstraints(minHeight: 64),
        padding: const EdgeInsets.symmetric(vertical: AmiSpacing.s),
        child: Row(
          children: [
            for (final id in faces)
              Padding(
                padding: const EdgeInsets.only(right: 4),
                child: HexAvatar(
                    label: '', color: agentById(id).color, size: 30),
              ),
            const SizedBox(width: AmiSpacing.s),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisSize: MainAxisSize.min,
                children: [
                  Text(l.floorFirmHeading,
                      style: AmiTypography.labelMono
                          .copyWith(fontSize: 10, color: AmiColors.hexCyan)),
                  const SizedBox(height: 2),
                  Text(l.floorFirmSeats(unlockedCount, _seats),
                      style: AmiTypography.caption
                          .copyWith(color: AmiColors.textMed)),
                ],
              ),
            ),
            const Icon(Icons.chevron_right,
                color: AmiColors.textLow, size: 20),
          ],
        ),
      ),
    );
  }
}

/// CR102 — the inbox bell in the Floor header.
///
/// The unread count is derived client-side from the inbox payload
/// (`unreadInboxCountProvider`), which yields 0 while loading and on
/// error — so a failed fetch renders a bare bell, never a stale claim.
/// The badge copies the 14px amber attention-badge visual from
/// `hex_avatar.dart` so "needs your eyes" reads the same everywhere.
class _InboxBell extends ConsumerWidget {
  const _InboxBell();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l = AppLocalizations.of(context);
    final count = ref.watch(unreadInboxCountProvider);
    return Semantics(
      label: l.inboxBellSemantics(count),
      button: true,
      child: Stack(
        clipBehavior: Clip.none,
        children: [
          IconButton(
            icon: const Icon(Icons.notifications_outlined,
                color: AmiColors.textLow),
            onPressed: () => Navigator.of(context).pushNamed('/inbox'),
          ),
          if (count > 0)
            Positioned(
              top: 6,
              right: 6,
              child: IgnorePointer(
                child: Container(
                  width: 14,
                  height: 14,
                  decoration: const BoxDecoration(
                    color: AmiColors.hexAmber,
                    shape: BoxShape.circle,
                  ),
                  alignment: Alignment.center,
                  child: Text(
                    count > 9 ? '9+' : '$count',
                    style: const TextStyle(
                      fontFamily: AmiTypography.jetBrains,
                      fontSize: 9,
                      height: 1.0,
                      fontWeight: FontWeight.w700,
                      color: AmiColors.slate900,
                    ),
                  ),
                ),
              ),
            ),
        ],
      ),
    );
  }
}
