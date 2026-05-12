/// Watchlist client model (A18).
///
/// The list endpoint returns rows with an inline live quote so the UI
/// doesn't fan-out one /sim/quote call per row. `dayChangePct` is
/// nullable — when the backend provider doesn't carry the previous
/// close yet, the field is omitted and the UI hides the delta chip.
library;

class WatchlistEntry {
  const WatchlistEntry({
    required this.id,
    required this.userId,
    required this.ticker,
    this.notes,
    required this.addedAt,
    this.price,
    this.dayChangePct,
    this.priceSource,
  });

  final String id;
  final String userId;
  final String ticker;
  final String? notes;
  final DateTime addedAt;
  final double? price;
  final double? dayChangePct;
  final String? priceSource;

  factory WatchlistEntry.fromJson(Map<String, dynamic> j) {
    // The list endpoint nests the entry under `entry` and tucks quote
    // fields at the top level. The single-row POST returns the same
    // shape. Tolerate both.
    final entryJson = (j['entry'] as Map<String, dynamic>?) ?? j;
    return WatchlistEntry(
      id: entryJson['id'] as String,
      userId: entryJson['user_id'] as String,
      ticker: entryJson['ticker'] as String,
      notes: entryJson['notes'] as String?,
      addedAt: DateTime.parse(entryJson['added_at'] as String),
      price: (j['price'] as num?)?.toDouble(),
      dayChangePct: (j['day_change_pct'] as num?)?.toDouble(),
      priceSource: j['price_source'] as String?,
    );
  }
}
