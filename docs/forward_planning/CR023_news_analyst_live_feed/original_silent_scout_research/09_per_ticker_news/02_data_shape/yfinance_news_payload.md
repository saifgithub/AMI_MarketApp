# yfinance news payload shape

## Sample output

```python
import yfinance as yf

ticker = yf.Ticker("AAPL")
news = ticker.news  # Returns list of dicts

# Sample structure (actual fields from yfinance 0.2.50+):
[
  {
    "uuid": "...",  # unique ID for deduplication
    "title": "Apple Stock Hits New High as AI Optimism Continues",
    "publisher": "Bloomberg",
    "link": "https://...",
    "providerPublishTime": 1691234567,  # unix timestamp
    "type": "ARTICLE",
    "thumbnail": {
      "resolutions": [
        {"url": "https://...", "width": 100, "height": 100},
        {"url": "https://...", "width": 200, "height": 200}
      ]
    }
  },
  # ... up to 30–50 items
]
```

---

## Reliable fields

| Field | Type | Reliability | Use | Fallback |
|---|---|---|---|---|
| `title` | string | ✓ Always present | Headline on news strip | (skip item) |
| `publisher` | string | ✓ Always present | Source attribution | "Unknown" |
| `link` | string | ✓ Always present | Tap-to-open URL | (skip item) |
| `providerPublishTime` | int (unix sec) | ✓ Always present | Age badge ("2 hours ago") | (skip item) |
| `type` | string | ✓ Usually "ARTICLE" | (filter if needed) | Include all |
| `uuid` | string | ✓ Present | Deduplication | (skip item) |
| `thumbnail.resolutions` | list | ~ Frequent but not guaranteed | Image on news strip | Show text-only |

---

## Empty list vs None

- **Empty list:** `[]` when yfinance returns no news for a ticker (common for new IPOs, delisted tickers, API error)
- **None:** when the API call fails or times out
- **Treatment:** both cases → same "No recent news" empty state in the frontend

---

## Timestamps

`providerPublishTime` is unix seconds (UTC). Convert to relative age in the frontend:

```
1 hour ago → age badge
2 days ago → date only
```

---

## Surface rules

- **Max 5 headlines:** yfinance returns 30–50, but 5 are sufficient for the news strip on the holding detail screen (08_holding_detail)
- **Sort by `providerPublishTime` descending:** most recent first
- **Deduplication:** track `uuid` to avoid repeats across poll cycles
- **URL validation:** discard items with missing `link` (rare but possible)

---

## Caching strategy (see 03_backend_design/fetch_and_cache.md)

Each ticker's news is cached for **5 minutes** to avoid hammering Yahoo on every page load. Cache key is ticker; cache miss triggers a fresh fetch.

---

## Rate limit considerations

yfinance free tier has soft limits (~2000 calls/hour if using a session). At 5-min TTL, a single ticker is polled ~12 times/hour. A portfolio of 20 holdings is ~240 calls/hour — well within limits for Alpha.
