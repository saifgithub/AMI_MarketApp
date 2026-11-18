/// CR273 (CR267 WP-31, D-084) — the 18+ confirmation that opens onboarding.
///
/// Onboarding cannot start, and therefore cannot complete, without a
/// deliberate "I am 18 or older" confirmation: the checkbox starts unticked,
/// CONTINUE is disabled until it is ticked, and nothing reaches the server
/// before then. A user who says they are under 18 gets a clear dead end, not a
/// silent loop. Only a timestamp is ever stored (server side); no birth date
/// is asked for.
///
/// Only `ApiClient` is faked so the real screen + notifier are under test.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/onboarding.dart';
import 'package:ami_trade/qa/semantics_ids.dart';
import 'package:ami_trade/screens/onboarding/onboarding_screen.dart';
import 'package:ami_trade/services/api/api_client.dart';
import 'package:ami_trade/state/onboarding_providers.dart';
import 'package:ami_trade/widgets/hex/hex_button.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

class _RecordingApi extends ApiClient {
  _RecordingApi() : super(baseUrl: 'test://localhost');

  final List<bool> startCalls = [];

  @override
  Future<StartOnboardingResponse> startOnboarding({
    required String locale,
    required String timezone,
    required bool ageConfirmed,
  }) async {
    startCalls.add(ageConfirmed);
    return const StartOnboardingResponse(
      sessionId: 'sid-age',
      welcomeMessage: OnboardingMessage(
        author: ChatAuthorRemote.concierge,
        content: 'Welcome (test)',
        step: 'welcome',
      ),
      firstQuestion: OnboardingMessage(
        author: ChatAuthorRemote.concierge,
        content: 'First question (test)',
        step: 'q1_goal',
        chips: ['option a'],
      ),
    );
  }
}

Future<AppLocalizations> _pump(WidgetTester t, _RecordingApi api) async {
  await t.binding.setSurfaceSize(const Size(390, 780));
  addTearDown(() => t.binding.setSurfaceSize(null));
  await t.pumpWidget(ProviderScope(
    overrides: [apiClientProvider.overrideWithValue(api)],
    child: MaterialApp(
      localizationsDelegates: AppLocalizations.localizationsDelegates,
      supportedLocales: AppLocalizations.supportedLocales,
      home: const OnboardingScreen(),
    ),
  ));
  await t.pump();
  return AppLocalizations.delegate.load(const Locale('en'));
}

Finder _byId(String id) => find.byWidgetPredicate(
    (w) => w is Semantics && w.properties.identifier == id);

bool _continueEnabled(WidgetTester t, AppLocalizations l) {
  final button = t.widget<HexButton>(find.descendant(
    of: _byId(OnboardingIds.ageContinue),
    matching: find.byType(HexButton),
  ));
  return button.onPressed != null;
}

void main() {
  setUp(() => SharedPreferences.setMockInitialValues({}));

  testWidgets('the gate opens onboarding, unticked, with nothing sent',
      (t) async {
    final api = _RecordingApi();
    final l = await _pump(t, api);

    expect(find.text(l.onboardingAgeBody), findsOneWidget);
    expect(find.text(l.onboardingAgeCheckbox), findsOneWidget);
    expect(t.widget<Checkbox>(find.byType(Checkbox)).value, isFalse,
        reason: 'the confirmation must be a deliberate act, never pre-ticked');
    expect(api.startCalls, isEmpty,
        reason: 'no session may be created before the user confirms');
    expect(find.text('Welcome (test)'), findsNothing);
  });

  testWidgets('CONTINUE is disabled until the checkbox is ticked and cannot '
      'start onboarding', (t) async {
    final api = _RecordingApi();
    final l = await _pump(t, api);

    expect(_continueEnabled(t, l), isFalse);
    await t.tap(find.text(l.onboardingAgeContinue), warnIfMissed: false);
    await t.pump();
    expect(api.startCalls, isEmpty);
    expect(find.text(l.onboardingAgeBody), findsOneWidget,
        reason: 'still on the gate');
  });

  testWidgets('ticking then CONTINUE starts the interview with '
      'age_confirmed=true', (t) async {
    final api = _RecordingApi();
    final l = await _pump(t, api);

    await t.tap(find.byType(Checkbox));
    await t.pump();
    expect(t.widget<Checkbox>(find.byType(Checkbox)).value, isTrue);
    expect(_continueEnabled(t, l), isTrue);

    await t.tap(find.text(l.onboardingAgeContinue));
    // The Concierge bubble streams its text, so the tree never settles.
    for (var i = 0; i < 5; i++) {
      await t.pump(const Duration(milliseconds: 100));
    }

    expect(api.startCalls, [true]);
    expect(find.text(l.onboardingAgeBody), findsNothing);
    expect(find.text('First question (test)'), findsOneWidget);
  });

  testWidgets('"I am under 18" is a respectful dead end that stores and sends '
      'nothing, and GO BACK returns to an unticked gate', (t) async {
    final api = _RecordingApi();
    final l = await _pump(t, api);

    await t.tap(find.text(l.onboardingAgeDecline));
    await t.pump();

    expect(find.text(l.onboardingAgeDeclinedTitle), findsOneWidget);
    expect(find.text(l.onboardingAgeDeclinedBody), findsOneWidget);
    expect(find.byType(Checkbox), findsNothing,
        reason: 'a decline is not looped back into the same question');
    expect(api.startCalls, isEmpty);

    await t.tap(find.text(l.onboardingAgeDeclinedBack));
    await t.pump();
    expect(find.text(l.onboardingAgeBody), findsOneWidget);
    expect(t.widget<Checkbox>(find.byType(Checkbox)).value, isFalse);
  });

  test('the notifier itself refuses to start without the confirmation',
      () async {
    final api = _RecordingApi();
    final notifier = OnboardingNotifier(api);

    await notifier.start(locale: 'en', timezone: 'UTC');

    expect(api.startCalls, isEmpty);
    expect(notifier.state.phase, OnboardingPhase.notStarted);
    expect(notifier.state.sessionId, isNull,
        reason: 'no session means no readback and no completion');
  });

  test('copy names AMI and never "the AI"', () async {
    final l = await AppLocalizations.delegate.load(const Locale('en'));
    final copy = [
      l.onboardingAgeTitle,
      l.onboardingAgeBody,
      l.onboardingAgeCheckbox,
      l.onboardingAgeDeclinedTitle,
      l.onboardingAgeDeclinedBody,
    ].join(' ');
    expect(copy, contains('AMI'));
    expect(copy.toLowerCase(), isNot(contains('the ai')));
  });
}
