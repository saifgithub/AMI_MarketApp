/// CR109 — the client must parse what the backend ACTUALLY sends.
///
/// Both fixtures below are copied verbatim from live Alpha responses, not
/// from the design doc. That distinction is the point of this file: the doc
/// described the fields and never the envelope, and both lanes were unit
/// tested against their own idea of the contract, so both were green while
/// the app was broken.
///
/// Two real failures this pins:
///
///  1. `/v1/games/runs` and `/v1/games/cadences` return a BARE JSON ARRAY.
///     The client asked Dio for `Map<String, dynamic>` and read an envelope
///     (`data['runs']`), so the cast threw and the screen showed
///     "Couldn't load your game runs" sitting on top of an HTTP 200. The
///     server log said success; the user saw failure.
///
///  2. The cadence payload carries the next field FLAT (`field_id`, `state`,
///     `starts_on`, …) rather than nested under `next_field`, and names three
///     keys differently: `state`, `deadline`, `already_held`. Every read was
///     null-safe, so this one did NOT throw — it quietly produced a cadence
///     with no field, no deadline and `alreadyHolds: false`. A silent wrong
///     answer, which is the worse of the two.
library;

import 'package:ami_trade/models/games.dart';
import 'package:flutter_test/flutter_test.dart';

/// Verbatim from `GET /v1/games/cadences` on Alpha, 2026-08-09.
const _liveCadence = <String, dynamic>{
  'cadence': 'week',
  'field_id': 'c1289fe9-2bed-4ee4-a00a-18758df2a648',
  'state': 'entry_open',
  'entry_opens_at': '2026-08-03T09:00:00-04:00',
  'locks_at': '2026-08-10T09:00:00-04:00',
  'starts_on': '2026-08-10',
  'ends_on': '2026-08-14',
  'queue_count': 0,
  'deadline': '2026-08-10T09:00:00-04:00',
  'already_held': false,
};

/// Verbatim from `GET /v1/games/runs` on Alpha, 2026-08-09.
const _liveRun = <String, dynamic>{
  'run_id': '58219342-7206-42e7-9140-7712f0f85726',
  'field_id': 'c1289fe9-2bed-4ee4-a00a-18758df2a648',
  'cadence': 'week',
  'state': 'entered',
  'intent': 'thesis',
  'twr_pct': null,
  'days_left': 5,
  'starts_on': '2026-08-10',
  'ends_on': '2026-08-14',
  'fees_paid': 0.0,
  'trade_count': 0,
};

void main() {
  group('cadence payload — the flat shape the backend really sends', () {
    test('resolves the next field even though it is not nested', () {
      final c = GameCadenceInfo.fromJson(_liveCadence);
      expect(
        c.nextField,
        isNotNull,
        reason: 'a null field renders an entry card that cannot say when '
            'entry closes — the silent half of this defect',
      );
      expect(c.nextField!.fieldId, 'c1289fe9-2bed-4ee4-a00a-18758df2a648');
      expect(c.nextField!.startsOn, DateTime.parse('2026-08-10'));
    });

    test('reads state / deadline / already_held under the names sent', () {
      final c = GameCadenceInfo.fromJson(_liveCadence);
      expect(c.entryState, 'entry_open');
      expect(c.queueDeadline, isNotNull);
      expect(c.alreadyHolds, isFalse);
    });

    test('already_held true is not silently dropped', () {
      final c = GameCadenceInfo.fromJson({..._liveCadence, 'already_held': true});
      expect(
        c.alreadyHolds,
        isTrue,
        reason: 'dropping this shows "enter this field" to a player who is '
            'already in, and the enter call then 409s',
      );
    });

    test('still accepts the nested/enveloped shape, if it ever ships', () {
      final c = GameCadenceInfo.fromJson({
        'cadence': 'week',
        'next_field': {'field_id': 'abc', 'starts_on': '2026-08-10'},
        'entry_state': 'entry_open',
        'queue_deadline': '2026-08-10T09:00:00-04:00',
        'already_holds': true,
      });
      expect(c.nextField!.fieldId, 'abc');
      expect(c.entryState, 'entry_open');
      expect(c.alreadyHolds, isTrue);
    });
  });

  group('run payload', () {
    test('parses the live shape', () {
      final r = GameRunSummary.fromJson(_liveRun);
      expect(r.runId, '58219342-7206-42e7-9140-7712f0f85726');
      expect(r.cadence, 'week');
      expect(r.daysLeft, 5);
      expect(r.twrPct, isNull, reason: 'no NAV history yet — null, not 0.0');
    });
  });
}
