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
/// Read-only except for one narrow exception (CR227, D-071; widened CR233):
/// `submitOrder` places an order — market, limit, stop, stop_limit, or a
/// bracket (stop-loss + take-profit legs) — and only when `creds.baseUrl`
/// resolves to a confirmed Alpaca *paper* host. It is the sole POST this file
/// is allowed to grow, and it re-checks the paper-host rule itself rather
/// than trusting whatever the caller already checked — the backend never
/// sees this call at all (still true, unchanged by CR227/CR233: DEF145's
/// guard test pins that the backend has no path to `/v2/orders`). A
/// live/production Alpaca account remains permanently unreachable for order
/// placement from this client.
///
/// **CR233 — real Alpaca order types, not just a market fill.** CR227
/// shipped market-only because `submitOrder` itself only ever built a market
/// request; the ticket's `_destinationLocked` hid the picker for every other
/// order type as the enforcing check. This CR gives `submitOrder` the other
/// three AMI order types natively, so the lock in `trade_ticket_sheet.dart`
/// can come off order type (see [buildAlpacaOrderPayload] and
/// [validateAlpacaOrder] below — the same "predicts, never silently
/// converts" split of authority `order_pricing.dart` already uses: this
/// module builds the exact wire body or refuses loudly, and Alpaca's own API
/// is the final word on whether the order is accepted).
library;

import 'package:ami_trade/features/sim/order_pricing.dart'
    show SimOrderType, SimOrderTif, SimOrderTypeX;
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

/// CR233 — Alpaca's own time-in-force vocabulary, mapped from AMI's resting-
/// order TIF (`order_pricing.dart`'s `SimOrderTif`).
///
/// AMI's `day` already means "this session" (CR170's `resting_order_expiry`
/// anchors DAY to the session close at placement — the same thing Alpaca's
/// own `day` means), so that leg maps exactly.
///
/// AMI's `gtd30`/`gtd90` resolve server-side to a **fixed session-close N
/// calendar-days out** (`RESTING_ORDER_TIFS = {"gtd_30": 30, "gtd_90": 90}`).
/// Alpaca's REST API has no equivalent "N days then expire" time in force on
/// the simple orders endpoint — its own `gtd` requires a client-supplied
/// `expires_at` timestamp with narrower rules (a market-hours cutoff, and
/// not honoured by every asset class), which is a second, independent
/// resting-order expiry mechanism this CR does not attempt to keep in lock-
/// step with AMI's own sweep. Rather than build that second mechanism (and
/// risk the two silently drifting apart — the exact DEF098 shape), both map
/// to Alpaca's `gtc` (good-till-cancelled): the order rests at Alpaca
/// indefinitely, until filled or the user cancels it there directly.
///
/// **This is a documented approximation, not an equivalence** — an AMI
/// GTD-30 order and its Alpaca `gtc` mirror do NOT expire at the same time
/// (AMI's expires in 30 days; Alpaca's never expires on its own). Alpaca
/// paper orders are cancellable from Alpaca's own dashboard/API, so the gap
/// is recoverable, but the ticket's result copy must not claim the two
/// expire together.
String alpacaTimeInForce(SimOrderTif tif) => switch (tif) {
      SimOrderTif.day => 'day',
      SimOrderTif.gtd30 || SimOrderTif.gtd90 => 'gtc',
      SimOrderTif.unknown => 'day',
    };

/// CR233 — client-side refusal reasons for an Alpaca order this client will
/// not even attempt to place. Distinct from [AlpacaOrderRejected] only in
/// that these are raised BEFORE any network call, by [validateAlpacaOrder] —
/// kept as the same exception type so every call site's existing
/// `on AlpacaOrderRejected catch` (CR227's refusal → CR230 `outcome:
/// refused_client_side` reporting) covers this new class of refusal for
/// free, with no new branch to forget.
///
/// A price relationship Alpaca itself would also reject (e.g. Alpaca
/// independently validates bracket ordering) is still checked here first —
/// failing loudly on THIS client's own terms, with a sentence naming what's
/// wrong, beats forwarding a vague 422 from Alpaca's own error body (DEF312/
/// DEF377's "refuse it at submit with a sentence, do not silently accept
/// it," applied to the venue call instead of the AMI mandate check).

