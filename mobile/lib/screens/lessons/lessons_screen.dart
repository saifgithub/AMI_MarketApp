/// Lessons landing — hex cluster overview.
///
/// Zone A: slim progress bar (lesson count + agents unlocked).
/// Zone B: 7-hex honeycomb cluster (1 centre + 6 surrounding tracks).
/// Tapping a hex navigates to [TrackLessonsScreen].
library;

import 'package:ami_trade/features/tour/lessons_tour.dart';
import 'package:ami_trade/features/tour/tour_providers.dart';
import 'package:ami_trade/features/tour/tour_service.dart';
import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/lessons.dart';
import 'package:ami_trade/screens/lessons/track_lessons_screen.dart';
import 'package:ami_trade/state/lessons_providers.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:ami_trade/theme/hex_clipper.dart';
import 'package:ami_trade/widgets/hex/hex_toast.dart';
import 'package:ami_trade/widgets/hex/track_hex_button.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:tutorial_coach_mark/tutorial_coach_mark.dart';

// ─── track config ────────────────────────────────────────────────────────────

const _trackColor = {
  'foundations': AmiColors.hexBlue,
  'fundamentals_analysis': AmiColors.hexCyan,
  'technical_analysis': AmiColors.hexPurple,
  'news_macro': AmiColors.hexAmber,
  'sentiment_behaviour': AmiColors.hexPink,
  'risk_portfolio': AmiColors.hexRed,
  'edge_process': AmiColors.hexGreen,
};

const _trackLabel = {
  'foundations': 'FOUNDATIONS',
  'fundamentals_analysis': 'FUNDAMENTALS',
  'technical_analysis': 'TECHNICAL',
  'news_macro': 'NEWS & MACRO',
  'sentiment_behaviour': 'SENTIMENT',
  'risk_portfolio': 'RISK',
  'edge_process': 'EDGE',
};

// ─── screen ──────────────────────────────────────────────────────────────────

class LessonsScreen extends ConsumerStatefulWidget {
  const LessonsScreen({super.key});

  @override
  ConsumerState<LessonsScreen> createState() => _LessonsScreenState();
}

class _LessonsScreenState extends ConsumerState<LessonsScreen> {
  final _headerKey = GlobalKey();
  final _progressKey = GlobalKey();
  final _hexClusterKey = GlobalKey();

