/// CR181 — persona telemetry emitter (the client half).
///
/// Batches the deterministic UI-interaction events behind the four persona
/// segments (bounce / convene / depth / locale) and posts them to
/// `POST /v1/telemetry/events`, fire-and-forget: a failed send NEVER
/// surfaces to the user or throws into a caller. It is logged, the batch is
/// retained and retried, and anything the emitter has to discard (queue
/// overflow, so memory stays bounded offline) is counted and reported as a
/// `client_drop` marker event on the next successful flush — a drop is
/// countable, never silently absorbed (CR040).
///
/// [TelemetryEvents.all] is the lockstep mirror of the backend's canonical
/// vocabulary (`backend/app/schemas/telemetry.py::TELEMETRY_EVENT_TYPES`);
/// the parity test in `test/services/telemetry_emitter_test.dart` anchors
/// the two files to each other. The payload carries NO PII: the backend
/// takes `user_id` from the bearer token (there is nowhere to name one in
/// the body), and `locale` is a setting, not a location. `event_id` is a
/// client-minted UUID — the server dedups on (user_id, event_id), so a
/// retried batch whose first attempt actually landed is absorbed as
/// `duplicates`, not double-counted.
library;

import 'dart:async';

import 'package:flutter/foundation.dart' show debugPrint, visibleForTesting;
import 'package:uuid/uuid.dart';

/// The wire vocabulary. One name per interaction point; `clientDrop` is the
/// emitter's own failure accounting and is never recorded by a call site.
abstract final class TelemetryEvents {
  static const String appOpen = 'app_open';
  static const String roomConvene = 'room_convene';
  static const String oneOnOneOpen = 'one_on_one_open';
  static const String firmOpen = 'firm_open';
  static const String lessonOpen = 'lesson_open';
  static const String tradePlace = 'trade_place';
  static const String challengeAttempt = 'challenge_attempt';
  static const String briefEdit = 'brief_edit';
  static const String clientDrop = 'client_drop';

  /// Same members, same order, as the backend's TELEMETRY_EVENT_TYPES.
  static const List<String> all = [
    appOpen,
    roomConvene,
    oneOnOneOpen,
    firmOpen,
    lessonOpen,
    tradePlace,
    challengeAttempt,
    briefEdit,
    clientDrop,
  ];
}

/// The transport: one batched POST, returning the server's own accounting.
/// In the app this is `ApiClient.telemetryEvents`; tests inject a capture.
typedef TelemetrySend = Future<({int accepted, int duplicates})> Function(
    List<Map<String, dynamic>> events);

class TelemetryEmitter {
  TelemetryEmitter({
    required TelemetrySend send,
    String? Function()? locale,
    this.flushDelay = const Duration(seconds: 3),
    this.retryDelay = const Duration(seconds: 30),
    this.maxPending = 200,
    DateTime Function()? now,
    String Function()? newId,
  })  : _send = send,
        _locale = locale,
        _now = now ?? DateTime.now,
        _newId = newId ?? (() => const Uuid().v4());

  /// TelemetryBatchIn's max_length on the backend — never exceeded per POST.
  static const int maxBatch = 500;

  final TelemetrySend _send;
  final String? Function()? _locale;

  /// Debounce window between the first queued event and the POST, so a
  /// burst of taps rides one request.
  final Duration flushDelay;

  /// Back-off after a failed POST. Events stay queued in between.
  final Duration retryDelay;

  /// Queue bound. Beyond it the OLDEST event is discarded and counted into
  /// the next `client_drop` marker — bounded memory, honest books.
  final int maxPending;

  final DateTime Function() _now;
  final String Function() _newId;

  final List<Map<String, dynamic>> _pending = [];
  int _dropped = 0;

  /// Stable id for the in-flight `client_drop` marker, so a retried marker
  /// batch dedups server-side instead of double-counting drops. Minted
  /// lazily, cleared only when a flush carrying it succeeds.
  String? _dropMarkerId;

  Timer? _flushTimer;
  bool _flushing = false;
  bool _disposed = false;

