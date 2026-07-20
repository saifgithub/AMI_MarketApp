/// Row model + tier-partitioning for the per-track lesson list (DEF071).
///
/// Kept separate from `TrackLessonsScreen` so the ordering rules — which are the
/// substance of the DEF071 fix — are pure and unit-testable without pumping a
/// widget or mocking Riverpod/the API.
library;

import 'package:ami_trade/models/lessons.dart';

enum LessonTier { inProgress, notStarted, completed }

/// A row in the per-track list: either a tier section header or a lesson.
sealed class TrackRow {
  const TrackRow();
}

class TrackHeaderRow extends TrackRow {
  const TrackHeaderRow(this.label, {required this.isFirst});
  final String label;
  final bool isFirst;
}

class TrackLessonRow extends TrackRow {
  const TrackLessonRow(this.meta);
  final LessonMeta meta;
}

/// Build the ordered rows: three tiers (in-progress → never-started →
/// completed), catalogue order preserved within each.
///
/// Tier headers appear only once the user has progress worth grouping — i.e.
/// when more than one tier is non-empty. A first visit (everything
/// never-started) is a single tier and renders as a plain list, unchanged.
///
/// This is the DEF071 fix: the lesson badge is a stable canonical code
/// (`EDGE 49`), not a position, and the tier sort floats started lessons above
/// lower-numbered unstarted ones. The headers name the jump instead of leaving
/// a high number reading as a sequence error.
///
/// Partitioning (rather than a `List.sort` on a tier key) also makes "catalogue
/// order within a tier" real — Dart's `List.sort` is not guaranteed stable.
List<TrackRow> buildTrackRows({
  required List<LessonMeta> lessons,
  required LessonTier Function(LessonMeta) tierOf,
  required String inProgressLabel,
  required String notStartedLabel,
  required String completedLabel,
}) {
  final inProgress = <LessonMeta>[];
  final notStarted = <LessonMeta>[];
  final completed = <LessonMeta>[];
  for (final m in lessons) {
    switch (tierOf(m)) {
      case LessonTier.inProgress:
        inProgress.add(m);
      case LessonTier.notStarted:
        notStarted.add(m);
      case LessonTier.completed:
        completed.add(m);
    }
  }

  final tiers = <(String, List<LessonMeta>)>[
    (inProgressLabel, inProgress),
    (notStartedLabel, notStarted),
    (completedLabel, completed),
  ].where((t) => t.$2.isNotEmpty).toList();

  final showHeaders = tiers.length > 1;
  final rows = <TrackRow>[];
  for (final (label, tierLessons) in tiers) {
    if (showHeaders) {
      rows.add(TrackHeaderRow('$label · ${tierLessons.length}',
          isFirst: rows.isEmpty));
    }
    rows.addAll(tierLessons.map((m) => TrackLessonRow(m)));
  }
  return rows;
}
