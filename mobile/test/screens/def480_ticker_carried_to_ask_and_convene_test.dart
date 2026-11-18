/// DEF480 — ASK / CONVENE from the watchlist sheet must carry the ticker the
/// user was looking at.
///
/// Before: ASK opened a bare 1-on-1 with the Technical Strategist and CONVENE
/// opened an empty ticker picker, so the user retyped a symbol they had just
/// tapped. The OPEN TRADE TICKET action on the same sheet already pre-filled.
/// (Ticker detail's ASK takes the same `askAboutTickerMessage` path.)
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/one_on_one.dart';
import 'package:ami_trade/screens/agent/one_on_one_screen.dart';
import 'package:ami_trade/screens/room/convene_sheet.dart';
import 'package:ami_trade/services/api/api_client.dart';
import 'package:ami_trade/state/onboarding_providers.dart';
import 'package:ami_trade/widgets/watchlist_sheet.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

class _DeadApi extends ApiClient {
  _DeadApi() : super(baseUrl: 'test://localhost');

  @override
  Future<OneOnOneSession> startOneOnOne({
    required String agentId,
    String locale = 'en',
  }) async {
    throw Exception('backend down');
  }
}

Future<void> _openSheet(WidgetTester tester) async {
  tester.view.physicalSize = const Size(390, 844);
  tester.view.devicePixelRatio = 1.0;
  addTearDown(tester.view.reset);
  await tester.pumpWidget(ProviderScope(
    overrides: [apiClientProvider.overrideWithValue(_DeadApi())],
    child: MaterialApp(
      localizationsDelegates: AppLocalizations.localizationsDelegates,
      supportedLocales: AppLocalizations.supportedLocales,
      home: Scaffold(
        body: Consumer(
          builder: (context, ref, _) => ElevatedButton(
            onPressed: () => showWatchlistSheet(context, ref, ticker: 'GOOGL'),
            child: const Text('open'),
          ),
        ),
      ),
    ),
  ));
  await tester.tap(find.text('open'));
  await tester.pumpAndSettle();
}

void main() {
  testWidgets('watchlist ASK opens the 1-on-1 about the tapped ticker',
      (tester) async {
    await _openSheet(tester);
    await tester.tap(find.byIcon(Icons.chat_bubble_outline));
    await tester.pumpAndSettle();

    final screen = tester.widget<OneOnOneScreen>(find.byType(OneOnOneScreen));
    expect(screen.initialMessage, isNotNull);
    expect(screen.initialMessage, contains('GOOGL'));
  });

  testWidgets('watchlist CONVENE opens the picker pre-filled with the ticker',
      (tester) async {
    await _openSheet(tester);
    await tester.tap(find.byIcon(Icons.groups_outlined));
    await tester.pumpAndSettle();

    expect(find.byType(ConveneSheet), findsOneWidget);
    final field = tester.widget<TextField>(find.byType(TextField));
    expect(field.controller!.text, 'GOOGL');
  });

  testWidgets('a bare ConveneSheet still opens empty', (tester) async {
    await tester.pumpWidget(ProviderScope(
      overrides: [apiClientProvider.overrideWithValue(_DeadApi())],
      child: MaterialApp(
        localizationsDelegates: AppLocalizations.localizationsDelegates,
        supportedLocales: AppLocalizations.supportedLocales,
        home: Scaffold(
          body: Builder(
            builder: (context) => ElevatedButton(
              onPressed: () => ConveneSheet.show(context),
              child: const Text('open'),
            ),
          ),
        ),
      ),
    ));
    await tester.tap(find.text('open'));
    await tester.pumpAndSettle();
    final field = tester.widget<TextField>(find.byType(TextField));
    expect(field.controller!.text, isEmpty);
  });
}
