/// Direct Alpaca paper-API client (CR202).
///
/// The app talks to Alpaca itself, using credentials that never leave the
/// device. Flutter's HTTP stack is not a browser, so no CORS preflight
/// applies — the `APCA-API-*` headers work exactly as they do from a server.
///
/// The host defaults to `paper-api.alpaca.markets` but is user-overridable
/// (CR224) — Alpaca does not resolve every account to that same host, so the
/// base URL is read from `AlpacaCredentialStore` per request rather than
/// fixed at construction time.
///
/// **This deliberately does NOT reuse `api_client.dart`'s Dio.** That instance
/// carries AMI's base URL and an auth interceptor that attaches the user's AMI
/// bearer token to every request; borrowing it would send AMI's own credential
/// to a third party. A separate instance with no interceptors is the whole
/// point.
///
/// Read-only except for one narrow exception (CR227, D-071): `submitOrder`
/// places a **market** order, and only when `creds.baseUrl` resolves to a
/// confirmed Alpaca *paper* host. It is the sole POST this file is allowed to
/// grow, and it re-checks the paper-host rule itself rather than trusting
/// whatever the caller already checked — the backend never sees this call at
/// all (still true, unchanged by CR227: DEF145's guard test pins that the
/// backend has no path to `/v2/orders`). A live/production Alpaca account
/// remains permanently unreachable for order placement from this client.
library;

import 'package:ami_trade/models/alpaca.dart';
import 'package:ami_trade/services/alpaca/alpaca_credential_store.dart';
import 'package:dio/dio.dart';

/// True only when [baseUrl] resolves to a known Alpaca **paper** host.
///
/// Alpaca's own convention names the distinction in the hostname itself:
/// paper endpoints are `paper-api.alpaca.markets` (optionally region/account-
/// prefixed per CR224 — some users are handed a different subdomain), live
/// endpoints are `api.alpaca.markets`, no `paper-` segment. Checking by
/// pattern, not by an equality against the single default, is what makes this
/// work for a CR224 override too — the alternative, trusting a stored label,
/// is exactly the failure mode D-071 calls out ("never trust a label, check
/// the endpoint").
bool isAlpacaPaperHost(String baseUrl) {
  final host = Uri.tryParse(baseUrl)?.host.toLowerCase() ?? '';
  return host.endsWith('.alpaca.markets') && host.contains('paper');
}

class AlpacaOrderRejected implements Exception {
  const AlpacaOrderRejected(this.message);

  final String message;

  @override
  String toString() => 'AlpacaOrderRejected: $message';
}

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
              connectTimeout: const Duration(seconds: 10),
              receiveTimeout: const Duration(seconds: 10),
            ));

  final Dio _dio;

  Future<Map<String, String>> _headers(AlpacaCredentials creds) async {
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
    final creds = await AlpacaCredentialStore.read();
    if (creds == null) {
      throw const AlpacaException(null, 'not linked');
    }
    try {
      final r = await _dio.get<dynamic>(
        '${creds.baseUrl}$path',
        options: Options(headers: await _headers(creds)),
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
  /// claims to open. Takes the credentials (and base URL) directly rather
  /// than reading the store, so the connect screen can check a pair — and an
  /// endpoint override (CR224) — the user has not committed to yet.
  Future<void> validate(
    String keyId,
    String secret, {
    String baseUrl = kDefaultAlpacaBaseUrl,
  }) async {
    try {
      await _dio.get<dynamic>(
        '$baseUrl/v2/account',
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

  /// Place a market order against the user's linked Alpaca **paper** account
  /// (CR227, D-071). Callers are expected to have already cleared AMI's
  /// mandate/compliance floor (via `/v1/sim/preview`) before calling this —
  /// this method only re-enforces the paper-host rule, not the trading
  /// mandate, which it has no knowledge of.
  ///
  /// Market + day only, matching AMI's own "no partial fill, single price"
  /// semantics — see CR227's Non-goals for why resting order types aren't
  /// modelled here.
  Future<AlpacaOrder> submitOrder({
    required String symbol,
    required String side,
    required double qty,
  }) async {
    final creds = await AlpacaCredentialStore.read();
    if (creds == null) {
      throw const AlpacaException(null, 'not linked');
    }
    if (!isAlpacaPaperHost(creds.baseUrl)) {
      throw AlpacaOrderRejected(
        'refusing to place an order against a non-paper Alpaca host: '
        '${creds.baseUrl}',
      );
    }
    try {
      final r = await _dio.post<dynamic>(
        '${creds.baseUrl}/v2/orders',
        data: {
          'symbol': symbol,
          'side': side,
          'qty': qty.toString(),
          'type': 'market',
          'time_in_force': 'day',
        },
        options: Options(headers: await _headers(creds)),
      );
      return AlpacaOrder.fromJson(r.data as Map<String, dynamic>);
    } on DioException catch (e) {
      throw AlpacaException(
        e.response?.statusCode,
        e.response?.data?.toString() ?? e.message ?? 'network error',
      );
    }
  }
}