/// The bracket leg prices this order carries, if any (CR233). Both null
/// means "no bracket" — a plain order. Mirrors the trade ticket's own
/// `_stop`/`_target` fields; this client has no knowledge of AMI's bracket
/// concept beyond these two numbers.
class AlpacaBracket {
  const AlpacaBracket({this.stopLoss, this.takeProfit});

  /// Alpaca's `stop_loss.stop_price` — the protective stop.
  final double? stopLoss;

  /// Alpaca's `take_profit.limit_price` — the profit target.
  final double? takeProfit;

  bool get isEmpty => stopLoss == null && takeProfit == null;
}

/// CR233 — validates the order's price relationships BEFORE any network
/// call, and throws [AlpacaOrderRejected] (never silently reshapes the
/// order) on the first violation found. Consistent with AMI's own DEF312/
/// DEF377 wrong-side-bracket rules (`short_rules.dart`'s `stopIsWrongSide`/
/// `targetIsWrongSide`): a long's stop sits below entry and its target
/// above; a sell (closing or opening a short via Alpaca's own independent
/// position) inverts. Alpaca has no separate "opens a short" concept from
/// the order alone — a SELL either reduces an existing long or, if none is
/// held, opens a short on Alpaca's own book — so the side-only rule below
/// (buy stop/target reasoning vs. sell) is the same shape order_pricing.dart
/// already applies for the resting-order hint, not a new invention.
///
/// A field Alpaca cannot take (unknown order type, a bracket without a
/// side Alpaca accepts brackets on) fails loudly here too — never converted
/// to something Alpaca might accept instead.
void validateAlpacaOrder({
  required String side,
  required SimOrderType orderType,
  double? limitPrice,
  double? triggerPrice,
  AlpacaBracket? bracket,
}) {
  if (orderType == SimOrderType.unknown) {
    throw const AlpacaOrderRejected(
      'refusing to place an order of an unrecognised type on Alpaca — an '
      'order type this build does not know must never be guessed at',
    );
  }
  final buy = side.toLowerCase() == 'buy';
  if (orderType.needsLimitPrice && (limitPrice == null || limitPrice <= 0)) {
    throw const AlpacaOrderRejected(
      'refusing to place a limit order on Alpaca with no limit price set',
    );
  }
  if (orderType.needsTriggerPrice &&
      (triggerPrice == null || triggerPrice <= 0)) {
    throw const AlpacaOrderRejected(
      'refusing to place a stop order on Alpaca with no stop price set',
    );
  }
  final b = bracket;
  if (b != null && !b.isEmpty) {
    // Mirrors `short_rules.dart`'s DEF312/DEF377 rule: for a BUY (a long
    // entry), the stop belongs below the fill and the target above; for a
    // SELL that opens a short on Alpaca's own book, it inverts. The named
    // entry price is the order's own limit/trigger when it has one,
    // otherwise there is nothing to compare against here (a market order's
    // fill price is unknown until Alpaca reports it) and the check is
    // skipped rather than guessed — the same "null means nothing to judge
    // yet" convention `stopIsWrongSide` uses.
    final entry = orderType.needsLimitPrice
        ? limitPrice
        : (orderType.needsTriggerPrice ? triggerPrice : null);
    if (entry != null) {
      final stop = b.stopLoss;
      final target = b.takeProfit;
      if (stop != null && stop > 0) {
        final wrongSide = buy ? stop >= entry : stop <= entry;
        if (wrongSide) {
          throw AlpacaOrderRejected(
            'refusing to place a bracket order on Alpaca whose stop-loss '
            '(\$${stop.toStringAsFixed(2)}) is on the wrong side of the '
            'entry (\$${entry.toStringAsFixed(2)}) for a $side order',
          );
        }
      }
      if (target != null && target > 0) {
        final wrongSide = buy ? target <= entry : target >= entry;
        if (wrongSide) {
          throw AlpacaOrderRejected(
            'refusing to place a bracket order on Alpaca whose take-profit '
            '(\$${target.toStringAsFixed(2)}) is on the wrong side of the '
            'entry (\$${entry.toStringAsFixed(2)}) for a $side order',
          );
        }
      }
    }
  }
}

