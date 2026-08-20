/// CR181 guard — the persona-telemetry emitter (client half).
///
/// Three things this file must keep true:
///
/// 1. **Vocabulary parity.** `TelemetryEvents.all` is a hand-mirrored copy
///    of the backend's `TELEMETRY_EVENT_TYPES` tuple
///    (`backend/app/schemas/telemetry.py`) — no codegen crosses that seam,
///    so the parity test below reads the backend file and diffs the two.
///    An event name that drifts is a 422 at ingest, which the emitter's
///    retry loop would then hammer forever.
/// 2. **Event shape.** What goes over the wire must parse against
///    `TelemetryEventIn`: a UUID `event_id`, a known `event_type`, an
///    ISO-8601 UTC `occurred_at`, the locale in force, `count >= 1`, and
///    batches never over 500 (`TelemetryBatchIn.max_length`).
/// 3. **Fire-and-forget that keeps honest books (CR040).** A failed send
///    never throws into a caller; events are retained and retried; what the
///    bounded queue has to discard is counted into a `client_drop` marker
///    whose stable `event_id` makes the accounting idempotent server-side.
library;

import 'dart:io';

import 'package:ami_trade/services/telemetry/telemetry_emitter.dart';
import 'package:flutter_test/flutter_test.dart';

/// Capturing transport: records every attempt (delivered or not) into
/// [attempted], the successful ones into [batches], fails on demand.
class _Capture {
  final List<List<Map<String, dynamic>>> batches = [];
  final List<List<Map<String, dynamic>>> attempted = [];
  int attempts = 0;
  bool fail = false;

  Future<({int accepted, int duplicates})> send(
      List<Map<String, dynamic>> events) async {
    attempts += 1;
    final copy = events.map(Map<String, dynamic>.from).toList();
    attempted.add(copy);
    if (fail) throw Exception('telemetry backend down');
    batches.add(copy);
    return (accepted: events.length, duplicates: 0);
  }

  List<Map<String, dynamic>> get delivered =>
      [for (final b in batches) ...b];
}

/// Deterministic ids: id-1, id-2, ...
String Function() _idGen() {
  var n = 0;
  return () => 'id-${++n}';
}

TelemetryEmitter _emitter(
  _Capture capture, {
  Duration flushDelay = const Duration(hours: 1),
  Duration retryDelay = const Duration(hours: 1),
  int maxPending = 200,
  String? locale = 'en',
}) {
  return TelemetryEmitter(
    send: capture.send,
    locale: () => locale,
    flushDelay: flushDelay,
    retryDelay: retryDelay,
    maxPending: maxPending,
    now: () => DateTime.utc(2026, 8, 20, 12, 0, 0),
    newId: _idGen(),
  );
}

