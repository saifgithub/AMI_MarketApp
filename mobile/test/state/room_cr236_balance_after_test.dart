/// CR236 — the post-Room "· 55 left" comes from the mandate refresh that
/// `done` triggers, never from the balance cached before the Room.
///
/// Drives the real `RoomNotifier.start()` through a scripted `done` event.
/// The mandate starts at a stale 63; a successful refresh moves it to 55 and
/// `balanceAfter` must read 55. A failed refresh keeps the stale 63, so
/// `balanceAfter` must stay null rather than report it.
library;

import 'package:ami_trade/models/journal.dart';
import 'package:ami_trade/models/mandate.dart';
import 'package:ami_trade/services/api/api_client.dart';
import 'package:ami_trade/state/journal_providers.dart';
import 'package:ami_trade/state/lessons_providers.dart';
import 'package:ami_trade/state/mandate_providers.dart';
import 'package:ami_trade/state/onboarding_providers.dart';
import 'package:ami_trade/state/room_providers.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

class _ScriptedApiClient extends ApiClient {
  _ScriptedApiClient(this.events) : super(baseUrl: 'test://localhost');

  final List<Map<String, dynamic>> events;

  @override
  Stream<Map<String, dynamic>> streamRoom({
    required String userId,
    required String ticker,
    String locale = 'en',
    Map<String, dynamic>? mandateOverride,
    Map<String, dynamic>? alpaca,
  }) {
    return Stream.fromIterable(events);
  }
}

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

UserMandate _mandate(int balance) => UserMandate.fromJson({
      'user_id': 'u1',
      'plan': 'trial_trader',
      'credit_balance': balance,
    });

/// Starts at the stale pre-Room balance; `refresh` either lands the
/// post-Room balance or fails the way `MandateNotifier.refresh` does
/// (mandate kept, error set).
class _ScriptedMandate extends MandateNotifier {
  _ScriptedMandate(super.ref, {required this.refreshSucceeds}) {
    state = MandateState(mandate: _mandate(63));
  }

  final bool refreshSucceeds;

  @override
  Future<void> refresh() async {
    state = refreshSucceeds
        ? MandateState(mandate: _mandate(55))
        : state.copyWith(error: "Couldn't load your mandate.");
  }
}

Future<RoomState> _runToDone({required bool refreshSucceeds}) async {
  SharedPreferences.setMockInitialValues({});
  const ticker = 'AAPL';
  final container = ProviderContainer(
    overrides: [
      apiClientProvider.overrideWithValue(_ScriptedApiClient([
        {'kind': 'done', 'run_id': 'r1', 'credit_cost': 8, 'refunded': false},
      ])),
      journalNotifierProvider.overrideWith((ref) => _NoopJournal(ref)),
      lessonsNotifierProvider.overrideWith((ref) => _NoopLessons(ref)),
      mandateNotifierProvider.overrideWith(
        (ref) => _ScriptedMandate(ref, refreshSucceeds: refreshSucceeds),
      ),
    ],
  );
  addTearDown(container.dispose);
  final sub = container.listen(
    roomNotifierProvider(ticker),
    (_, __) {},
    fireImmediately: true,
  );
  addTearDown(sub.close);
  await container.read(roomNotifierProvider(ticker).notifier).start();
  return sub.read();
}

void main() {
  test('balanceAfter is the refreshed balance, not the pre-Room one',
      () async {
    final state = await _runToDone(refreshSucceeds: true);
    expect(state.done, isTrue);
    expect(state.creditCost, 8);
    expect(state.balanceAfter, 55);
  });

  test('a failed refresh leaves balanceAfter unknown instead of stale',
      () async {
    final state = await _runToDone(refreshSucceeds: false);
    expect(state.done, isTrue);
    expect(state.creditCost, 8);
    expect(state.balanceAfter, isNull);
  });
}
