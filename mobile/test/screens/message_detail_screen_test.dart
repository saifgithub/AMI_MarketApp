/// CR102 — the message detail: read-marking fires once and only when
/// unread (acceptance #3), and a reply's draft survives failure (CR040 —
/// the user's words are not discarded on an error).
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/inbox_message.dart';
import 'package:ami_trade/screens/inbox/message_detail_screen.dart';
import 'package:ami_trade/services/api/api_client.dart';
import 'package:ami_trade/state/inbox_providers.dart';
import 'package:ami_trade/state/onboarding_providers.dart';
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

class _InboxApi extends ApiClient {
  _InboxApi({this.failReply = false}) : super(baseUrl: 'test://localhost');

  final bool failReply;
  final readCalls = <String>[];
  final replyBodies = <String>[];

  @override
  Future<void> markMessageRead(String messageId) async {
    readCalls.add(messageId);
  }

  @override
  Future<InboxReply> replyToMessage({
    required String messageId,
    required String body,
  }) async {
    if (failReply) {
      throw DioException(
        requestOptions: RequestOptions(path: '/v1/messages/$messageId/reply'),
        type: DioExceptionType.connectionError,
      );
    }
    replyBodies.add(body);
    return InboxReply(
      id: 'r-new',
      userId: 'u-1',
      replyToId: messageId,
      body: body,
      createdAt: DateTime.utc(2026, 8, 18, 12),
    );
  }
}

InboxMessage _parent({DateTime? readAt}) => InboxMessage(
      id: 'msg-1',
      direction: 'out',
      title: 'A broadcast',
      body: 'The full body.',
      priority: 'normal',
      createdAt: DateTime.utc(2026, 8, 18, 10),
      readAt: readAt,
    );

Future<_InboxApi> _pump(
  WidgetTester tester, {
  DateTime? readAt,
  bool failReply = false,
  List<InboxMessage> extraRows = const [],
}) async {
  tester.view.physicalSize = const Size(390, 844);
  tester.view.devicePixelRatio = 1.0;
  addTearDown(tester.view.reset);

  final api = _InboxApi(failReply: failReply);
  await tester.pumpWidget(ProviderScope(
    overrides: [
      apiClientProvider.overrideWithValue(api),
      inboxProvider.overrideWith(
          (ref) async => [_parent(readAt: readAt), ...extraRows]),
    ],
    child: const MaterialApp(
      localizationsDelegates: AppLocalizations.localizationsDelegates,
      supportedLocales: AppLocalizations.supportedLocales,
      home: MessageDetailScreen(messageId: 'msg-1'),
    ),
  ));
  await tester.pump();
  await tester.pump(const Duration(milliseconds: 300));
  return api;
}

void main() {
  testWidgets('an unread message is marked read exactly once on open',
      (tester) async {
    final api = await _pump(tester);
    expect(find.text('A broadcast'), findsOneWidget);
    expect(find.text('The full body.'), findsOneWidget);
    expect(api.readCalls, ['msg-1']);
  });

  testWidgets('an already-read message is NOT re-marked', (tester) async {
    final api = await _pump(tester, readAt: DateTime.utc(2026, 8, 18, 11));
    expect(api.readCalls, isEmpty);
  });

  testWidgets('replies to this message thread below it, oldest-first',
      (tester) async {
    await _pump(tester, extraRows: [
      InboxMessage(
        id: 'r-2',
        direction: 'in',
        body: 'second reply',
        replyToId: 'msg-1',
        createdAt: DateTime.utc(2026, 8, 18, 12),
      ),
      InboxMessage(
        id: 'r-1',
        direction: 'in',
        body: 'first reply',
        replyToId: 'msg-1',
        createdAt: DateTime.utc(2026, 8, 18, 11),
      ),
      // Another thread's reply must not bleed in.
      InboxMessage(
        id: 'r-x',
        direction: 'in',
        body: 'stranger',
        replyToId: 'msg-9',
        createdAt: DateTime.utc(2026, 8, 18, 11),
      ),
    ]);

    expect(find.text('first reply'), findsOneWidget);
    expect(find.text('second reply'), findsOneWidget);
    expect(find.text('stranger'), findsNothing);
    final first = tester.getTopLeft(find.text('first reply'));
    final second = tester.getTopLeft(find.text('second reply'));
    expect(first.dy, lessThan(second.dy));
  });

  testWidgets('a successful reply sends the typed body and clears the field',
      (tester) async {
    final api = await _pump(tester);

    await tester.enterText(find.byType(TextField), 'thanks, works now');
    await tester.tap(find.text('SEND'));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 300));

    expect(api.replyBodies, ['thanks, works now']);
    expect(tester.widget<TextField>(find.byType(TextField)).controller!.text,
        isEmpty);

    // Drain the success toast's overlay timers.
    await tester.pump(const Duration(seconds: 5));
  });

  testWidgets('a failed reply keeps the draft in the field', (tester) async {
    final api = await _pump(tester, failReply: true);

    await tester.enterText(find.byType(TextField), 'do not lose me');
    await tester.tap(find.text('SEND'));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 300));

    expect(api.replyBodies, isEmpty);
    expect(tester.widget<TextField>(find.byType(TextField)).controller!.text,
        'do not lose me');

    // Drain the error toast's overlay timers.
    await tester.pump(const Duration(seconds: 5));
  });
}
