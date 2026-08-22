/// REST client for the AMI Trade backend.
///
/// Base URL resolution priority:
///   1. AMI_API_URL Dart define (`--dart-define=AMI_API_URL=https://api...`)
///   2. Compile-time default for the platform:
///      - iOS simulator → http://localhost:8000
///      - Physical iOS device → http://HOST_LAN_IP:8000 (override via env)
///      - macOS / web → http://localhost:8000
library;

import 'dart:async';
import 'dart:convert';
import 'dart:io' show Platform;

import 'package:flutter/foundation.dart' show debugPrint, visibleForTesting;

import 'package:ami_trade/models/app_notification.dart';
import 'package:ami_trade/models/auth.dart';
import 'package:ami_trade/models/ai_coach.dart';
import 'package:ami_trade/models/billing_identity.dart';
import 'package:ami_trade/models/brief.dart';
import 'package:ami_trade/models/daily_challenge.dart';
import 'package:ami_trade/models/feedback.dart';
import 'package:ami_trade/models/games.dart';
import 'package:ami_trade/models/inbox_message.dart';
import 'package:ami_trade/models/journal.dart';
import 'package:ami_trade/models/league.dart';
import 'package:ami_trade/models/lessons.dart';
import 'package:ami_trade/models/mandate.dart';
import 'package:ami_trade/models/merge.dart';
import 'package:ami_trade/models/one_on_one.dart';
import 'package:ami_trade/models/onboarding.dart';
import 'package:ami_trade/models/portfolio_health.dart';
import 'package:ami_trade/models/price_alert.dart';
import 'package:ami_trade/models/release_floor.dart';
import 'package:ami_trade/models/room.dart';
import 'package:ami_trade/models/sector_watch.dart';
import 'package:ami_trade/models/sim.dart';
import 'package:ami_trade/models/sim_resting_order.dart';
import 'package:ami_trade/models/tickers.dart';
import 'package:ami_trade/models/watchlist.dart';
import 'package:ami_trade/services/api/api_exceptions.dart';
import 'package:ami_trade/services/api/friendly_error.dart' show kAmiWaitsOnModel;
import 'package:ami_trade/services/yahoo_finance_service.dart';
import 'package:dio/dio.dart';
import 'package:http/http.dart' as http;

const String _apiUrlFromEnv = String.fromEnvironment(
  'AMI_API_URL',
  defaultValue: '',
);

String _resolveBaseUrl() {
  if (_apiUrlFromEnv.isNotEmpty) return _apiUrlFromEnv;
  if (Platform.isIOS || Platform.isAndroid) {
    return 'http://localhost:8000';
  }
  return 'http://localhost:8000';
}

class _AuthInterceptor extends Interceptor {
  _AuthInterceptor(this._client);
  final ApiClient _client;

  @override
  void onRequest(RequestOptions options, RequestInterceptorHandler handler) {
    final token = _client._bearerToken;
    if (token != null) {
      options.headers['Authorization'] = 'Bearer $token';
    }
    // CR121: the version-gate header, set alongside the bearer at this same
    // single choke point. Sourced from DeviceContext.appVersion
    // (device_user.dart) via ApiClient.setAppVersion — nothing new is
    // computed here, same shape as the token above. Omitted (not sent as an
    // empty string) until bootstrap has read it once, so the server's
    // build-number parser only ever sees a real value or no header at all.
    final appVersion = _client._appVersion;
    if (appVersion != null) {
      options.headers['X-App-Version'] = appVersion;
    }
    handler.next(options);
  }

  @override
  void onError(DioException err, ErrorInterceptorHandler handler) {
    if (err.response?.statusCode == 401) {
      _client._handleUnauthorized(err.requestOptions.path);
    }
    handler.next(err);
  }
}

/// DEF073: annotate any 5xx response with a [ServerUnavailableException] on the
/// `DioException.error` slot, centralizing 5xx detection for REST callers. Purely
/// additive — the exception still propagates as a `DioException` with its original
/// type/message, so existing `catch` blocks are unchanged, while call sites that
/// want a friendly path can check `e is DioException && e.error is
/// ServerUnavailableException` (or `serverUnavailableFrom(e)`).
class _ServerErrorInterceptor extends Interceptor {
  @override
  void onError(DioException err, ErrorInterceptorHandler handler) {
    final code = err.response?.statusCode;
    if (code != null && code >= 500) {
      handler.next(DioException(
        requestOptions: err.requestOptions,
        response: err.response,
        type: err.type,
        message: err.message,
        stackTrace: err.stackTrace,
        error: ServerUnavailableException(code),
      ));
      return;
    }
    handler.next(err);
  }
}

/// Extract a [ServerUnavailableException] from a thrown REST error, if the 5xx
/// interceptor annotated it. Returns null for any other error (DEF073).
ServerUnavailableException? serverUnavailableFrom(Object error) {
  if (error is ServerUnavailableException) return error;
  if (error is DioException && error.error is ServerUnavailableException) {
    return error.error as ServerUnavailableException;
  }
  return null;
}

/// CR125 — the decision half of [_AuthInterceptor]'s 401-recovery guard,
/// pulled out pure and testable the same way [upgradeRequiredExceptionFor]
/// is. Returns true when a 401 on [path] should fire [ApiClient.onUnauthorized]:
///   - never for the auth router itself (`/v1/auth/*`) — those flows
///     (magic-link, Apple/Google claim, explicit sign-out) already surface
///     their own errors and must not be short-circuited by a background
///     recovery.
///   - never when no bearer was attached — an anonymous/unauthenticated
///     request can't have been "unauthorized" in the revocable-token sense.
///   - never twice for the same [bearerToken] — the retry-loop guard: a
///     backend that keeps 401ing even a freshly re-bootstrapped token can
///     only trigger one recovery attempt per distinct token it rejects.
@visibleForTesting
bool shouldRecoverFromUnauthorized({
  required String path,
  required String? bearerToken,
  required String? lastUnauthorizedToken,
}) {
  if (path.startsWith('/v1/auth/')) return false;
  if (bearerToken == null) return false;
  if (bearerToken == lastUnauthorizedToken) return false;
  return true;
}

/// CR121 — the decision half of [_VersionGateInterceptor], pulled out as a
/// pure, side-effect-free function for the same reason [parseRoomSseEvent]
/// is: the interceptor class itself is private to this library (matching
/// DEF073's `_ServerErrorInterceptor`), but the "is this a 426 the gate
/// should raise" question needs to be directly unit-testable against a real
/// backend-shaped response, not only exercisable through a live HTTP round
/// trip. Returns null for any status other than 426 (including 5xx, which
/// stays [_ServerErrorInterceptor]'s to annotate).
@visibleForTesting
UpgradeRequiredException? upgradeRequiredExceptionFor(DioException err) {
  final code = err.response?.statusCode;
  if (code != 426) return null;
  final data = err.response?.data;
  if (data is Map<String, dynamic>) {
    return UpgradeRequiredException.fromJson(data);
  }
  // 426 with an unparseable/missing body still means "raise the gate" —
  // the caller degrades to the generic chrome copy rather than the
  // per-raise message, never to "not gated at all".
  return const UpgradeRequiredException();
}

/// CR121: catches HTTP 426 (Upgrade Required — the client version floor)
/// and annotates it onto the `DioException.error` slot, same shape as
/// DEF073's [_ServerErrorInterceptor] one class above. Purely additive —
/// the exception still propagates as a `DioException`, so existing `catch`
/// blocks are unchanged; a call site that wants the structured gate detail
/// checks `upgradeRequiredFrom(e)`.
class _VersionGateInterceptor extends Interceptor {
  _VersionGateInterceptor(this._client);

  final ApiClient _client;

  @override
  void onError(DioException err, ErrorInterceptorHandler handler) {
    final upgrade = upgradeRequiredExceptionFor(err);
    if (upgrade != null) {
      // CR121 audit MAJOR: annotating the exception is not enough on its own.
      // Every one of the 15 call sites funnels errors through
      // `friendlyError`, which turned a 426 into "that request wasn't
      // accepted" — so the middleware's whole reason to exist ("a patched
      // binary that never calls the floor endpoint still cannot transact")
      // produced a refusal with no screen, no headline and no way to update.
      // The gate's own launch/resume checks don't cover the window between a
      // floor being raised mid-session and the next backgrounding, which is
      // precisely the window the middleware is for. Raising it here means any
      // 426, from any call, surfaces the real block screen.
      _client.onUpgradeRequired?.call(upgrade);
      handler.next(DioException(
        requestOptions: err.requestOptions,
        response: err.response,
        type: err.type,
        message: err.message,
        stackTrace: err.stackTrace,
        error: upgrade,
      ));
      return;
    }
    handler.next(err);
  }
}

/// Extract an [UpgradeRequiredException] from a thrown REST error, if
/// [_VersionGateInterceptor] annotated it. Returns null for any other error
/// (same shape as [serverUnavailableFrom]).
UpgradeRequiredException? upgradeRequiredFrom(Object error) =>
    asUpgradeRequired(error);

