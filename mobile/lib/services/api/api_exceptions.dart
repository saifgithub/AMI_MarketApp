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
