/// Lessons landing — hex cluster overview.
///
/// Zone A: slim progress bar (lesson count + agents unlocked).
/// Zone B: honeycomb cluster, one hex per track the API served (13 today).
/// Tapping a hex navigates to [TrackLessonsScreen].
library;

import 'package:ami_trade/features/tour/ami_tour_overlay.dart';
import 'package:ami_trade/features/tour/lessons_tour.dart';
import 'package:ami_trade/features/nav/ami_tab.dart';
import 'package:ami_trade/features/tour/tour_providers.dart';
import 'package:ami_trade/features/tour/tour_service.dart';
import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/lessons.dart';
import 'package:ami_trade/screens/lessons/honeycomb_layout.dart';
import 'package:ami_trade/screens/lessons/track_lessons_screen.dart';
import 'package:ami_trade/services/ads/ads_models.dart';
import 'package:ami_trade/state/lessons_providers.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:ami_trade/widgets/ads/ad_slot.dart';
import 'package:ami_trade/widgets/hex/ami_screen_header.dart';
import 'package:ami_trade/theme/hex_clipper.dart';
import 'package:ami_trade/widgets/hex/hex_toast.dart';
import 'package:ami_trade/widgets/hex/track_hex_button.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

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
    // DEF382 — the old `beforeFocus` + `Scrollable.ensureVisible` lives in
    // `showAmiTour` now, unchanged: 350ms, alignment 0.85 when the card sits
    // above the target and 0.15 when below.
    showAmiTour(
      context: context,
      steps: buildLessonsTargets(
        l: l,
        headerKey: _headerKey,
        progressKey: _progressKey,
        hexClusterKey: _hexClusterKey,
      ),
      onFinish: () {
        if (!mounted) return;
        HexToast.show(
          context,
          AppLocalizations.of(context).tourCompletionLessons,
          accent: AmiColors.hexGreen,
          icon: Icons.check_circle_outline,
        );
      },
    );
  }

  @override
  Widget build(BuildContext context) {
    // Fire tour when Lessons tab (index 3) becomes active for the first time.
    ref.listen<AmiTab>(activeTabProvider, (prev, next) async {
      if (next != AmiTab.lessons) return;
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
            AmiScreenHeader(
              key: _headerKey,
              title: AppLocalizations.of(context).lessonsHeading,
              titleColor: AmiColors.hexGreen,
              showBack: Navigator.of(context).canPop(),
            ),
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
              // CR122 — Academy Hub bottom is an approved ad placement
              // (ads.md:43). Self-gating slot; collapses for paying plans.
              const AdSlot(placement: AdPlacement.academyHubBottom),
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
            // DEF068: was `activations.length`, which counted the Concierge's
            // earn_path row and could render "13 / 12".
            Text(l.lessonsAgentsCount(state.unlockedAgentIds.length),
                style: AmiTypography.statMid),
          ],
        ),
      ],
    );
  }
}

// ─── Zone B — hex cluster ────────────────────────────────────────────────────

/// Honeycomb of every track the API served — 13 today, 4/5/4 across three
/// columns, foundations at the visual centre.
///
/// Flat-top hex tiling shares full edges at six positions (N, NE, SE, S, SW,
/// NW, H3-style), so three columns at x = 0, ¾W, 1½W with the side columns
/// dropped half a hex give a gapless comb of any height:
///
///         [C0]
///     [L0]    [R0]
///         [C1]
///     [L1]    [R1]        ← centre column runs one taller than the sides
///          …
///
/// Bounding box: 2.5·hexW wide (hence hexW = ⅖ × maxWidth) by
/// [honeycombHeightInHexes] tall. Slot geometry and fill order live in
/// `honeycomb_layout.dart`; the count comes from [tracks] and nowhere else,
/// which is the whole point of DEF082.
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
    final trackMap = {for (final t in tracks) t.track: t};
    final ordered = orderTracksForHoneycomb(trackMap.keys);

    return LayoutBuilder(
      builder: (context, constraints) {
        final hexW = constraints.maxWidth * honeycombHexWidthFraction;
        final hexH = hexW / flatTopRegularHexagonAspectRatio;
        final slots = honeycombSlots(ordered.length, hexW, hexH);
        // The comb no longer spans the full row, so centre it.
        final inset =
            (constraints.maxWidth - honeycombWidthInHexes * hexW) / 2;

        return SizedBox(
          width: constraints.maxWidth,
          height: honeycombHeightInHexes(ordered.length) * hexH,
          child: Stack(
            children: [
              for (var i = 0; i < ordered.length; i++)
                Positioned(
                  left: inset + slots[i].dx,
                  top: slots[i].dy,
                  width: hexW,
                  height: hexH,
                  child: TrackHexButton(
                    label: honeycombTrackLabel[ordered[i]] ??
                        trackMap[ordered[i]]!.title.toUpperCase(),
                    color: honeycombTrackColor[ordered[i]] ??
                        honeycombFallbackColors[i % honeycombFallbackColors.length],
                    completed:
                        progress?.byTrack[ordered[i]]?['completed'] ?? 0,
                    total: progress?.byTrack[ordered[i]]?['total'] ??
                        trackMap[ordered[i]]!.lessons.length,
                    onTap: () => onTrackTap(ordered[i]),
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

