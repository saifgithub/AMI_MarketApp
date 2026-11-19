// CR278 (CR267 WP-36) - the two Beta feedback controls on AMI's answers:
//   1. the thumbs card under a finished Room's verdict posts the answer and can
//      be dismissed, and never blocks anything;
//   2. "Report this response" opens the EXISTING bug sheet pre-filled for that
//      response, and sending it goes through the existing bug-report call with
//      the response's `route` and the recent trace ids.

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/auth.dart';
import 'package:ami_trade/models/response_report.dart';
import 'package:ami_trade/models/room_board.dart';
import 'package:ami_trade/screens/feedback/bug_report_sheet.dart';
import 'package:ami_trade/services/api/api_client.dart';
import 'package:ami_trade/services/api/trace_ids.dart';
import 'package:ami_trade/state/auth_providers.dart';
import 'package:ami_trade/state/feedback_providers.dart';
import 'package:ami_trade/state/onboarding_providers.dart';
import 'package:ami_trade/widgets/chat/chat_bubble.dart';
import 'package:ami_trade/widgets/report_response_sheet.dart';
import 'package:ami_trade/widgets/room/room_rating_card.dart';
import 'package:ami_trade/widgets/room/room_transcript_rows.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_secure_storage/test/test_flutter_secure_storage_platform.dart';
import 'package:flutter_secure_storage_platform_interface/flutter_secure_storage_platform_interface.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

const _runId = '5b0c1f1e-1111-4222-8333-444455556666';
const _traceA = 'a1b2c3d4-0000-4000-8000-000000000001';
const _traceB = 'a1b2c3d4-0000-4000-8000-000000000002';

class _Api extends ApiClient {
  _Api({this.failRating = false}) : super(baseUrl: 'test://localhost');

  final bool failRating;
  final ratings = <({String runId, bool helpful})>[];
  final reports = <Map<String, Object?>>[];

  @override
  Future<void> rateRoom({required String runId, required bool helpful}) async {
    if (failRating) throw Exception('offline');
    ratings.add((runId: runId, helpful: helpful));
  }

  @override
  Future<Map<String, dynamic>> submitBugReport({
    required String category,
    required String title,
    String? steps,
    String? route,
    required String appVersion,
    required String platform,
    String? attachmentPath,
    String? attachmentMime,
    String? token,
    List<String> traceIds = const [],
  }) async {
    reports.add({
      'category': category,
      'title': title,
      'route': route,
      'traceIds': traceIds,
    });
    return {'id': '788b80c0-ffc2-4b28-a197-37b000000000'};
  }
}

