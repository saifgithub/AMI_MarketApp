/// Direct Alpaca paper-API client (CR202).
///
/// The app talks to `paper-api.alpaca.markets` itself, using credentials that
/// never leave the device. Flutter's HTTP stack is not a browser, so no CORS
/// preflight applies — the `APCA-API-*` headers work exactly as they do from a
/// server.
///
/// **This deliberately does NOT reuse `api_client.dart`'s Dio.** That instance
/// carries AMI's base URL and an auth interceptor that attaches the user's AMI
/// bearer token to every request; borrowing it would send AMI's own credential
/// to a third party. A separate instance with no interceptors is the whole
/// point.
///
/// Read-only by construction: the only two calls are GETs. AMI is
/// simulation-only by locked decision and places no order on a user's
/// brokerage account, paper or otherwise (D-004, DEF145) — moving the
/// credential to the device does not change that, and nothing here should ever
/// grow a POST.
library;

import 'package:ami_trade/models/alpaca.dart';
import 'package:ami_trade/services/alpaca/alpaca_credential_store.dart';
import 'package:dio/dio.dart';

class AlpacaException implements Exception {
  const AlpacaException(this.statusCode, this.detail);

  final int? statusCode;
  final String detail;

  /// The credential was rejected — the user must re-link, and no retry helps.
  bool get isAuthFailure => statusCode == 401 || statusCode == 403;

  @override
  String toString() => 'AlpacaException($statusCode): $detail';
}

class AlpacaClient {
  AlpacaClient({Dio? dio})
      : _dio = dio ??
            Dio(BaseOptions(
              baseUrl: 'https://paper-api.alpaca.markets',
              connectTimeout: const Duration(seconds: 10),
              receiveTimeout: const Duration(seconds: 10),
            ));

  final Dio _dio;

  Future<Map<String, String>> _headers() async {
    final creds = await AlpacaCredentialStore.read();
    if (creds == null) {
      throw const AlpacaException(null, 'not linked');
    }
    // Mirrors the header branch the backend's `_paper_get` used to carry.
    if (creds.mode == AlpacaAuthMode.oauth) {
      return {'Authorization': 'Bearer ${creds.keyId}'};
    }
    return {
      'APCA-API-KEY-ID': creds.keyId,
      'APCA-API-SECRET-KEY': creds.secret,
    };
  }

  Future<T> _get<T>(String path, T Function(dynamic) parse) async {
    try {
      final r = await _dio.get<dynamic>(
        path,
        options: Options(headers: await _headers()),
      );
      return parse(r.data);
    } on DioException catch (e) {
      throw AlpacaException(
        e.response?.statusCode,
        e.response?.data?.toString() ?? e.message ?? 'network error',
      );
    }
  }

  /// Validate a candidate pair BEFORE storing it, by fetching the account it
  /// claims to open. Takes the credentials directly rather than reading the
  /// store, so the connect screen can check a pair the user has not committed
  /// to yet.
  Future<void> validate(String keyId, String secret) async {
    try {
      await _dio.get<dynamic>(
        '/v2/account',
        options: Options(headers: {
          'APCA-API-KEY-ID': keyId,
          'APCA-API-SECRET-KEY': secret,
        }),
      );
    } on DioException catch (e) {
      throw AlpacaException(
        e.response?.statusCode,
        e.response?.data?.toString() ?? e.message ?? 'network error',
      );
    }
  }

  Future<AlpacaPortfolio> account() =>
      _get('/v2/account', (d) => AlpacaPortfolio.fromJson(d as Map<String, dynamic>));

  Future<List<AlpacaPosition>> positions() => _get(
        '/v2/positions',
        (d) => (d as List<dynamic>)
            .map((e) => AlpacaPosition.fromJson(e as Map<String, dynamic>))
            .toList(),
      );
}
