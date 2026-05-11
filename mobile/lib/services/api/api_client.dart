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

import 'package:ami_trade/models/coach.dart';
import 'package:ami_trade/models/journal.dart';
import 'package:ami_trade/models/lessons.dart';
import 'package:ami_trade/models/one_on_one.dart';
import 'package:ami_trade/models/onboarding.dart';
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

class ApiClient {
  ApiClient({String? baseUrl})
      : _dio = Dio(BaseOptions(
          baseUrl: baseUrl ?? _resolveBaseUrl(),
          connectTimeout: const Duration(seconds: 10),
          receiveTimeout: const Duration(seconds: 30),
          headers: {'Content-Type': 'application/json'},
        ));

  final Dio _dio;

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
    String? userId,
  }) async {
    final r = await _dio.post<Map<String, dynamic>>(
      '/v1/agents/one_on_one/start',
      data: {
        'agent_id': agentId,
        'locale': locale,
        if (userId != null) 'user_id': userId,
      },
    );
    return OneOnOneSession.fromJson(r.data!);
  }

  // ── Coach Your Agent ────────────────────────────────────────────

  Future<CoachStartResponse> startCoach({
    required String agentId,
    required String userId,
    String mode = 'from_scratch',
    String locale = 'en',
  }) async {
    final r = await _dio.post<Map<String, dynamic>>(
      '/v1/coach/start',
      data: {
        'agent_id': agentId,
        'user_id': userId,
        'mode': mode,
        'locale': locale,
      },
    );
    return CoachStartResponse.fromJson(r.data!);
  }

  Stream<String> streamCoachMessage({
    required String sessionId,
    required String userMessage,
    required List<ChatMessage> history,
  }) async* {
    final uri = Uri.parse('$baseUrl/v1/coach/message');
    final body = jsonEncode({
      'session_id': sessionId,
      'user_message': userMessage,
      'history': history.map((m) => m.toJson()).toList(),
    });
    final client = http.Client();
    try {
      final request = http.Request('POST', uri)
        ..headers['Content-Type'] = 'application/json'
        ..headers['Accept'] = 'text/event-stream'
        ..body = body;
      final response = await client.send(request);
      if (response.statusCode != 200) {
        throw Exception('HTTP ${response.statusCode} from coach stream');
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

  Future<CoachProposal> proposeCoachChange({
    required String sessionId,
    required List<ChatMessage> history,
  }) async {
    final r = await _dio.post<Map<String, dynamic>>(
      '/v1/coach/propose',
      data: {
        'session_id': sessionId,
        'history': history.map((m) => m.toJson()).toList(),
      },
    );
    return CoachProposal.fromJson(r.data!);
  }

  /// Returns the new overlay if accepted, or a map with `refusal` if blocked.
  Future<Map<String, dynamic>> acceptCoachProposal({
    required String sessionId,
    required String proposalId,
  }) async {
    final r = await _dio.post<Map<String, dynamic>>(
      '/v1/coach/accept',
      data: {'session_id': sessionId, 'proposal_id': proposalId},
    );
    return r.data!;
  }

  Future<void> rejectCoachProposal({
    required String sessionId,
    required String proposalId,
  }) async {
    await _dio.post<Map<String, dynamic>>(
      '/v1/coach/reject',
      data: {'session_id': sessionId, 'proposal_id': proposalId},
    );
  }

  Future<UserOverlay> rollbackCoach({
    required String userId,
    required String agentId,
    required int toVersion,
  }) async {
    final r = await _dio.post<Map<String, dynamic>>(
      '/v1/coach/rollback',
      data: {
        'user_id': userId,
        'agent_id': agentId,
        'to_version': toVersion,
      },
    );
    return UserOverlay.fromJson(r.data!);
  }

  Future<CoachHistory> coachHistory({
    required String userId,
    required String agentId,
    String plan = 'trial_trader',
  }) async {
    final r = await _dio.get<Map<String, dynamic>>(
      '/v1/coach/history/$userId/$agentId',
      queryParameters: {'plan': plan},
    );
    return CoachHistory.fromJson(r.data!);
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
      final request = http.Request('POST', uri)
        ..headers['Content-Type'] = 'application/json'
        ..headers['Accept'] = 'text/event-stream'
        ..body = body;

      final response = await client.send(request);
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
    int limit = 100,
  }) async {
    final r = await _dio.get<Map<String, dynamic>>(
      '/v1/journal/$userId',
      queryParameters: {
        'plan': plan,
        if (entryType != null) 'entry_type': entryType,
        if (ticker != null) 'ticker': ticker,
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

  Future<List<AgentActivationRecord>> agentActivations(String userId) async {
    final r = await _dio.get<List<dynamic>>(
      '/v1/lessons/activations/$userId',
    );
    return (r.data ?? const [])
        .map((e) => AgentActivationRecord.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  Future<AgentActivationRecord> grantActivation({
    required String userId,
    required String agentId,
    String method = 'founder_grant',
  }) async {
    final r = await _dio.post<Map<String, dynamic>>(
      '/v1/lessons/activations/grant',
      data: {'user_id': userId, 'agent_id': agentId, 'method': method},
    );
    return AgentActivationRecord.fromJson(r.data!);
  }
}
