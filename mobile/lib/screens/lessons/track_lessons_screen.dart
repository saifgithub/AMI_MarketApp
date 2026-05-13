/// Per-track lesson list — navigated to from the lessons hex cluster.
///
/// Shows all lessons for a single track. Sort order (once per-lesson status
/// is available from the API): in-progress → never-started → completed.
/// Until then, catalogue order is preserved.
library;

import 'package:ami_trade/models/lessons.dart';
import 'package:ami_trade/screens/lessons/lesson_reader_screen.dart';
import 'package:ami_trade/state/lessons_providers.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:ami_trade/widgets/lessons/lesson_tile.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

/// Short display labels for each track — mirrors the spec table.
const _trackShortLabel = {
  'foundations': 'FOUNDATIONS',
  'fundamentals_analysis': 'FUNDAMENTALS',
  'technical_analysis': 'TECHNICAL',
  'news_macro': 'NEWS & MACRO',
  'sentiment_behaviour': 'SENTIMENT',
  'risk_portfolio': 'RISK',
  'edge_process': 'EDGE',
};

class TrackLessonsScreen extends ConsumerWidget {
  const TrackLessonsScreen({super.key, required this.trackId});

  final String trackId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(lessonsNotifierProvider);
    final heading = _trackShortLabel[trackId] ?? trackId.toUpperCase();

    return Scaffold(
      backgroundColor: AmiColors.slate900,
      body: SafeArea(
        child: Column(
          children: [
            _Header(heading: heading),
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

    final track = cat.tracks.where((t) => t.track == trackId).firstOrNull;
    if (track == null || track.lessons.isEmpty) {
      return Center(
        child: Text('No lessons in this track.',
            style: AmiTypography.body.copyWith(color: AmiColors.textMed)),
      );
    }

    final lessons = _sorted(track.lessons);

    return RefreshIndicator(
      onRefresh: () => ref.read(lessonsNotifierProvider.notifier).refresh(),
      color: AmiColors.hexBlue,
      child: ListView.separated(
        padding: const EdgeInsets.all(AmiSpacing.m),
        itemCount: lessons.length,
        separatorBuilder: (_, __) => const SizedBox(height: AmiSpacing.s),
        itemBuilder: (context, i) {
          final meta = lessons[i];
          return LessonTile(
            meta: meta,
            onRead: () => Navigator.of(context).push(
              MaterialPageRoute<void>(
                builder: (_) => LessonReaderScreen(lessonId: meta.id),
              ),
            ),
            onQuizOnly: () => Navigator.of(context).push(
              MaterialPageRoute<void>(
                builder: (_) =>
                    LessonReaderScreen(lessonId: meta.id, quizOnly: true),
              ),
            ),
          );
        },
      ),
    );
  }

  /// Catalogue order preserved; extend here when per-lesson status is
  /// available from GET /v1/lessons/progress/{userId}/by_lesson.
  List<LessonMeta> _sorted(List<LessonMeta> lessons) => lessons;
}

class _Header extends StatelessWidget {
  const _Header({required this.heading});
  final String heading;

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
          GestureDetector(
            onTap: () => Navigator.of(context).pop(),
            child: const Icon(Icons.arrow_back_ios_new,
                size: 18, color: AmiColors.textMed),
          ),
          const SizedBox(width: AmiSpacing.m),
          Text(heading,
              style: AmiTypography.labelMono
                  .copyWith(color: AmiColors.hexGreen)),
        ],
      ),
    );
  }
}
