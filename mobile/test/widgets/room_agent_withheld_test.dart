/// CR098-MOBILE-LIVE — the locked-chair / roster-countdown surface for
/// `agent_withheld` (roster tenure pull-back), plus `withheld_tenure` on the
/// existing CR090 `live_data_notice` card.
///
/// Two layers proven here:
///   1. `RoomNotifier.start()` end-to-end: a real `agent_withheld` event,
///      shaped exactly like `parseRoomSseEvent` emits it, drives the
///      notifier's own switch and lands in `RoomState.withheldAgents` +
///      `order` — not just a fixture-seeded state (acceptance #3).
///   2. `RoomScreen` renders the locked chair inline, in seat, with a
///      roster-level (never per-agent) countdown, and the `withheld_tenure`
///      live-data-notice case renders distinctly from `withheld_paid` /
///      `unavailable` with its own CTA (D1) — a mutation swapping it onto
///      the credits CTA fails the last test in this file.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/screens/room/room_screen.dart';
import 'package:ami_trade/services/api/api_client.dart';
import 'package:ami_trade/state/onboarding_providers.dart';
import 'package:ami_trade/state/room_providers.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

/// Replays a canned event sequence as if already parsed by
/// `parseRoomSseEvent` — no real HTTP/SSE involved, but the exact shape
/// `parseRoomSseEvent('agent_withheld', ...)` returns (api_client.dart).
class _ScriptedApiClient extends ApiClient {
  _ScriptedApiClient(this.events) : super(baseUrl: 'test://localhost');

  final List<Map<String, dynamic>> events;

  @override
  Stream<Map<String, dynamic>> streamRoom({
    required String userId,
    required String ticker,
    String locale = 'en',
    Map<String, dynamic>? mandateOverride,
  }) {
    return Stream.fromIterable(events);
  }
}

class _FixedRoomNotifier extends RoomNotifier {
  _FixedRoomNotifier(super.ref, super.ticker, RoomState fixed) {
    state = fixed;
  }
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  setUp(() {
    SharedPreferences.setMockInitialValues({});
  });

  group('agent_withheld reaches RoomState via the real notifier', () {
    test('populates withheldAgents and mirrors the agentId into order', () async {
      const ticker = 'AAPL';
      final fake = _ScriptedApiClient([
        {'kind': 'phase', 'label': 'ANALYSTS'},
        {
          'kind': 'agent_withheld',
          'agent_id': 'market_analyst',
          'reason': 'upgrade',
          'next_step_agent': 'social_media_analyst',
          'next_step_days': 4,
        },
      ]);
      final container = ProviderContainer(
        overrides: [apiClientProvider.overrideWithValue(fake)],
      );
      addTearDown(container.dispose);

      await container.read(roomNotifierProvider(ticker).notifier).start();

      final state = container.read(roomNotifierProvider(ticker));
      expect(state.withheldAgents['market_analyst'], isNotNull);
      expect(state.withheldAgents['market_analyst']!.nextStepAgentId,
          'social_media_analyst');
      expect(state.withheldAgents['market_analyst']!.nextStepDays, 4);
      expect(state.order, contains('market_analyst'));
      // Never in transcript — a locked chair has no streamed text.
      expect(state.transcript.containsKey('market_analyst'), isFalse);
    });

    test('next_step both null is preserved as null, not defaulted', () async {
      const ticker = 'MSFT';
      final fake = _ScriptedApiClient([
        {
          'kind': 'agent_withheld',
          'agent_id': 'social_media_analyst',
          'reason': 'upgrade',
          'next_step_agent': null,
          'next_step_days': null,
        },
      ]);
      final container = ProviderContainer(
        overrides: [apiClientProvider.overrideWithValue(fake)],
      );
      addTearDown(container.dispose);

      await container.read(roomNotifierProvider(ticker).notifier).start();

      final info = container
          .read(roomNotifierProvider(ticker))
          .withheldAgents['social_media_analyst']!;
      expect(info.nextStepAgentId, isNull);
      expect(info.nextStepDays, isNull);
    });
  });

