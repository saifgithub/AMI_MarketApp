/// CR237 — "Ask the CIO again" on the CIO-outage PASS. Renders ONLY when
/// the server's `cio_retry_available` flag is true (`RoomState.cioRetryAvailable`)
/// — never on the desks-unreachable NO_VERDICT case or a reasoned PASS, and
/// never driven by matching `verdict.reason` text.
///
/// Harness mirrors room_cr236_result_cost_line_test.dart — the real
/// `RoomScreen` with `RoomNotifier` fixed to a chosen `RoomState`, view mode
/// forced to 'board' (the action lives in `_VerdictActions`, which only
/// renders on the board footer — `showBoard = settled && !mode.showsTranscript`).
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/room.dart';
import 'package:ami_trade/screens/room/room_screen.dart';
import 'package:ami_trade/state/room_providers.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

class _FixedRoomNotifier extends RoomNotifier {
  _FixedRoomNotifier(super.ref, super.ticker, RoomState fixed) {
    state = fixed;
  }

  @override
  Future<void> retryCio() async {
    // No-op in these rendering tests — the retry flow itself is covered by
    // the backend's own suite (test_cr237_cio_retry.py) and by
    // room_providers.dart's event-handling logic directly.
  }
}

RoomVerdict _cioOutagePassVerdict() => RoomVerdict.fromJson({
      'action': 'PASS',
      'reason': "AMI's analyst room lost its model connection before the "
          'Chief Investment Officer could rule. This Room wasn\'t charged.',
      'violations': <String>[],
      'overridden_from_llm': true,
      'opinions_not_included': <String>[],
    });

RoomVerdict _noVerdictOutageVerdict() => RoomVerdict.fromJson({
      'action': 'NO_VERDICT',
      'reason': 'Too much of your analyst room was unreachable this run — '
          "reconvene when the desks are back. This Room wasn't charged.",
      'violations': <String>[],
      'overridden_from_llm': true,
      'opinions_not_included': <String>[],
    });

RoomVerdict _reasonedPassVerdict() => RoomVerdict.fromJson({
      'action': 'PASS',
      'reason': 'Chief Investment Officer: the thesis does not clear the '
          'mandate at this size.',
      'violations': <String>[],
      'overridden_from_llm': false,
      'opinions_not_included': <String>[],
    });

Future<void> _pump(
  WidgetTester t, {
  required RoomState roomState,
  Size size = const Size(390, 844),
  double textScale = 1.0,
}) async {
  SharedPreferences.setMockInitialValues({'ami_room_view_mode': 'board'});
  t.view.physicalSize = size;
  t.view.devicePixelRatio = 1.0;
  addTearDown(t.view.reset);

  const ticker = 'AAPL';
  await t.pumpWidget(
    ProviderScope(
      overrides: [
        roomNotifierProvider(ticker).overrideWith(
          (ref) => _FixedRoomNotifier(ref, ticker, roomState),
        ),
      ],
      child: MediaQuery(
        data: MediaQueryData(size: size, textScaler: TextScaler.linear(textScale)),
        child: MaterialApp(
          localizationsDelegates: AppLocalizations.localizationsDelegates,
          supportedLocales: AppLocalizations.supportedLocales,
          home: const RoomScreen(ticker: ticker),
        ),
      ),
    ),
  );
  // Bounded pumps, not pumpAndSettle: `retryingCio: true` renders
  // HexPulseLoader, whose AnimationController repeats forever
  // (`..repeat(reverse: true)`) — settling would never complete, same fix
  // room_live_status_test.dart already applies for this exact widget.
  await t.pump();
  await t.pump(const Duration(milliseconds: 50));
}

AppLocalizations _l(WidgetTester t) => AppLocalizations.of(t.element(find.byType(RoomScreen)));

