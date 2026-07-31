/// Price alert client model (CR027 §4).
library;

class PriceAlert {
  const PriceAlert({
    required this.id,
    required this.userId,
    required this.ticker,
    required this.thresholdType,
    required this.thresholdPrice,
    required this.status,
    this.tradeRef,
    required this.createdAt,
    this.firedAt,
    this.cancelledAt,
    this.agentCommentary,
  });

  final String id;
  final String userId;
  final String ticker;

  /// stop | target | manual_above | manual_below
  final String thresholdType;
  final double thresholdPrice;

  /// active | fired | cancelled
  final String status;
  final String? tradeRef;
  final DateTime createdAt;
  final DateTime? firedAt;
  final DateTime? cancelledAt;
  final String? agentCommentary;

  factory PriceAlert.fromJson(Map<String, dynamic> j) {
    DateTime? parseNullable(String? v) => v == null ? null : DateTime.parse(v);
    return PriceAlert(
      id: j['id'] as String,
      userId: j['user_id'] as String,
      ticker: j['ticker'] as String,
      thresholdType: j['threshold_type'] as String,
      thresholdPrice: (j['threshold_price'] as num).toDouble(),
      status: j['status'] as String,
      tradeRef: j['trade_ref'] as String?,
      createdAt: DateTime.parse(j['created_at'] as String),
      firedAt: parseNullable(j['fired_at'] as String?),
      cancelledAt: parseNullable(j['cancelled_at'] as String?),
      agentCommentary: j['agent_commentary'] as String?,
    );
  }
}