/// CR233 — the exact `POST /v2/orders` body for one order, built once so the
/// mobile test suite can assert on it directly (golden-style) and
/// [AlpacaClient.submitOrder] has one place that decides the wire shape.
///
/// Never called before [validateAlpacaOrder] has passed — see the call site.
Map<String, dynamic> buildAlpacaOrderPayload({
  required String symbol,
  required String side,
  required double qty,
  required SimOrderType orderType,
  double? limitPrice,
  double? triggerPrice,
  SimOrderTif tif = SimOrderTif.day,
  AlpacaBracket? bracket,
}) {
  final payload = <String, dynamic>{
    'symbol': symbol,
    'side': side,
    'qty': qty.toString(),
    'type': orderType.wire == 'stop_limit' ? 'stop_limit' : orderType.wire,
    'time_in_force':
        orderType == SimOrderType.market ? 'day' : alpacaTimeInForce(tif),
  };
  if (orderType.needsLimitPrice) {
    payload['limit_price'] = limitPrice!.toString();
  }
  if (orderType.needsTriggerPrice) {
    payload['stop_price'] = triggerPrice!.toString();
  }
  final b = bracket;
  if (b != null && !b.isEmpty) {
    payload['order_class'] = 'bracket';
    if (b.takeProfit != null) {
      payload['take_profit'] = {
        'limit_price': b.takeProfit!.toStringAsFixed(2),
      };
    }
    if (b.stopLoss != null) {
      payload['stop_loss'] = {
        'stop_price': b.stopLoss!.toStringAsFixed(2),
      };
    }
  }
  return payload;
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

  /// Place an order against the user's linked Alpaca **paper** account
  /// (CR227, D-071; widened CR233). Callers are expected to have already
  /// cleared AMI's mandate/compliance floor (via `/v1/sim/preview`) before
  /// calling this — this method only re-enforces the paper-host rule and the
  /// order's own internal validity ([validateAlpacaOrder]), not the trading
  /// mandate, which it has no knowledge of.
  ///
  /// **CR233 — market, limit, stop, stop_limit, and an optional bracket
  /// (stop-loss + take-profit legs), matching the AMI ticket's own order
  /// types.** CR227 shipped market-only because this method itself only
  /// ever built a market request — round-1 audit (MAJOR-1) found that a
  /// LIMIT/STOP order routed to Alpaca was silently converted to an
  /// immediate market fill, with nothing telling the user their limit was
  /// never honoured. The fix then was to REFUSE every non-market order
  /// (`orderType != market` threw `AlpacaOrderRejected`) and hide the
  /// destination picker for one in the UI. This CR replaces that refusal
  /// with the real thing: [buildAlpacaOrderPayload] builds the exact wire
  /// body for whatever `orderType` names, [validateAlpacaOrder] checks it
  /// first and throws (never silently reshapes it) if Alpaca could not take
  /// it as asked. `orderType == unknown` still refuses, for the same reason
  /// CR227 refused everything non-market: a type this build does not
  /// recognise must never be guessed at.
  ///
  /// `tif` selects Alpaca's own time-in-force via [alpacaTimeInForce] — see
  /// that function's docstring for the `gtd30`/`gtd90` → `gtc` mapping and
  /// why it is an approximation, not an equivalence. A market order is
  /// always `day` regardless of what is passed, matching AMI's own market
  /// orders (which carry no TIF concept at all — they fill or they don't).
  Future<AlpacaOrder> submitOrder({
    required String symbol,
    required String side,
    required double qty,
    required SimOrderType orderType,
    double? limitPrice,
    double? triggerPrice,
    SimOrderTif tif = SimOrderTif.day,
    AlpacaBracket? bracket,
  }) async {
    validateAlpacaOrder(
      side: side,
      orderType: orderType,
      limitPrice: limitPrice,
      triggerPrice: triggerPrice,
      bracket: bracket,
    );
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
        data: buildAlpacaOrderPayload(
          symbol: symbol,
          side: side,
          qty: qty,
          orderType: orderType,
          limitPrice: limitPrice,
          triggerPrice: triggerPrice,
          tif: tif,
          bracket: bracket,
        ),
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
