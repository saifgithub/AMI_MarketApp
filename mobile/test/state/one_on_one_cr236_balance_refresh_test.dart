/// CR236 round 2 (auditor MAJOR-1) — a 1-on-1 turn bills
/// `one_on_one_credit_cost`, so the mandate must be refreshed after every
/// completed `send()`, exactly once, the same way `room_providers.dart`
/// does after a Room's `done` event. A failed send must refresh too — the
/// backend charges before it streams a byte (`one_on_one.py`), so a
/// client-visible failure can still be a real charge (with or without a
/// server-side refund already landed).
///
/// Mirrors the scripted-client pattern in `room_cr236_balance_after_test.dart`:
/// a counting fake `MandateNotifier` in place of the real network call.
library;

import 'package:ami_trade/models/one_on_one.dart';
import 'package:ami_trade/services/api/api_client.dart';
import 'package:ami_trade/state/mandate_providers.dart';
import 'package:ami_trade/state/onboarding_providers.dart';
import 'package:ami_trade/state/one_on_one_providers.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

class _CountingMandate extends MandateNotifier {
  _CountingMandate(super.ref);

  int refreshCalls = 0;

  @override
  Future<void> refresh() async {
    refreshCalls++;
  }
}

class _ScriptedApiClient extends ApiClient {
  _ScriptedApiClient({required this.chunks, this.throwAfter})
      : super(baseUrl: 'test://localhost');

  final List<String> chunks;
  final Object? throwAfter;

  @override
  Future<OneOnOneSession> startOneOnOne({
    required String agentId,
    String locale = 'en',
  }) async {
    return const OneOnOneSession(id: 's1', agentId: 'fundamentals_analyst', locale: 'en');
  }

  @override
  Stream<String> streamOneOnOneMessage({
    required String sessionId,
    required String userMessage,
    required List<ChatMessage> history,
    Map<String, dynamic>? alpaca,
  }) async* {
    for (final c in chunks) {
      yield c;
    }
    if (throwAfter != null) {
      throw Exception(throwAfter);
    }
  }
}

Future<(OneOnOneState, _CountingMandate)> _drive({
  required List<String> chunks,
  Object? throwAfter,
}) async {
  SharedPreferences.setMockInitialValues({});
  late _CountingMandate mandate;
  final container = ProviderContainer(
    overrides: [
      apiClientProvider.overrideWithValue(
        _ScriptedApiClient(chunks: chunks, throwAfter: throwAfter),
      ),
      mandateNotifierProvider.overrideWith((ref) {
        mandate = _CountingMandate(ref);
        return mandate;
      }),
    ],
  );
  addTearDown(container.dispose);

  final notifier =
      container.read(oneOnOneNotifierProvider('fundamentals_analyst').notifier);
  final sub = container.listen(
    oneOnOneNotifierProvider('fundamentals_analyst'),
    (_, __) {},
    fireImmediately: true,
  );
  addTearDown(sub.close);

  // Let the provider's auto-open microtask settle before sending.
  await Future<void>.delayed(Duration.zero);
  await notifier.send('What do you think of AAPL?');

  return (sub.read(), mandate);
}

void main() {
  test('a completed 1-on-1 turn refreshes the mandate exactly once',
      () async {
    final (state, mandate) = await _drive(chunks: ['Margins ', 'expanding.']);
    expect(state.streaming, isFalse);
    expect(state.error, isNull);
    expect(mandate.refreshCalls, 1);
  });

  test('a failed 1-on-1 turn also refreshes the mandate', () async {
    final (state, mandate) =
        await _drive(chunks: ['partial'], throwAfter: 'stream dropped');
    expect(state.streaming, isFalse);
    expect(state.error, isNotNull);
    expect(mandate.refreshCalls, 1);
  });
}
