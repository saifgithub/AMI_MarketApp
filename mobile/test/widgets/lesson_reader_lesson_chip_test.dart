/// CR053-MOBILE — the reader's `{{lesson:ID}}` inline tokenizer.
///
/// A resolvable id renders a tappable chip labeled with the target lesson's
/// CR044 code and deep-links to its reader. An id absent from the catalogue
/// degrades loudly (CR040) to plain text with no dead tap — never a
/// GestureDetector/InkWell wrapping unresolved text.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/lessons.dart';
import 'package:ami_trade/screens/lessons/lesson_reader_screen.dart';
import 'package:ami_trade/state/lessons_providers.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

const _readerLessonId = '007_test_lesson';
const _targetLessonId = '039';

const _targetMeta = LessonMeta(
  id: _targetLessonId,
  title: 'Reading Candles',
  durationMin: 4,
  level: 1,
  track: 'foundations',
  topic: 'general',
  prerequisites: [],
  tags: [],
  agentCallouts: [],
  code: 'FUND 8',
);

const _readerMeta = LessonMeta(
  id: _readerLessonId,
  title: 'Test Lesson',
  durationMin: 3,
  level: 1,
  track: 'foundations',
  topic: 'general',
  prerequisites: [],
  tags: [],
  agentCallouts: [],
  code: 'FUND 1',
);

const _catalogue = LessonCatalogue(
  tracks: [
    TrackCatalogue(
      track: 'foundations',
      title: 'Foundations',
      lessons: [_targetMeta, _readerMeta],
    ),
  ],
  totalLessons: 2,
);

final _lesson = Lesson(
  meta: _readerMeta,
  blocks: const [
    LessonBlock(
      kind: LessonBlockKind.markdown,
      markdown: 'See {{lesson:039}} and {{lesson:zzz}} for more.',
    ),
  ],
  quizzes: const [],
);

/// Injects a fixed [LessonsState] (the catalogue the chip resolves against)
/// without touching the network.
class _FixtureLessonsNotifier extends LessonsNotifier {
  _FixtureLessonsNotifier(super.ref, LessonsState fixture) {
    state = fixture;
  }
}

/// Injects a fixed [LessonReaderState] so the reader renders immediately,
/// skipping the real `load()` (network + device-user lookup).
class _FixtureLessonReaderNotifier extends LessonReaderNotifier {
  _FixtureLessonReaderNotifier(super.ref, super.lessonId, LessonReaderState fixture) {
    state = fixture;
  }
}

Widget _harness() {
  return ProviderScope(
    overrides: [
      lessonsNotifierProvider.overrideWith(
        (ref) => _FixtureLessonsNotifier(ref, const LessonsState(catalogue: _catalogue)),
      ),
      lessonReaderProvider(_readerLessonId).overrideWith(
        (ref) => _FixtureLessonReaderNotifier(
          ref,
          _readerLessonId,
          LessonReaderState(lesson: _lesson, loading: false),
        ),
      ),
    ],
    child: MaterialApp(
      localizationsDelegates: AppLocalizations.localizationsDelegates,
      supportedLocales: AppLocalizations.supportedLocales,
      home: const LessonReaderScreen(lessonId: _readerLessonId),
    ),
  );
}

void main() {
  testWidgets('a resolvable {{lesson:ID}} token renders a tappable chip',
      (t) async {
    await t.pumpWidget(_harness());
    await t.pump();

    expect(find.text('FUND 8'), findsOneWidget);
    expect(
      find.ancestor(
        of: find.text('FUND 8'),
        matching: find.byType(GestureDetector),
      ),
      findsOneWidget,
    );
    expect(t.takeException(), isNull);

    await t.tap(find.text('FUND 8'));
    await t.pump();
    await t.pump(const Duration(milliseconds: 300));

    // Navigator pushed a second reader instance for the resolved lesson.
    expect(find.byType(LessonReaderScreen), findsNWidgets(2));
    expect(t.takeException(), isNull);
  });

  testWidgets('an unresolvable {{lesson:ID}} degrades to plain text, no dead tap',
      (t) async {
    await t.pumpWidget(_harness());
    await t.pump();

    expect(find.text('zzz'), findsOneWidget);
    expect(
      find.ancestor(
        of: find.text('zzz'),
        matching: find.byType(GestureDetector),
      ),
      findsNothing,
    );
    expect(
      find.ancestor(
        of: find.text('zzz'),
        matching: find.byType(InkWell),
      ),
      findsNothing,
    );
    expect(t.takeException(), isNull);
  });
}
