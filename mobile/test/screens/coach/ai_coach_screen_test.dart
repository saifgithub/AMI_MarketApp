/// DEF198 — AI Coach's empty-state copy hardcoded "280 questions" while the
/// corpus grew to 295 with nothing keeping it in sync.
///
/// Two things pinned here, because a naive fix (280 -> 295) just moves the
/// staleness forward to the next corpus change:
///   1. The screen renders `AiCoachCorpus.totalCount`, not a literal in the
///      widget — proven by asserting the OLD number is gone and the
///      constant's value is what's on screen.
///   2. `AiCoachCorpus.totalCount` itself is checked against the real
///      corpus files on disk. This is the test that actually catches drift:
///      if `content/ai_coach/*.json` grows again, this goes red until the
///      constant is updated — the guard DEF198 asks for, given no backend
///      total-count field exists yet to derive it from at runtime (see
///      `AiCoachCorpus`'s doc for why).
library;

import 'dart:convert';
import 'dart:io';

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/ai_coach.dart';
import 'package:ami_trade/screens/coach/ai_coach_screen.dart';
import 'package:ami_trade/services/api/api_client.dart';
import 'package:ami_trade/state/onboarding_providers.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

class _NeverCalledApiClient extends ApiClient {
  _NeverCalledApiClient() : super(baseUrl: 'test://localhost');
}

/// Repo-root `content/ai_coach/*.json` — the EN corpus files named in the
/// DEF198 row. `mobile/` is `Directory.current` under `flutter test`, so the
/// repo root is one level up.
const _kCorpusFiles = [
  'beginner',
  'intermediate',
  'psychology',
  'scam',
  'platform',
  'ai_meta',
  'islamic_finance',
];

int _realCorpusCount() {
  var total = 0;
  for (final name in _kCorpusFiles) {
    final file = File('../content/ai_coach/$name.json');
    final entries = jsonDecode(file.readAsStringSync()) as List;
    total += entries.length;
  }
  return total;
}

void main() {
  test(
      'DEF198: AiCoachCorpus.totalCount matches the real corpus files on '
      'disk', () {
    // Non-vacuity: fail loudly, not with a false pass, if the path is wrong.
    expect(File('../content/ai_coach/beginner.json').existsSync(), isTrue,
        reason: 'corpus fixture path is wrong — this guard would silently '
            'never run');

    expect(AiCoachCorpus.totalCount, _realCorpusCount(),
        reason: 'DEF198: the corpus grew (or shrank) and '
            'AiCoachCorpus.totalCount was not updated to match — this is '
            'exactly the drift that shipped "280 questions" for however '
            'long the corpus had already been at 295');
  });

  testWidgets(
      'DEF198: the empty-state hint shows the real count, not a stale '
      'hardcoded one', (tester) async {
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          apiClientProvider.overrideWithValue(_NeverCalledApiClient()),
        ],
        child: MaterialApp(
          localizationsDelegates: AppLocalizations.localizationsDelegates,
          supportedLocales: AppLocalizations.supportedLocales,
          home: const AICoachScreen(),
        ),
      ),
    );
    await tester.pump();

    expect(
      find.textContaining('${AiCoachCorpus.totalCount} questions'),
      findsOneWidget,
    );
    // The specific number DEF198 reported as stale must be gone, not just
    // outnumbered by a second, correct string.
    expect(find.textContaining('280 questions'), findsNothing);
    expect(tester.takeException(), isNull);
  });
}