  void _runTour() {
    final l = AppLocalizations.of(context);
    TutorialCoachMark(
      targets: buildLessonsTargets(
        l: l,
        headerKey: _headerKey,
        progressKey: _progressKey,
        hexClusterKey: _hexClusterKey,
      ),
      hideSkip: true,
      colorShadow: Colors.black,
      opacityShadow: 0.88,
      pulseEnable: false,
      beforeFocus: (target) async {
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
          AppLocalizations.of(context).tourCompletionLessons,
          accent: AmiColors.hexGreen,
          icon: Icons.check_circle_outline,
        );
      },
    ).show(context: context);
  }

  @override
  Widget build(BuildContext context) {
    // Fire tour when Lessons tab (index 3) becomes active for the first time.
    ref.listen<int>(activeTabIndexProvider, (prev, next) async {
      if (next != 3) return;
      final service = ref.read(tourServiceProvider);
      if (await service.hasSeen(TourSection.lessons)) return;
      await service.markSeen(TourSection.lessons);
      if (!mounted) return;
      _runTour();
    });

    final state = ref.watch(lessonsNotifierProvider);
    return Scaffold(
      backgroundColor: AmiColors.slate900,
      body: SafeArea(
        child: Column(
          children: [
            _Header(key: _headerKey, showBack: Navigator.of(context).canPop()),
            Expanded(child: _body(context, state)),
          ],
        ),
      ),
    );
  }

  Widget _body(BuildContext context, LessonsState state) {
    if (state.loading && state.catalogue == null) {
      return const Center(child: CircularProgressIndicator());
    }
    if (state.error != null) {
      return Padding(
        padding: const EdgeInsets.all(AmiSpacing.l),
        child: Center(child: Text(state.error!, style: AmiTypography.body)),
      );
    }
    final cat = state.catalogue;
    if (cat == null) return const SizedBox.shrink();

    return RefreshIndicator(
      onRefresh: () => ref.read(lessonsNotifierProvider.notifier).refresh(),
      color: AmiColors.hexBlue,
      child: SingleChildScrollView(
        physics: const AlwaysScrollableScrollPhysics(),
        child: Padding(
          padding: const EdgeInsets.all(AmiSpacing.m),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              _SlimProgressBar(key: _progressKey, state: state),
              const SizedBox(height: AmiSpacing.xl),
              _HexCluster(
                key: _hexClusterKey,
                tracks: cat.tracks,
                progress: state.progress,
                onTrackTap: (trackId) => Navigator.of(context).push(
                  MaterialPageRoute<void>(
                    builder: (_) => TrackLessonsScreen(trackId: trackId),
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

// ─── Zone A — slim progress bar ───────────────────────────────────────────────

class _SlimProgressBar extends StatelessWidget {
  const _SlimProgressBar({super.key, required this.state});
  final LessonsState state;

  @override
  Widget build(BuildContext context) {
    final p = state.progress;
    final l = AppLocalizations.of(context);
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(l.lessonsYourProgress,
                style: AmiTypography.labelMono.copyWith(fontSize: 10)),
            Text(
              l.lessonsCount(p?.lessonsCompleted ?? 0, p?.lessonsTotal ?? 0),
              style: AmiTypography.statMid,
            ),
          ],
        ),
        Column(
          crossAxisAlignment: CrossAxisAlignment.end,
          children: [
            Text(l.lessonsAgents,
                style: AmiTypography.labelMono.copyWith(fontSize: 10)),
            Text(l.lessonsAgentsCount(state.activations.length),
                style: AmiTypography.statMid),
          ],
        ),
      ],
    );
  }
}

// ─── Zone B — hex cluster ────────────────────────────────────────────────────

/// 7-hex honeycomb: foundations (centre) + 6 surrounding tracks.
///
/// Flat-top hex tiling has true edge-sharing neighbours at six positions —
/// N, NE, SE, S, SW, NW (H3-style). Centre-to-neighbour offsets:
///   N/S:  (0, ∓hexH)            // share full flat top/bottom edge
///   NE/SE/SW/NW: (±¾hexW, ±½hexH) // share diagonal edges
///
/// Clock layout (all 6 surroundings touch FON edge-to-edge):
///
///         [TA]            ← 12 (N)
///     [FA]    [NM]        ← 10 (NW), 2 (NE)
///         [FON]           ← centre
///     [RP]    [SB]        ← 8  (SW), 4 (SE)
///         [EP]            ← 6  (S)
///
/// Cluster bounding box: 2.5*hexW × 3*hexH. To make it fill the available
/// width, hexW = ⅖ × maxWidth.
class _HexCluster extends StatelessWidget {
  const _HexCluster({
    super.key,
    required this.tracks,
    required this.progress,
    required this.onTrackTap,
  });

  final List<TrackCatalogue> tracks;
  final ProgressSummary? progress;
  final void Function(String trackId) onTrackTap;

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        // Cluster width = 2.5 * hexW → hexW = maxWidth * 2/5.
        final hexW = constraints.maxWidth * 2 / 5;
        final hexH = hexW / flatTopRegularHexagonAspectRatio;
        final clusterH = 3 * hexH;

        // Each Positioned uses (left, top) of the hex bounding box.
        // Centre FON at (¾hexW, hexH); the cluster's centre point is
        // (1¼hexW, 1½hexH) inside a 2½hexW × 3hexH container.
        final origins = {
          'technical_analysis':     Offset(hexW * 0.75, 0),            // N
          'news_macro':             Offset(hexW * 1.5,  hexH * 0.5),   // NE
          'sentiment_behaviour':    Offset(hexW * 1.5,  hexH * 1.5),   // SE
          'edge_process':           Offset(hexW * 0.75, hexH * 2),     // S
          'risk_portfolio':         Offset(0,           hexH * 1.5),   // SW
          'fundamentals_analysis':  Offset(0,           hexH * 0.5),   // NW
          'foundations':            Offset(hexW * 0.75, hexH),         // centre
        };

        final trackMap = {for (final t in tracks) t.track: t};

        return SizedBox(
          width: constraints.maxWidth,
          height: clusterH,
          child: Stack(
            children: [
              for (final entry in origins.entries)
                if (trackMap.containsKey(entry.key))
                  Positioned(
                    left: entry.value.dx,
                    top: entry.value.dy,
                    width: hexW,
                    height: hexH,
                    child: TrackHexButton(
                      label:
                          _trackLabel[entry.key] ?? entry.key.toUpperCase(),
                      color: _trackColor[entry.key] ?? AmiColors.hexBlue,
                      completed: progress?.byTrack[entry.key]?['completed'] ?? 0,
                      total: progress?.byTrack[entry.key]?['total'] ??
                          trackMap[entry.key]!.lessons.length,
                      onTap: () => onTrackTap(entry.key),
                    ),
                  ),
            ],
          ),
        );
      },
    );
  }
}

// ─── chrome ──────────────────────────────────────────────────────────────────

class _Header extends StatelessWidget {
  const _Header({super.key, this.showBack = false});

  final bool showBack;

  @override
  Widget build(BuildContext context) {
    return Container(
      height: 64,
      padding: const EdgeInsets.symmetric(horizontal: AmiSpacing.m),
      decoration: const BoxDecoration(
        color: AmiColors.glassChrome,
        border: Border(bottom: BorderSide(color: AmiColors.slate700)),
      ),
      child: Row(
        children: [
          if (showBack) ...[
            GestureDetector(
              onTap: () => Navigator.of(context).pop(),
              child: const Icon(Icons.arrow_back_ios_new,
                  size: 18, color: AmiColors.textMed),
            ),
            const SizedBox(width: AmiSpacing.m),
          ],
          Text(AppLocalizations.of(context).lessonsHeading,
              style: AmiTypography.labelMono.copyWith(color: AmiColors.hexGreen)),
        ],
      ),
    );
  }
}

