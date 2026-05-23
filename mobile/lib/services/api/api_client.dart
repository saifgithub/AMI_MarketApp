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

import 'package:ami_trade/models/auth.dart';
import 'package:ami_trade/models/ai_coach.dart';
import 'package:ami_trade/models/brief.dart';
import 'package:ami_trade/models/daily_challenge.dart';
import 'package:ami_trade/models/journal.dart';
import 'package:ami_trade/models/lessons.dart';
import 'package:ami_trade/models/mandate.dart';
import 'package:ami_trade/models/one_on_one.dart';
import 'package:ami_trade/models/onboarding.dart';
import 'package:ami_trade/models/room.dart';
import 'package:ami_trade/models/sim.dart';
import 'package:ami_trade/models/watchlist.dart';
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
    handler.next(options);
  }
}

class ApiClient {
  ApiClient({String? baseUrl}) : _dio = Dio(BaseOptions(
        baseUrl: baseUrl ?? _resolveBaseUrl(),
        connectTimeout: const Duration(seconds: 10),
        receiveTimeout: const Duration(seconds: 30),
        headers: {'Content-Type': 'application/json'},
      )) {
    _dio.interceptors.add(_AuthInterceptor(this));
  }

  final Dio _dio;
  String? _bearerToken;

  void setToken(String? token) {
    _bearerToken = token;
  }

  /// Build a raw `http.Request` for SSE endpoints that can't go through Dio.
  /// Adversarial audit (2026-05-18) finding A8: previously these requests
  /// bypassed the Dio interceptor and sent no Authorization header, so
  /// `/v1/brief/message`, `/v1/agents/one_on_one/message`, and
  /// `/v1/room/stream` would 401 once the backend enforced auth.
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

  Future<ReadbackConfirmResponse> confirmReadback({
    required String sessionId,
    required bool confirm,
  }) async {
    final r = await _dio.post<Map<String, dynamic>>(
      '/v1/onboarding/readback/confirm',
      data: {
        'session_id': sessionId,
        'confirm': confirm ? 'confirm' : 'edit',
        'edits': const <String, dynamic>{},
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
    final client = http.Client();
    try {
      final response = await client.send(_sseRequest(uri, body));
      if (response.statusCode != 200) {
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
            yield data.replaceAll(r'\n', '\n').replaceAll(r'\\', r'\');
          } else if (eventType == 'done') {
            return;
          } else if (eventType == 'error') {
            throw Exception('Server error: $data');
          }
        }
      }
    } finally {
      client.close();
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
  }) async* {
    final uri = Uri.parse('$baseUrl/v1/agents/one_on_one/message');
    final body = jsonEncode({
      'session_id': sessionId,
      'user_message': userMessage,
      'history': history.map((m) => m.toJson()).toList(),
    });

    final client = http.Client();
    try {
      final response = await client.send(_sseRequest(uri, body));
      if (response.statusCode != 200) {
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
            // Backend escapes newlines as "\\n"; un-escape for display.
            yield data.replaceAll(r'\n', '\n').replaceAll(r'\\', r'\');
          } else if (eventType == 'done') {
            return;
          } else if (eventType == 'error') {
            throw Exception('Server error: $data');
          }
        }
      }
    } finally {
      client.close();
    }
  }

  // ── Decision Journal ────────────────────────────────────────────

  Future<JournalListResponse> listJournal({
    required String userId,
    String plan = 'trial_trader',
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

  Future<Lesson> getLesson(String lessonId) async {
    final r = await _dio.get<Map<String, dynamic>>('/v1/lessons/$lessonId');
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
    double portfolioValue = 100000.0,
    double currentDrawdownPct = 0.0,
  }) async* {
    final uri = Uri.parse('$baseUrl/v1/room/stream');
    final body = jsonEncode({
      'user_id': userId,
      'ticker': ticker,
      'locale': locale,
      if (mandateOverride != null) 'mandate_override': mandateOverride,
      'portfolio_value': portfolioValue,
      'current_drawdown_pct': currentDrawdownPct,
    });
    final client = http.Client();
    try {
      final response = await client.send(_sseRequest(uri, body));
      if (response.statusCode != 200) {
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
          try {
            switch (eventType) {
              case 'started':
                final j = jsonDecode(data) as Map<String, dynamic>;
                yield {'kind': 'started', 'run_id': j['run_id']};
                break;
              case 'phase':
                final j = jsonDecode(data) as Map<String, dynamic>;
                yield {'kind': 'phase', 'label': j['label']};
                break;
              case 'agent_token':
                final j = jsonDecode(data) as Map<String, dynamic>;
                final text = (j['text'] as String? ?? '')
                    .replaceAll(r'\n', '\n')
                    .replaceAll(r'\\', r'\');
                yield {
                  'kind': 'agent_token',
                  'agent_id': j['agent_id'],
                  'text': text,
                };
                break;
              case 'agent_done':
                final j = jsonDecode(data) as Map<String, dynamic>;
                yield {'kind': 'agent_done', 'agent_id': j['agent_id']};
                break;
              case 'verdict':
                final j = jsonDecode(data) as Map<String, dynamic>;
                yield {'kind': 'verdict', 'verdict': RoomVerdict.fromJson(j)};
                break;
              case 'done':
                final j = jsonDecode(data) as Map<String, dynamic>;
                yield {'kind': 'done', 'run_id': j['run_id']};
                return;
              case 'error':
                yield {'kind': 'error', 'message': data};
                return;
            }
          } catch (e) {
            // skip malformed event
          }
        }
      }
    } finally {
      client.close();
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
        if (stop != null) 'stop': stop,
        if (target != null) 'target': target,
        if (horizonDays != null) 'horizon_days': horizonDays,
        if (verdictRef != null) 'verdict_ref': verdictRef,
      },
    );
    return SimSubmitResult.fromJson(r.data!);
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
}
