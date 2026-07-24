/// CR087-MOBILE — the lessons list + reader request the active locale, and a
/// lesson served in Arabic renders right-to-left.
///
/// Covers the four CR087 mobile acceptance points:
///   1. the catalogue fetch carries the active locale (list ↔ detail agree);
///   2. the reader fetch carries the same active locale and shows the AR body;
///   3. an AR-missing lesson (server fell back to EN) renders with no error and
///      no client-side "missing translation" branch — the app renders whatever
///      body it got;
///   4. quiz submit grades under AR.
/// Plus a widget-level check that the AR body + quiz render under RTL
/// Directionality, and the `contentLocaleFor` derivation (null → 'en').
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/i18n/locale_provider.dart';
import 'package:ami_trade/models/lessons.dart';
import 'package:ami_trade/screens/lessons/lesson_reader_screen.dart';
import 'package:ami_trade/services/api/api_client.dart';
import 'package:ami_trade/state/lessons_providers.dart';
import 'package:ami_trade/state/onboarding_providers.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

const _arLessonId = '007_support';
const _enFallbackId = '090_en_only';

const _arQuiz = QuizQuestion(
  id: 'q1',
  question: 'ما هو الدعم؟',
  options: ['مستوى سعري', 'مؤشر فني', 'نوع سهم'],
  answerIndex: 0,
  explanation: 'الدعم مستوى سعري.',
);

const _arMeta = LessonMeta(
  id: _arLessonId,
  title: 'الدعم والمقاومة',
  durationMin: 4,
  level: 1,
  track: 'foundations',
  topic: 'general',
  prerequisites: [],
  tags: [],
  agentCallouts: [],
  code: 'FUND 1',
);

final _arLesson = Lesson(
  meta: _arMeta,
  blocks: const [
    LessonBlock(
      kind: LessonBlockKind.markdown,
      markdown: '# الدعم والمقاومة\n\nالدعم هو مستوى سعري مهم.',
    ),
    LessonBlock(kind: LessonBlockKind.quiz, quiz: _arQuiz),
  ],
  quizzes: const [_arQuiz],
);

/// English content returned even when the client asked for `ar` — this is what
/// the backend's server-side EN fallback looks like from the app's side.
final _enFallbackLesson = Lesson(
  meta: const LessonMeta(
    id: _enFallbackId,
    title: 'Support & Resistance',
    durationMin: 4,
    level: 1,
    track: 'foundations',
    topic: 'general',
    prerequisites: [],
    tags: [],
    agentCallouts: [],
    code: 'FUND 9',
  ),
  blocks: const [
    LessonBlock(
      kind: LessonBlockKind.markdown,
      markdown: '# Support and Resistance\n\nSupport is a price floor.',
    ),
  ],
  quizzes: const [],
);

const _arCatalogue = LessonCatalogue(
  tracks: [
    TrackCatalogue(
      track: 'foundations',
      title: 'الأساسيات',
      lessons: [_arMeta],
    ),
  ],
  totalLessons: 1,
);

const _enCatalogue = LessonCatalogue(
  tracks: [
    TrackCatalogue(
      track: 'foundations',
      title: 'Foundations',
      lessons: [],
    ),
  ],
  totalLessons: 0,
);

/// Test double: records the locale each content call is made with and returns
/// Arabic (or EN-fallback) fixtures without any network. Extends [ApiClient]
/// so it inherits the dio field; only the lessons-path methods are overridden.
class _FakeApiClient extends ApiClient {
  _FakeApiClient() : super(baseUrl: 'test://localhost');

  final List<String> catalogueLocales = [];
  final List<String> getLessonLocales = [];

  @override
  Future<LessonCatalogue> lessonCatalogue({String locale = 'en'}) async {
    catalogueLocales.add(locale);
    return locale == 'ar' ? _arCatalogue : _enCatalogue;
  }

  @override
  Future<Lesson> getLesson(String lessonId, {String locale = 'en'}) async {
    getLessonLocales.add(locale);
    return lessonId == _enFallbackId ? _enFallbackLesson : _arLesson;
  }

  @override
  Future<void> startLesson({
    required String userId,
    required String lessonId,
  }) async {}

  @override
  Future<QuizResult> submitQuiz({
    required String userId,
    required String lessonId,
    required List<int> answers,
  }) async {
    return QuizResult(
      lessonId: lessonId,
      correct: 1,
      total: 1,
      passed: true,
      score: 1.0,
      perQuestion: const [],
      unlockedAgents: const [],
    );
  }

  @override
  Future<ProgressSummary> lessonsProgress(String userId) async =>
      ProgressSummary(
        userId: userId,
        lessonsCompleted: 0,
        lessonsTotal: 1,
        byTrack: const {},
        agentsUnlocked: const [],
      );

  @override
  Future<Map<String, LessonStatus>> lessonStatusByLesson(String userId) async =>
      const {};

