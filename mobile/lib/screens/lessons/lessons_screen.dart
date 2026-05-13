/// Lessons landing — hex cluster overview.
///
/// Zone A: slim progress bar (lesson count + agents unlocked).
/// Zone B: 7-hex honeycomb cluster (1 centre + 6 surrounding tracks).
/// Tapping a hex navigates to [TrackLessonsScreen].
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/lessons.dart';
import 'package:ami_trade/screens/lessons/track_lessons_screen.dart';
import 'package:ami_trade/state/lessons_providers.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:ami_trade/theme/hex_clipper.dart';
import 'package:ami_trade/widgets/hex/track_hex_button.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

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

class LessonsScreen extends ConsumerWidget {
  const LessonsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(lessonsNotifierProvider);
    return Scaffold(
      backgroundColor: AmiColors.slate900,
      body: SafeArea(
        child: Column(
          children: [
            const _Header(),
            Expanded(child: _body(context, ref, state)),
          ],
        ),
      ),
    );
  }

  Widget _body(BuildContext context, WidgetRef ref, LessonsState state) {
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
              _SlimProgressBar(state: state),
              const SizedBox(height: AmiSpacing.xl),
              _HexCluster(
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
  const _SlimProgressBar({required this.state});
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
/// Flat-top honeycomb neighbor offsets from centre (cx, cy):
///   left/right:      (±hexW, 0)
///   upper/lower diag: (±hexW/2, ∓hexH/2)
///
/// Grid (3 columns × 2 rows, total container 3W × 2H):
///
///   [TA]  [NM]        top-left / top-right of centre
/// [FA] [FON] [SB]     left / centre / right
///   [RP]  [EP]        bottom-left / bottom-right of centre
class _HexCluster extends StatelessWidget {
  const _HexCluster({
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
        final hexW = constraints.maxWidth / 3;
        final hexH = hexW / flatTopRegularHexagonAspectRatio;
        final clusterH = 2 * hexH;

        // Cluster top-left origins for each hex widget (Positioned left/top).
        // Centre of the 3W × 2H container is at (1.5W, 1H).
        // FON (foundations) = centre; others are neighbour offsets from it.
        final origins = {
          'foundations': Offset(hexW, hexH / 2),             // (1.5W - 0.5W, 1H - 0.5H)
          'fundamentals_analysis': Offset(0, hexH / 2),      // left
          'technical_analysis': Offset(hexW / 2, 0),         // upper-left
          'news_macro': Offset(hexW * 1.5, 0),               // upper-right
          'sentiment_behaviour': Offset(hexW * 2, hexH / 2), // right
          'risk_portfolio': Offset(hexW / 2, hexH),          // lower-left
          'edge_process': Offset(hexW * 1.5, hexH),          // lower-right
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
  const _Header();

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
          Text(AppLocalizations.of(context).lessonsHeading,
              style: AmiTypography.labelMono.copyWith(color: AmiColors.hexGreen)),
        ],
      ),
    );
  }
}

