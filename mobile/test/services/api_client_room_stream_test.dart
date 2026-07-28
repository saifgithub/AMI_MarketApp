/// CR090 contract guard — the fixture below is transcribed directly from the
/// backend SSE payload construction, not from `parseRoomSseEvent`'s own
/// switch cases. A fixture mirrored off this file's own model would only
/// ever contain the keys the parser already reads, reproducing a
/// silently-dropped-field bug instead of catching it (the CR100 defect
/// class — see `sim_cr100_contract_test.dart`).
///
/// Transcribed from:
///   - `backend/app/api/room.py:225-232` on `lane/CR090-ROOM.coder.room` @
///     `e06ed4b` — the `event: live_data_notice\ndata: {...}\n\n` frame shape.
///   - `backend/app/services/room_runner.py:1769-1777` (same branch/commit)
///     — the exact dict keys/values: `news`, `social` (each a lowercase
///     `LiveDataState.value`: `live` / `withheld_paid` / `unavailable`),
///     `surcharge_charged` (int, `max(0, credit_cost - room_cost_for_plan)`).
/// Read from source 2026-07-27.
library;

import 'package:ami_trade/services/api/api_client.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('CR090 — live_data_notice contract', () {
    test('parses a real backend frame (news withheld, social unavailable)', () {
      // Transcribed verbatim from the assign doc's paste of room.py:225-232,
      // itself lifted from room_runner.py's live_data dict construction.
      const data = '{"news": "withheld_paid", "social": "unavailable", '
          '"surcharge_charged": 0}';
      final parsed = parseRoomSseEvent('live_data_notice', data);

      expect(parsed, isNotNull);
      expect(parsed!['kind'], 'live_data_notice');
      expect(parsed['news'], 'withheld_paid');
      expect(parsed['social'], 'unavailable');
      expect(parsed['surcharge_charged'], 0);
    });

    test('parses the live-both-feeds shape with a non-zero surcharge', () {
      // Live feeds cost 2 credits each per the runner (room_runner.py:1486,
      // live_data_surcharge) — 2 LIVE feeds -> surcharge_charged: 4.
      const data =
          '{"news": "live", "social": "live", "surcharge_charged": 4}';
      final parsed = parseRoomSseEvent('live_data_notice', data);

      expect(parsed!['news'], 'live');
      expect(parsed['social'], 'live');
      expect(parsed['surcharge_charged'], 4);
    });

    test('an unrecognised event kind is dropped, not thrown (D2)', () {
      expect(
        () => parseRoomSseEvent('some_future_event_kind', '{"x": 1}'),
        returnsNormally,
      );
      expect(parseRoomSseEvent('some_future_event_kind', '{"x": 1}'), isNull);
    });

    test('garbage data under a known kind is dropped, not thrown', () {
      expect(
        () => parseRoomSseEvent('live_data_notice', 'not json at all'),
        returnsNormally,
      );
      expect(parseRoomSseEvent('live_data_notice', 'not json at all'), isNull);
    });

    test('parses agent_withheld (CR098) with a roster-level next step', () {
      // Transcribed from `backend/app/api/room.py:248-260` — the client's
      // own SSE parser silently dropped this kind before this test was
      // written (default branch -> null, see the acceptance-#2 note in the
      // CR098-MOBILE-LIVE hand-off).
      const data = '{"agent_id": "market_analyst", "reason": "upgrade", '
          '"next_step_agent": "social_media_analyst", "next_step_days": 4}';
      final parsed = parseRoomSseEvent('agent_withheld', data);

      expect(parsed, isNotNull);
      expect(parsed!['kind'], 'agent_withheld');
      expect(parsed['agent_id'], 'market_analyst');
      expect(parsed['reason'], 'upgrade');
      expect(parsed['next_step_agent'], 'social_media_analyst');
      expect(parsed['next_step_days'], 4);
    });

    test('parses agent_withheld with next_step both null', () {
      const data = '{"agent_id": "social_media_analyst", "reason": "upgrade", '
          '"next_step_agent": null, "next_step_days": null}';
      final parsed = parseRoomSseEvent('agent_withheld', data);

      expect(parsed!['next_step_agent'], isNull);
      expect(parsed['next_step_days'], isNull);
    });

    test('existing event kinds are unaffected by the CR090 addition', () {
      final started = parseRoomSseEvent('started', '{"run_id": "abc123"}');
      expect(started!['kind'], 'started');
      expect(started['run_id'], 'abc123');

      final done = parseRoomSseEvent('done', '{"run_id": "abc123"}');
      expect(done!['kind'], 'done');
    });
  });
}
