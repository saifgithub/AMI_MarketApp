/// REST client for the AMI Trade backend.
///
/// Base URL resolution priority:
///   1. AMI_API_URL Dart define (`--dart-define=AMI_API_URL=https://api...`)
///   2. Compile-time default for the platform:
///      - iOS simulator → http://localhost:8000
///      - Physical iOS device → http://HOST_LAN_IP:8000 (override via env)
///      - macOS / web → http://localhost:8000
library;

import 'dart:io' show Platform;

import 'package:ami_trade/models/onboarding.dart';
import 'package:dio/dio.dart';

const String _apiUrlFromEnv = String.fromEnvironment(
  'AMI_API_URL',
  defaultValue: '',
);

String _resolveBaseUrl() {
  if (_apiUrlFromEnv.isNotEmpty) return _apiUrlFromEnv;
  // Default — assume Mac host is reachable at localhost (Simulator)
  // or at the developer's LAN IP (physical device). For the alpha demo
  // we hard-code one; production resolves via DNS.
  if (Platform.isIOS || Platform.isAndroid) {
    // ASSUMPTION: backend runs on Saiful's Mac at host LAN IP.
    // Set --dart-define=AMI_API_URL=http://192.168.x.y:8000 to override.
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
}