void main() {
  group('vocabulary parity with backend TELEMETRY_EVENT_TYPES', () {
    test('Dart list mirrors the backend tuple, same members, same order', () {
      // `mobile/` is Directory.current under `flutter test`.
      final source = File('../backend/app/schemas/telemetry.py')
          .readAsStringSync();
      final tuple = RegExp(
        r'TELEMETRY_EVENT_TYPES:\s*tuple\[str,\s*\.\.\.\]\s*=\s*\(([^)]*)\)',
        dotAll: true,
      ).firstMatch(source);
      expect(tuple, isNotNull,
          reason: 'TELEMETRY_EVENT_TYPES tuple not found in '
              'backend/app/schemas/telemetry.py — if it moved or was '
              'renamed, re-anchor this parity test');
      final backendTypes = RegExp(r'"([a-z_]+)"')
          .allMatches(tuple!.group(1)!)
          .map((m) => m.group(1))
          .toList();
      expect(TelemetryEvents.all, equals(backendTypes));
    });
  });

  group('event shape', () {
    test('one recorded event serializes to the TelemetryEventIn shape', () async {
      final capture = _Capture();
      final e = _emitter(capture, locale: 'ar');
      e.record(TelemetryEvents.appOpen);
      await e.flush();

      expect(capture.batches, hasLength(1));
      expect(capture.batches.single, hasLength(1));
      final ev = capture.batches.single.single;
      expect(
        ev.keys.toSet(),
        {'event_id', 'event_type', 'occurred_at', 'locale', 'count'},
      );
      expect(ev['event_id'], 'id-1');
      expect(ev['event_type'], 'app_open');
      expect(ev['occurred_at'], '2026-08-20T12:00:00.000Z');
      expect(DateTime.parse(ev['occurred_at'] as String).isUtc, isTrue);
      expect(ev['locale'], 'ar');
      expect(ev['count'], 1);
      e.dispose();
    });

    test('default id generator mints RFC-4122 UUIDs', () async {
      final capture = _Capture();
      final e = TelemetryEmitter(send: capture.send);
      e.record(TelemetryEvents.lessonOpen);
      await e.flush();
      final id = capture.delivered.single['event_id'] as String;
      expect(
        RegExp(r'^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-'
                r'[0-9a-f]{12}$')
            .hasMatch(id),
        isTrue,
        reason: 'backend parses event_id as a UUID; got: $id',
      );
      e.dispose();
    });

    test('an unknown event_type throws and queues nothing', () {
      final capture = _Capture();
      final e = _emitter(capture);
      expect(() => e.record('door_slam'), throwsArgumentError);
      expect(e.pendingEvents, isEmpty);
      e.dispose();
    });

    test('a batch never exceeds 500 events (TelemetryBatchIn cap)', () async {
      final capture = _Capture();
      final e = _emitter(capture, maxPending: 600);
      for (var i = 0; i < 505; i++) {
        e.record(TelemetryEvents.appOpen);
      }
      await e.flush();
      await e.flush();
      expect(capture.batches.first, hasLength(500));
      for (final b in capture.batches) {
        expect(b.length, lessThanOrEqualTo(500));
      }
      expect(capture.delivered, hasLength(505));
      expect(e.pendingEvents, isEmpty);
      e.dispose();
    });
  });

  group('batching', () {
    test('a burst of records rides one POST via the debounce timer', () async {
      final capture = _Capture();
      final e = _emitter(capture,
          flushDelay: const Duration(milliseconds: 5));
      e.record(TelemetryEvents.appOpen);
      e.record(TelemetryEvents.roomConvene);
      e.record(TelemetryEvents.tradePlace);
      expect(capture.attempts, 0, reason: 'debounce window still open');
      await Future<void>.delayed(const Duration(milliseconds: 100));
      expect(capture.batches, hasLength(1));
      expect(capture.batches.single, hasLength(3));
      e.dispose();
    });
  });

  group('fire-and-forget failure path (CR040 — honest books)', () {
    test('a failed send never throws, retains the events, delivers on retry',
        () async {
      final capture = _Capture();
      final e = _emitter(capture);
      e.record(TelemetryEvents.roomConvene);
      e.record(TelemetryEvents.lessonOpen);

      capture.fail = true;
      await e.flush(); // must complete normally — nothing to catch here
      expect(capture.attempts, 1);
      expect(capture.batches, isEmpty);
      expect(e.pendingEvents, hasLength(2),
          reason: 'a failed batch is retained, not discarded');

      capture.fail = false;
      await e.flush();
      expect(capture.delivered.map((ev) => ev['event_id']),
          ['id-1', 'id-2'],
          reason: 'the SAME events (same ids) go out on retry — the server '
              'dedups replays on event_id');
      expect(e.pendingEvents, isEmpty);
      e.dispose();
    });

    test('after a failure the retry timer flushes without a new record()',
        () async {
      final capture = _Capture();
      final e = _emitter(capture,
          retryDelay: const Duration(milliseconds: 5));
      e.record(TelemetryEvents.appOpen);
      capture.fail = true;
      await e.flush();
      expect(e.pendingEvents, hasLength(1));

      capture.fail = false;
      await Future<void>.delayed(const Duration(milliseconds: 100));
      expect(capture.delivered, hasLength(1));
      expect(e.pendingEvents, isEmpty);
      e.dispose();
    });

    test('overflow drops the OLDEST events and reports them as client_drop',
        () async {
      final capture = _Capture();
      final e = _emitter(capture, maxPending: 3);
      for (var i = 0; i < 5; i++) {
        e.record(TelemetryEvents.appOpen); // ids id-1 .. id-5
      }
      expect(e.pendingEvents, hasLength(3));
      expect(e.droppedCount, 2);
      expect(e.pendingEvents.first['event_id'], 'id-3',
          reason: 'the oldest two were discarded');

      await e.flush();
      final batch = capture.batches.single;
      expect(batch.first['event_type'], 'client_drop');
      expect(batch.first['count'], 2,
          reason: 'the marker carries how many events were discarded');
      expect(batch, hasLength(4)); // marker + the 3 surviving events
      expect(e.droppedCount, 0, reason: 'books settled after a success');

      await e.flush();
      expect(capture.batches, hasLength(1),
          reason: 'nothing left — no phantom marker on the next flush');
      e.dispose();
    });

    test('the drop marker keeps ONE id across failed retries (idempotent), '
        'and only a success clears it', () async {
      final capture = _Capture();
      final e = _emitter(capture, maxPending: 1);
      e.record(TelemetryEvents.appOpen);
      e.record(TelemetryEvents.appOpen);
      e.record(TelemetryEvents.appOpen); // 2 dropped, 1 pending
      expect(e.droppedCount, 2);

      capture.fail = true;
      // Failed attempts do not deliver; the marker id must not churn,
      // or a replayed batch double-counts drops server-side.
      await e.flush();
      await e.flush();
      capture.fail = false;
      await e.flush();
      expect(capture.attempted, hasLength(3));
      final seen = {
        for (final b in capture.attempted) b.first['event_id'] as String,
      };
      expect(seen, hasLength(1),
          reason: 'same marker event_id on every attempt of this cycle');
      expect(e.droppedCount, 0);

      // A fresh drop cycle mints a fresh marker id.
      e.record(TelemetryEvents.appOpen);
      e.record(TelemetryEvents.appOpen); // 1 dropped
      await e.flush();
      final markerIds = capture.batches
          .where((b) => b.first['event_type'] == 'client_drop')
          .map((b) => b.first['event_id'])
          .toSet();
      expect(markerIds, hasLength(2));
      e.dispose();
    });

    test('record() after dispose is a silent no-op', () {
      final capture = _Capture();
      final e = _emitter(capture);
      e.dispose();
      e.record(TelemetryEvents.appOpen);
      expect(e.pendingEvents, isEmpty);
    });

    test('flush() with nothing queued sends nothing', () async {
      final capture = _Capture();
      final e = _emitter(capture);
      await e.flush();
      expect(capture.attempts, 0);
      e.dispose();
    });
  });
}
