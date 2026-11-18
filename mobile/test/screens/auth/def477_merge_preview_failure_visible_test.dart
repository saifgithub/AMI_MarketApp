// DEF477 — a failed merge preview was swallowed silently, so an anonymous
// user's earlier portfolio/journal was skipped with no word and no retry (and
// the code cited a Settings entry that does not exist). It must now say so,
// offer RETRY, and show the merge sheet when the retry succeeds; SKIP must
// continue without it.

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/merge.dart';
import 'package:ami_trade/screens/auth/merge_sheet.dart';
import 'package:ami_trade/services/api/api_client.dart';
import 'package:ami_trade/state/onboarding_providers.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

class _FlakyMergeApi extends ApiClient {
  _FlakyMergeApi({required this.failures}) : super(baseUrl: 'test://localhost');

  int failures;
  int calls = 0;

  @override
  Future<MergePreview> previewMerge({required String fromUserId}) async {
    calls++;
    if (failures > 0) {
      failures--;
      throw Exception('network blip');
    }
    return MergePreview(
      fromUserId: fromUserId,
      toUserId: 'u2',
      journalEntries: 3,
      simTrades: 0,
      simHoldings: 0,
      simWatchlists: 0,
      lessonsProgress: 0,
      agentActivations: 0,
      oneOnOneMessages: 0,
      roomRuns: 0,
      userOverlays: 0,
      bugReports: 0,
      mandateConflict: false,
    );
  }
}

Future<void> _open(WidgetTester tester, ApiClient api) async {
  await tester.pumpWidget(ProviderScope(
    overrides: [apiClientProvider.overrideWithValue(api)],
    child: MaterialApp(
      localizationsDelegates: AppLocalizations.localizationsDelegates,
      supportedLocales: AppLocalizations.supportedLocales,
      home: Scaffold(
        body: Consumer(
          builder: (context, ref, _) => ElevatedButton(
            onPressed: () =>
                showMergeSheet(context, ref, adoptedFromUserId: 'orphan'),
            child: const Text('go'),
          ),
        ),
      ),
    ),
  ));
  await tester.tap(find.text('go'));
  await tester.pumpAndSettle();
}

void main() {
  testWidgets('a failed preview is announced, not swallowed', (tester) async {
    final api = _FlakyMergeApi(failures: 99);
    await _open(tester, api);

    expect(find.text("COULDN'T CHECK YOUR EARLIER DATA"), findsOneWidget);
    expect(find.text('RETRY'), findsOneWidget);
    expect(find.text('SKIP'), findsOneWidget);
  });

  testWidgets('RETRY re-requests the preview and opens the merge sheet',
      (tester) async {
    final api = _FlakyMergeApi(failures: 1);
    await _open(tester, api);

    await tester.tap(find.text('RETRY'));
    await tester.pumpAndSettle();

    expect(api.calls, 2);
    expect(find.text("COULDN'T CHECK YOUR EARLIER DATA"), findsNothing);
    final l = await AppLocalizations.delegate.load(const Locale('en'));
    expect(find.text(l.mergeSheetTitle), findsOneWidget);
  });

  testWidgets('SKIP continues without the sheet and asks once', (tester) async {
    final api = _FlakyMergeApi(failures: 99);
    await _open(tester, api);

    await tester.tap(find.text('SKIP'));
    await tester.pumpAndSettle();

    expect(api.calls, 1);
    expect(find.byType(AlertDialog), findsNothing);
  });
}
