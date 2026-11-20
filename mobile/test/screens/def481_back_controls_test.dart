/// DEF481 — every pushed page's back control carries `ami.nav.back` and a
/// "Back" tooltip, so the UAT crawler can address it by id and a screen reader
/// can name it. Two layers: real-widget checks on the screens that can be
/// pumped cheaply, and a source walk (the P36 shape) so a NEW hand-rolled back
/// arrow that skips either fails here instead of surfacing in a crawl.
library;

import 'dart:io';

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/lessons.dart';
import 'package:ami_trade/qa/semantics_ids.dart';
import 'package:ami_trade/screens/lessons/lesson_reader_screen.dart';
import 'package:ami_trade/screens/lessons/track_lessons_screen.dart';
import 'package:ami_trade/state/lesson_view_mode_provider.dart';
import 'package:ami_trade/state/lessons_providers.dart';
import 'package:ami_trade/state/mandate_providers.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

class _FixedReader extends LessonReaderNotifier {
  _FixedReader(super.ref, super.lessonId, LessonReaderState fixed) {
    state = fixed;
  }
}

class _FixedMandate extends MandateNotifier {
  _FixedMandate(super.ref) {
    state = const MandateState();
  }
}

class _FixedLessons extends LessonsNotifier {
  _FixedLessons(super.ref);
}

Widget _app(Widget home, List<Override> overrides) => ProviderScope(
      overrides: overrides,
      child: MaterialApp(
        localizationsDelegates: AppLocalizations.localizationsDelegates,
        supportedLocales: AppLocalizations.supportedLocales,
        home: home,
      ),
    );

void _expectBackControl(WidgetTester t) {
  expect(find.bySemanticsIdentifier(ExitIds.navBack), findsOneWidget,
      reason: 'DEF481: the back control must carry ami.nav.back');
  final tooltip = MaterialLocalizations.of(t.element(find.byType(Scaffold)))
      .backButtonTooltip;
  expect(
    find.byWidgetPredicate((w) =>
        (w is IconButton && w.tooltip == tooltip) ||
        (w is Semantics && w.properties.label == tooltip)),
    findsWidgets,
    reason: 'DEF481: the back control must be named "$tooltip"',
  );
}

void main() {
  testWidgets('lesson reader back control has id and tooltip', (t) async {
    final h = t.ensureSemantics();
    await t.binding.setSurfaceSize(const Size(390, 800));
    addTearDown(() => t.binding.setSurfaceSize(null));
    const id = '014_position_sizing_basics';
    await t.pumpWidget(_app(const LessonReaderScreen(lessonId: id), [
      lessonReaderProvider(id).overrideWith((ref) => _FixedReader(
          ref,
          id,
          const LessonReaderState(
            lesson: Lesson(
              meta: LessonMeta(
                id: id,
                title: 'Position sizing basics',
                durationMin: 5,
                level: 1,
                track: 'risk_portfolio',
                topic: 'position_sizing',
                prerequisites: [],
                tags: [],
                agentCallouts: [],
              ),
              quizzes: [],
              blocks: [
                LessonBlock(kind: LessonBlockKind.markdown, markdown: '# A'),
              ],
            ),
            loading: false,
          ))),
      mandateNotifierProvider.overrideWith((ref) => _FixedMandate(ref)),
      lessonsNotifierProvider.overrideWith((ref) => _FixedLessons(ref)),
      lessonViewModeProvider.overrideWith(
          (ref) => LessonViewModeNotifier.withoutHydration(null)),
    ]));
    await t.pump();

    _expectBackControl(t);
    h.dispose();
  });

  testWidgets('track lessons back control has id and tooltip', (t) async {
    final h = t.ensureSemantics();
    await t.binding.setSurfaceSize(const Size(390, 800));
    addTearDown(() => t.binding.setSurfaceSize(null));
    await t.pumpWidget(
        _app(const TrackLessonsScreen(trackId: 'risk_portfolio'), [
      lessonsNotifierProvider.overrideWith((ref) => _FixedLessons(ref)),
    ]));
    await t.pump();

    _expectBackControl(t);
    h.dispose();
  });

  test('every id declared in SheetIds / LessonIds is attached somewhere', () {
    final used = [
      for (final f in Directory('lib/screens')
          .listSync(recursive: true)
          .whereType<File>()
          .where((f) => f.path.endsWith('.dart')))
        f.readAsStringSync(),
    ].join('\n');
    for (final ref in [
      SheetIds.conveneCta,
      SheetIds.mergeCta,
      LessonIds.modeBook,
      LessonIds.modeInteractive,
    ]) {
      final name = {
        SheetIds.conveneCta: 'SheetIds.conveneCta',
        SheetIds.mergeCta: 'SheetIds.mergeCta',
        LessonIds.modeBook: 'LessonIds.modeBook',
        LessonIds.modeInteractive: 'LessonIds.modeInteractive',
      }[ref]!;
      expect(used.contains(name), isTrue,
          reason: '$name ($ref) is declared but no screen attaches it');
    }
  });

  test('every hand-rolled back arrow in lib/screens carries id and tooltip',
      () {
    final arrow = RegExp(r'Icons\.arrow_back(?:_ios_new)?\b');
    final offenders = <String>[];
    var sites = 0;
    for (final f in Directory('lib/screens')
        .listSync(recursive: true)
        .whereType<File>()
        .where((f) => f.path.endsWith('.dart'))) {
      final src = f.readAsStringSync();
      for (final m in arrow.allMatches(src)) {
        sites++;
        final from = (m.start - 450).clamp(0, src.length);
        final before = src.substring(from, m.start);
        final around =
            src.substring(from, (m.end + 450).clamp(0, src.length));
        final line = '\n'.allMatches(src.substring(0, m.start)).length + 1;
        if (!before.contains('ExitIds.navBack')) {
          offenders.add('${f.path}:$line missing ExitIds.navBack');
        }
        if (!around.contains('backButtonTooltip')) {
          offenders.add('${f.path}:$line missing backButtonTooltip');
        }
      }
    }
    expect(sites, greaterThanOrEqualTo(8),
        reason: 'the walk found too few back arrows — the pattern rotted');
    expect(offenders, isEmpty);
  });
}