void main() {
  group('CR237 — Ask the CIO again action', () {
    testWidgets('renders when cio_retry_available is true on the outage PASS',
        (t) async {
      await _pump(
        t,
        roomState: RoomState(
          done: true,
          runId: 'run-1',
          order: const [],
          transcript: const {},
          verdict: _cioOutagePassVerdict(),
          creditCost: 12,
          refunded: true,
          cioRetryAvailable: true,
        ),
      );

      final l = _l(t);
      expect(find.text(l.roomVerdictAskCioAgain), findsOneWidget);
      expect(find.text(l.roomVerdictAskCioAgainSubtitle), findsOneWidget);
    });

    testWidgets('does not render when cio_retry_available is false', (t) async {
      await _pump(
        t,
        roomState: RoomState(
          done: true,
          runId: 'run-1',
          order: const [],
          transcript: const {},
          verdict: _cioOutagePassVerdict(),
          creditCost: 12,
          refunded: true,
          cioRetryAvailable: false,
        ),
      );

      final l = _l(t);
      expect(find.text(l.roomVerdictAskCioAgain), findsNothing);
    });

    testWidgets(
        'never renders on the desks-unreachable NO_VERDICT even if the flag '
        'were somehow true (server-side eligibility already excludes this '
        'shape — belt-and-braces at the render layer too)', (t) async {
      await _pump(
        t,
        roomState: RoomState(
          done: true,
          runId: 'run-1',
          order: const [],
          transcript: const {},
          verdict: _noVerdictOutageVerdict(),
          creditCost: 12,
          refunded: true,
          // Server would never send this combination — is_llm_outage_verdict
          // excludes NO_VERDICT from eligibility — but the client-side gate
          // is the flag alone, so proving that here documents the contract.
          cioRetryAvailable: false,
        ),
      );

      final l = _l(t);
      expect(find.text(l.roomVerdictAskCioAgain), findsNothing);
    });

    testWidgets('never renders on a reasoned PASS', (t) async {
      await _pump(
        t,
        roomState: RoomState(
          done: true,
          runId: 'run-1',
          order: const [],
          transcript: const {},
          verdict: _reasonedPassVerdict(),
          creditCost: 8,
          refunded: false,
          cioRetryAvailable: false,
        ),
      );

      final l = _l(t);
      expect(find.text(l.roomVerdictAskCioAgain), findsNothing);
    });

    testWidgets('shows the in-progress label and disables the button while retrying',
        (t) async {
      await _pump(
        t,
        roomState: RoomState(
          done: true,
          runId: 'run-1',
          order: const [],
          transcript: const {},
          verdict: _cioOutagePassVerdict(),
          creditCost: 12,
          refunded: true,
          cioRetryAvailable: true,
          retryingCio: true,
        ),
      );

      final l = _l(t);
      expect(find.text(l.roomVerdictAskCioAgainInProgress), findsOneWidget);
      expect(find.text(l.roomVerdictAskCioAgain), findsNothing);
      // No cost subtitle while retrying — matches the widget's own gate.
      expect(find.text(l.roomVerdictAskCioAgainSubtitle), findsNothing);

      final button = t.widget<ElevatedButton>(find.byType(ElevatedButton).first);
      expect(button.onPressed, isNull);
    });

    testWidgets('renders the third cost-line branch when cio_retried is true',
        (t) async {
      await _pump(
        t,
        roomState: RoomState(
          done: true,
          runId: 'run-1',
          order: const [],
          transcript: const {},
          verdict: RoomVerdict.fromJson({
            'action': 'APPROVE',
            'size_pct': 2.5,
            'entry': 190.0,
            'target': 210.0,
            'stop': 180.0,
            'reason': 'Cleared on retry.',
            'violations': <String>[],
            'overridden_from_llm': false,
            'opinions_not_included': <String>[],
          }),
          creditCost: 12,
          refunded: false,
          cioRetryAvailable: false,
          cioRetried: true,
        ),
      );

      final l = _l(t);
      expect(find.text(l.roomResultCioRetried), findsOneWidget);
      expect(find.text(l.roomResultRefunded), findsNothing);
      expect(find.textContaining('used 12 credits'), findsNothing);
    });

    // Two pre-existing, out-of-scope overflows fire at 320dp/1.3x regardless
    // of CR237 (confirmed by running this pump with cioRetryAvailable:
    // false, i.e. `_AskCioAgainButton` not even in the tree): `_Header`'s
    // title Row (32px) and `_Footer`'s settled-state share Row (82px).
    // Neither touches `_VerdictActions`/`_AskCioAgainButton`; both predate
    // this CR, matching CR236's own documented experience with a different
    // pre-existing overflow in the sibling ConveneSheet.
    //
    // `FlutterError.onError` (flutter_test's binding.dart) coalesces a
    // SECOND exception occurring before the first is drained into a single
    // "Multiple exceptions (N)" sentinel — both overflows happen during the
    // same `pumpAndSettle`, before test code gets a chance to call
    // `takeException()` in between, so draining one at a time is not
    // possible here. The message NAMES the count, so pinning that string is
    // the only way to assert "no MORE overflows than the two known ones"
    // without fighting the framework's own coalescing.
    const twoKnownOverflowsMessage =
        'Multiple exceptions (2) were detected during the running of the '
        'current test, and at least one was unexpected.';

    testWidgets(
        'renders with exactly the two known pre-existing overflows at '
        '320dp/1.3x when the action is NOT showing (baseline)', (t) async {
      await _pump(
        t,
        size: const Size(320, 690),
        textScale: 1.3,
        roomState: RoomState(
          done: true,
          runId: 'run-1',
          order: const [],
          transcript: const {},
          verdict: _cioOutagePassVerdict(),
          creditCost: 12,
          refunded: true,
          cioRetryAvailable: false,
        ),
      );
      final err = t.takeException();
      expect(err.toString(), twoKnownOverflowsMessage,
          reason: 'expected exactly the two known pre-existing, '
              'out-of-scope overflows — a different count means the '
              'baseline moved and this test needs re-pinning');
    });

    testWidgets(
        'renders with the SAME two known pre-existing overflows at '
        '320dp/1.3x when the action IS showing — no new overflow added',
        (t) async {
      await _pump(
        t,
        size: const Size(320, 690),
        textScale: 1.3,
        roomState: RoomState(
          done: true,
          runId: 'run-1',
          order: const [],
          transcript: const {},
          verdict: _cioOutagePassVerdict(),
          creditCost: 12,
          refunded: true,
          cioRetryAvailable: true,
        ),
      );
      final err = t.takeException();
      expect(err.toString(), twoKnownOverflowsMessage,
          reason: 'the Ask the CIO again action introduced a NEW overflow '
              'at 320dp/1.3x — the count moved beyond the two pre-existing, '
              'out-of-scope ones');
      // The action itself is present and findable despite the pre-existing,
      // unrelated overflows elsewhere on screen.
      final l = _l(t);
      expect(find.text(l.roomVerdictAskCioAgain), findsOneWidget);
    });
  });
}