  @visibleForTesting
  List<Map<String, dynamic>> get pendingEvents => List.unmodifiable(_pending);

  @visibleForTesting
  int get droppedCount => _dropped;

  /// Queue one event, capture the locale in force NOW, schedule a flush.
  /// Synchronous and non-throwing for every name in [TelemetryEvents.all] —
  /// an unknown name is a programming error and throws [ArgumentError]
  /// (call sites use the constants, so this can only fire in development).
  void record(String eventType) {
    if (!TelemetryEvents.all.contains(eventType)) {
      throw ArgumentError.value(
        eventType,
        'eventType',
        'unknown telemetry event_type; allowed: '
            '${TelemetryEvents.all.join(', ')}',
      );
    }
    if (_disposed) return;
    _pending.add({
      'event_id': _newId(),
      'event_type': eventType,
      'occurred_at': _now().toUtc().toIso8601String(),
      'locale': _locale?.call(),
      'count': 1,
    });
    while (_pending.length > maxPending) {
      _pending.removeAt(0);
      _dropped += 1;
      debugPrint(
          'telemetry: queue over $maxPending, dropped oldest (dropped=$_dropped)');
    }
    _scheduleFlush(flushDelay);
  }

  void _scheduleFlush(Duration delay) {
    if (_disposed || _flushing || _flushTimer != null) return;
    _flushTimer = Timer(delay, () {
      _flushTimer = null;
      unawaited(flush());
    });
  }

  /// Send what is queued (plus the drop marker, when drops are owed), up to
  /// [maxBatch] events. Never throws: a failure logs, keeps the batch, and
  /// re-schedules itself after [retryDelay]. Also safe to call directly —
  /// the app does on backgrounding, so a session's tail isn't lost to the
  /// debounce window.
  Future<void> flush() async {
    if (_disposed || _flushing) return;
    // Consume any parked debounce timer: this flush is about to do its job,
    // and a stale pending timer would otherwise block [_scheduleFlush] from
    // arming the retry after a failure (found by the retry-timer test).
    _flushTimer?.cancel();
    _flushTimer = null;
    final batch = <Map<String, dynamic>>[];
    final markerCount = _dropped;
    if (markerCount > 0) {
      _dropMarkerId ??= _newId();
      batch.add({
        'event_id': _dropMarkerId,
        'event_type': TelemetryEvents.clientDrop,
        'occurred_at': _now().toUtc().toIso8601String(),
        'locale': _locale?.call(),
        'count': markerCount,
      });
    }
    final take = _pending.take(maxBatch - batch.length).toList();
    batch.addAll(take);
    if (batch.isEmpty) return;
    _flushing = true;
    try {
      final result = await _send(batch);
      _pending.removeRange(0, take.length);
      if (markerCount > 0) {
        _dropped -= markerCount;
        _dropMarkerId = null;
      }
      if (result.duplicates > 0) {
        debugPrint(
            'telemetry: flushed ${batch.length} events, ${result.duplicates} '
            'were server-side duplicates (retried batch had landed)');
      }
      _flushing = false;
      if (_pending.isNotEmpty || _dropped > 0) {
        _scheduleFlush(Duration.zero);
      }
    } catch (e) {
      _flushing = false;
      debugPrint('telemetry: flush of ${batch.length} events failed, '
          'retrying in ${retryDelay.inSeconds}s: $e');
      _scheduleFlush(retryDelay);
    }
  }

  /// Stop timers. Anything still queued is lost — logged loudly, because a
  /// dead emitter cannot post its own drop marker. Only the provider
  /// teardown path calls this (backend-mode flip in dev, test containers).
  void dispose() {
    if (_disposed) return;
    _disposed = true;
    _flushTimer?.cancel();
    _flushTimer = null;
    if (_pending.isNotEmpty || _dropped > 0) {
      debugPrint('telemetry: disposed with ${_pending.length} unsent events '
          'and $_dropped uncounted drops — lost with this emitter');
    }
  }
}
