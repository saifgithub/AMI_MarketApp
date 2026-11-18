/// WP-38 (CR267) / CR239 - the app's memory of the request trace ids the
/// backend echoed on its failed calls.
///
/// The backend mints one id per request (`HTTPAuditMiddleware`, `X-Request-Id`
/// header and the `request_id` field of every error body) and binds it onto
/// every log line of that request. This file is the client half: [ApiClient]
/// records the id of each failed response here, so
///   1. an error state can show it as a small copyable "Ref: abc12345"
///      (`TraceRefLine`) even when its own copy is a fixed localised string
///      that never saw the exception, and
///   2. the bug-report sheet can attach the last few of them, so a report
///      joins straight to `http_audit` and the log lines of the requests that
///      actually failed.
///
/// A request that never reached the server (DNS, offline, TLS) has no id; it
/// is recorded as a *gap* so a stale id from an earlier, unrelated failure is
/// never presented as the cause of the one on screen (CR040: never show a
/// confident wrong reference). The id is never user content - it is a random
/// UUID - so holding it in memory is not a privacy concern.
library;

import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart' show visibleForTesting;

/// One recorded failure. [id] is null for a request that got no response.
class TraceEntry {
  const TraceEntry({
    required this.id,
    required this.at,
    this.path,
    this.status,
  });

  final String? id;
  final DateTime at;
  final String? path;
  final int? status;
}

/// `RequestOptions.extra` key under which the interceptor stamps the id of a
/// failed response, for any caller that wants it without re-reading headers.
const String kTraceIdExtraKey = 'ami_trace_id';

/// A failure older than this is not offered as the reference for whatever
/// error is on screen now.
const Duration kTraceRefFreshness = Duration(minutes: 2);

/// The most ids a bug report carries (mirrors `MAX_TRACE_IDS` server-side).
const int kMaxReportTraceIds = 5;

class TraceIdStore {
  TraceIdStore({DateTime Function()? now}) : _now = now ?? DateTime.now;

  /// The app-wide store. [ApiClient] writes it; widgets and the bug-report
  /// path read it.
  static final TraceIdStore instance = TraceIdStore();

  static const int _capacity = 30;

  final DateTime Function() _now;
  final List<TraceEntry> _entries = []; // oldest first

  /// Record a failed response that carried [id].
  void record(String id, {String? path, int? status}) {
    _add(TraceEntry(id: id, at: _now(), path: path, status: status));
  }

  /// Record a failed request that got no response (so no id exists). Marks the
  /// most recent failure as one we cannot attribute to a server request.
  void recordNoResponse({String? path}) {
    _add(TraceEntry(id: null, at: _now(), path: path));
  }

  void _add(TraceEntry e) {
    _entries.add(e);
    if (_entries.length > _capacity) {
      _entries.removeRange(0, _entries.length - _capacity);
    }
  }

  /// The id to offer for the error currently on screen: the most recent
  /// failure's, provided it was a response that carried one and is fresh.
  String? recentId() {
    if (_entries.isEmpty) return null;
    final last = _entries.last;
    if (last.id == null) return null;
    if (_now().difference(last.at) > kTraceRefFreshness) return null;
    return last.id;
  }

  /// Up to [max] distinct recorded ids, newest first - what a bug report
  /// attaches. Unlike [recentId] there is no freshness window: a report filed
  /// a few minutes after the failure is exactly the case it exists for.
  List<String> recentIds({int max = kMaxReportTraceIds}) {
    final out = <String>[];
    for (final e in _entries.reversed) {
      final id = e.id;
      if (id != null && !out.contains(id)) out.add(id);
      if (out.length >= max) break;
    }
    return out;
  }

  /// The full id for a short on-screen prefix, if we recorded it.
  String? resolve(String idOrPrefix) {
    for (final e in _entries.reversed) {
      final id = e.id;
      if (id != null && id.startsWith(idOrPrefix)) return id;
    }
    return null;
  }

  @visibleForTesting
  void clear() => _entries.clear();
}

/// The trace id a backend response carries: the `X-Request-Id` header, falling
/// back to the `request_id` field of a JSON error body (a client that only
/// kept the body, or a proxy that stripped the header, still gets it).
String? traceIdFromResponse(Response<dynamic>? response) {
  if (response == null) return null;
  final header = response.headers.value('x-request-id');
  if (header != null && header.isNotEmpty) return header;
  final data = response.data;
  if (data is Map) {
    final v = data['request_id'];
    if (v is String && v.isNotEmpty) return v;
  }
  return null;
}

/// The short, screen-legible form of [id] (a git-style 8-character prefix).
String shortTraceId(String id) => id.length > 8 ? id.substring(0, 8) : id;

/// Matches the reference footnote `friendlyError` and the backend's SSE
/// `error` events append: `... Ref: a1b2c3d4.` - always last, always eight hex
/// characters. The lookbehind keeps the Room's `Run ref:` (a run id, a
/// different thing) out of it.
final RegExp _trailingRef =
    RegExp(r'\s*(?<!Run )Ref: ([0-9a-fA-F]{8})\.?\s*$');

/// Splits an error [message] into its headline and the trace reference it
/// ends with, if any. The headline is returned unchanged when there is none.
({String message, String? ref}) splitTraceRef(String message) {
  final m = _trailingRef.firstMatch(message);
  if (m == null) return (message: message, ref: null);
  return (message: message.substring(0, m.start), ref: m.group(1));
}
