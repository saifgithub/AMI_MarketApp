/// CR181 guard — the 1-on-1 screen records `one_on_one_open` on arrival,
/// and telemetry is genuinely fire-and-forget at the widget layer.
///
/// The depth segment counts "opened a 1-on-1", so the event must fire when
/// the screen appears — once per arrival, not per rebuild — and it must
/// fire even when the session behind the screen fails to start (a user who
/// opened the door explored, whatever the backend did next). The API here
/// is a dead backend on purpose: the screen renders its error state and
/// the telemetry event is queued anyway, with no exception escaping into
/// the widget tree.
library;

import 'package:ami_trade/models/agent.dart';
import 'package:ami_trade/models/one_on_one.dart';
import 'package:ami_trade/screens/agent/one_on_one_screen.dart';
import 'package:ami_trade/services/api/api_client.dart';
import 'package:ami_trade/services/telemetry/telemetry_emitter.dart';
import 'package:ami_trade/state/onboarding_providers.dart';
import 'package:ami_trade/state/telemetry_providers.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ami_trade/generated/l10n/app_localizations.dart';

/// A backend that is down: the session open fails, which must not stop the
/// open event from being recorded.
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

void main() {
  testWidgets(
      'opening the 1-on-1 screen queues exactly one one_on_one_open, '
      'even with the session API dead', (tester) async {
    final sent = <List<Map<String, dynamic>>>[];
    final emitter = TelemetryEmitter(
      send: (events) async {
        sent.add(events);
        return (accepted: events.length, duplicates: 0);
      },
      // Park the debounce far out so the queue is inspectable.
      flushDelay: const Duration(hours: 1),
    );

    await tester.pumpWidget(ProviderScope(
      overrides: [
        apiClientProvider.overrideWithValue(_DeadApi()),
        telemetryProvider.overrideWithValue(emitter),
      ],
      child: MaterialApp(
        localizationsDelegates: AppLocalizations.localizationsDelegates,
        supportedLocales: AppLocalizations.supportedLocales,
        home: OneOnOneScreen(agent: kAllAgents.first),
      ),
    ));
    // Let the auto-open microtask fail and the error state render.
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 50));

    expect(tester.takeException(), isNull,
        reason: 'neither the dead API nor telemetry may throw into the tree');
    final types =
        emitter.pendingEvents.map((e) => e['event_type']).toList();
    expect(types, ['one_on_one_open'],
        reason: 'exactly one open event, queued on arrival');
    expect(sent, isEmpty,
        reason: 'debounce window still open — nothing sent yet, and the '
            'screen never waited on telemetry');

    // Cancel the parked debounce timer inside the test body — the binding
    // asserts no timers are pending the moment the body returns.
    emitter.dispose();
  });
}
