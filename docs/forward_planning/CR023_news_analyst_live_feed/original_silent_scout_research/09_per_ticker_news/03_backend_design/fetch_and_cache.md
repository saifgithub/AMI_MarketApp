# Backend design: fetch and cache

## Function signature

Add to `backend/app/services/fundamentals.py` (alongside `fetch_live_fundamentals()`):

```python
@cache_ttl(seconds=300)  # 5-min TTL
def fetch_live_news(ticker: str, max_items: int = 5) -> list[dict]:
    """
    Fetch live news for a ticker from yfinance.
    
    Args:
        ticker: e.g. "AAPL"
        max_items: max headlines to return (default 5)
    
    Returns:
        List of dicts with keys: title, publisher, link, providerPublishTime.
        Empty list if no news available or API error.
    
    Graceful fallback: returns [] on yfinance error, never raises.
    """
    try:
        if not USE_REAL_MARKET_DATA:
            return []  # No news in dev/mock mode
        
        ticker_obj = yf.Ticker(ticker)
        news = ticker_obj.news or []
        
        # Sort by date descending, take top N
        news_sorted = sorted(
            news, 
            key=lambda x: x.get('providerPublishTime', 0),
            reverse=True
        )
        
        # Extract minimal fields for frontend
        return [
            {
                'title': item['title'],
                'publisher': item.get('publisher', 'Unknown'),
                'link': item['link'],
                'providerPublishTime': item['providerPublishTime'],
            }
            for item in news_sorted[:max_items]
            if item.get('title') and item.get('link')
        ]
    except Exception as e:
        logger.warning(f"fetch_live_news({ticker}) failed: {e}")
        return []
```

---

## Cache decorator

The `@cache_ttl(seconds=300)` decorator is a hypothetical shorthand. Implementation options:

### Option A: Redis-backed (preferred if melehost has Redis)

```python
from app.cache import cached

@cached(ttl=300)
def fetch_live_news(ticker: str, max_items: int = 5) -> list[dict]:
    ...
```

The `cached` decorator stores in Redis with key `news:{ticker}`, auto-expires after 5 min.

### Option B: functools.lru_cache (fallback if no Redis)

```python
from functools import lru_cache

@lru_cache(maxsize=128)  # cache up to 128 tickers
def fetch_live_news_cached(ticker: str, max_items: int = 5):
    """Cached version of fetch_live_news."""
    return fetch_live_news_impl(ticker, max_items)

def fetch_live_news(ticker: str, max_items: int = 5) -> list[dict]:
    return fetch_live_news_cached(ticker, max_items)
```

LRU cache is in-process but volatile across server restarts.

---

## API endpoint

Add to `backend/app/api/ticker.py` (or new `backend/app/api/news.py`):

```python
@router.get("/v1/ticker/{ticker}/news")
async def get_ticker_news(
    ticker: str,
    max_items: int = Query(5, ge=1, le=10)
) -> NewsResponse:
    """Get recent news for a ticker.
    
    Returns:
        {
            "ticker": "AAPL",
            "news": [
                {
                    "title": "...",
                    "publisher": "...",
                    "link": "...",
                    "publishedAt": "2024-06-01T12:34:56Z"
                },
                ...
            ]
        }
    """
    news = fetch_live_news(ticker, max_items)
    return {
        "ticker": ticker,
        "news": news
    }
```

**Schema:**

```python
from pydantic import BaseModel
from datetime import datetime

class NewsItem(BaseModel):
    title: str
    publisher: str
    link: str
    publishedAt: str  # ISO 8601 (convert from unix timestamp client-side or here)

class NewsResponse(BaseModel):
    ticker: str
    news: list[NewsItem]
```

---

## Error handling

- **yfinance timeout:** return `{"ticker": "AAPL", "news": []}`
- **Invalid ticker:** yfinance silently returns empty list; we return `{"ticker": "INVALID", "news": []}`
- **Rate limit:** on second 429, backoff is handled by yfinance Session; we log and return empty

---

## Integration with Room/1-on-1 paths

In `backend/app/agents/overlay_generator.py:168`, extend `_news_block()`:

```python
def _news_block(self):
    """Generate News Analyst overlay with real + synthetic catalyst data."""
    recent_news = fetch_live_news(self.ticker, max_items=5)
    
    # Inject into prompt context
    self.context['recent_news'] = [
        {
            'headline': item['title'],
            'source': item['publisher'],
            'link': item['link']
        }
        for item in recent_news
    ]
    
    # If no real news, still include synthetic data for fallback
    if not recent_news:
        self.context['recent_news'] = [
            {
                'headline': f"Market moving based on {self.ticker}'s valuation metrics",
                'source': 'Synthetic'
            }
        ]
    
    return f"Recent news: {json.dumps(self.context['recent_news'], indent=2)}"
```

---

## Testing

Unit test in `backend/tests/unit/test_fundamentals.py`:

```python
def test_fetch_live_news_success(monkeypatch):
    mock_news = [
        {
            'title': 'Apple stock rises',
            'publisher': 'Reuters',
            'link': 'https://...',
            'providerPublishTime': 1691234567
        }
    ]
    monkeypatch.setattr('yfinance.Ticker.news', mock_news)
    
    result = fetch_live_news('AAPL', max_items=5)
    assert len(result) == 1
    assert result[0]['title'] == 'Apple stock rises'

def test_fetch_live_news_empty(monkeypatch):
    monkeypatch.setattr('yfinance.Ticker.news', [])
    result = fetch_live_news('NEWCO', max_items=5)
    assert result == []

def test_fetch_live_news_error(monkeypatch):
    def mock_error(*args):
        raise Exception("yfinance timeout")
    monkeypatch.setattr('yfinance.Ticker', mock_error)
    result = fetch_live_news('AAPL', max_items=5)
    assert result == []
```
