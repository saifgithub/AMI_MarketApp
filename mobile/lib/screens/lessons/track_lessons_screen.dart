/// Per-track lesson list — navigated to from the lessons hex cluster.
///
/// Lessons are grouped into three tiers: in-progress → never-started →
/// completed, in that order, with a section header per tier once the user has
/// any progress (DEF071). Status comes from
/// GET /v1/lessons/progress/{userId}/by_lesson via LessonsState.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/lessons.dart';
import 'package:ami_trade/screens/lessons/lesson_reader_screen.dart';
import 'package:ami_trade/screens/lessons/track_row_builder.dart';
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

    final rows = _rows(track.lessons, state, AppLocalizations.of(context));

    return RefreshIndicator(
      onRefresh: () => ref.read(lessonsNotifierProvider.notifier).refresh(),
      color: AmiColors.hexBlue,
      child: ListView.builder(
        padding: const EdgeInsets.all(AmiSpacing.m),
        itemCount: rows.length,
        itemBuilder: (context, i) {
          final row = rows[i];
          switch (row) {
            case TrackHeaderRow():
              return _TierHeader(label: row.label, isFirst: row.isFirst);
            case TrackLessonRow(:final meta):
              return Padding(
                padding: const EdgeInsets.only(bottom: AmiSpacing.s),
                child: LessonTile(
                  meta: meta,
                  status: state.lessonStatuses[meta.id],
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
                ),
              );
          }
        },
      ),
    );
  }

  /// Classify then delegate to the pure [buildTrackRows] (see
  /// `track_row_builder.dart` for the ordering rules and the DEF071 rationale).
  List<TrackRow> _rows(
      List<LessonMeta> lessons, LessonsState state, AppLocalizations l) {
    LessonTier tierOf(LessonMeta m) {
      if (state.isLessonInProgress(m.id)) return LessonTier.inProgress;
      if (state.isLessonCompleted(m.id)) return LessonTier.completed;
      return LessonTier.notStarted;
    }

    return buildTrackRows(
      lessons: lessons,
      tierOf: tierOf,
      inProgressLabel: l.lessonsTierInProgress,
      notStartedLabel: l.lessonsTierNotStarted,
      completedLabel: l.lessonsTierCompleted,
    );
  }
}

class _TierHeader extends StatelessWidget {
  const _TierHeader({required this.label, required this.isFirst});
  final String label;
  final bool isFirst;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: EdgeInsets.only(
          top: isFirst ? 0 : AmiSpacing.m, bottom: AmiSpacing.s),
      child: Text(
        label,
        style: AmiTypography.labelMono
            .copyWith(fontSize: 11, color: AmiColors.textMed),
      ),
    );
  }
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
