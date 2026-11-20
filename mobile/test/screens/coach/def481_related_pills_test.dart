/// DEF481 item 5 — related pills must not look tappable unless they are.
///
/// Founder ruling: "if there is a reason to be tappable, yes, but if there is
/// no reason, then redesign." A related lesson that resolves in the catalogue
/// opens its reader; a related agent (no profile screen exists) and an
/// unresolvable lesson render as plain captions with no tap handler and no
/// button semantics.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/ai_coach.dart';
import 'package:ami_trade/models/lessons.dart';
import 'package:ami_trade/qa/semantics_ids.dart';
import 'package:ami_trade/screens/coach/ai_coach_screen.dart';
import 'package:ami_trade/screens/lessons/lesson_reader_screen.dart';
import 'package:ami_trade/state/lessons_providers.dart';
import 'package:ami_trade/widgets/lessons/related_pills.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

const _meta = LessonMeta(
  id: '065_guaranteed_return_scams',
  title: 'Guaranteed return scams',
  durationMin: 4,
  level: 7,
  track: 'edge_process',
  topic: 'scam',
  prerequisites: [],
  tags: [],
  agentCallouts: [],
  code: 'EDGE 15',
  number: 65,
);

const _catalogue = LessonCatalogue(
  tracks: [
    TrackCatalogue(track: 'edge_process', title: 'Edge', lessons: [_meta]),
  ],
  totalLessons: 1,
);

class _FakeLessons extends LessonsNotifier {
  _FakeLessons(super.ref) {
    state = const LessonsState(catalogue: _catalogue);
  }

  @override
  Future<void> refresh() async {}
}

const _qa = CoachQA(
  id: 'q1',
  category: 'scam',
  question: 'Is a guaranteed return real?',
  shortAnswer: 'No.',
  longAnswer: 'No investment guarantees a return.',
  relatedLessons: ['065', '999'],
  relatedAgents: ['portfolio_manager'],
);

Widget _host(Widget child) => ProviderScope(
      overrides: [
        lessonsNotifierProvider.overrideWith((ref) => _FakeLessons(ref)),
      ],
      child: MaterialApp(
        localizationsDelegates: AppLocalizations.localizationsDelegates,
        supportedLocales: AppLocalizations.supportedLocales,
        home: Scaffold(body: child),
      ),
    );

void main() {
  test('a bare lesson number resolves to its catalogue slug', () {
    expect(resolveRelatedLesson(_catalogue, '065')?.id, _meta.id);
    expect(resolveRelatedLesson(_catalogue, _meta.id)?.id, _meta.id);
    expect(resolveRelatedLesson(_catalogue, '999'), isNull);
    expect(resolveRelatedLesson(null, '065'), isNull);
  });

  test('related agents use the CR160 display name, not the raw id', () {
    expect(relatedAgentLabel('portfolio_manager'), isNot('portfolio manager'));
    expect(relatedAgentLabel('not_an_agent'), 'not an agent');
  });

  testWidgets('a resolvable related-lesson pill is a >=40px button that opens '
      'the lesson', (t) async {
    final semantics = t.ensureSemantics();
    await t.pumpWidget(_host(const AnswerSheet(qa: _qa)));
    await t.pump();

    final pill = find.bySemanticsIdentifier(RelatedIds.lessonPill);
    expect(pill, findsOneWidget, reason: 'only 065 resolves; 999 must not');
    expect(t.getSemantics(pill).flagsCollection.isButton, isTrue);
    expect(t.getSemantics(pill).rect.height, greaterThanOrEqualTo(40));

    await t.tap(pill);
    await t.pump();
    await t.pump();
    final reader = t.widget<LessonReaderScreen>(find.byType(LessonReaderScreen));
    expect(reader.lessonId, _meta.id);
    semantics.dispose();
  });

  testWidgets('unresolvable lessons and related agents are plain captions: no '
      'button semantics, no tap handler', (t) async {
    final semantics = t.ensureSemantics();
    await t.pumpWidget(_host(const AnswerSheet(qa: _qa)));
    await t.pump();

    final agentLabel = find.text(relatedAgentLabel('portfolio_manager'));
    final unresolved = find.text('999');
    for (final label in [agentLabel, unresolved]) {
      expect(label, findsOneWidget);
      expect(
          find.ancestor(of: label, matching: find.byType(InkWell)), findsNothing);
      expect(find.ancestor(of: label, matching: find.byType(GestureDetector)),
          findsNothing);
      expect(
          find.ancestor(of: label, matching: find.byType(DecoratedBox)),
          findsNothing,
          reason: 'a border or fill reads as a button');
      expect(t.getSemantics(label).flagsCollection.isButton, isFalse);
    }
    semantics.dispose();
  });
}
