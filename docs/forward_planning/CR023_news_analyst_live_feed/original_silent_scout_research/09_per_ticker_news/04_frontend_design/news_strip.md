# Frontend design: news strip widget

## Widget specification

**Widget class name:** `NewsStrip`

**Location:** `mobile/lib/widgets/sim/news_strip.dart` (new file)

**Props:**

```dart
class NewsStrip extends StatelessWidget {
  final String ticker;  // e.g. "AAPL"
  final List<NewsItem> news;  // from API
  final VoidCallback? onRefresh;  // optional refresh callback
  
  const NewsStrip({
    required this.ticker,
    this.news = const [],
    this.onRefresh,
  });
  
  @override
  Widget build(BuildContext context) { ... }
}

// Data model
class NewsItem {
  final String title;
  final String publisher;
  final String link;
  final DateTime publishedAt;
  
  NewsItem({
    required this.title,
    required this.publisher,
    required this.link,
    required this.publishedAt,
  });
}
```

---

## Visual spec

### Empty state

**Title:** "No recent news"  
**Height:** ~30 px  
**Color:** `AmiColors.textSubtle` (neutral gray)  
**Alignment:** center  

```
┌─────────────────────────────────────────┐
│                                         │
│            No recent news               │
│                                         │
└─────────────────────────────────────────┘
```

### Populated state (1–5 items)

**Max items:** 5 headlines  
**Item height:** ~80 px per headline  
**Total height:** 5–25 px (header) + (items × 80) = 85–405 px  

```
┌─────────────────────────────────────────┐
│ Recent News                             │
├─────────────────────────────────────────┤
│ Apple beats earnings expectations       │
│ Reuters • 2 hours ago                   │
│ [Tap to open]                           │
├─────────────────────────────────────────┤
│ Tech rally continues on AI gains        │
│ Bloomberg • 4 hours ago                 │
│ [Tap to open]                           │
├─────────────────────────────────────────┤
│ (up to 5 items total)                   │
└─────────────────────────────────────────┘
```

### Item structure

Each news item is a card with:

1. **Headline** (2 lines max)
   - Font: `AmiTypography.bodyMediumBold` (14 px, weight 600)
   - Color: `AmiColors.textPrimary`
   - Overflow: `TextOverflow.ellipsis` (max 2 lines)

2. **Publisher + age** (1 line)
   - Font: `AmiTypography.bodySmall` (12 px, weight 400)
   - Color: `AmiColors.textSubtle`
   - Format: `"Bloomberg • 2 hours ago"`
   - Age calculation: `DateTime.now().difference(publishedAt)` → "2 hours ago" / "1 day ago" / "Jun 1"

3. **Tap action**
   - Tap → `launchUrl(newsItem.link, mode: LaunchMode.externalApplication)`
   - Visual feedback: opacity change on tap
   - No in-app WebView (open in Safari/Chrome)

---

## Integration into holding_detail_screen.dart

Add `NewsStrip` to the holding detail `ListView`:

```dart
// In holding_detail_screen.dart, around line 95:

import 'package:sim_app/widgets/sim/news_strip.dart';

class _HoldingDetailScreenState extends State<HoldingDetailScreen> {
  // ... existing code ...
  
  @override
  Widget build(BuildContext context) {
    return Scaffold(
      // ... app bar ...
      body: RefreshIndicator(
        onRefresh: _onRefresh,  // existing pull-to-refresh
        child: ListView(
          children: [
            // 1. Chart zone (in-dev, placeholder)
            _ChartZone(ticker: widget.ticker),
            
            // 2. Position card (existing)
            _PositionCard(...),
            
            // 3. Quick-actions row (existing)
            _QuickActions(...),
            
            // 4. News strip (NEW — section 09)
            FutureBuilder<List<NewsItem>>(
              future: _loadNews(),  // call GET /v1/ticker/{ticker}/news
              builder: (context, snapshot) {
                if (snapshot.connectionState == ConnectionState.waiting) {
                  return SizedBox.shrink();  // hide while loading
                }
                final news = snapshot.data ?? [];
                return NewsStrip(
                  ticker: widget.ticker,
                  news: news,
                  onRefresh: _onRefresh,
                );
              },
            ),
            
            // 5. Earnings chip (section 11 — TBD)
            // EarningsChip(...),
            
            // 6. Stop/Target chip (section 15 — TBD)
            // StopTargetChip(...),
            
            // 7. Trade history (existing)
            _TradeHistory(...),
          ],
        ),
      ),
    );
  }
  
  Future<List<NewsItem>> _loadNews() async {
    final response = await api.get('/v1/ticker/$widget.ticker/news');
    return (response['news'] as List)
      .map((item) => NewsItem(
        title: item['title'],
        publisher: item['publisher'],
        link: item['link'],
        publishedAt: DateTime.parse(item['publishedAt']),
      ))
      .toList();
  }
}
```

---

## Theme integration

All colors use `AmiColors.*` tokens from the design system:

| Element | Token | Fallback |
|---|---|---|
| Header "Recent News" | `textPrimary` | #1A1A1A |
| Headline text | `textPrimary` | #1A1A1A |
| Publisher + age | `textSubtle` | #999999 |
| Empty state | `textSubtle` | #999999 |
| Divider | `divider` | #E0E0E0 |
| Item background | `surfaceSecondary` | #F5F5F5 |
| Tap opacity | 0.7 | (system default) |

---

## Accessibility

- Headline is semantically a heading (Semantics wrapper w/ `enabled: true`).
- Link tap is announced as "Open link: Apple beats earnings…"
- Age text is not hidden (screen readers announce it).

---

## Performance notes

- `NewsStrip` itself is a stateless widget — no rebuilds on scroll.
- News data is cached server-side (5-min TTL), so repeated page opens don't re-fetch.
- Image loading (if thumbnails are added later): lazy-load, no preload.

---

## Future extensions (post-Tier 1)

- Thumbnail image from `yfinance` (requires permission, ~200KB extra payload)
- Tap to expand full article in a bottom sheet (instead of external browser)
- Sentiment score per headline (requires additional API)
- Search within news items (requires client-side indexing)
