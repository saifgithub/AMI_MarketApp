/// DEF071 — the per-track list showed a lesson's stable canonical badge
/// (`EDGE 49`) above lower-numbered unstarted ones because started lessons are
/// floated to the top. These tests pin the fix: the tier ordering, and that
/// section headers appear exactly when there's a jump to explain.
library;

import 'package:ami_trade/models/lessons.dart';
import 'package:ami_trade/screens/lessons/track_row_builder.dart';
import 'package:flutter_test/flutter_test.dart';

LessonMeta _lesson(String id) => LessonMeta(
      id: id,
      title: id,
      durationMin: 3,
      level: 1,
      track: 'edge_process',
      topic: 'x',
      prerequisites: const [],
      tags: const [],
      agentCallouts: const [],
    );

List<TrackRow> _build(
  List<LessonMeta> lessons,
  Map<String, LessonTier> tiers,
) =>
    buildTrackRows(
      lessons: lessons,
      tierOf: (m) => tiers[m.id] ?? LessonTier.notStarted,
      inProgressLabel: 'IN PROGRESS',
      notStartedLabel: 'NOT STARTED',
      completedLabel: 'COMPLETED',
    );

List<String> _lessonIds(List<TrackRow> rows) => [
      for (final r in rows)
        if (r is TrackLessonRow) r.meta.id,
    ];

List<String> _headers(List<TrackRow> rows) => [
      for (final r in rows)
        if (r is TrackHeaderRow) r.label,
    ];

void main() {
  group('buildTrackRows', () {
    test('a single tier (all never-started) renders no headers', () {
      final lessons = [_lesson('045_a'), _lesson('046_b'), _lesson('047_c')];
      final rows = _build(lessons, const {});

      expect(_headers(rows), isEmpty);
      expect(_lessonIds(rows), ['045_a', '046_b', '047_c']);
    });

    test('the reporter scenario: a started high-number lesson floats above '
        'lower-number unstarted ones, and headers explain the jump', () {
      // EDGE 49 in progress, EDGE 2..5 not started — the exact bug report.
      final lessons = [
        _lesson('002_two'),
        _lesson('003_three'),
        _lesson('004_four'),
        _lesson('005_five'),
        _lesson('049_forty_nine'),
      ];
      final rows = _build(lessons, {
        '049_forty_nine': LessonTier.inProgress,
      });

      // In-progress lesson leads, its section header first.
      expect(rows.first, isA<TrackHeaderRow>());
      expect((rows.first as TrackHeaderRow).label, 'IN PROGRESS · 1');
      expect((rows.first as TrackHeaderRow).isFirst, isTrue);

      expect(_headers(rows), ['IN PROGRESS · 1', 'NOT STARTED · 4']);
      expect(_lessonIds(rows),
          ['049_forty_nine', '002_two', '003_three', '004_four', '005_five']);
    });

    test('all three tiers appear in order with catalogue order kept inside each',
        () {
      final lessons = [
        _lesson('001_a'),
        _lesson('002_b'),
        _lesson('003_c'),
        _lesson('004_d'),
      ];
      final rows = _build(lessons, {
        '002_b': LessonTier.inProgress,
        '001_a': LessonTier.completed,
        '004_d': LessonTier.inProgress,
      });

      expect(_headers(rows),
          ['IN PROGRESS · 2', 'NOT STARTED · 1', 'COMPLETED · 1']);
      // 002 and 004 keep their relative catalogue order in the in-progress tier.
      expect(_lessonIds(rows), ['002_b', '004_d', '003_c', '001_a']);
    });

    test('completed + not-started (no in-progress) still shows headers', () {
      final lessons = [_lesson('001_a'), _lesson('002_b')];
      final rows = _build(lessons, {'001_a': LessonTier.completed});

      // Two non-empty tiers → the jump exists → headers shown. In-progress
      // tier is absent, so it produces no empty header.
      expect(_headers(rows), ['NOT STARTED · 1', 'COMPLETED · 1']);
      expect(_lessonIds(rows), ['002_b', '001_a']);
    });

    test('empty input yields no rows', () {
      expect(_build(const [], const {}), isEmpty);
    });
  });
}