/// Inverts the backend's per-chunk SSE escape (`room.py`, `brief.py`,
/// `one_on_one.py`: `chunk.replace("\\", "\\\\").replace("\n", "\\n")`).
///
/// DEF114: the previously-shipped `.replaceAll(r'\n', '\n').replaceAll(r'\\',
/// r'\')` pair cannot invert that encode in either order — the first pass
/// matches across an escape boundary (e.g. `C:\next` decodes wrong because
/// the literal `\n` inside it gets read as a newline escape). A single
/// left-to-right scan that consumes escape pairs atomically is the only
/// correct inverse; each backend sender escapes every chunk independently
/// and completely, so no escape sequence spans a chunk boundary (D3) and
/// per-chunk decoding is safe.
@visibleForTesting
String unescapeSseText(String s) {
  final buffer = StringBuffer();
  var i = 0;
  while (i < s.length) {
    final ch = s[i];
    if (ch == r'\' && i + 1 < s.length) {
      final next = s[i + 1];
      if (next == r'\') {
        buffer.write(r'\');
      } else if (next == 'n') {
        buffer.write('\n');
      } else {
        buffer.write(ch);
        buffer.write(next);
      }
      i += 2;
      continue;
    }
    buffer.write(ch);
    i += 1;
  }
  return buffer.toString();
}

/// Parse one decoded SSE event block (`event: <type>` + joined `data:` lines)
/// from the Room stream into the typed map the notifier consumes, or `null`
/// if the block is malformed or its kind isn't recognised.
///
/// Extracted to a top-level, side-effect-free (besides the CR090 (D2) log
/// line) function so the parsing contract is directly unit-testable against
/// a real backend-transcribed frame — see api_client_room_stream_test.dart.
///
/// CR090 (D2): an unrecognised `eventType` returns `null` (dropped, logged),
/// never throws — a client on this build must not crash when a newer
/// backend adds an event kind it doesn't know about yet.
@visibleForTesting
Map<String, dynamic>? parseRoomSseEvent(String eventType, String data) {
  try {
    switch (eventType) {
      case 'started':
        final j = jsonDecode(data) as Map<String, dynamic>;
        return {'kind': 'started', 'run_id': j['run_id']};
      case 'phase':
        final j = jsonDecode(data) as Map<String, dynamic>;
        return {'kind': 'phase', 'label': j['label']};
      case 'live_data_notice':
        // CR090: structural live-data disclosure, one per run. Returned
        // as-is (news/social/surcharge_charged) — the notifier owns
        // rendering. See room_providers.dart for the D3/D4/D5 rules.
        final j = jsonDecode(data) as Map<String, dynamic>;
        return {
          'kind': 'live_data_notice',
          'news': j['news'],
          'social': j['social'],
          'surcharge_charged': j['surcharge_charged'],
        };
      case 'agent_token':
        final j = jsonDecode(data) as Map<String, dynamic>;
        final text = unescapeSseText(j['text'] as String? ?? '');
        return {'kind': 'agent_token', 'agent_id': j['agent_id'], 'text': text};
      case 'agent_done':
        // CR106 B2 — the agent's own stated position rides its completion
        // event. `containsKey` on the decoded map is what tells the client the
        // run recorded stances AT ALL: a server that predates B2 sends neither
        // key, and that is a different fact from an agent that took no side.
        final j = jsonDecode(data) as Map<String, dynamic>;
        return {
          'kind': 'agent_done',
          'agent_id': j['agent_id'],
          if (j.containsKey('stance')) 'stance': j['stance'],
          if (j.containsKey('conviction')) 'conviction': j['conviction'],
          if (j.containsKey('headline')) 'headline': j['headline'],
        };
      case 'agent_withheld':
        // CR098 — one per withheld analyst, emitted before any analyst
        // speaks. `next_step_agent`/`next_step_days` are roster-level (the
        // SAME value on every event this run) — never a per-agent countdown.
        final j = jsonDecode(data) as Map<String, dynamic>;
        return {
          'kind': 'agent_withheld',
          'agent_id': j['agent_id'],
          'reason': j['reason'],
          'next_step_agent': j['next_step_agent'],
          'next_step_days': j['next_step_days'],
        };
      case 'verdict':
        final j = jsonDecode(data) as Map<String, dynamic>;
        return {'kind': 'verdict', 'verdict': RoomVerdict.fromJson(j)};
      case 'done':
        final j = jsonDecode(data) as Map<String, dynamic>;
        return {'kind': 'done', 'run_id': j['run_id']};
      case 'error':
        return {'kind': 'error', 'message': unescapeSseText(data)};
      default:
        // CR040 degrade loudly: log only, never surface to the user.
        debugPrint('room stream: unknown event kind "$eventType"');
        return null;
    }
  } catch (e) {
    // skip malformed event
    return null;
  }
}

class ApiClient {
  /// DEF114 (D4): [httpClient] is the transport the three SSE streams
  /// (`streamBriefMessage`, `streamOneOnOneMessage`, `streamRoom`) send
  /// through, in place of each building its own `http.Client()` inline —
  /// that made "does `done` terminate the stream?" untestable. Defaults to
  /// a real `http.Client()`; tests inject a fake to control the response.
  ApiClient({String? baseUrl, http.Client? httpClient})
      : _dio = Dio(BaseOptions(
          baseUrl: baseUrl ?? _resolveBaseUrl(),
          connectTimeout: const Duration(seconds: 10),
          receiveTimeout: const Duration(seconds: 30),
          headers: {'Content-Type': 'application/json'},
        )),
        _httpClient = httpClient ?? http.Client() {
    _dio.interceptors.add(_AuthInterceptor(this));
    _dio.interceptors.add(_ServerErrorInterceptor()); // DEF073
    _dio.interceptors.add(_VersionGateInterceptor(this)); // CR121
  }

  final Dio _dio;
  final http.Client _httpClient;
  String? _bearerToken;
  String? _appVersion;

  /// CR125 — fired when a guarded request 401s (expired `exp`, or a
  /// `token_version` revoked by a sign-out on another session). Wired by
  /// [AuthNotifier] to clear the local credential and re-bootstrap an
  /// anonymous session, the same recovery path a manual sign-out already
  /// takes. Left null (no-op) outside the app's Riverpod wiring, e.g. in
  /// tests that talk to [ApiClient] directly.
  void Function()? onUnauthorized;

  /// CR121 — fired when any request is refused with 426 by
  /// `VersionGateMiddleware`. Wired by `versionGateControllerProvider` to
  /// raise the block screen, so a floor raised mid-session reaches the user
  /// on their next request rather than waiting for a backgrounding. Left
  /// null (no-op) outside the app's Riverpod wiring, e.g. in tests that talk
  /// to [ApiClient] directly.
  void Function(UpgradeRequiredException)? onUpgradeRequired;

  /// CR125 retry-loop guard: the token that most recently triggered
  /// [onUnauthorized]. A 401 only fires the callback once per distinct
  /// bearer — the auth routes themselves are excluded (they own their own
  /// error handling), and a request with no bearer attached can't be
  /// "unauthorized" in the recoverable sense, so both are ignored.
  String? _lastUnauthorizedToken;

  void _handleUnauthorized(String path) {
    final token = _bearerToken;
    if (!shouldRecoverFromUnauthorized(
      path: path,
      bearerToken: token,
      lastUnauthorizedToken: _lastUnauthorizedToken,
    )) {
      return;
    }
    _lastUnauthorizedToken = token;
    onUnauthorized?.call();
  }

  void setToken(String? token) {
    _bearerToken = token;
  }

  /// CR121: the version string sent as `X-App-Version` on every request from
  /// here on (via `_AuthInterceptor`). Set once from `DeviceContext.appVersion`
  /// during auth bootstrap — same "compute once, replay on every request"
  /// shape as [setToken].
  void setAppVersion(String? version) {
    _appVersion = version;
  }

  /// Build a raw `http.Request` for SSE endpoints that can't go through Dio.
  /// Adversarial audit (2026-05-18) finding A8: previously these requests
  /// bypassed the Dio interceptor and sent no Authorization header, so
  /// `/v1/brief/message`, `/v1/agents/one_on_one/message`, and
  /// `/v1/room/stream` would 401 once the backend enforced auth.
  /// CR125 audit MAJOR — the three SSE routes send via raw
  /// `_httpClient.send()` (see [_sseRequest]) and so bypass every Dio
  /// interceptor, including the one that fires [onUnauthorized]. That was
  /// pre-existing (AT:R33 finding A8) and harmless while tokens never
  /// expired; CR125 is what makes a 401 on these routes routine rather than
  /// attacker-only. Without this, a mid-session revocation on Convene the
  /// Room, a Brief, or a 1-on-1 — the app's three flagship interactive
  /// surfaces — throws an inert exception, and retrying keeps 401ing until
  /// some unrelated Dio call happens to trigger recovery or the user
  /// force-quits.
  ///
  /// Deliberately fires only on 401. A 403 is an authorization decision
  /// about a valid identity; clearing the session over one would log the
  /// user out of an account that is working fine.
  void _notifyIfUnauthorized(int statusCode) {
    if (statusCode == 401) onUnauthorized?.call();
  }

  http.Request _sseRequest(Uri uri, String body) {
    final token = _bearerToken;
    if (token == null) {
      throw StateError(
        'SSE request attempted before auth bootstrap completed — '
        'no Bearer token available',
      );
    }
    return http.Request('POST', uri)
      ..headers['Content-Type'] = 'application/json'
      ..headers['Accept'] = 'text/event-stream'
      ..headers['Authorization'] = 'Bearer $token'
      ..body = body;
  }

  Dio get dio => _dio;

  String get baseUrl => _dio.options.baseUrl;

  // ── Onboarding ────────────────────────────────────────────────────────

  Future<StartOnboardingResponse> startOnboarding({
    required String locale,
    required String timezone,
  }) async {
    final r = await _dio.post<Map<String, dynamic>>(
      '/v1/onboarding/start',
      data: {'locale': locale, 'timezone': timezone},
    );
    return StartOnboardingResponse.fromJson(r.data!);
  }

  Future<AnswerResponse> submitAnswer({
    required String sessionId,
    required String step,
    required String answer,
  }) async {
    final r = await _dio.post<Map<String, dynamic>>(
      '/v1/onboarding/answer',
      data: {'session_id': sessionId, 'step': step, 'answer': answer},
    );
    return AnswerResponse.fromJson(r.data!);
  }

  /// DEF160 (mobile half): [restart] is the explicit "replace my mandate"
  /// signal — the backend only acts on it when the request is ALSO
  /// authenticated (see `confirm_readback` in `onboarding.py`), and the
  /// Bearer header is attached automatically by [_AuthInterceptor] whenever
  /// a signed-in user's token is set via [setToken]. Defaults to `false` so
  /// every existing anonymous-onboarding call site is byte-for-byte
  /// unchanged.
  Future<ReadbackConfirmResponse> confirmReadback({
    required String sessionId,
    required bool confirm,
    bool restart = false,
  }) async {
    final r = await _dio.post<Map<String, dynamic>>(
      '/v1/onboarding/readback/confirm',
      data: {
        'session_id': sessionId,
        'confirm': confirm ? 'confirm' : 'edit',
        'edits': const <String, dynamic>{},
        'restart': restart,
      },
    );
    return ReadbackConfirmResponse.fromJson(r.data!);
  }

  Future<bool> health() async {
    try {
      final r = await _dio.get<Map<String, dynamic>>('/v1/health');
      return r.data?['status'] == 'ok';
    } catch (_) {
      return false;
    }
  }

  /// CR121 — the client version-gate read. UNAUTHENTICATED, same as
  /// [health]: it must answer even before bootstrap (the token may not
  /// exist yet, or may belong to a build the server refuses). Callers MUST
  /// fail open on any error — see `version_gate_providers.dart`'s
  /// `VersionGateController`, which is the one place this is called from.
  Future<ReleaseFloorResponse> getReleaseFloor({
    required int? build,
    required String locale,
    required String platform,
  }) async {
    final r = await _dio.get<Map<String, dynamic>>(
      '/v1/client/release-floor',
      queryParameters: {
        if (build != null) 'build': build,
        'locale': locale,
        'platform': platform,
      },
    );
    return ReleaseFloorResponse.fromJson(r.data!);
  }

  // ── 1-on-1 ──────────────────────────────────────────────────────

  Future<OneOnOneSession> startOneOnOne({
    required String agentId,
    String locale = 'en',
  }) async {
    // L-1 cleanup (AT:R32): `user_id` no longer sent in the body. Backend
    // sources the user from the Bearer token. See OneOnOneStartRequest.
    final r = await _dio.post<Map<String, dynamic>>(
      '/v1/agents/one_on_one/start',
      data: {
        'agent_id': agentId,
        'locale': locale,
      },
    );
    return OneOnOneSession.fromJson(r.data!);
  }

  // ── Coach Your Agent ────────────────────────────────────────────

  Future<BriefStartResponse> startBrief({
    required String agentId,
    required String userId,
    String mode = 'from_scratch',
    String locale = 'en',
  }) async {
    final r = await _dio.post<Map<String, dynamic>>(
      '/v1/brief/start',
      data: {
        'agent_id': agentId,
        'user_id': userId,
        'mode': mode,
        'locale': locale,
      },
    );
    return BriefStartResponse.fromJson(r.data!);
  }

  Stream<String> streamBriefMessage({
    required String sessionId,
    required String userMessage,
    required List<ChatMessage> history,
  }) async* {
    final uri = Uri.parse('$baseUrl/v1/brief/message');
    final body = jsonEncode({
      'session_id': sessionId,
      'user_message': userMessage,
      'history': history.map((m) => m.toJson()).toList(),
    });
    final response = await _httpClient.send(_sseRequest(uri, body));
    if (response.statusCode != 200) {
      _notifyIfUnauthorized(response.statusCode);
      throw Exception('HTTP ${response.statusCode} from brief stream');
    }
    String buffer = '';
    await for (final chunk in response.stream.transform(utf8.decoder)) {
      buffer += chunk;
      while (buffer.contains('\n\n')) {
        final idx = buffer.indexOf('\n\n');
        final event = buffer.substring(0, idx);
        buffer = buffer.substring(idx + 2);

        String? eventType;
        final dataLines = <String>[];
        for (final line in event.split('\n')) {
          if (line.startsWith('event: ')) {
            eventType = line.substring(7).trim();
          } else if (line.startsWith('data: ')) {
            dataLines.add(line.substring(6));
          }
        }
        final data = dataLines.join('\n');
        if (eventType == 'token') {
          yield unescapeSseText(data);
        } else if (eventType == 'done') {
          return;
        } else if (eventType == 'error') {
          throw Exception('Server error: ${unescapeSseText(data)}');
        }
      }
    }
  }

  Future<BriefProposal> proposeBriefChange({
    required String sessionId,
    required List<ChatMessage> history,
  }) async {
    final r = await _dio.post<Map<String, dynamic>>(
      '/v1/brief/propose',
      data: {
        'session_id': sessionId,
        'history': history.map((m) => m.toJson()).toList(),
      },
      // DEF253 — this one really does wait on the model (`brief_engine.propose`
      // streams from `self._llm`), so a receive timeout may say so.
      options: Options(extra: kAmiWaitsOnModel),
    );
    return BriefProposal.fromJson(r.data!);
  }

  /// Returns the new overlay if accepted, or a map with `refusal` if blocked.
  Future<Map<String, dynamic>> acceptBriefProposal({
    required String sessionId,
    required String proposalId,
  }) async {
    final r = await _dio.post<Map<String, dynamic>>(
      '/v1/brief/accept',
      data: {'session_id': sessionId, 'proposal_id': proposalId},
    );
    return r.data!;
  }

  Future<void> rejectBriefProposal({
    required String sessionId,
    required String proposalId,
  }) async {
    await _dio.post<Map<String, dynamic>>(
      '/v1/brief/reject',
      data: {'session_id': sessionId, 'proposal_id': proposalId},
    );
  }

  Future<UserOverlay> rollbackBrief({
    required String userId,
    required String agentId,
    required int toVersion,
  }) async {
    final r = await _dio.post<Map<String, dynamic>>(
      '/v1/brief/rollback',
      data: {
        'user_id': userId,
        'agent_id': agentId,
        'to_version': toVersion,
      },
    );
    return UserOverlay.fromJson(r.data!);
  }

  Future<BriefHistory> briefHistory({
    required String userId,
    required String agentId,
    String plan = 'trial_trader',
  }) async {
    final r = await _dio.get<Map<String, dynamic>>(
      '/v1/brief/history/$userId/$agentId',
      queryParameters: {'plan': plan},
    );
    return BriefHistory.fromJson(r.data!);
  }

  /// Send a message and yield string chunks as they arrive (SSE).
  /// Uses `package:http` directly because Dio's streaming SSE handling is
  /// awkward — http exposes the underlying stream cleanly.
  Stream<String> streamOneOnOneMessage({
    required String sessionId,
    required String userMessage,
    required List<ChatMessage> history,
    Map<String, dynamic>? alpaca,
  }) async* {
    final uri = Uri.parse('$baseUrl/v1/agents/one_on_one/message');
    final body = jsonEncode({
      'session_id': sessionId,
      'user_message': userMessage,
      'history': history.map((m) => m.toJson()).toList(),
      if (alpaca != null) 'alpaca': alpaca,
    });

    final response = await _httpClient.send(_sseRequest(uri, body));
    if (response.statusCode != 200) {
      _notifyIfUnauthorized(response.statusCode);
      throw Exception('HTTP ${response.statusCode} from 1-on-1 stream');
    }

    // SSE parser: each event is "event: <type>\ndata: <payload>\n\n"
    String buffer = '';
    await for (final chunk in response.stream.transform(utf8.decoder)) {
      buffer += chunk;
      while (buffer.contains('\n\n')) {
        final idx = buffer.indexOf('\n\n');
        final event = buffer.substring(0, idx);
        buffer = buffer.substring(idx + 2);

        String? eventType;
        final dataLines = <String>[];
        for (final line in event.split('\n')) {
          if (line.startsWith('event: ')) {
            eventType = line.substring(7).trim();
          } else if (line.startsWith('data: ')) {
            dataLines.add(line.substring(6));
          }
        }
        final data = dataLines.join('\n');
        if (eventType == 'token') {
          yield unescapeSseText(data);
        } else if (eventType == 'done') {
          return;
        } else if (eventType == 'error') {
          throw Exception('Server error: ${unescapeSseText(data)}');
        }
      }
    }
  }

  // ── Decision Journal ────────────────────────────────────────────

  Future<JournalListResponse> listJournal({
    required String userId,
    // DEF173 — no default: a missing plan is a compile error, not a silent
    // 'trial_trader'. The caller must derive it from the authenticated user.
    required String plan,
    String? entryType,
    String? ticker,
    String? q,
    int limit = 100,
  }) async {
    final r = await _dio.get<Map<String, dynamic>>(
      '/v1/journal/$userId',
      queryParameters: {
        'plan': plan,
        if (entryType != null) 'entry_type': entryType,
        if (ticker != null) 'ticker': ticker,
        if (q != null && q.isNotEmpty) 'q': q,
        'limit': limit,
      },
    );
    return JournalListResponse.fromJson(r.data!);
  }

  Future<JournalEntry> getJournalEntry({
    required String userId,
    required String entryId,
  }) async {
    final r = await _dio.get<Map<String, dynamic>>(
      '/v1/journal/$userId/entry/$entryId',
    );
    return JournalEntry.fromJson(r.data!);
  }

  Future<JournalEntry> annotateJournalEntry({
    required String userId,
    required String entryId,
    String? note,
    List<String>? tags,
    String? outcome,
  }) async {
    final r = await _dio.post<Map<String, dynamic>>(
      '/v1/journal/$userId/entry/$entryId/note',
      data: {
        if (note != null) 'note': note,
        if (tags != null) 'tags': tags,
        if (outcome != null) 'outcome': outcome,
      },
    );
    return JournalEntry.fromJson(r.data!);
  }

  Future<void> deleteJournalEntry({
    required String userId,
    required String entryId,
  }) async {
    await _dio.delete<void>('/v1/journal/$userId/entry/$entryId');
  }

  Future<void> restoreJournalEntry({
    required String userId,
    required String entryId,
  }) async {
    await _dio.post<void>('/v1/journal/$userId/entry/$entryId/restore');
  }

  Future<JournalListResponse> listJournalTrash({
    required String userId,
    int limit = 100,
  }) async {
    final r = await _dio.get<Map<String, dynamic>>(
      '/v1/journal/$userId/trash',
      queryParameters: {'limit': limit},
    );
    return JournalListResponse.fromJson(r.data!);
  }

  // ── Lessons ─────────────────────────────────────────────────────

  Future<LessonCatalogue> lessonCatalogue({String locale = 'en'}) async {
    final r = await _dio.get<Map<String, dynamic>>(
      '/v1/lessons',
      queryParameters: {'locale': locale},
    );
    return LessonCatalogue.fromJson(r.data!);
  }

  Future<Lesson> getLesson(String lessonId, {String locale = 'en'}) async {
    final r = await _dio.get<Map<String, dynamic>>(
      '/v1/lessons/$lessonId',
      queryParameters: {'locale': locale},
    );
    return Lesson.fromJson(r.data!);
  }

  Future<void> startLesson({
    required String userId,
    required String lessonId,
  }) async {
    await _dio.post<Map<String, dynamic>>(
      '/v1/lessons/start',
      data: {'user_id': userId, 'lesson_id': lessonId},
    );
  }

  Future<QuizResult> submitQuiz({
    required String userId,
    required String lessonId,
    required List<int> answers,
  }) async {
    final r = await _dio.post<Map<String, dynamic>>(
      '/v1/lessons/quiz',
      data: {
        'user_id': userId,
        'lesson_id': lessonId,
        'answers': answers,
      },
    );
    return QuizResult.fromJson(r.data!);
  }

  Future<ProgressSummary> lessonsProgress(String userId) async {
    final r = await _dio.get<Map<String, dynamic>>(
      '/v1/lessons/progress/$userId',
    );
    return ProgressSummary.fromJson(r.data!);
  }

  /// Batch quote fetch via backend — used as fallback when direct Yahoo Finance
  /// fails on device. Returns quotes mapped by symbol (upper-cased).
  Future<List<TickerQuote>> fetchTapeQuotes(List<String> symbols) async {
    if (symbols.isEmpty) return [];
    final r = await _dio.get<List<dynamic>>(
      '/v1/sim/quotes',
      queryParameters: {'symbols': symbols.join(',')},
    );
    return (r.data ?? const [])
        .whereType<Map<String, dynamic>>()
        .map((m) => TickerQuote(
              symbol: (m['ticker'] as String?) ?? '',
              price: (m['price'] as num?)?.toDouble() ?? 0,
              changePercent: (m['change_pct'] as num?)?.toDouble() ?? 0,
              marketState: (m['market_state'] as String?) ?? 'CLOSED',
            ))
        .where((q) => q.symbol.isNotEmpty && q.price > 0)
        .toList();
  }

  Future<Map<String, LessonStatus>> lessonStatusByLesson(String userId) async {
    final r = await _dio.get<List<dynamic>>(
      '/v1/lessons/progress/$userId/by_lesson',
    );
    return {
      for (final e in (r.data ?? const []))
        (e as Map<String, dynamic>)['lesson_id'] as String:
            LessonStatus.fromJson(e),
    };
  }

  /// DEF068 — per-agent gateway lessons and how far this user has got on each.
  /// Keyed by agent id for the locked sheet's direct lookup.
  Future<Map<String, AgentUnlockRequirement>> unlockRequirements(
      String userId) async {
    final r = await _dio.get<List<dynamic>>(
      '/v1/lessons/requirements/$userId',
    );
    return {
      for (final e in (r.data ?? const []))
        (e as Map<String, dynamic>)['agent_id'] as String:
            AgentUnlockRequirement.fromJson(e),
    };
  }

  Future<List<AgentActivationRecord>> agentActivations(String userId) async {
    final r = await _dio.get<List<dynamic>>(
      '/v1/lessons/activations/$userId',
    );
    return (r.data ?? const [])
        .map((e) => AgentActivationRecord.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  // `grantActivation()` was removed alongside the backend route per
  // adversarial audit finding A5. Founder grants now happen via psql on
  // melehost — see the comment block in `backend/app/api/lessons.py`.

  // ── Convene the Room ───────────────────────────────────────────

  /// Stream a full Room run for [ticker]. Yields typed events.
  ///
  /// Event kinds:
  ///   {'kind':'phase','label': ...}
  ///   {'kind':'agent_token','agent_id': ..., 'text': ...}
  ///   {'kind':'agent_done','agent_id': ...}
  ///   {'kind':'verdict','verdict': RoomVerdict}
  ///   {'kind':'done','run_id': ...}
  ///   {'kind':'error','message': ...}
  Stream<Map<String, dynamic>> streamRoom({
    required String userId,
    required String ticker,
    String locale = 'en',
    Map<String, dynamic>? mandateOverride,
    Map<String, dynamic>? alpaca,
  }) async* {
    final uri = Uri.parse('$baseUrl/v1/room/stream');
    // CR202: `alpaca` must ride the START request. The run is a detached
    // background task that composes its prompts after this call returns, so
    // there is no later point at which the backend could ask this device for
    // the account. Null = no linked account = no overlay.
    final body = jsonEncode({
      'user_id': userId,
      'ticker': ticker,
      'locale': locale,
      if (mandateOverride != null) 'mandate_override': mandateOverride,
      if (alpaca != null) 'alpaca': alpaca,
    });
    final response = await _httpClient.send(_sseRequest(uri, body));
    if (response.statusCode == 402) {
      // CR047: the credit wall. Read the structured body and surface it as a
      // typed exception so the Room screen can render a paywall / Winzip
      // countdown instead of a generic "Stream failed". The 402 lands before
      // the SSE stream starts (see api/room.py), so the body is the whole
      // response, not an in-band event.
      final raw = await response.stream.bytesToString();
      Map<String, dynamic>? decoded;
      try {
        decoded = jsonDecode(raw) as Map<String, dynamic>;
      } catch (_) {
        decoded = null;
      }
      if (decoded != null) {
        throw InsufficientCreditsException.fromJson(decoded);
      }
      throw Exception('HTTP 402 from room stream');
    }
    if (response.statusCode >= 500) {
      // DEF073: a 5xx (deploy/restart/tunnel blip) — surface it typed so the
      // Room screen renders a friendly "try again" card, not a raw status code.
      throw ServerUnavailableException(response.statusCode);
    }
    if (response.statusCode != 200) {
      _notifyIfUnauthorized(response.statusCode);
      throw Exception('HTTP ${response.statusCode} from room stream');
    }
    String buffer = '';
    await for (final chunk in response.stream.transform(utf8.decoder)) {
      buffer += chunk;
      while (buffer.contains('\n\n')) {
        final idx = buffer.indexOf('\n\n');
        final event = buffer.substring(0, idx);
        buffer = buffer.substring(idx + 2);

        String? eventType;
        final dataLines = <String>[];
        for (final line in event.split('\n')) {
          if (line.startsWith('event: ')) {
            eventType = line.substring(7).trim();
          } else if (line.startsWith('data: ')) {
            dataLines.add(line.substring(6));
          }
        }
        final data = dataLines.join('\n');
        if (eventType == null) continue;
        final parsed = parseRoomSseEvent(eventType, data);
        if (parsed == null) continue;
        yield parsed;
        if (parsed['kind'] == 'done' || parsed['kind'] == 'error') return;
      }
    }
  }

  Future<RoomRunSnapshot> getRoom(String runId) async {
    final r = await _dio.get<Map<String, dynamic>>('/v1/room/$runId');
    return RoomRunSnapshot.fromJson(r.data!);
  }

  Future<List<RoomRunSnapshot>> listUserRooms(String userId, {int limit = 50}) async {
    final r = await _dio.get<List<dynamic>>(
      '/v1/room/user/$userId',
      queryParameters: {'limit': limit},
    );
    return (r.data ?? const [])
        .map((e) => RoomRunSnapshot.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  // ── Sim Trading ─────────────────────────────────────────────────

  Future<SimPortfolio> simPortfolio(String userId) async {
    final r = await _dio.get<Map<String, dynamic>>('/v1/sim/portfolio/$userId');
    return SimPortfolio.fromJson(r.data!);
  }

  Future<SimPortfolio> simResetPortfolio(String userId) async {
    final r = await _dio.post<Map<String, dynamic>>(
      '/v1/sim/portfolio/$userId/reset',
    );
    return SimPortfolio.fromJson(r.data!);
  }

  Future<SimSubmitResult> simSubmit({
    required String userId,
    required String ticker,
    required String side, // 'buy' | 'sell'
    required double quantity,
    String orderType = 'market',
    double? limitPrice,
    double? triggerPrice,
    String? tif,
    double? stop,
    double? target,
    int? horizonDays,
    String? verdictRef,
  }) async {
    final r = await _dio.post<Map<String, dynamic>>(
      '/v1/sim/submit',
      data: {
        'user_id': userId,
        'ticker': ticker,
        'side': side,
        'quantity': quantity,
        'order_type': orderType,
        if (limitPrice != null) 'limit_price': limitPrice,
        if (triggerPrice != null) 'trigger_price': triggerPrice,
        if (tif != null) 'tif': tif,
        if (stop != null) 'stop': stop,
        if (target != null) 'target': target,
        if (horizonDays != null) 'horizon_days': horizonDays,
        if (verdictRef != null) 'verdict_ref': verdictRef,
      },
    );
    return SimSubmitResult.fromJson(r.data!);
  }

  /// CR170 — the resting-order book. Working orders plus terminal rows from the
  /// last 24h, so a rejected or expired order never silently vanishes
  /// overnight.
  ///
  /// **This is also the capability probe.** A backend without CR170's routes
  /// answers 404, and [SimNotifier] reads that as "resting orders are not
  /// available here" and hides the controls — rather than offering an
  /// order-type picker whose non-market values would be accepted by the old
  /// `/submit` and filled *instantly at the named price*. That is the failure
  /// worth designing against: not a missing feature, but a money-moving control
  /// that silently does something else (CR040). Probing beats a compile-time
  /// flag because it flips itself the moment the backend ships, with no rebuild.
  Future<List<SimRestingOrder>> simRestingOrders(String userId) async {
    final r = await _dio.get<Map<String, dynamic>>('/v1/sim/orders/$userId');
    final list = (r.data?['orders'] as List?) ?? const [];
    return list
        .map((o) => SimRestingOrder.fromJson((o as Map).cast<String, dynamic>()))
        .toList();
  }

  /// Returns the SERVER's verdict, which is not always "cancelled" — a cancel
  /// can lose a race with the sweep that filled it.
  Future<RestingOrderCancelResult> simCancelRestingOrder(
      String userId, String orderId) async {
    final r = await _dio.post<Map<String, dynamic>>(
      '/v1/sim/orders/$userId/$orderId/cancel',
    );
    return RestingOrderCancelResult.fromJson(r.data!);
  }

  Future<List<SimTrade>> simListTrades(String userId, {String? statusFilter}) async {
    final r = await _dio.get<Map<String, dynamic>>(
      '/v1/sim/trades/$userId',
      queryParameters: {
        if (statusFilter != null) 'status_filter': statusFilter,
      },
    );
    final list = ((r.data?['trades'] as List?) ?? const []);
    return list
        .map((t) => SimTrade.fromJson(t as Map<String, dynamic>))
        .toList();
  }

  Future<void> simEvaluate(String userId) async {
    await _dio.post<Map<String, dynamic>>('/v1/sim/trades/$userId/evaluate');
  }

  Future<SimTrade> simCloseTrade(String userId, String tradeId) async {
    final r = await _dio.post<Map<String, dynamic>>(
      '/v1/sim/trades/$userId/close',
      data: {'trade_id': tradeId},
    );
    return SimTrade.fromJson(r.data!['trade'] as Map<String, dynamic>);
  }

  Future<double> simQuote(String ticker) async {
    final r = await _dio.get<Map<String, dynamic>>('/v1/sim/quote/$ticker');
    return (r.data!['price'] as num).toDouble();
  }

  /// Full quote — price + change% + source + market state. Used by the
  /// trade ticket sheet to anchor TP/SL when the user trades manually.
  Future<({double price, double changePct, String source, String marketState})>
      simQuoteDetail(String ticker) async {
    final r = await _dio.get<Map<String, dynamic>>('/v1/sim/quote/$ticker');
    final d = r.data!;
    return (
      price: (d['price'] as num).toDouble(),
      changePct: (d['change_pct'] as num?)?.toDouble() ?? 0.0,
      source: d['source'] as String? ?? 'unknown',
      marketState: d['market_state'] as String? ?? 'UNKNOWN',
    );
  }

  /// OHLCV history for the TickerDetail chart.
  /// `period` is one of: 1d, 1w, 1m, 3m, 1y, 5y. Server caches 60s.
  ///
  /// DEF151: lowercased on the wire. `ticker_chart.dart` labels its chips
  /// `1D/1W/1M/…` and passed the label through verbatim, so every request
  /// 422'd and the chart was dark on every ticker and period. The label is UI
  /// copy; the wire token is not. The server normalises too — that half is
  /// what repairs the builds already installed — so this is the belt to its
  /// braces, not the fix on its own.
  Future<SimHistory> simHistory(String ticker, String period) async {
    final r = await _dio.get<Map<String, dynamic>>(
      '/v1/sim/history/$ticker',
      queryParameters: {'period': period.trim().toLowerCase()},
    );
    return SimHistory.fromJson(r.data!);
  }

  /// Portfolio equity-curve feed for the Portfolio screen (CR109 slice 1).
  /// `price_source` rides per point so the client can mark a non-live day
  /// rather than draw it as fact (CR040).
  Future<SimPortfolioHistory> simPortfolioHistory(String userId) async {
    final r = await _dio
        .get<Map<String, dynamic>>('/v1/sim/portfolio/$userId/history');
    return SimPortfolioHistory.fromJson(r.data!);
  }

  /// Recent news articles for the TickerDetail news section. Server caches 5 min.
  Future<SimNews> simNews(String ticker) async {
    final r = await _dio.get<Map<String, dynamic>>('/v1/sim/news/$ticker');
    return SimNews.fromJson(r.data!);
  }

  /// SECTOR WATCH card feed (CR183): the top-moving GICS sector among the
  /// user's touched tickers (watchlist + holdings), its leader, and the
  /// leader's top headline. Always HTTP 200 — degrade states ride the body's
  /// `state` field rather than an error code (CR040).
  Future<SectorWatch> sectorWatch(String userId) async {
    final r =
        await _dio.get<Map<String, dynamic>>('/v1/sector-watch/$userId');
    return SectorWatch.fromJson(r.data!);
  }

  /// Upcoming earnings info within 90 days (CR030 adds the dividend fields
  /// on this same response). Server caches 6 hours.
  Future<SimEarnings> simEarnings(String ticker) async {
    final r = await _dio.get<Map<String, dynamic>>('/v1/sim/earnings/$ticker');
    return SimEarnings.fromJson(r.data!);
  }

  /// Per-lot cost-basis / FIFO realised-P&L reconstruction for one held
  /// ticker (CR029).
  Future<HoldingLots> simHoldingLots(String userId, String ticker) async {
    final r = await _dio
        .get<Map<String, dynamic>>('/v1/sim/lots/$userId/$ticker');
    return HoldingLots.fromJson(r.data!);
  }

  /// Sector-allocation donut feed + concentration-compliance (CR026).
  Future<SectorAllocation> sectorAllocation(String userId) async {
    final r = await _dio
        .get<Map<String, dynamic>>('/v1/portfolio/sector-allocation/$userId');
    return SectorAllocation.fromJson(r.data!);
  }

  /// CR136 M09 — Portfolio Health tiles + gate status. Free, never gated (M07
  /// §3.4): a mock-mode refusal or an all-insufficient book still answers 200,
  /// carrying the state the card is meant to show.
  Future<PortfolioHealth> portfolioHealth(String userId) async {
    final r =
        await _dio.get<Map<String, dynamic>>('/v1/portfolio/health/$userId');
    return PortfolioHealth.fromJson(r.data!);
  }

  /// CR136 M09 — generate (or replay today's) Finding. A same-day repeat
  /// returns the stored entry with `created:false` and consumes no budget
  /// (M07 §3.5 step 6), which is what makes a `FutureProvider` around a POST
  /// safe here.
  Future<HealthFinding> generateHealthFinding(String userId) async {
    final r = await _dio.post<Map<String, dynamic>>(
      '/v1/portfolio/health/$userId/finding',
      // DEF253 — the one LLM route in `api/portfolio.py`
      // (`generate_and_persist_finding(gateway=get_llm_gateway())`). Every
      // other portfolio call the screen makes is a database or quote read, and
      // marking this one is what keeps them out of the AMI wording.
      options: Options(extra: kAmiWaitsOnModel),
    );
    return HealthFinding.fromJson(r.data!);
  }

  // ── Ticker Reference (CR128) ────────────────────────────────────

  /// Existence check + closest-match suggestion, called at submit-time from
  /// Convene the Room, trade submit, and watchlist add before the actual
  /// action request — the client resolves to a valid ticker here so the
  /// action endpoints' own guard (defense in depth) never fires in the
  /// normal path.
  Future<TickerValidation> validateTicker(String ticker) async {
    final r = await _dio.get<Map<String, dynamic>>(
      '/v1/tickers/validate',
      queryParameters: {'ticker': ticker},
    );
    return TickerValidation.fromJson(r.data!);
  }

  // ── Watchlist (A18) ─────────────────────────────────────────────

  Future<List<WatchlistEntry>> watchlistList(String userId) async {
    final r = await _dio.get<Map<String, dynamic>>('/v1/watchlist/$userId');
    final items = ((r.data?['items'] as List?) ?? const []);
    return items
        .map((j) => WatchlistEntry.fromJson(j as Map<String, dynamic>))
        .toList();
  }

  Future<WatchlistEntry> watchlistAdd(
    String userId,
    String ticker, {
    String? notes,
  }) async {
    final r = await _dio.post<Map<String, dynamic>>(
      '/v1/watchlist/$userId',
      data: {
        'ticker': ticker,
        if (notes != null) 'notes': notes,
      },
    );
    return WatchlistEntry.fromJson(r.data!);
  }

  Future<void> watchlistRemove(String userId, String ticker) async {
    await _dio.delete<void>('/v1/watchlist/$userId/$ticker');
  }

  // ── Price alerts (CR027 §4) ──────────────────────────────────────

  Future<List<PriceAlert>> priceAlerts(String userId, {String? status}) async {
    final r = await _dio.get<Map<String, dynamic>>(
      '/v1/price_alerts/$userId',
      queryParameters: status == null ? null : {'status': status},
    );
    final items = ((r.data?['items'] as List?) ?? const []);
    return items
        .map((j) => PriceAlert.fromJson(j as Map<String, dynamic>))
        .toList();
  }

  Future<PriceAlert> createPriceAlert(
    String userId, {
    required String ticker,
    required String thresholdType,
    required double thresholdPrice,
    String? tradeRef,
  }) async {
    final r = await _dio.post<Map<String, dynamic>>(
      '/v1/price_alerts/$userId',
      data: {
        'ticker': ticker,
        'threshold_type': thresholdType,
        'threshold_price': thresholdPrice,
        if (tradeRef != null) 'trade_ref': tradeRef,
      },
    );
    return PriceAlert.fromJson(r.data!);
  }

  Future<PriceAlert> cancelPriceAlert(String userId, String alertId) async {
    final r = await _dio
        .delete<Map<String, dynamic>>('/v1/price_alerts/$userId/$alertId');
    return PriceAlert.fromJson(r.data!);
  }

  // ── Mandate ─────────────────────────────────────────────────────

  Future<UserMandate> getMandate(String userId) async {
    final r = await _dio.get<Map<String, dynamic>>('/v1/mandate/$userId');
    return UserMandate.fromJson(r.data!);
  }

  Future<UserMandate> patchMandate({
    required String userId,
    required Map<String, dynamic> updates,
  }) async {
    final r = await _dio.patch<Map<String, dynamic>>(
      '/v1/mandate/$userId',
      data: updates,
    );
    return UserMandate.fromJson(r.data!);
  }

  /// BL12 (CR101-MOBILE): audit current holdings against the mandate that is
  /// now persisted server-side. Call immediately after a risk-limit PATCH —
  /// there is no "preview" endpoint, so retro-tightening disclosure is
  /// necessarily post-save, not pre-save (see the CR101-MOBILE bridge).
  Future<HoldingsAuditResult> auditMandateHoldings(String userId) async {
    final r = await _dio.get<Map<String, dynamic>>('/v1/mandate/$userId/audit');
    return HoldingsAuditResult.fromJson(r.data!);
  }

  // ── Billing identity (CR084) ────────────────────────────────────────────

  /// The id the RevenueCat SDK logs in with, so RC's `app_user_id` on every
  /// webhook event equals our `users.id`. Auth-gated (`GET /v1/billing/identity`
  /// → `backend/app/api/billing.py`). Called once before the SDK is configured.
  Future<BillingIdentity> getBillingIdentity() async {
    final r = await _dio.get<Map<String, dynamic>>('/v1/billing/identity');
    return BillingIdentity.fromJson(r.data!);
  }

  // ── Auth (anonymous-first; Apple + magic-link claim) ────────────

  Future<AnonSessionResponse> bootstrapAnon({
    String? deviceUserId,
    String locale = 'en',
    String timezone = 'UTC',
    String? deviceModel,
    String? osVersion,
    String? appVersion,
    String? deviceInstallId,
  }) async {
    final r = await _dio.post<Map<String, dynamic>>(
      '/v1/auth/anon',
      data: {
        if (deviceUserId != null) 'device_user_id': deviceUserId,
        'locale': locale,
        'timezone': timezone,
        if (deviceModel != null) 'device_model': deviceModel,
        if (osVersion != null) 'os_version': osVersion,
        if (appVersion != null) 'app_version': appVersion,
        if (deviceInstallId != null) 'device_install_id': deviceInstallId,
      },
    );
    return AnonSessionResponse.fromJson(r.data!);
  }

  // Adversarial audit (2026-05-18) finding A3: magic-link routes no longer
  // accept user_id in the body. The claim is bound to the Bearer-authenticated
  // user_id server-side (the Dio interceptor sends the anon token automatically).
  Future<MagicLinkStartResponse> startMagicLink({required String email}) async {
    final r = await _dio.post<Map<String, dynamic>>(
      '/v1/auth/magic_link/start',
      data: {'email': email},
    );
    return MagicLinkStartResponse.fromJson(r.data!);
  }

  Future<AuthVerifyResponse> verifyMagicLink({
    required String email,
    required String code,
    String? onboardingSessionId,
  }) async {
    final r = await _dio.post<Map<String, dynamic>>(
      '/v1/auth/magic_link/verify',
      data: {
        'email': email,
        'code': code,
        if (onboardingSessionId != null)
          'onboarding_session_id': onboardingSessionId,
      },
    );
    return AuthVerifyResponse.fromJson(r.data!);
  }

  Future<AuthVerifyResponse> signInWithApple({
    required String identityToken,
    String? userId,
    String? fullName,
    String? onboardingSessionId,
  }) async {
    // Phase 3 (AT:R29): backend verifies the identity_token against
    // Apple's JWKS. 400 on bad signature / wrong iss/aud / expired.
    final r = await _dio.post<Map<String, dynamic>>(
      '/v1/auth/apple',
      data: {
        'identity_token': identityToken,
        if (userId != null) 'user_id': userId,
        if (fullName != null) 'full_name': fullName,
        if (onboardingSessionId != null)
          'onboarding_session_id': onboardingSessionId,
      },
    );
    return AuthVerifyResponse.fromJson(r.data!);
  }

  Future<AuthVerifyResponse> signInWithGoogle({
    required String identityToken,
    String? userId,
    String? onboardingSessionId,
  }) async {
    // D-057 (AT:R36): Android-only at alpha. Backend verifies the
    // ID token against Google's JWKS (signature + iss + aud + exp +
    // email_verified) via OIDCVerifier. 400 on any failure.
    // No `full_name` field — Google ships `name` inside the verified
    // ID token, so the backend reads it from claims.
    final r = await _dio.post<Map<String, dynamic>>(
      '/v1/auth/google',
      data: {
        'identity_token': identityToken,
        if (userId != null) 'user_id': userId,
        if (onboardingSessionId != null)
          'onboarding_session_id': onboardingSessionId,
      },
    );
    return AuthVerifyResponse.fromJson(r.data!);
  }

  Future<void> signOut() async {
    try {
      await _dio.delete<void>('/v1/auth/session');
    } catch (_) {
      // Fire-and-forget — client clears its token regardless of server response.
    }
    _bearerToken = null;
  }

  // ── BL16 account merge (AT:R38) ────────────────────────────────────────

  /// Read-only counts of what an account merge would move from the orphan
  /// `fromUserId` into the current bearer's user. 403 if the bearer is not
  /// the legitimate adopter, 404 if the orphan was already merged.
  Future<MergePreview> previewMerge({required String fromUserId}) async {
    final r = await _dio.get<Map<String, dynamic>>(
      '/v1/auth/merge/preview/$fromUserId',
    );
    return MergePreview.fromJson(r.data!);
  }

  /// Re-key journal / sim / lessons / overlays from orphan into the
  /// current bearer's user. Server-side single transaction. The orphan
  /// row is deleted at the end.
  Future<MergeResult> executeMerge({required String fromUserId}) async {
    final r = await _dio.post<Map<String, dynamic>>(
      '/v1/auth/merge',
      data: {'from_user_id': fromUserId},
    );
    return MergeResult.fromJson(r.data!);
  }

  Future<AuthUser> me({required String token}) async {
    final r = await _dio.get<Map<String, dynamic>>(
      '/v1/auth/me',
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
    return AuthUser.fromJson(r.data!);
  }

  // ── AI Coach Q&A ────────────────────────────────────────────────────

  Future<List<CoachSearchHit>> aiCoachSearch(String query, {int limit = 5}) async {
    final r = await _dio.get<Map<String, dynamic>>(
      '/v1/ai_coach/search',
      queryParameters: {'q': query, 'limit': limit},
    );
    final hits = (r.data!['hits'] as List)
        .map((h) => CoachSearchHit.fromJson(h as Map<String, dynamic>))
        .toList();
    return hits;
  }

  Future<List<String>> aiCoachCategories() async {
    final r = await _dio.get<List<dynamic>>('/v1/ai_coach/categories');
    return List<String>.from(r.data!);
  }

  // ── Daily Challenge ─────────────────────────────────────────────────

  Future<DailyChallengeWithDate?> dailyChallengeToday() async {
    try {
      final r = await _dio.get<Map<String, dynamic>>('/v1/daily_challenge/today');
      return DailyChallengeWithDate.fromJson(r.data!);
    } on DioException catch (e) {
      if (e.response?.statusCode == 404) return null;
      rethrow;
    }
  }

  // CR010 (B5): server-graded attempt. A repeat returns the stored result
  // with alreadyAttempted=true (backend persists one attempt per challenge).
  Future<DailyChallengeAttemptResult> dailyChallengeAttempt(
    String challengeId,
    int selectedOption,
  ) async {
    final r = await _dio.post<Map<String, dynamic>>(
      '/v1/daily_challenge/$challengeId/attempt',
      data: {'selected_option': selectedOption},
    );
    return DailyChallengeAttemptResult.fromJson(r.data!);
  }

  // ── League (CR010) ──────────────────────────────────────────────────

  Future<LeagueMe> leagueMe() async {
    final r = await _dio.get<Map<String, dynamic>>('/v1/league/me');
    return LeagueMe.fromJson(r.data!);
  }

  Future<LeagueStandings?> leagueStandings() async {
    try {
      final r = await _dio.get<Map<String, dynamic>>('/v1/league/standings');
      return LeagueStandings.fromJson(r.data!);
    } on DioException catch (e) {
      if (e.response?.statusCode == 404) return null; // not_in_league yet
      rethrow;
    }
  }

  Future<List<LeagueHistoryEntry>> leagueHistory() async {
    final r = await _dio.get<List<dynamic>>('/v1/league/history');
    return (r.data ?? const [])
        .map((e) => LeagueHistoryEntry.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  Future<String> regenerateHandle() async {
    final r = await _dio.patch<Map<String, dynamic>>('/v1/league/handle');
    return r.data!['handle'] as String;
  }

  // ── Feedback ─────────────────────────────────────────────────────────

  Future<Map<String, dynamic>> submitBugReport({
    required String category,
    required String title,
    String? steps,
    String? route,
    required String appVersion,
    required String platform,
    String? attachmentPath,
    String? attachmentMime,
    String? token,
  }) async {
    final form = FormData.fromMap({
      'category': category,
      'title': title,
      if (steps != null) 'steps': steps,
      if (route != null) 'route': route,
      'app_version': appVersion,
      'platform': platform,
      if (attachmentPath != null)
        'file': await MultipartFile.fromFile(
          attachmentPath,
          filename: attachmentPath.split('/').last,
          contentType: attachmentMime != null
              ? DioMediaType.parse(attachmentMime)
              : null,
        ),
    });
    final r = await _dio.post<Map<String, dynamic>>(
      '/v1/feedback/bug',
      data: form,
      options: token != null
          ? Options(headers: {'Authorization': 'Bearer $token'})
          : null,
    );
    return r.data!;
  }

  /// CR043 — resolved reports this user filed and hasn't been shown yet.
  /// Polled once per cold start; normally returns an empty list.
  Future<List<BugResolutionUpdate>> feedbackUpdates() async {
    final r = await _dio.get<List<dynamic>>('/v1/feedback/updates');
    return (r.data ?? [])
        .map((e) => BugResolutionUpdate.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  /// Mark a resolution message delivered so it fires exactly once.
  Future<void> ackFeedback(String reportId) async {
    await _dio.post<void>('/v1/feedback/$reportId/ack');
  }

  // ── CR102 in-app tester messaging ──────────────────────────────────────

  /// The whole inbox, newest-first, both directions. The bearer token
  /// identifies the caller — no user_id on the wire. The client derives the
  /// unread count from `read_at`; there is no count endpoint by design.
  Future<List<InboxMessage>> inboxMessages() async {
    final r = await _dio.get<List<dynamic>>('/v1/messages');
    return (r.data ?? [])
        .map((e) => InboxMessage.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  /// Idempotent server-side `read_at` stamp. 404 on another user's row.
  Future<void> markMessageRead(String messageId) async {
    await _dio.post<void>('/v1/messages/$messageId/read');
  }

  /// Reply to a broadcast (≤ 2000 chars). Threads via `reply_to_id`.
  Future<InboxReply> replyToMessage({
    required String messageId,
    required String body,
  }) async {
    final r = await _dio.post<Map<String, dynamic>>(
      '/v1/messages/$messageId/reply',
      data: {'body': body},
    );
    return InboxReply.fromJson(r.data!);
  }

  /// Server-side once-only `toasted_at` stamp for the priority=high
  /// cold-start toast — survives a reinstall, unlike a local flag.
  Future<void> markMessageToasted(String messageId) async {
    await _dio.post<void>('/v1/messages/$messageId/toasted');
  }

  // ── CR135 in-app notification centre ───────────────────────────────────
  //
  // Unlike `/v1/messages`, these routes carry `{user_id}` in the path
  // (price_alerts pattern) — the backend 403s a path user that isn't the
  // token's, and per-row routes 404 identically for foreign and
  // nonexistent ids.

  /// One page, newest-first. `total` counts the whole history for paging.
  Future<NotificationPage> notifications(
    String userId, {
    int limit = 50,
    int offset = 0,
  }) async {
    final r = await _dio.get<Map<String, dynamic>>(
      '/v1/notifications/$userId',
      queryParameters: {'limit': limit, 'offset': offset},
    );
    return NotificationPage.fromJson(r.data!);
  }

  /// Idempotent server-side `read_at` stamp.
  Future<void> markNotificationRead(String userId, String notificationId) async {
    await _dio.post<void>('/v1/notifications/$userId/$notificationId/read');
  }

  /// Stamp every unread row; returns how many were stamped.
  Future<int> markAllNotificationsRead(String userId) async {
    final r = await _dio
        .post<Map<String, dynamic>>('/v1/notifications/$userId/read_all');
    return ((r.data?['updated'] as num?) ?? 0).toInt();
  }

  /// Server-counted unread rows — the same `notifications` table the OS
  /// icon badge reads (CR135 badge-count parity: no second counter).
  Future<int> notificationUnreadCount(String userId) async {
    final r = await _dio
        .get<Map<String, dynamic>>('/v1/notifications/$userId/unread_count');
    return ((r.data?['unread'] as num?) ?? 0).toInt();
  }

  /// Every type in the backend vocabulary, defaults filled in (no stored
  /// row = enabled). The server's list is authoritative — the client
  /// renders what arrives, so a type this build predates still shows.
  Future<List<NotificationPreference>> notificationPreferences(
      String userId) async {
    final r = await _dio
        .get<Map<String, dynamic>>('/v1/notifications/$userId/preferences');
    return ((r.data?['items'] as List?) ?? const [])
        .map((e) => NotificationPreference.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  /// Partial update — only the named types change. Returns the full
  /// refreshed set. Unknown types are a 422, surfaced, never swallowed.
  Future<List<NotificationPreference>> patchNotificationPreferences(
    String userId,
    Map<String, bool> updates,
  ) async {
    final r = await _dio.patch<Map<String, dynamic>>(
      '/v1/notifications/$userId/preferences',
      data: {'updates': updates},
    );
    return ((r.data?['items'] as List?) ?? const [])
        .map((e) => NotificationPreference.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  // ── CR181 persona telemetry ────────────────────────────────────────────

  /// POST /v1/telemetry/events — batched persona-telemetry ingest. The
  /// backend takes the user from the bearer token; the payload never names
  /// one. Callers go through `TelemetryEmitter` (fire-and-forget, retries,
  /// drop accounting) — never call this on a user-visible path.
  Future<({int accepted, int duplicates})> telemetryEvents(
    List<Map<String, dynamic>> events,
  ) async {
    final r = await _dio.post<Map<String, dynamic>>(
      '/v1/telemetry/events',
      data: {'events': events},
    );
    final data = r.data!;
    return (
      accepted: data['accepted'] as int,
      duplicates: data['duplicates'] as int,
    );
  }

  // ── Alpaca paper trading (AT:R45; gutted CR202) ────────────────────────
  //
  // The status / portfolio / positions proxies and both link-and-store calls
  // are gone: the credential lives on this device now and the app talks to
  // paper-api.alpaca.markets directly (services/alpaca/alpaca_client.dart).
  // What the backend still receives is the *result* — positions, uploaded with
  // a Room convene or a 1-on-1 turn so the agents can see the linked account.
  // See the `alpaca` argument on streamRoom / streamOneOnOneMessage.
  //
  // The one exception is the OAuth code exchange: Alpaca's token endpoint
  // requires client_secret and documents no PKCE, so it cannot run on-device.
  // The backend performs it and hands the tokens straight back — it stores
  // nothing. Parked: unreachable until ALPACA_CLIENT_ID is set and Alpaca
  // approves the app.

  /// CR203 — tell the backend WHETHER this device holds a credential, never
  /// what it is. Best-effort at every call site: failing to report must not
  /// fail the link itself, because the link is device-local and already
  /// succeeded by the time this runs.
  Future<void> alpacaReportLinkState(bool linked) async {
    await _dio.post<Map<String, dynamic>>(
      '/v1/alpaca/link_state',
      data: {'linked': linked},
    );
  }

  Future<({String accessToken, String refreshToken})> alpacaExchangeOAuthCode(
    String code,
  ) async {
    final r = await _dio.post<Map<String, dynamic>>(
      '/v1/alpaca/link',
      data: {'code': code},
    );
    return (
      accessToken: r.data!['access_token'] as String,
      refreshToken: (r.data!['refresh_token'] ?? '') as String,
    );
  }

  // ── Games (CR109 slice 2 — dark-launched behind AMI_GAMES) ─────────────
  //
  // The API surface itself is NOT gated: Amendment F's gate is client-route
  // -only (`/v1/games/*` registers server-side with `include_in_schema=False`,
  // never behind a runtime flag — see `features/games/games_gate.dart`). So
  // these methods are ordinary and unconditional; nothing calls them unless
  // a gated build's `/games` route is reached, and no store binary reaches it.
  // No `{user_id}` in any path — like `/v1/league/me`, the caller is derived
  // from the Bearer token `_AuthInterceptor` already attaches.

  /// CR109. `/v1/games/cadences` and `/v1/games/runs` return a BARE JSON
  /// ARRAY, not an enveloped object. Asking Dio for `Map<String, dynamic>`
  /// makes it throw on the cast, which surfaced in the app as
  /// "Couldn't load your game runs" on top of a perfectly good HTTP 200 —
  /// the network log said success while the screen said failure.
  ///
  /// `_listBody` accepts either shape so the client cannot break again if an
  /// envelope is added later, and so neither side has to guess.
  static List<dynamic> _listBody(dynamic data, String envelopeKey) {
    if (data is List) return data;
    if (data is Map && data[envelopeKey] is List) {
      return data[envelopeKey] as List;
    }
    return const [];
  }

  Future<List<GameCadenceInfo>> gamesCadences() async {
    final r = await _dio.get<dynamic>('/v1/games/cadences');
    return _listBody(r.data, 'cadences')
        .map((e) => GameCadenceInfo.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  /// 409 if the caller already holds this cadence (§4.1's one-live-run-
  /// per-cadence guard) — propagates as an ordinary `DioException`, same
  /// shape as every other refused write in this client.
  Future<GameEntry> gamesEnter({required String cadence}) async {
    final r = await _dio.post<Map<String, dynamic>>(
      '/v1/games/enter',
      data: {'cadence': cadence},
    );
    return GameEntry.fromJson(r.data!);
  }

  Future<List<GameRunSummary>> gamesRuns() async {
    final r = await _dio.get<dynamic>('/v1/games/runs');
    return _listBody(r.data, 'runs')
        .map((e) => GameRunSummary.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  Future<GameRunDetail> gamesRunDetail(String runId) async {
    final r = await _dio.get<Map<String, dynamic>>('/v1/games/runs/$runId');
    return GameRunDetail.fromJson(r.data!);
  }

  /// The ticket's TAP-3 pre-confirm — shares, est. fee, book-percentage
  /// (§5.4). [notional] is client-computed (a size chip's % × the run's
  /// current cash), per the design's "zero round trips" rule for the size
  /// chips themselves — this is the ticket's ONE network call before submit.
  /// Sized by DOLLARS or by SHARES — exactly one, which is what the endpoint's
  /// own validator enforces.
  ///
  /// A BUY sizes in dollars: the ticket picks a percentage of the book, which
  /// is inherently a notional, and only the server has the price to turn that
  /// into a share count.
  ///
  /// A SELL sizes in SHARES, because the thing being divided up is the
  /// position, not the cash. "Sell 50%" means half the shares you hold — a
  /// number the client already knows exactly — and routing it through a
  /// dollar amount would re-derive it from a price and land a few thousandths
  /// off, which at 100% is the difference between closing a position and
  /// leaving a dust holding behind.
  Future<GameTradeQuote> gamesTradeQuote({
    required String runId,
    required String ticker,
    required String side,
    double? notional,
    double? quantity,
  }) async {
    assert(
      (notional == null) != (quantity == null),
      'exactly one of notional or quantity',
    );
    final r = await _dio.post<Map<String, dynamic>>(
      '/v1/games/runs/$runId/trade/quote',
      data: {
        'ticker': ticker,
        'side': side,
        if (notional != null) 'notional': notional,
        if (quantity != null) 'quantity': quantity,
      },
    );
    return GameTradeQuote.fromJson(r.data!);
  }

  /// Places or queues the order the ticket just quoted. §5.1: outside US
  /// market hours this queues rather than filling at a stale price — the
  /// server decides and the response's `status` says which happened.
  /// Takes SHARES, not dollars. The ticket sizes in dollars, so the caller
  /// passes the `quantity` the quote just returned.
  ///
  /// That is not an accident of the API: outside market hours this order
  /// queues, and the backend never prices a queued order — pricing it at
  /// queue time is the stale-price hindsight exploit the market-hours rule
  /// exists to prevent. Sending dollars would force a conversion, and the
  /// conversion needs a price.
  Future<GameTradeResult> gamesTrade({
    required String runId,
    required String ticker,
    required String side,
    required double quantity,
  }) async {
    final r = await _dio.post<Map<String, dynamic>>(
      '/v1/games/runs/$runId/trade',
      data: {'ticker': ticker, 'side': side, 'quantity': quantity},
    );
    return GameTradeResult.fromJson(r.data!);
  }

  /// Every order still waiting on the next US open, priced at read time.
  /// Returns a BARE JSON array (`list[dict]` from the router), same as
  /// `/cadences` and `/runs` — `_listBody` accepts either shape so a later
  /// envelope cannot break this the way it broke `gamesRuns`.
  Future<List<GameQueuedOrder>> gamesQueuedOrders(String runId) async {
    final r = await _dio.get<dynamic>('/v1/games/runs/$runId/orders');
    return _listBody(r.data, 'orders')
        .map((e) => GameQueuedOrder.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  /// Cancels a queued order. The ticket has promised "free to cancel any
  /// time before it fills" (§5.1) since slice 2 shipped; this is what lets
  /// the app keep it.
  ///
  /// Returns the server's own `cancelled` boolean rather than "it did not
  /// throw". An order that filled between the list and the tap comes back
  /// `{"cancelled": false, "state": "filled"}` with a 200 — reporting that
  /// as a cancellation would be the same class of lie as the `status ??
  /// 'filled'` default this file's models were built to stop.
  Future<bool> gamesCancelQueuedOrder({
    required String runId,
    required String orderId,
  }) async {
    final r = await _dio.post<Map<String, dynamic>>(
      '/v1/games/runs/$runId/orders/$orderId/cancel',
    );
    return r.data?['cancelled'] == true;
  }

  /// §6.7 — restart is preview-then-commit over one endpoint: called with
  /// `confirm: false` (the default) it returns the forfeit cost without
  /// acting; `confirm: true` commits it.
  Future<GameRestartPreview> gamesRestart({
    required String runId,
    bool confirm = false,
  }) async {
    final r = await _dio.post<Map<String, dynamic>>(
      '/v1/games/runs/$runId/restart',
      data: {'confirm': confirm},
    );
    return GameRestartPreview.fromJson(r.data!);
  }

  // ── Games — the Close and the Record (CR109 slice 3) ────────────────────
  //
  // Same unconditional-surface note as the slice-2 block above: the server
  // route is never gated, only the client's own reachability is
  // (`features/games/games_gate.dart`).

  /// The Close's full payload (design §10.2) — three beats plus the debrief
  /// block. Carries no entitlement field; see `models/games.dart`'s
  /// `GameCloseResult` docstring for why.
  Future<GameCloseResult> gamesClose(String runId) async {
    final r =
        await _dio.get<Map<String, dynamic>>('/v1/games/runs/$runId/close');
    return GameCloseResult.fromJson(r.data!);
  }

  /// The field board — where you stand against everyone else in the run.
  ///
  /// Ranks on % TWR only (design §6.1's written-down invariant), moves once
  /// per US close rather than per tick (§10), and carries no currency amount
  /// for any entrant including you.
  Future<GameBoard> gamesBoard(String runId) async {
    final r =
        await _dio.get<Map<String, dynamic>>('/v1/games/runs/$runId/board');
    return GameBoard.fromJson(r.data!);
  }

  /// The period arc's live beat (CR109 slice 5, design §10) — the entry
  /// countdown, the bell, the daily standing, the final stretch.
  ///
  /// Separate from [gamesRunDetail] for the same reason [gamesBoard] is: it
  /// ranks the whole field, and the run detail is re-read on every size drag
  /// of the ticket. Standings inside it move once per US close; the
  /// attribution line is live.
  Future<GameArc> gamesArc(String runId) async {
    final r = await _dio.get<Map<String, dynamic>>('/v1/games/runs/$runId/arc');
    return GameArc.fromJson(r.data!);
  }

  /// The house desks' published rules (design §11.2). The rule text comes
  /// from the server, not from app copy — a rule that lived in the client
  /// would drift from the code that actually picks the names, and a stale
  /// published rule is worse than none.
  Future<List<GameDeskProfile>> gamesDesks() async {
    final r = await _dio.get<dynamic>('/v1/games/desks');
    return _listBody(r.data, 'desks')
        .map((e) => GameDeskProfile.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  /// Career points, forfeit count and run history — the Record's
  /// "identity / movement / history" surface (design §13.3).
  Future<GameRecord> gamesRecord() async {
    final r = await _dio.get<Map<String, dynamic>>('/v1/games/record');
    return GameRecord.fromJson(r.data!);
  }

  /// The shipped `games_record_service.py.get_personal_records` response is
  /// an OBJECT keyed by category — `{best_weekly_twr: {...}|null,
  /// best_alpha: {...}|null, best_drawdown_control: {...}|null,
  /// longest_hold_days: {...}|null, longest_finish_streak: {...}|null}` —
  /// not a list, and each category's own value lives under a DIFFERENT key
  /// (`final_twr_pct` / `alpha_scored_pct` / `max_drawdown_pct` / `days` /
  /// `count`). This is the wire-shape adapter into
  /// [GamePersonalRecord]'s generic `{kind, entry_id, value}` shape — a
  /// category also carrying a fallback flat `prs` list (an older/plan-doc
  /// shape) is read first if present, so this stays correct against
  /// either.
  static const _prCategoryValueKeys = <String, String>{
    'best_weekly_twr': 'final_twr_pct',
    'best_alpha': 'alpha_scored_pct',
    'best_drawdown_control': 'max_drawdown_pct',
    'longest_hold_days': 'days',
    'longest_finish_streak': 'count',
  };

  /// The PR board — works at n = 1 (implementation_plan.md §4.4.2).
  Future<List<GamePersonalRecord>> gamesRecordPrs() async {
    final r = await _dio.get<Map<String, dynamic>>('/v1/games/record/prs');
    final data = r.data ?? const <String, dynamic>{};

    final flatList = data['prs'];
    if (flatList is List) {
      return flatList
          .map((e) => GamePersonalRecord.fromJson(e as Map<String, dynamic>))
          .toList();
    }

    final out = <GamePersonalRecord>[];
    for (final category in _prCategoryValueKeys.entries) {
      final raw = data[category.key];
      if (raw is! Map<String, dynamic>) continue;
      // 'longest_hold_days' is the wire category key; 'longest_hold' is
      // this client's `kind` constant (matches GamePersonalRecord's own
      // category labels in games_record_screen.dart).
      final kind = category.key == 'longest_hold_days' ? 'longest_hold' : category.key;
      out.add(GamePersonalRecord.fromJson({
        'kind': kind,
        'entry_id': raw['entry_id'],
        'value': raw[category.value],
      }));
    }
    return out;
  }
}
