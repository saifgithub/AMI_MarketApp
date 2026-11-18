/// CR272 (client half) - the Room's `provider_switch` event.
///
/// When the main model fails, the backend restarts the whole Room on the backup
/// slot and emits `provider_switch` with AMI's own notice. Everything streamed
/// before it is void; the app must clear it and show the notice, so no stale
/// turn from the abandoned discussion stays on screen next to the new one.
///
/// The frame is transcribed from `backend/app/api/room.py` (the
/// `provider_switch` branch: `json.dumps({"text": ev.text or ""})`) with the
/// text of `ROOM_BACKUP_SWITCH_NOTICE`.
library;

import 'dart:async';

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/journal.dart';
import 'package:ami_trade/screens/room/room_screen.dart';
import 'package:ami_trade/services/api/api_client.dart';
import 'package:ami_trade/state/journal_providers.dart';
import 'package:ami_trade/state/lessons_providers.dart';
import 'package:ami_trade/state/onboarding_providers.dart';
import 'package:ami_trade/state/room_providers.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

const _notice =
    'AMI switched to its backup model and restarted the discussion.';
const _frame = '{"text": "$_notice"}';

class _NoopJournal extends JournalNotifier {
  _NoopJournal(super.ref);
  @override
  Future<void> refresh({
    JournalEntryType? filterType,
    String plan = 'trial_trader',
    String? q,
  }) async {}
}

class _NoopLessons extends LessonsNotifier {
  _NoopLessons(super.ref);
  @override
  Future<void> refresh() async {}
}

/// Hands the test a controller so it can look at the state between events.
class _ControlledApi extends ApiClient {
  _ControlledApi(this.controller) : super(baseUrl: 'test://localhost');
  final StreamController<Map<String, dynamic>> controller;

  @override
  Stream<Map<String, dynamic>> streamRoom({
    required String userId,
    required String ticker,
    String locale = 'en',
    Map<String, dynamic>? mandateOverride,
    Map<String, dynamic>? alpaca,
  }) =>
      controller.stream;
}

class _FixedRoomNotifier extends RoomNotifier {
  _FixedRoomNotifier(super.ref, super.ticker, RoomState fixed) {
    state = fixed;
  }
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  setUp(() => SharedPreferences.setMockInitialValues({}));

  group('parseRoomSseEvent', () {
    test('parses the backend frame to the notice text', () {
      final parsed = parseRoomSseEvent('provider_switch', _frame);
      expect(parsed, {'kind': 'provider_switch', 'text': _notice});
    });

    test('a frame with no usable text is dropped, not thrown', () {
      expect(parseRoomSseEvent('provider_switch', '{"text": ""}'), isNull);
      expect(parseRoomSseEvent('provider_switch', '{"text": 7}'), isNull);
      expect(parseRoomSseEvent('provider_switch', '{}'), isNull);
      expect(parseRoomSseEvent('provider_switch', 'not json'), isNull);
    });
  });

  test('the notifier clears the transcript so far and shows the notice',
      () async {
    final controller = StreamController<Map<String, dynamic>>();
    final c = ProviderContainer(overrides: [
      apiClientProvider.overrideWithValue(_ControlledApi(controller)),
      journalNotifierProvider.overrideWith((ref) => _NoopJournal(ref)),
      lessonsNotifierProvider.overrideWith((ref) => _NoopLessons(ref)),
    ]);
    addTearDown(c.dispose);
    final sub = c.listen(roomNotifierProvider('AAPL'), (_, __) {},
        fireImmediately: true);
    addTearDown(sub.close);

    final run = c.read(roomNotifierProvider('AAPL').notifier).start();
    Future<void> settle() => Future<void>.delayed(const Duration(milliseconds: 20));

    await settle();
    controller
      ..add({'kind': 'started', 'run_id': 'run-1'})
      ..add({
        'kind': 'agent_withheld',
        'agent_id': 'social_media_analyst',
        'reason': 'upgrade',
      })
      ..add({'kind': 'phase', 'label': 'ANALYSTS'})
      ..add({'kind': 'agent_token', 'agent_id': 'market_analyst', 'text': 'stale turn'})
      ..add({'kind': 'agent_done', 'agent_id': 'market_analyst', 'stance': 'for'});
    await settle();
    var s = sub.read();
    expect(s.transcript['market_analyst'], 'stale turn');
    expect(s.providerSwitchNotice, isNull);

    controller.add({'kind': 'provider_switch', 'text': _notice});
    await settle();
    s = sub.read();
    expect(s.transcript, isEmpty, reason: 'stale turns must not survive');
    expect(s.agentStances, isEmpty);
    expect(s.activeAgent, isNull);
    expect(s.providerSwitchNotice, _notice);
    expect(s.runId, 'run-1', reason: 'same run, restarted');
    expect(s.streaming, isTrue);
    expect(s.withheldAgents.keys, ['social_media_analyst'],
        reason: 'emitted before the restart point; not re-sent');
    expect(s.order, ['social_media_analyst']);

    controller
      ..add({'kind': 'phase', 'label': 'ANALYSTS'})
      ..add({'kind': 'agent_token', 'agent_id': 'news_analyst', 'text': 'fresh turn'})
      ..add({'kind': 'done', 'run_id': 'run-1'});
    await controller.close();
    await run;
    s = sub.read();
    expect(s.transcript.keys, ['news_analyst']);
    expect(s.transcript.containsKey('market_analyst'), isFalse);
    expect(s.providerSwitchNotice, _notice);
  });

  testWidgets('the Room screen shows the notice as a visible banner',
      (tester) async {
    tester.view.physicalSize = const Size(390, 844);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.reset);

    await tester.pumpWidget(ProviderScope(
      overrides: [
        roomNotifierProvider('AAPL').overrideWith((ref) => _FixedRoomNotifier(
              ref,
              'AAPL',
              const RoomState(
                streaming: true,
                runId: 'run-1',
                providerSwitchNotice: _notice,
              ),
            )),
      ],
      child: MaterialApp(
        localizationsDelegates: AppLocalizations.localizationsDelegates,
        supportedLocales: AppLocalizations.supportedLocales,
        home: const RoomScreen(ticker: 'AAPL'),
      ),
    ));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 400));

    expect(find.text(_notice), findsOneWidget);
  });
}
