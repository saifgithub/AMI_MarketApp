// WP-38 (CR267) / CR239 - an error state shows the trace id as a small,
// copyable "Ref: abc12345", and a screen with no ref is unchanged.

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/screens/inbox/inbox_screen.dart';
import 'package:ami_trade/services/api/trace_ids.dart';
import 'package:ami_trade/state/inbox_providers.dart';
import 'package:ami_trade/widgets/trace_ref_line.dart';
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

const _full = 'a1b2c3d4-0000-4000-8000-000000000001';

Widget _app(Widget child, {List<Override> overrides = const []}) =>
    ProviderScope(
      overrides: overrides,
      child: MaterialApp(
        localizationsDelegates: AppLocalizations.localizationsDelegates,
        supportedLocales: AppLocalizations.supportedLocales,
        home: Scaffold(body: Center(child: child)),
      ),
    );

void main() {
  setUp(TraceIdStore.instance.clear);

  testWidgets('AmiErrorMessage splits the footnote into a Ref line',
      (tester) async {
    await tester.pumpWidget(_app(const AmiErrorMessage(
        "Couldn't load your lessons — try again. Ref: a1b2c3d4.")));
    expect(find.text("Couldn't load your lessons — try again."), findsOneWidget);
    expect(find.text('Ref: a1b2c3d4'), findsOneWidget);
  });

  testWidgets('AmiErrorMessage with no ref is exactly the plain message',
      (tester) async {
    await tester.pumpWidget(_app(const AmiErrorMessage('Nothing to see.')));
    expect(find.text('Nothing to see.'), findsOneWidget);
    expect(find.textContaining('Ref'), findsNothing);
  });

  testWidgets('tapping the Ref copies the FULL id, not the short prefix',
      (tester) async {
    TraceIdStore.instance.record(_full);
    String? copied;
    tester.binding.defaultBinaryMessenger
        .setMockMethodCallHandler(SystemChannels.platform, (call) async {
      if (call.method == 'Clipboard.setData') {
        copied = (call.arguments as Map)['text'] as String;
      }
      return null;
    });
    addTearDown(() => tester.binding.defaultBinaryMessenger
        .setMockMethodCallHandler(SystemChannels.platform, null));

    await tester.pumpWidget(_app(const TraceRefLine('a1b2c3d4')));
    await tester.tap(find.text('Ref: a1b2c3d4'));
    await tester.pump();
    expect(copied, _full);
    expect(find.text('Reference copied'), findsOneWidget);
    await tester.pump(const Duration(seconds: 3)); // let the toast expire
  });

  testWidgets('TraceRefLine.recent shows the latest id, or nothing',
      (tester) async {
    await tester.pumpWidget(_app(const TraceRefLine.recent()));
    expect(find.textContaining('Ref:'), findsNothing);

    TraceIdStore.instance.record(_full);
    await tester.pumpWidget(_app(const TraceRefLine.recent(key: Key('r'))));
    expect(find.text('Ref: a1b2c3d4'), findsOneWidget);

    TraceIdStore.instance.recordNoResponse();
    await tester.pumpWidget(_app(const TraceRefLine.recent(key: Key('r2'))));
    expect(find.textContaining('Ref:'), findsNothing,
        reason: 'the latest failure never reached the server - no stale id');
  });

  group('a real error state (inbox)', () {
    Future<void> pumpInbox(WidgetTester tester) async {
      tester.view.physicalSize = const Size(390, 844);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(tester.view.reset);
      await tester.pumpWidget(_app(const InboxScreen(), overrides: [
        inboxProvider.overrideWith((ref) => throw DioException(
              requestOptions: RequestOptions(path: '/v1/messages'),
              type: DioExceptionType.badResponse,
              response: Response<void>(
                  requestOptions: RequestOptions(path: '/v1/messages'),
                  statusCode: 500),
            )),
      ]));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 300));
    }

    testWidgets('shows Ref: after a failed request carrying an id',
        (tester) async {
      TraceIdStore.instance.record(_full, path: '/v1/messages', status: 500);
      await pumpInbox(tester);
      expect(find.text('Ref: a1b2c3d4'), findsOneWidget);
    });

    testWidgets('shows no Ref line when no request id is known',
        (tester) async {
      await pumpInbox(tester);
      expect(find.textContaining('Ref:'), findsNothing);
    });
  });
}
