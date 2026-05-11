/// Lessons catalogue + progress overview.
///
/// Track-grouped lesson list. Each lesson shows duration, agent callouts,
/// and a complete/incomplete chip. Tap → lesson reader. Top of screen shows
/// progress + unlocked agents.
library;

import 'package:ami_trade/models/agent.dart';
import 'package:ami_trade/models/lessons.dart';
import 'package:ami_trade/screens/lessons/lesson_reader_screen.dart';
import 'package:ami_trade/state/lessons_providers.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:ami_trade/widgets/hex/hex_avatar.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

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
      child: ListView(
        padding: const EdgeInsets.all(AmiSpacing.m),
        children: [
          _ProgressCard(state: state),
          const SizedBox(height: AmiSpacing.l),
          for (final t in cat.tracks)
            _TrackSection(
              track: t,
              state: state,
              onTap: (lessonId) => Navigator.of(context).push(MaterialPageRoute<void>(
                builder: (_) => LessonReaderScreen(lessonId: lessonId),
              )),
            ),
        ],
      ),
    );
  }
}


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
          Text('LESSONS',
              style: AmiTypography.labelMono.copyWith(color: AmiColors.hexGreen)),
        ],
      ),
    );
  }
}


class _ProgressCard extends StatelessWidget {
  const _ProgressCard({required this.state});
  final LessonsState state;

  @override
  Widget build(BuildContext context) {
    final p = state.progress;
    final unlocked = state.activations;
    final pct = (p == null || p.lessonsTotal == 0)
        ? 0.0
        : p.lessonsCompleted / p.lessonsTotal;
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
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('YOUR PROGRESS',
                        style: AmiTypography.labelMono.copyWith(color: AmiColors.hexGreen)),
                    const SizedBox(height: 4),
                    Text(
                      '${p?.lessonsCompleted ?? 0} / ${p?.lessonsTotal ?? 0} lessons',
                      style: AmiTypography.statMid,
                    ),
                  ],
                ),
              ),
              Column(
                crossAxisAlignment: CrossAxisAlignment.end,
                children: [
                  Text('AGENTS', style: AmiTypography.labelMono.copyWith(fontSize: 10)),
                  Text('${unlocked.length} / 12', style: AmiTypography.statMid),
                ],
              ),
            ],
          ),
          const SizedBox(height: AmiSpacing.s),
          ClipRRect(
            borderRadius: BorderRadius.circular(2),
            child: LinearProgressIndicator(
              value: pct,
              minHeight: 6,
              backgroundColor: AmiColors.slate900,
              valueColor: const AlwaysStoppedAnimation(AmiColors.hexGreen),
            ),
          ),
          if (unlocked.isNotEmpty) ...[
            const SizedBox(height: AmiSpacing.m),
            Wrap(
              spacing: 6,
              runSpacing: 6,
              children: [
                for (final a in unlocked)
                  _UnlockedPill(agentId: a.agentId, method: a.activationMethod),
              ],
            ),
          ],
          if (p?.nextRecommendedLesson != null) ...[
            const SizedBox(height: AmiSpacing.m),
            Text('NEXT UP', style: AmiTypography.labelMono.copyWith(fontSize: 10)),
            const SizedBox(height: 2),
            Text(
              state.catalogue
                      ?.tracks
                      .expand((t) => t.lessons)
                      .firstWhere(
                        (l) => l.id == p!.nextRecommendedLesson,
                        orElse: () => LessonMeta(
                          id: p!.nextRecommendedLesson!,
                          title: p.nextRecommendedLesson!,
                          durationMin: 3,
                          level: 1,
                          track: '',
                          topic: '',
                          prerequisites: const [],
                          tags: const [],
                          agentCallouts: const [],
                        ),
                      )
                      .title ??
                  '',
              style: AmiTypography.body,
            ),
          ],
        ],
      ),
    );
  }
}


class _UnlockedPill extends StatelessWidget {
  const _UnlockedPill({required this.agentId, required this.method});
  final String agentId;
  final String method;

  @override
  Widget build(BuildContext context) {
    final a = agentById(agentId);
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(
        color: a.color.withValues(alpha: 0.15),
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: a.color),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(a.abbreviation,
              style: AmiTypography.labelMono.copyWith(
                  color: a.color, fontSize: 10)),
          const SizedBox(width: 4),
          Icon(
            method == 'earn_path' ? Icons.school : Icons.workspace_premium,
            size: 11,
            color: a.color,
          ),
        ],
      ),
    );
  }
}


class _TrackSection extends StatelessWidget {
  const _TrackSection({
    required this.track,
    required this.state,
    required this.onTap,
  });

  final TrackCatalogue track;
  final LessonsState state;
  final void Function(String lessonId) onTap;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: AmiSpacing.l),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 4),
            child: Text(
              track.title.toUpperCase(),
              style: AmiTypography.labelMono.copyWith(color: AmiColors.textHigh),
            ),
          ),
          const SizedBox(height: AmiSpacing.s),
          for (final l in track.lessons)
            Padding(
              padding: const EdgeInsets.only(bottom: 8),
              child: _LessonTile(meta: l, onTap: () => onTap(l.id)),
            ),
        ],
      ),
    );
  }
}


class _LessonTile extends StatelessWidget {
  const _LessonTile({required this.meta, required this.onTap});
  final LessonMeta meta;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final callouts = meta.agentCallouts;
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(AmiRadii.card),
      child: Container(
        padding: const EdgeInsets.all(AmiSpacing.m),
        decoration: BoxDecoration(
          color: AmiColors.slate800,
          borderRadius: BorderRadius.circular(AmiRadii.card),
          border: Border.all(color: AmiColors.slate700),
        ),
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
                      Text('${meta.durationMin} min',
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
            const Icon(Icons.chevron_right, color: AmiColors.textLow),
          ],
        ),
      ),
    );
  }
}
