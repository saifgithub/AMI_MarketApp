/// DEF523 — after a Brief rollback the chat's first bubble must name the now
/// active version.
///
/// Field report (AMI-DL-14): rolled back v2 -> v1, went back to the Brief
/// screen, and the first bubble still said "You're currently briefing me at
/// version 2". The server builds that opener once, at `/v1/brief/start`; the
/// client kept the session it opened before the rollback. The fix starts a
/// fresh session (free: no credit, no edit) after a successful rollback and
/// swaps only the opener, so a chat already in progress is kept.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/agent.dart';
import 'package:ami_trade/models/brief.dart';
import 'package:ami_trade/screens/agent/brief_screen.dart';
import 'package:ami_trade/services/api/api_client.dart';
import 'package:ami_trade/state/onboarding_providers.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

UserOverlay _v(int n) => UserOverlay(
      id: 'o$n',
      userId: 'u1',
      agentId: 'fundamentals_analyst',
      version: n,
      content: 'overlay body $n',
      plainEnglish: 'Version $n summary',
      createdAt: DateTime.utc(2026, 11, 21, 6, n),
    );

class _Api extends ApiClient {
  _Api({this.failStart = false}) : super(baseUrl: 'test://localhost');

  int active = 2;
  bool failStart;
  final startCalls = <int>[];

  @override
  Future<BriefStartResponse> startBrief({
    required String agentId,
    required String userId,
    String mode = 'from_scratch',
    String locale = 'en',
  }) async {
    startCalls.add(active);
    if (failStart && startCalls.length > 1) throw Exception('start down');
    return BriefStartResponse(
      session: BriefSession(
        id: 's${startCalls.length}',
        userId: userId,
        agentId: agentId,
        mode: mode,
        locale: locale,
        baseOverlayVersion: active,
      ),
      currentOverlay: _v(active),
      openingMessage:
          "I'm Fundamentals. You're currently briefing me at version $active. "
          'What do you want to change?',
    );
  }

  @override
  Future<BriefHistory> briefHistory({
    required String userId,
    required String agentId,
    String plan = 'trial_trader',
  }) async =>
      BriefHistory(
        agentId: agentId,
        userId: userId,
        versions: [_v(1), _v(2)],
        activeVersion: active,
        editCount: 2,
        editsRemaining: 1,
      );

  @override
  Future<UserOverlay> rollbackBrief({
    required String userId,
    required String agentId,
    required int toVersion,
  }) async {
    active = toVersion;
    return _v(toVersion);
  }
}

Future<void> _rollbackToV1(WidgetTester t, _Api api,
    {bool goBack = true}) async {
  SharedPreferences.setMockInitialValues({'ami.device_user_id': 'u1'});
  t.view.physicalSize = const Size(390, 844);
  t.view.devicePixelRatio = 1.0;
  addTearDown(t.view.reset);
  await t.pumpWidget(ProviderScope(
    overrides: [apiClientProvider.overrideWithValue(api)],
    child: MaterialApp(
      localizationsDelegates: AppLocalizations.localizationsDelegates,
      supportedLocales: AppLocalizations.supportedLocales,
      home: BriefScreen(agent: agentById('fundamentals_analyst')),
    ),
  ));
  await t.pumpAndSettle();
  expect(find.textContaining('currently briefing me at version 2'),
      findsOneWidget,
      reason: 'precondition: the opener names the version active at start');

  await t.tap(find.byIcon(Icons.history));
  await t.pumpAndSettle();
  await t.tap(find.text('ROLLBACK TO THIS'));
  await t.pumpAndSettle();
  await t.tap(find.widgetWithText(ElevatedButton, 'ROLLBACK'));
  await t.pumpAndSettle();
  if (!goBack) return;
  await t.pageBack();
  await t.pumpAndSettle();
  // The saved-overlay toast on the Brief screen holds a 3 s timer.
  await t.pump(const Duration(seconds: 4));
}

void main() {
  testWidgets('after rolling back v2 -> v1 the first bubble says version 1',
      (t) async {
    final api = _Api();
    await _rollbackToV1(t, api);

    expect(find.textContaining('currently briefing me at version 1'),
        findsOneWidget);
    expect(find.textContaining('currently briefing me at version 2'),
        findsNothing,
        reason: 'DEF523: the opener named the abandoned version');
    expect(api.startCalls, [2, 1], reason: 'one fresh (free) session start');
  });

  testWidgets('a failed opener refresh is shown on the history page',
      (t) async {
    final api = _Api(failStart: true);
    await _rollbackToV1(t, api, goBack: false);

    expect(api.startCalls.length, 2);
    expect(find.byType(SnackBar), findsOneWidget,
        reason: 'a stale opener must not go unannounced');
    expect(find.textContaining("Couldn't refresh the briefing"),
        findsOneWidget);
    await t.pageBack();
    await t.pump(const Duration(seconds: 4));
  });
}
