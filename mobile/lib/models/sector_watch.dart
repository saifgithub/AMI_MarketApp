/// CR183 — the SECTOR WATCH card's payload (`GET /v1/sector-watch/{user_id}`).
///
/// The wire is a fixed-key object whose `state` says how much of it is real:
/// `ok` carries every fact, `empty` carries none (nothing touched yet — the
/// card teaches), and `unavailable` means the feed could not be read honestly
/// (`reason` says why). Absent facts arrive as `null` and stay `null` here —
/// the server never fabricates a 0.0% move and this model never defaults one
/// in (CR040).
library;

/// The leading sector's leader ticker's top headline. Present only on
/// `state == "ok"`.
class SectorHeadline {
  const SectorHeadline({
    required this.title,
    this.publisher,
    this.publishedAt,
  });

  final String title;
  final String? publisher;

  /// Unix epoch seconds (the yfinance convention the /v1/sim/news feed uses).
  final int? publishedAt;

  factory SectorHeadline.fromJson(Map<String, dynamic> j) => SectorHeadline(
        title: j['title'] as String? ?? '',
        publisher: j['publisher'] as String?,
        publishedAt: (j['published_at'] as num?)?.toInt(),
      );
}

class SectorWatch {
  const SectorWatch({
    required this.state,
    this.reason,
    this.sector,
    this.movePct,
    this.leader,
    this.leaderChangePct,
    this.tickersConsidered = 0,
    this.headline,
    this.quoteSource,
    this.newsSource,
  });

  /// `ok` | `empty` | `unavailable`. A value this build has never seen must
  /// render as unavailable, never as ok — the DEF210 unknown-wire-value rule.
  final String state;

  /// Why the feed was unreadable — `no_live_quotes` | `no_news` | `error`.
  /// Null unless `state == "unavailable"`.
  final String? reason;

  final String? sector;

  /// Mean day change over the LIVE-sourced touched tickers in [sector], as a
  /// raw percent (2.0 == +2.0%). Null unless `state == "ok"`.
  final double? movePct;

  final String? leader;
  final double? leaderChangePct;

  /// How many live-sourced, sector-classified touched tickers fed the
  /// computation. 0 on `empty` / `no_live_quotes`.
  final int tickersConsidered;

  final SectorHeadline? headline;
  final String? quoteSource;
  final String? newsSource;

  factory SectorWatch.fromJson(Map<String, dynamic> j) => SectorWatch(
        // A missing state is a feed this build cannot vouch for — unavailable,
        // not ok (CR040).
        state: j['state'] as String? ?? 'unavailable',
        reason: j['reason'] as String?,
        sector: j['sector'] as String?,
        movePct: (j['move_pct'] as num?)?.toDouble(),
        leader: j['leader'] as String?,
        leaderChangePct: (j['leader_change_pct'] as num?)?.toDouble(),
        tickersConsidered: (j['tickers_considered'] as num?)?.toInt() ?? 0,
        headline: j['headline'] is Map
            ? SectorHeadline.fromJson(
                (j['headline'] as Map).cast<String, dynamic>())
            : null,
        quoteSource: j['quote_source'] as String?,
        newsSource: j['news_source'] as String?,
      );
}
