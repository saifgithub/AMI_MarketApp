/// CR102 — the inbox list: broadcasts render, and error ≠ empty (CR040,
/// acceptance #8).
///
/// The distinctness assertions are the point of this file: "couldn't load"
/// carries a retry button and its own copy; "no messages" carries neither.
/// A silently-empty inbox on failure is the DEF038/DEF063 dark-feature
/// class the CR doc names.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/inbox_message.dart';
import 'package:ami_trade/screens/inbox/inbox_screen.dart';
import 'package:ami_trade/state/inbox_providers.dart';
import 'package:ami_trade/widgets/hex/accent_card.dart';
import 'package:ami_trade/widgets/hex/hex_button.dart';
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

InboxMessage _broadcast(
  String id, {
  String? title,
  String priority = 'normal',
  DateTime? readAt,
}) =>
    InboxMessage(
      id: id,
      direction: 'out',
      title: title ?? 'Message $id',
      body: 'Body of $id.\nSecond line.',
      priority: priority,
      createdAt: DateTime.utc(2026, 8, 18, 10),
      readAt: readAt,
    );

InboxMessage _reply(String id, String parentId) => InboxMessage(
      id: id,
      direction: 'in',
      body: 'reply body',
      replyToId: parentId,
      createdAt: DateTime.utc(2026, 8, 18, 11),
    );

Future<void> _pump(
  WidgetTester tester, {
  List<InboxMessage>? rows,
  Object? error,
}) async {
  tester.view.physicalSize = const Size(390, 844);
  tester.view.devicePixelRatio = 1.0;
  addTearDown(tester.view.reset);

  await tester.pumpWidget(ProviderScope(
    overrides: [
      inboxProvider.overrideWith((ref) {
        if (error != null) throw error;
        return rows ?? const [];
      }),
    ],
    child: const MaterialApp(
      localizationsDelegates: AppLocalizations.localizationsDelegates,
      supportedLocales: AppLocalizations.supportedLocales,
      home: InboxScreen(),
    ),
  ));
  await tester.pump();
  await tester.pump(const Duration(milliseconds: 300));
}

void main() {
  testWidgets('broadcasts render as cards; replies do not', (tester) async {
    await _pump(tester, rows: [
      _broadcast('m1', title: 'First broadcast'),
      _broadcast('m2', title: 'Second broadcast', readAt: DateTime.utc(2026)),
      _reply('r1', 'm1'),
    ]);

    expect(find.text('First broadcast'), findsOneWidget);
    expect(find.text('Second broadcast'), findsOneWidget);
    expect(find.byType(AccentCard), findsNWidgets(2),
        reason: 'the reply row is thread content, not a top-level card');
    expect(find.text('reply body'), findsNothing);
  });

  testWidgets('the unread dot marks only unread broadcasts', (tester) async {
    await _pump(tester, rows: [
      _broadcast('m1', title: 'Unread one'),
      _broadcast('m2', title: 'Read one', readAt: DateTime.utc(2026)),
    ]);

    // The 8px cyan dot renders only inside the unread card's row.
    final dots = tester
        .widgetList<Container>(find.descendant(
          of: find.byType(AccentCard),
          matching: find.byType(Container),
        ))
        .where((c) {
      final d = c.decoration;
      return d is BoxDecoration &&
          d.shape == BoxShape.circle &&
          c.constraints?.maxWidth == 8;
    });
    expect(dots.length, 1);
  });

  testWidgets('a priority=high broadcast carries the PRIORITY chip',
      (tester) async {
    await _pump(tester, rows: [
      _broadcast('m1', title: 'Urgent', priority: 'high'),
      _broadcast('m2', title: 'Calm'),
    ]);
    expect(find.text('PRIORITY'), findsOneWidget);
  });

  testWidgets('an unknown priority renders as a normal row (DEF210)',
      (tester) async {
    await _pump(tester,
        rows: [_broadcast('m1', title: 'Odd', priority: 'shouting')]);
    expect(find.text('Odd'), findsOneWidget);
    expect(find.text('PRIORITY'), findsNothing);
    expect(tester.takeException(), isNull);
  });

  testWidgets('empty shows inboxEmpty and NO retry button', (tester) async {
    await _pump(tester, rows: const []);

    expect(find.text('No messages yet.'), findsOneWidget);
    expect(find.text('TRY AGAIN'), findsNothing);
    expect(find.byType(HexButton), findsNothing);
    expect(find.text("Couldn't load your messages."), findsNothing);
  });

  testWidgets('error shows inboxError WITH retry — distinct from empty',
      (tester) async {
    await _pump(
      tester,
      error: DioException(
        requestOptions: RequestOptions(path: '/v1/messages'),
        type: DioExceptionType.connectionError,
      ),
    );

    expect(find.text("Couldn't load your messages."), findsOneWidget);
    expect(find.text('TRY AGAIN'), findsOneWidget);
    expect(find.text('No messages yet.'), findsNothing,
        reason: 'CR040 acceptance #8: error must never look like empty');
  });

  testWidgets('retry invalidates the provider and can recover',
      (tester) async {
    var calls = 0;
    tester.view.physicalSize = const Size(390, 844);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.reset);

    await tester.pumpWidget(ProviderScope(
      overrides: [
        inboxProvider.overrideWith((ref) {
          calls += 1;
          if (calls == 1) {
            throw DioException(
              requestOptions: RequestOptions(path: '/v1/messages'),
              type: DioExceptionType.connectionError,
            );
          }
          return [_broadcast('m1', title: 'After retry')];
        }),
      ],
      child: const MaterialApp(
        localizationsDelegates: AppLocalizations.localizationsDelegates,
        supportedLocales: AppLocalizations.supportedLocales,
        home: InboxScreen(),
      ),
    ));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 300));
    expect(find.text('TRY AGAIN'), findsOneWidget);

    await tester.tap(find.text('TRY AGAIN'));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 300));

    expect(calls, 2);
    expect(find.text('After retry'), findsOneWidget);
    expect(find.text('TRY AGAIN'), findsNothing);
  });
}
