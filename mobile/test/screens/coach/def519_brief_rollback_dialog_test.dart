/// DEF519 — ROLLBACK TO THIS > ROLLBACK must close its confirm dialog and send
/// the request.
///
/// Field report (0.1.0+122, Android, AMI-DL-11): confirming the rollback closed
/// the history page, left the dialog frozen over the Brief screen, and never
/// sent POST /v1/brief/rollback. The dialog's buttons popped with the history
/// page's context. The app runs every tab in its own nested Navigator
/// (home_shell.dart) while showDialog pushes onto the root one, so that pop hit
/// the tab navigator and removed the page under the dialog instead of the
/// dialog. The harness reproduces the shape: history pushed inside a nested
/// Navigator under MaterialApp.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/agent.dart';
import 'package:ami_trade/models/brief.dart';
import 'package:ami_trade/screens/agent/brief_history_screen.dart';
import 'package:ami_trade/services/api/api_client.dart';
import 'package:ami_trade/state/brief_providers.dart';
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
  _Api({this.failRollback = false}) : super(baseUrl: 'test://localhost');

  final bool failRollback;
  final rollbackCalls = <int>[];
  int active = 2;

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
    rollbackCalls.add(toVersion);
    if (failRollback) throw Exception('boom');
    active = toVersion;
    return _v(toVersion);
  }
}

class _Notifier extends BriefNotifier {
  _Notifier(super.ref, super.agentId);
  @override
  Future<void> openSession({String locale = 'en'}) async {}
}

Future<void> _pump(WidgetTester t, _Api api) async {
  SharedPreferences.setMockInitialValues({});
  t.view.physicalSize = const Size(390, 844);
  t.view.devicePixelRatio = 1.0;
  addTearDown(t.view.reset);
  final agent = agentById('fundamentals_analyst');
  await t.pumpWidget(ProviderScope(
    overrides: [
      apiClientProvider.overrideWithValue(api),
      briefNotifierProvider.overrideWith((ref, id) => _Notifier(ref, id)),
    ],
    child: MaterialApp(
      localizationsDelegates: AppLocalizations.localizationsDelegates,
      supportedLocales: AppLocalizations.supportedLocales,
      home: Scaffold(
        body: Navigator(
          onGenerateRoute: (_) => MaterialPageRoute<void>(
            builder: (ctx) => Scaffold(
              body: Center(
                child: ElevatedButton(
                  onPressed: () => Navigator.of(ctx).push(MaterialPageRoute<void>(
                    builder: (_) => BriefHistoryScreen(agent: agent),
                  )),
                  child: const Text('open history'),
                ),
              ),
            ),
          ),
        ),
      ),
    ),
  ));
  await t.tap(find.text('open history'));
  await t.pumpAndSettle();
}

Future<void> _confirmRollbackOnV1(WidgetTester t) async {
  await t.tap(find.text('ROLLBACK TO THIS'));
  await t.pumpAndSettle();
  expect(find.byType(AlertDialog), findsOneWidget);
  await t.tap(find.widgetWithText(ElevatedButton, 'ROLLBACK'));
  await t.pumpAndSettle();
}

void main() {
  testWidgets('confirming closes the dialog, calls the API with v1, activates v1',
      (t) async {
    final api = _Api();
    await _pump(t, api);
    expect(find.text('ACTIVE'), findsOneWidget);

    await _confirmRollbackOnV1(t);

    expect(find.byType(AlertDialog), findsNothing,
        reason: 'DEF519: the confirm dialog stayed on screen');
    expect(api.rollbackCalls, [1],
        reason: 'DEF519: the rollback request was never sent');
    expect(find.byType(BriefHistoryScreen), findsOneWidget,
        reason: 'DEF519: confirming must not pop the history page');
    expect(api.active, 1);
    expect(find.text('ROLLBACK TO THIS'), findsOneWidget,
        reason: 'v2 is now the rollback target, v1 the active one');
  });

  testWidgets('a failed rollback closes the dialog and shows an error',
      (t) async {
    final api = _Api(failRollback: true);
    await _pump(t, api);

    await _confirmRollbackOnV1(t);

    expect(find.byType(AlertDialog), findsNothing);
    expect(api.rollbackCalls, [1]);
    expect(find.byType(SnackBar), findsOneWidget,
        reason: 'a failed rollback must be visible on the history page');
  });

  testWidgets('cancel closes only the dialog and sends nothing', (t) async {
    final api = _Api();
    await _pump(t, api);

    await t.tap(find.text('ROLLBACK TO THIS'));
    await t.pumpAndSettle();
    await t.tap(find.widgetWithText(TextButton, 'CANCEL'));
    await t.pumpAndSettle();

    expect(find.byType(AlertDialog), findsNothing);
    expect(find.byType(BriefHistoryScreen), findsOneWidget);
    expect(api.rollbackCalls, isEmpty);
  });
}