  Future<void> pumpFixed(WidgetTester t, String ticker, RoomState fixed) {
    return t.pumpWidget(
      ProviderScope(
        overrides: [
          roomNotifierProvider(ticker)
              .overrideWith((ref) => _FixedRoomNotifier(ref, ticker, fixed)),
        ],
        child: MaterialApp(
          localizationsDelegates: AppLocalizations.localizationsDelegates,
          supportedLocales: AppLocalizations.supportedLocales,
          home: RoomScreen(ticker: ticker),
        ),
      ),
    );
  }

  group('locked chair rendering (D3/D4)', () {
    testWidgets(
        'renders in seat with a roster-level countdown naming the OTHER agent',
        (t) async {
      const ticker = 'AAPL';
      await pumpFixed(
        t,
        ticker,
        const RoomState(
          streaming: true,
          order: ['market_analyst'],
          withheldAgents: {
            'market_analyst': WithheldAgentInfo(
              agentId: 'market_analyst',
              reason: 'upgrade',
              nextStepAgentId: 'social_media_analyst',
              nextStepDays: 4,
            ),
          },
        ),
      );
      await t.pump();

      expect(find.textContaining('off your roster'), findsOneWidget);
      // Roster-level: names the NEXT step's agent (Social), never claims
      // the withheld chair (Market) itself is the one returning.
      expect(find.textContaining('Social Media Analyst'), findsOneWidget);
      expect(find.textContaining('4 days'), findsOneWidget);
      expect(t.takeException(), isNull);
    });

    testWidgets('next_step both null omits the countdown, no "null days"',
        (t) async {
      const ticker = 'AAPL';
      await pumpFixed(
        t,
        ticker,
        const RoomState(
          streaming: true,
          order: ['social_media_analyst'],
          withheldAgents: {
            'social_media_analyst': WithheldAgentInfo(
              agentId: 'social_media_analyst',
              reason: 'upgrade',
            ),
          },
        ),
      );
      await t.pump();

      expect(find.textContaining('off your roster'), findsOneWidget);
      expect(find.textContaining('Next roster change'), findsNothing);
      expect(find.textContaining('null'), findsNothing);
      expect(t.takeException(), isNull);
    });

    testWidgets('locked chair sits ahead of a real agent line in the same order',
        (t) async {
      const ticker = 'AAPL';
      await pumpFixed(
        t,
        ticker,
        const RoomState(
          streaming: true,
          order: ['market_analyst', 'fundamentals_analyst'],
          transcript: {'fundamentals_analyst': 'The balance sheet is solid.'},
          withheldAgents: {
            'market_analyst': WithheldAgentInfo(
              agentId: 'market_analyst',
              reason: 'upgrade',
            ),
          },
        ),
      );
      await t.pump();

      final chairFinder = find.textContaining('off your roster');
      final lineFinder = find.textContaining('balance sheet is solid');
      expect(chairFinder, findsOneWidget);
      expect(lineFinder, findsOneWidget);
      final chairY = t.getTopLeft(chairFinder).dy;
      final lineY = t.getTopLeft(lineFinder).dy;
      expect(chairY, lessThan(lineY));
    });
  });

  group('live_data_notice withheld_tenure (CR098 D1)', () {
    testWidgets(
        'renders distinct copy from withheld_paid/unavailable, with its OWN CTA',
        (t) async {
      const ticker = 'AAPL';
      await pumpFixed(
        t,
        ticker,
        const RoomState(
          liveDataNotice: RoomLiveDataNotice(
            news: 'withheld_tenure',
            social: 'unavailable',
            surchargeCharged: 0,
          ),
        ),
      );
      await t.pump();

      expect(find.textContaining('needs a plan upgrade'), findsOneWidget);
      expect(find.text('UPGRADE YOUR PLAN'), findsOneWidget);
      // The DEF059-class inversion this state exists to catch: a tenure
      // withhold must NEVER show the credits CTA (buying credits does
      // nothing for it).
      expect(find.text('UPGRADE FOR LIVE DATA'), findsNothing);
      expect(find.textContaining('needs credits'), findsNothing);
      expect(t.takeException(), isNull);
    });
  });
}
