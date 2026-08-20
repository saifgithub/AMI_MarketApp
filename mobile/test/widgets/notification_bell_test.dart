/// CR135 — the YOU-header bell: the badge asserts the server's unread
/// count and nothing else — absent at zero, absent on error (a badge has
/// nothing honest to claim when the count is unknown), capped at 9+.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/screens/notifications/notification_bell.dart';
import 'package:ami_trade/state/notification_centre_providers.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

Future<void> _pump(WidgetTester tester, AsyncValue<int> count) async {
  await tester.pumpWidget(ProviderScope(
    overrides: [
      notificationUnreadCountProvider.overrideWith(
        (ref) => count.when(
          data: Future.value,
          error: (e, st) => Future<int>.error(e, st),
          loading: () => Future.value(0),
        ),
      ),
    ],
    child: const MaterialApp(
      localizationsDelegates: AppLocalizations.localizationsDelegates,
      supportedLocales: AppLocalizations.supportedLocales,
      home: Scaffold(body: NotificationBell()),
    ),
  ));
  await tester.pump();
  await tester.pump(const Duration(milliseconds: 100));
}

void main() {
  testWidgets('badge shows the server count', (tester) async {
    await _pump(tester, const AsyncValue.data(3));
    expect(find.text('3'), findsOneWidget);
  });

  testWidgets('badge is absent at zero', (tester) async {
    await _pump(tester, const AsyncValue.data(0));
    expect(find.text('0'), findsNothing);
  });

  testWidgets('badge caps at 9+', (tester) async {
    await _pump(tester, const AsyncValue.data(12));
    expect(find.text('9+'), findsOneWidget);
  });

  testWidgets('badge is absent on error rather than guessing', (tester) async {
    await _pump(tester,
        AsyncValue.error(Exception('boom'), StackTrace.current));
    expect(find.byType(Text), findsNothing);
    // The bell itself still renders and stays tappable.
    expect(find.byIcon(Icons.notifications_outlined), findsOneWidget);
  });
}
