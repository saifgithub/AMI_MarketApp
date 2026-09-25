/// CR236 — the settled Room states what the run cost: "This Room used 8
/// credits · 55 left", or "Not charged — the desks were unreachable" when
/// CR039/DEF425/DEF432 refunded a FAILED run.
///
/// Harness mirrors room_no_verdict_test.dart — the real `RoomScreen` with
/// `RoomNotifier` fixed to a chosen `RoomState`, plus `MandateNotifier` fixed
/// for the "balance after" half of the line.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/mandate.dart';
import 'package:ami_trade/models/room.dart';
import 'package:ami_trade/screens/room/room_screen.dart';
import 'package:ami_trade/state/mandate_providers.dart';
import 'package:ami_trade/state/room_providers.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

class _FixedRoomNotifier extends RoomNotifier {
  _FixedRoomNotifier(super.ref, super.ticker, RoomState fixed) {
    state = fixed;
  }
}

class _FixedMandateNotifier extends MandateNotifier {
  _FixedMandateNotifier(super.ref, UserMandate? initial) {
    state = MandateState(mandate: initial);
  }

  @override
  Future<void> refresh() async {}
}

UserMandate _mandate({int? creditBalance}) => UserMandate.fromJson({
      'user_id': 'u1',
      'plan': 'trial_trader',
      if (creditBalance != null) 'credit_balance': creditBalance,
    });

RoomVerdict _approveVerdict() => RoomVerdict.fromJson({
      'action': 'APPROVE',
      'size_pct': 2.5,
      'entry': 190.0,
      'target': 210.0,
      'stop': 180.0,
      'time_horizon_days': 30,
      'reason': 'Cleared — thesis and levels hold.',
      'violations': <String>[],
      'overridden_from_llm': false,
      'opinions_not_included': <String>[],
    });

Future<void> _pump(
  WidgetTester t, {
  required RoomState roomState,
  UserMandate? mandate,
}) async {
  SharedPreferences.setMockInitialValues({'ami_room_view_mode': 'transcript'});
  const ticker = 'AAPL';
  await t.pumpWidget(
    ProviderScope(
      overrides: [
        roomNotifierProvider(ticker).overrideWith(
          (ref) => _FixedRoomNotifier(ref, ticker, roomState),
        ),
        mandateNotifierProvider.overrideWith(
          (ref) => _FixedMandateNotifier(ref, mandate),
        ),
      ],
      child: MaterialApp(
        localizationsDelegates: AppLocalizations.localizationsDelegates,
        supportedLocales: AppLocalizations.supportedLocales,
        home: const RoomScreen(ticker: ticker),
      ),
    ),
  );
  await t.pumpAndSettle();
}

AppLocalizations _l(WidgetTester t) =>
    AppLocalizations.of(t.element(find.byType(RoomScreen)));

void main() {
  group('CR236 — Room result cost line', () {
    testWidgets('shows the actual charge and the refreshed balance', (t) async {
      await _pump(
        t,
        roomState: RoomState(
          done: true,
          runId: 'run-1',
          order: const ['fundamentals_analyst'],
          transcript: const {'fundamentals_analyst': 'Margins are expanding.'},
          verdict: _approveVerdict(),
          creditCost: 8,
          refunded: false,
        ),
        mandate: _mandate(creditBalance: 55),
      );

      final l = _l(t);
      expect(find.text(l.roomResultCost('8', '55')), findsOneWidget);
      expect(find.text(l.roomResultRefunded), findsNothing);
    });

    testWidgets('shows the refunded line instead of a charge when refunded=true',
        (t) async {
      await _pump(
        t,
        roomState: RoomState(
          done: true,
          runId: 'run-1',
          order: const [],
          transcript: const {},
          verdict: null,
          creditCost: 8,
          refunded: true,
        ),
        mandate: _mandate(creditBalance: 63),
      );

      final l = _l(t);
      expect(find.text(l.roomResultRefunded), findsOneWidget);
      expect(find.textContaining('used 8 credits'), findsNothing);
    });

    testWidgets('renders nothing when creditCost is unknown (older backend)',
        (t) async {
      await _pump(
        t,
        roomState: RoomState(
          done: true,
          runId: 'run-1',
          order: const ['fundamentals_analyst'],
          transcript: const {'fundamentals_analyst': 'Margins are expanding.'},
          verdict: _approveVerdict(),
          // creditCost defaults to null — a pre-CR236 backend's `done` event.
        ),
        mandate: _mandate(creditBalance: 55),
      );

      final l = _l(t);
      expect(find.text(l.roomResultRefunded), findsNothing);
      expect(find.textContaining('This Room used'), findsNothing);
    });

    testWidgets('shows "—" for the left-over balance if the mandate has not refreshed',
        (t) async {
      await _pump(
        t,
        roomState: RoomState(
          done: true,
          runId: 'run-1',
          order: const ['fundamentals_analyst'],
          transcript: const {'fundamentals_analyst': 'Margins are expanding.'},
          verdict: _approveVerdict(),
          creditCost: 8,
          refunded: false,
        ),
        mandate: null,
      );

      final l = _l(t);
      expect(find.text(l.roomResultCost('8', '—')), findsOneWidget);
    });
  });
}
