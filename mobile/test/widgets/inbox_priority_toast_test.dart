/// CR102 acceptance #5 — a priority=high broadcast toasts on the next cold
/// start and only that one.
///
/// Once-only is server-side: `toasted_at` is stamped (via the ApiClient)
/// as the toast shows, and a row that already carries the stamp — or was
/// already read — never queues. The `_seen` guard holds the same line
/// within a session across provider rebuilds.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/inbox_message.dart';
import 'package:ami_trade/screens/feedback/bug_resolution_toasts.dart';
import 'package:ami_trade/services/api/api_client.dart';
import 'package:ami_trade/state/feedback_providers.dart';
import 'package:ami_trade/state/inbox_providers.dart';
import 'package:ami_trade/state/onboarding_providers.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

class _ToastApi extends ApiClient {
  _ToastApi() : super(baseUrl: 'test://localhost');

  final toastedCalls = <String>[];

  @override
  Future<void> markMessageToasted(String messageId) async {
    toastedCalls.add(messageId);
  }
}

InboxMessage _message(
  String id, {
  String priority = 'high',
  String direction = 'out',
  DateTime? readAt,
  DateTime? toastedAt,
}) =>
    InboxMessage(
      id: id,
      direction: direction,
      title: 'Broadcast $id',
      body: 'body first line\nsecond',
      priority: priority,
      createdAt: DateTime.utc(2026, 8, 18, 10),
      readAt: readAt,
      toastedAt: toastedAt,
    );

Widget _harness(_ToastApi api, List<InboxMessage> messages) {
  return ProviderScope(
    overrides: [
      apiClientProvider.overrideWithValue(api),
      feedbackUpdatesProvider.overrideWith((ref) async => const []),
      inboxProvider.overrideWith((ref) async => messages),
    ],
    child: const MaterialApp(
      localizationsDelegates: AppLocalizations.localizationsDelegates,
      supportedLocales: AppLocalizations.supportedLocales,
      home: Scaffold(
        body: BugResolutionToasts(child: SizedBox.expand()),
      ),
    ),
  );
}

/// Pump past the settle delay and the toast's slide-in.
Future<void> _drainOne(WidgetTester t) async {
  await t.pump(const Duration(milliseconds: 1500));
  await t.pump(const Duration(milliseconds: 400));
}

void main() {
  testWidgets('a high-priority unread broadcast toasts and is stamped',
      (t) async {
    final api = _ToastApi();
    await t.pumpWidget(_harness(api, [_message('m1')]));
    await t.pump();
    await _drainOne(t);

    expect(find.textContaining('Broadcast m1'), findsOneWidget);
    expect(api.toastedCalls, ['m1']);
    await t.pump(const Duration(seconds: 8));
  });

  testWidgets('an already-toasted row never re-toasts (server-side once-only)',
      (t) async {
    final api = _ToastApi();
    await t.pumpWidget(_harness(
        api, [_message('m1', toastedAt: DateTime.utc(2026, 8, 18, 11))]));
    await t.pump();
    await _drainOne(t);

    expect(find.textContaining('Broadcast m1'), findsNothing);
    expect(api.toastedCalls, isEmpty);
  });

  testWidgets('an already-read row needs no herald', (t) async {
    final api = _ToastApi();
    await t.pumpWidget(
        _harness(api, [_message('m1', readAt: DateTime.utc(2026, 8, 18))]));
    await t.pump();
    await _drainOne(t);

    expect(find.textContaining('Broadcast m1'), findsNothing);
    expect(api.toastedCalls, isEmpty);
  });

  testWidgets('normal, unknown-priority and reply rows never toast',
      (t) async {
    final api = _ToastApi();
    await t.pumpWidget(_harness(api, [
      _message('m1', priority: 'normal'),
      _message('m2', priority: 'shouting'),
      _message('m3', direction: 'in'),
    ]));
    await t.pump();
    await _drainOne(t);

    expect(find.textContaining('Broadcast'), findsNothing);
    expect(api.toastedCalls, isEmpty);
    expect(t.takeException(), isNull);
  });

  testWidgets('a provider rebuild does not re-queue a shown message',
      (t) async {
    final api = _ToastApi();
    await t.pumpWidget(_harness(api, [_message('m1')]));
    await t.pump();
    await _drainOne(t);
    expect(find.textContaining('Broadcast m1'), findsOneWidget);

    // Rebuild while the toast is still on screen — without the _seen guard
    // this enqueues a duplicate.
    await t.pumpWidget(_harness(api, [_message('m1')]));
    await t.pump();
    await _drainOne(t);

    expect(find.textContaining('Broadcast m1'), findsOneWidget);
    expect(api.toastedCalls, ['m1']);
    await t.pump(const Duration(seconds: 12));
  });
}
