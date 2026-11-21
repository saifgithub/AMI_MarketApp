// DEF526 - the Inbox error state showed no "Ref: xxxxxxxx" on device run
// AMI-DL-17 although Alpha minted request ids for both failing GET
// /v1/messages calls. This drives the REAL ApiClient (fake Dio adapter
// answering the backend's exact 503 shape) through the REAL inbox provider and
// screen, so the whole chain from interceptor to rendered line is covered.

import 'dart:convert';
import 'dart:typed_data';

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/auth.dart';
import 'package:ami_trade/screens/inbox/inbox_screen.dart';
import 'package:ami_trade/services/api/api_client.dart';
import 'package:ami_trade/services/api/trace_ids.dart';
import 'package:ami_trade/state/auth_providers.dart';
import 'package:ami_trade/state/onboarding_providers.dart';
import 'package:ami_trade/widgets/hex/hex_button.dart';
import 'package:ami_trade/widgets/trace_ref_line.dart';
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

const _id1 = 'aaaa1111-0000-4000-8000-000000000001';
const _id2 = 'bbbb2222-0000-4000-8000-000000000002';

class _Fault503Adapter implements HttpClientAdapter {
  _Fault503Adapter(this.ids);
  final List<String> ids;
  int calls = 0;

  @override
  Future<ResponseBody> fetch(RequestOptions options,
      Stream<Uint8List>? requestStream, Future<void>? cancelFuture) async {
    final id = ids[calls < ids.length ? calls : ids.length - 1];
    calls++;
    return ResponseBody.fromString(
      jsonEncode({
        'detail': 'uat fault injected',
        'request_id': id,
      }),
      503,
      headers: {
        Headers.contentTypeHeader: ['application/json'],
        'x-request-id': [id],
      },
    );
  }

  @override
  void close({bool force = false}) {}
}

class _SignedInAuth extends AuthNotifier {
  _SignedInAuth(super.ref) {
    state = AuthState(
      user: AuthUser(
        id: 'u1',
        email: 'trader@example.com',
        isAnonymous: false,
        createdAt: DateTime.utc(2026, 1, 1),
      ),
      token: 'tok',
    );
  }

  @override
  Future<void> bootstrap() async {}
}

Future<_Fault503Adapter> _pump(WidgetTester tester) async {
  tester.view.physicalSize = const Size(390, 844);
  tester.view.devicePixelRatio = 1.0;
  addTearDown(tester.view.reset);
  final adapter = _Fault503Adapter([_id1, _id2]);
  final api = ApiClient(baseUrl: 'http://fake', dioAdapter: adapter);
  await tester.pumpWidget(ProviderScope(
    overrides: [
      authNotifierProvider.overrideWith((ref) => _SignedInAuth(ref)),
      apiClientProvider.overrideWithValue(api),
    ],
    child: const MaterialApp(
      localizationsDelegates: AppLocalizations.localizationsDelegates,
      supportedLocales: AppLocalizations.supportedLocales,
      home: InboxScreen(),
    ),
  ));
  await tester.pump();
  await tester.pump(const Duration(milliseconds: 300));
  return adapter;
}

void main() {
  setUp(TraceIdStore.instance.clear);

  testWidgets('a 503 on GET /v1/messages shows the Ref, and the NEW one after retry',
      (tester) async {
    final adapter = await _pump(tester);
    expect(adapter.calls, 1);
    expect(find.text("Couldn't load your messages."), findsOneWidget);
    expect(find.text('Ref: aaaa1111'), findsOneWidget);

    await tester.tap(find.byType(HexButton));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 300));

    expect(adapter.calls, 2);
    expect(find.text('Ref: bbbb2222'), findsOneWidget);
    expect(find.text('Ref: aaaa1111'), findsNothing);
  });

  testWidgets(
      'every TraceRefLine.recent() follows the store after its first build',
      (tester) async {
    final store = TraceIdStore();
    await tester.pumpWidget(MaterialApp(
      localizationsDelegates: AppLocalizations.localizationsDelegates,
      supportedLocales: AppLocalizations.supportedLocales,
      home: Scaffold(body: TraceRefLine.recent(store: store)),
    ));
    expect(find.textContaining('Ref:'), findsNothing);

    store.record(_id1);
    await tester.pump();
    expect(find.text('Ref: aaaa1111'), findsOneWidget);

    store.record(_id2);
    await tester.pump();
    expect(find.text('Ref: bbbb2222'), findsOneWidget);

    store.recordNoResponse();
    await tester.pump();
    expect(find.textContaining('Ref:'), findsNothing,
        reason: 'a later failure with no response must not keep an old id');
  });

  testWidgets(
      'a failure cached for minutes before the screen opened still shows its Ref',
      (tester) async {
    var now = DateTime(2026, 11, 21, 10, 19, 57);
    final store = TraceIdStore(now: () => now)..record(_id1);
    now = now.add(const Duration(minutes: 3));
    await tester.pumpWidget(MaterialApp(
      localizationsDelegates: AppLocalizations.localizationsDelegates,
      supportedLocales: AppLocalizations.supportedLocales,
      home: Scaffold(body: TraceRefLine.recent(store: store)),
    ));
    expect(find.text('Ref: aaaa1111'), findsOneWidget);
  });
}