  @override
  Future<Map<String, AgentUnlockRequirement>> unlockRequirements(
    String userId,
  ) async =>
      const {};

  @override
  Future<List<AgentActivationRecord>> agentActivations(String userId) async =>
      const [];
}

ProviderContainer _container(_FakeApiClient fake, {String locale = 'ar'}) {
  return ProviderContainer(
    overrides: [
      apiClientProvider.overrideWithValue(fake),
      contentLocaleProvider.overrideWithValue(locale),
    ],
  );
}

/// Injects a fixed [LessonReaderState] so the reader renders immediately,
/// skipping the real network `load()`.
class _FixtureReader extends LessonReaderNotifier {
  _FixtureReader(super.ref, super.lessonId, LessonReaderState fixture) {
    state = fixture;
  }
}

class _FixtureLessons extends LessonsNotifier {
  _FixtureLessons(super.ref, LessonsState fixture) {
    state = fixture;
  }
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  setUp(() {
    SharedPreferences.setMockInitialValues({});
  });

  group('contentLocaleFor derivation', () {
    test('null (follow system) → en; explicit override → its code', () {
      expect(contentLocaleFor(null), 'en');
      expect(contentLocaleFor(const Locale('ar')), 'ar');
      expect(contentLocaleFor(const Locale('ms')), 'ms');
    });
  });

  group('locale threading (list ↔ detail agree)', () {
    test('catalogue fetch carries the active locale and returns AR', () async {
      final fake = _FakeApiClient();
      final c = _container(fake);
      addTearDown(c.dispose);

      await c.read(lessonsNotifierProvider.notifier).refresh();

      expect(fake.catalogueLocales, contains('ar'));
      final cat = c.read(lessonsNotifierProvider).catalogue;
      expect(cat?.tracks.single.title, 'الأساسيات');
    });

    test('reader fetch carries the same active locale and shows the AR body',
        () async {
      final fake = _FakeApiClient();
      final c = _container(fake);
      addTearDown(c.dispose);

      await c.read(lessonReaderProvider(_arLessonId).notifier).load();

      expect(fake.getLessonLocales, contains('ar'));
      final state = c.read(lessonReaderProvider(_arLessonId));
      expect(state.error, isNull);
      expect(state.lesson?.meta.title, 'الدعم والمقاومة');
      expect(state.lesson?.quizzes.single.question, 'ما هو الدعم؟');
    });

    test('AR-missing lesson renders the EN body it got, no error, no branch',
        () async {
      final fake = _FakeApiClient();
      final c = _container(fake);
      addTearDown(c.dispose);

      await c.read(lessonReaderProvider(_enFallbackId).notifier).load();

      // Client still asked for AR — the fallback is entirely server-side.
      expect(fake.getLessonLocales.last, 'ar');
      final state = c.read(lessonReaderProvider(_enFallbackId));
      expect(state.error, isNull);
      expect(state.lesson?.meta.title, 'Support & Resistance');
    });

    test('quiz submit grades under AR', () async {
      final fake = _FakeApiClient();
      final c = _container(fake);
      addTearDown(c.dispose);

      final notifier = c.read(lessonReaderProvider(_arLessonId).notifier);
      await notifier.load();
      notifier.selectAnswer('q1', 0);
      await notifier.submit();

      final state = c.read(lessonReaderProvider(_arLessonId));
      expect(state.error, isNull);
      expect(state.result?.passed, isTrue);
    });
  });

  group('RTL rendering', () {
    Widget harness() {
      return ProviderScope(
        overrides: [
          lessonsNotifierProvider.overrideWith(
            (ref) => _FixtureLessons(ref, const LessonsState()),
          ),
          lessonReaderProvider(_arLessonId).overrideWith(
            (ref) => _FixtureReader(
              ref,
              _arLessonId,
              LessonReaderState(lesson: _arLesson, loading: false),
            ),
          ),
        ],
        child: const MaterialApp(
          locale: Locale('ar'),
          localizationsDelegates: AppLocalizations.localizationsDelegates,
          supportedLocales: AppLocalizations.supportedLocales,
          home: LessonReaderScreen(lessonId: _arLessonId),
        ),
      );
    }

    testWidgets('AR body heading + quiz render under RTL Directionality',
        (t) async {
      await t.pumpWidget(harness());
      await t.pump();

      // Body heading (plain Text) and quiz (question + option) all in Arabic.
      expect(find.text('الدعم والمقاومة'), findsWidgets);
      expect(find.text('ما هو الدعم؟'), findsOneWidget);
      expect(find.text('مستوى سعري'), findsWidgets);
      expect(t.takeException(), isNull);

      // The whole lesson subtree is laid out right-to-left.
      final ctx = t.element(find.text('ما هو الدعم؟'));
      expect(Directionality.of(ctx), TextDirection.rtl);
    });
  });
}
