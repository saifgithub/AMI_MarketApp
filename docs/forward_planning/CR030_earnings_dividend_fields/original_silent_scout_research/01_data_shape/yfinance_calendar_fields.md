# yfinance calendar fields

## Relevant fields in Ticker.info

```python
import yfinance as yf

ticker_obj = yf.Ticker("AAPL")
info = ticker_obj.info

# Fields of interest
earnings_date = info.get('earningsDate')  # unix timestamp or None
ex_dividend_date = info.get('exDividendDate')  # unix timestamp or None
dividend_rate = info.get('dividendRate', 0.0)  # annual dividend per share
next_fiscal_year_end = info.get('nextFiscalYearEnd')  # unix timestamp
```

---

## Field reliability

| Field | Type | Present | Reliable | Notes |
|---|---|---|---|---|
| `earningsDate` | int (unix sec) | ~80% | ✓ if present | Major exchanges only; OTC stocks often None |
| `exDividendDate` | int (unix sec) | ~70% | ✓ if present | Depends on company dividend policy |
| `dividendRate` | float | ~70% | ✓ if present | Annual rate; 0.0 if no dividend |
| `nextFiscalYearEnd` | int (unix sec) | ~90% | ~ | Sometimes in future, sometimes current year |

---

## Handling None

**If `earningsDate` is None:**
- The company has not announced next earnings (likely OTC, pre-earnings, or data lag)
- Render the chip as hidden — don't show "TBA" or "Coming soon"

**If `exDividendDate` is None:**
- The company is not a dividend payer (e.g., tech growth stocks)
- Render as hidden — user won't see an empty dividend chip

---

## Format conversion

yfinance returns unix timestamps (seconds since epoch, UTC). Convert client-side in Flutter:

```dart
final earningsDate = DateTime.fromMillisecondsSinceEpoch(earningsDateUnix * 1000);
final formatted = DateFormat('MMM d').format(earningsDate);  // e.g. "Jun 12"
```

Or format server-side as ISO 8601 and parse in Flutter.

---

## Sample responses

### AAPL (major cap, pays dividend, reports earnings quarterly)

```json
{
  "earningsDate": 1691500800,  // unix sec → Jun 12, 2024
  "exDividendDate": 1695091200,  // unix sec → Sep 19, 2024
  "dividendRate": 0.96
}
```

### TSLA (major cap, no dividend, reports quarterly)

```json
{
  "earningsDate": 1693526400,  // Jul 19, 2024
  "exDividendDate": null,
  "dividendRate": 0.0
}
```

### NEWCO (small cap, no public schedule)

```json
{
  "earningsDate": null,
  "exDividendDate": null,
  "dividendRate": 0.0
}
```

---

## Rate limits

Fetching `Ticker.info` once per holding per session is safe (cached). Don't refetch on every page load — use the same TTL as `fetch_live_fundamentals()` (~5 min).

---

## Storage in backend

Store earnings/dividend fields in the API response:

```json
{
  "ticker": "AAPL",
  "earningsDate": "2024-06-12T00:00:00Z",  // ISO 8601
  "exDividendDate": "2024-09-19T00:00:00Z",
  "dividendRate": 0.96,
  "dividendYield": 0.0125  // optional, computed: divRate / current_price
}
```

---

## Edge cases

**Earnings date in the past:** yfinance sometimes returns the previous earnings date if the next one hasn't been announced. Hint: if `earningsDate < now`, suppress the chip (don't show "AAPL reported earnings on Mar 15" on a page opened in June).

Check client-side: `if (earningsDate > DateTime.now()) { showChip = true; }`

**Dividend rate = 0.0 with exDividendDate present:** rare but possible (company suspended dividend). Show the ex-dividend date but no rate ("Ex-div: Jun 12").