class _ClaimedAuthNotifier extends AuthNotifier {
  _ClaimedAuthNotifier(super.ref) {
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

Widget _app(_Api api, Widget home) => ProviderScope(
      overrides: [
        apiClientProvider.overrideWithValue(api),
        authNotifierProvider.overrideWith((ref) => _ClaimedAuthNotifier(ref)),
        appVersionProvider.overrideWith((ref) async => '0.1.0+1'),
      ],
      child: MaterialApp(
        localizationsDelegates: AppLocalizations.localizationsDelegates,
        supportedLocales: AppLocalizations.supportedLocales,
        home: Scaffold(body: SingleChildScrollView(child: home)),
      ),
    );

Future<void> _settle(WidgetTester t) async {
  for (var i = 0; i < 6; i++) {
    await t.pump(const Duration(milliseconds: 80));
  }
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  setUp(() {
    FlutterSecureStoragePlatform.instance =
        TestFlutterSecureStoragePlatform(<String, String>{});
    SharedPreferences.setMockInitialValues({});
    TraceIdStore.instance.clear();
  });

  group('ResponseReportTarget', () {
    test('route names the surface, the Room, the agent and the turn', () {
      expect(
        const ResponseReportTarget(
          surface: ResponseSurface.verdict,
          agentId: 'portfolio_manager',
          agentLabel: 'CIO',
          runId: _runId,
        ).route,
        'response:verdict:$_runId:portfolio_manager',
      );
      expect(
        const ResponseReportTarget(
          surface: ResponseSurface.concierge,
          agentId: 'concierge',
          agentLabel: 'AMI',
          turn: 3,
        ).route,
        'response:concierge:-:concierge:t3',
      );
    });
  });

  group('thumbs card', () {
    testWidgets('thumbs-up posts helpful=true for the Room and says thanks',
        (t) async {
      final api = _Api();
      await t.pumpWidget(_app(api, const RoomRatingCard(runId: _runId)));
      final l = await AppLocalizations.delegate.load(const Locale('en'));
      expect(find.text(l.roomRatingQuestion), findsOneWidget);
      expect(find.text(l.roomRatingThanks), findsNothing);

      await t.tap(find.byKey(const Key('roomRatingUp')));
      await _settle(t);

      expect(api.ratings, [(runId: _runId, helpful: true)]);
      expect(find.text(l.roomRatingThanks), findsOneWidget);
    });

    testWidgets('tapping the other thumb changes the answer', (t) async {
      final api = _Api();
      await t.pumpWidget(_app(api, const RoomRatingCard(runId: _runId)));
      await t.tap(find.byKey(const Key('roomRatingUp')));
      await _settle(t);
      await t.tap(find.byKey(const Key('roomRatingDown')));
      await _settle(t);
      expect(api.ratings.map((r) => r.helpful), [true, false]);
    });

    testWidgets('a failed save is a quiet line and the thumbs stay usable',
        (t) async {
      final api = _Api(failRating: true);
      await t.pumpWidget(_app(api, const RoomRatingCard(runId: _runId)));
      final l = await AppLocalizations.delegate.load(const Locale('en'));
      await t.tap(find.byKey(const Key('roomRatingUp')));
      await _settle(t);
      expect(find.text(l.roomRatingFailed), findsOneWidget);
      expect(find.text(l.roomRatingThanks), findsNothing);
      final up = t.widget<OutlinedButton>(find.byKey(const Key('roomRatingUp')));
      expect(up.onPressed, isNotNull);
    });

    testWidgets('dismissing hides the card and posts nothing', (t) async {
      final api = _Api();
      await t.pumpWidget(_app(api, const RoomRatingCard(runId: _runId)));
      await t.tap(find.byKey(const Key('roomRatingDismiss')));
      await _settle(t);
      expect(find.byKey(const Key('roomRatingCard')), findsNothing);
      expect(api.ratings, isEmpty);
    });

    testWidgets('the card has a report link only when given a handler',
        (t) async {
      var reported = 0;
      await t.pumpWidget(_app(
        _Api(),
        RoomRatingCard(runId: _runId, onReport: () => reported++),
      ));
      await t.tap(find.byKey(const Key('roomRatingReport')));
      expect(reported, 1);

      await t.pumpWidget(_app(_Api(), const RoomRatingCard(runId: _runId)));
      expect(find.byKey(const Key('roomRatingReport')), findsNothing);
    });
  });

  group('Report this response', () {
    const target = ResponseReportTarget(
      surface: ResponseSurface.room,
      agentId: 'risk_manager',
      agentLabel: 'RISK',
      runId: _runId,
    );

    testWidgets('opens the existing bug sheet pre-filled, and sends it with '
        'the response route and the recent trace ids', (t) async {
      TraceIdStore.instance.record(_traceA, path: '/v1/x', status: 500);
      TraceIdStore.instance.record(_traceB, path: '/v1/y', status: 502);
      final api = _Api();
      await t.pumpWidget(_app(
        api,
        Consumer(
          builder: (context, ref, _) => ElevatedButton(
            onPressed: () => showBugReportSheet(context, ref, response: target),
            child: const Text('open'),
          ),
        ),
      ));
      await t.tap(find.text('open'));
      await _settle(t);
      final l = await AppLocalizations.delegate.load(const Locale('en'));

      expect(find.byKey(const Key('reportResponseContext')), findsOneWidget);
      expect(find.text(l.reportResponseContext('RISK')), findsOneWidget);
      expect(find.text(l.reportResponseTitlePrefill('RISK')), findsOneWidget);

      await t.tap(find.text(l.bugSheetSend));
      await _settle(t);

      expect(api.reports, hasLength(1));
      final sent = api.reports.single;
      expect(sent['route'], 'response:room:$_runId:risk_manager');
      expect(sent['category'], 'wrong_data');
      expect(sent['title'], l.reportResponseTitlePrefill('RISK'));
      expect(sent['traceIds'], [_traceB, _traceA]);
    });

    testWidgets('a plain bug sheet is unchanged: no response caption, '
        'empty title', (t) async {
      await t.pumpWidget(_app(
        _Api(),
        Consumer(
          builder: (context, ref, _) => ElevatedButton(
            onPressed: () => showBugReportSheet(context, ref),
            child: const Text('open'),
          ),
        ),
      ));
      await t.tap(find.text('open'));
      await _settle(t);
      expect(find.byKey(const Key('reportResponseContext')), findsNothing);
    });

    testWidgets('long-press on a Room turn offers the report and opens the '
        'pre-filled sheet', (t) async {
      final api = _Api();
      const voice = RoomVoice(
        agentId: 'risk_manager',
        content: 'Position size is too large for the mandate. **12%**',
      );
      await t.pumpWidget(_app(
        api,
        Consumer(
          builder: (context, ref, _) => RoomTranscriptRows(
            voices: const [voice],
            onReportVoice: (v) => showReportResponseActions(
              context,
              ref,
              ResponseReportTarget(
                surface: ResponseSurface.room,
                agentId: v.agentId,
                agentLabel: 'RISK',
                runId: _runId,
              ),
            ),
          ),
        ),
      ));
      final l = await AppLocalizations.delegate.load(const Locale('en'));

      await t.longPress(find.byType(TranscriptRow));
      await _settle(t);
      expect(find.byKey(const Key('reportResponseTile')), findsOneWidget);

      await t.tap(find.byKey(const Key('reportResponseTile')));
      await _settle(t);
      expect(find.text(l.reportResponseContext('RISK')), findsOneWidget);
    });

    testWidgets('a Journal-style row list (no handler) ignores long-press',
        (t) async {
      const voice = RoomVoice(agentId: 'risk_manager', content: 'Too large.');
      await t.pumpWidget(_app(_Api(), const RoomTranscriptRows(voices: [voice])));
      await t.longPress(find.byType(TranscriptRow));
      await _settle(t);
      expect(find.byKey(const Key('reportResponseTile')), findsNothing);
    });

    testWidgets('chat bubble: long-press fires for a reply, not for the '
        "user's own message", (t) async {
      var fired = 0;
      await t.pumpWidget(_app(
        _Api(),
        Column(children: [
          ChatBubble(
            content: 'reply',
            author: ChatAuthor.concierge,
            onLongPress: () => fired++,
          ),
          ChatBubble(
            content: 'mine',
            author: ChatAuthor.user,
            onLongPress: () => fired += 100,
          ),
        ]),
      ));
      await t.longPress(find.text('reply'));
      await t.longPress(find.text('mine'));
      expect(fired, 1);
    });
  });
}
