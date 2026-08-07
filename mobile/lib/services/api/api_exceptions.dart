/// Typed API exceptions for the AMI Trade backend.
///
/// The first custom exception in the mobile codebase (CR047). The Room stream
/// used to collapse every non-200 into a generic `Exception('HTTP 402…')`,
/// throwing away the structured credit-wall body the backend deliberately
/// sends. `InsufficientCreditsException` carries that body so the UI can render
/// a real paywall — and, under "The Winzip" funnel, a live cooldown countdown —
/// instead of a "Stream failed" toast.
library;

/// Raised when a Room convene is refused for credits (HTTP 402).
///
/// The backend body is `{"detail": {code, balance, cost, plan, resets_at, ...}}`.
/// Under GTM_FUNNEL=winzip it also carries `funnel`, `cooldown_until`, and
/// `retry_after_seconds` — the server has already re-granted one Room, so the
/// client just renders the countdown until [cooldownUntil].
import 'package:dio/dio.dart';

class InsufficientCreditsException implements Exception {
  final int balance;
  final int cost;
  final String plan;
  final DateTime? resetsAt;

  /// The active GTM funnel, e.g. 'winzip'. Null on the legacy hard wall.
  final String? funnel;

  /// When the user may convene again (Winzip). Null on the legacy hard wall.
  final DateTime? cooldownUntil;

  /// Seconds until [cooldownUntil], as computed server-side at response time.
  final int? retryAfterSeconds;

  const InsufficientCreditsException({
    required this.balance,
    required this.cost,
    required this.plan,
    this.resetsAt,
    this.funnel,
    this.cooldownUntil,
    this.retryAfterSeconds,
  });

  /// True when this is a soft, self-resetting Winzip wall rather than the
  /// hard monthly wall.
  bool get isWinzip => funnel == 'winzip';

  factory InsufficientCreditsException.fromJson(Map<String, dynamic> json) {
    // FastAPI wraps HTTPException(detail=…) as {"detail": {…}}; tolerate a
    // flat body too in case a caller passes the inner object directly.
    final detail = (json['detail'] as Map<String, dynamic>?) ?? json;

    DateTime? parseDt(Object? v) =>
        (v is String && v.isNotEmpty) ? DateTime.tryParse(v)?.toLocal() : null;

    return InsufficientCreditsException(
      balance: (detail['balance'] as num?)?.toInt() ?? 0,
      cost: (detail['cost'] as num?)?.toInt() ?? 0,
      plan: detail['plan'] as String? ?? 'floor_pass',
      resetsAt: parseDt(detail['resets_at']),
      funnel: detail['funnel'] as String?,
      cooldownUntil: parseDt(detail['cooldown_until']),
      retryAfterSeconds: (detail['retry_after_seconds'] as num?)?.toInt(),
    );
  }

  @override
  String toString() =>
      'InsufficientCreditsException(balance: $balance, cost: $cost, '
      'plan: $plan, funnel: $funnel, cooldownUntil: $cooldownUntil)';
}

/// Raised when the backend or the Cloudflare edge returns a 5xx (500/502/503/504).
///
/// DEF073: transport-level unavailability — usually transient (a deploy, a
/// container restart, or a tunnel blip like DEF070). The UI must render a
/// friendly, localized "try again" message with a Retry, never a raw status
/// code. Mapped centrally: from the Room SSE path in [ApiClient.streamRoom] and,
/// for REST, annotated onto the `DioException.error` by the client's server-error
/// interceptor so callers can `is`-check it.
class ServerUnavailableException implements Exception {
  final int statusCode;
  const ServerUnavailableException(this.statusCode);

  @override
  String toString() => 'ServerUnavailableException(status: $statusCode)';
}

/// Raised when the backend refuses a request from a build below the active
/// version floor (HTTP 426 Upgrade Required — CR121).
///
/// Same shape DEF073 established for [ServerUnavailableException]: annotated
/// onto the `DioException.error` slot by `_VersionGateInterceptor`
/// (`api_client.dart`), so the existing `DioException` still propagates
/// unchanged for any caller that doesn't specifically check for this.
///
/// The body is `{"detail": {min_build, recommended_build, action, headline,
/// body, store_url}}` — the same JSON `GET /v1/client/release-floor`
/// returns, so one screen can render either source. `action` is always
/// `"block"` here (the middleware only emits 426 for the block case), kept
/// as a field rather than assumed so a future server change that reuses 426
/// for a different action doesn't silently mis-render.
class UpgradeRequiredException implements Exception {
  final int? minBuild;
  final int? recommendedBuild;
  final String action;
  final String? headline;
  final String? body;
  final String? storeUrl;

  const UpgradeRequiredException({
    this.minBuild,
    this.recommendedBuild,
    this.action = 'block',
    this.headline,
    this.body,
    this.storeUrl,
  });

  factory UpgradeRequiredException.fromJson(Map<String, dynamic> json) {
    final detail = (json['detail'] as Map<String, dynamic>?) ?? json;
    return UpgradeRequiredException(
      minBuild: (detail['min_build'] as num?)?.toInt(),
      recommendedBuild: (detail['recommended_build'] as num?)?.toInt(),
      action: detail['action'] as String? ?? 'block',
      headline: detail['headline'] as String?,
      body: detail['body'] as String?,
      storeUrl: detail['store_url'] as String?,
    );
  }

  @override
  String toString() =>
      'UpgradeRequiredException(minBuild: $minBuild, action: $action)';
}

/// Extract an [UpgradeRequiredException] from a thrown REST error, whether it
/// arrives bare or annotated onto a `DioException.error` slot by
/// `_VersionGateInterceptor`.
///
/// CR121 audit MAJOR — this lives here, next to the exception, rather than in
/// `api_client.dart`, because BOTH the client and `friendly_error.dart` need
/// it and `friendly_error.dart` must not depend on the whole API client. The
/// wrapped shape is the one that matters in practice: the interceptor
/// annotates and re-throws a `DioException`, so every real call site catches
/// the wrapper, never the bare exception. A branch that only tests
/// `error is UpgradeRequiredException` looks correct and matches nothing —
/// which is exactly how the 426 reached users as "AMI is unreachable".
UpgradeRequiredException? asUpgradeRequired(Object error) {
  if (error is UpgradeRequiredException) return error;
  if (error is DioException && error.error is UpgradeRequiredException) {
    return error.error as UpgradeRequiredException;
  }
  return null;
}
