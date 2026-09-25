/// CR236 round 2 (auditor MAJOR-1) — a Brief turn bills `brief_credit_cost`,
/// so the mandate must be refreshed after every completed `send()`, exactly
/// once, the same way `room_providers.dart` does after a Room's `done`
/// event. A failed send must refresh too — the backend charges before it
/// streams a byte (`brief.py`), so a client-visible failure can still be a
/// real charge (with or without a server-side refund already landed).
///
/// Mirrors the scripted-client pattern in `room_cr236_balance_after_test.dart`:
/// a counting fake `MandateNotifier` in place of the real network call.
library;

import 'package:ami_trade/models/brief.dart';
import 'package:ami_trade/models/one_on_one.dart';
import 'package:ami_trade/services/api/api_client.dart';
import 'package:ami_trade/state/brief_providers.dart';
import 'package:ami_trade/state/mandate_providers.dart';
import 'package:ami_trade/state/onboarding_providers.dart';
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

BriefSession _session() => BriefSession.fromJson({
      'id': 'b1',
      'user_id': 'u1',
      'agent_id': 'fundamentals_analyst',
      'mode': 'from_scratch',
      'locale': 'en',
      'base_overlay_version': 0,
    });

class _ScriptedApiClient extends ApiClient {
  _ScriptedApiClient({required this.chunks, this.throwAfter})
      : super(baseUrl: 'test://localhost');

  final List<String> chunks;
  final Object? throwAfter;

  @override
  Future<BriefStartResponse> startBrief({
    required String agentId,
    required String userId,
    String mode = 'from_scratch',
    String locale = 'en',
  }) async {
    return BriefStartResponse(session: _session(), openingMessage: 'Hi.');
  }

  @override
  Future<BriefHistory> briefHistory({
    required String userId,
    required String agentId,
    String plan = 'trial_trader',
  }) async {
    return BriefHistory.fromJson({
      'agent_id': agentId,
      'user_id': userId,
      'versions': <dynamic>[],
      'active_version': 0,
      'edit_count': 0,
    });
  }

  @override
  Stream<String> streamBriefMessage({
    required String sessionId,
    required String userMessage,
    required List<ChatMessage> history,
  }) async* {
    for (final c in chunks) {
      yield c;
    }
    if (throwAfter != null) {
      throw Exception(throwAfter);
    }
  }
}

Future<(BriefState, _CountingMandate)> _drive({
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
      container.read(briefNotifierProvider('fundamentals_analyst').notifier);
  final sub = container.listen(
    briefNotifierProvider('fundamentals_analyst'),
    (_, __) {},
    fireImmediately: true,
  );
  addTearDown(sub.close);

  // Let the provider's auto-open microtask (openSession + loadHistory)
  // settle before sending.
  await Future<void>.delayed(Duration.zero);
  await Future<void>.delayed(Duration.zero);
  await notifier.send('Tighten my stop-loss rule.');

  return (sub.read(), mandate);
}

void main() {
  test('a completed Brief turn refreshes the mandate exactly once', () async {
    final (state, mandate) = await _drive(chunks: ['Understood, ', 'noted.']);
    expect(state.streaming, isFalse);
    expect(state.error, isNull);
    expect(mandate.refreshCalls, 1);
  });

  test('a failed Brief turn also refreshes the mandate', () async {
    final (state, mandate) =
        await _drive(chunks: ['partial'], throwAfter: 'stream dropped');
    expect(state.streaming, isFalse);
    expect(state.error, isNotNull);
    expect(mandate.refreshCalls, 1);
  });
}
