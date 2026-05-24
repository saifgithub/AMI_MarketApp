# Informal comparison path and pre-conditions

## Current working path

**1-on-1 chat already supports multi-ticker comparison:**

```
User message:
  "How does AAPL's valuation compare to MSFT? 
   Which is a better entry?"

Backend processing:
  fundamentals.py:47 extract_tickers(message) → ["AAPL", "MSFT"]
  Fetch live data for both tickers
  Inject both into Fundamentals Analyst's context
  Analyst compares in response
```

**Result:** Analyst provides comparison without a dedicated UI.

Example output:
```
AAPL: 28.5x PE, 12% dividend yield, $2.4T market cap
MSFT: 32x PE, 0.8% dividend yield, $3.1T market cap

MSFT is slightly more expensive on a PE basis, but AAPL pays 
a higher dividend if income is your goal. Consider your risk 
tolerance and time horizon.
```

---

## Why not a dedicated screen

1. **Low frequency:** most comparisons happen naturally in chat
2. **Complexity:** a comparison matrix is more pixels than a well-reasoned explanation
3. **Agent expertise:** the analyst is better at reasoning about differences than a spreadsheet
4. **Deferral:** when users explicitly ask for a dedicated view, we build it

---

## Pre-conditions to build

### 1. User feedback from Alpha

Test with iPhone 13. If users say "I wish I could compare stocks side-by-side" more than twice, it's worth building.

### 2. Interaction pattern clarity

Count in analytics: how often do users ask for comparisons?
- If > 20% of agent interactions: build the screen
- If < 5%: stay with informal path

### 3. Design validation

Sketch a comparison UI and get feedback:
- Comparison matrix (valuation metrics × 2–3 tickers)?
- Side-by-side cards (price, earnings, dividend, etc.)?
- Split screen (two holding details)?

---

## If we do build it

**Reuse existing infrastructure:**

```python
# Already in fundamentals.py
extract_tickers(query: str) -> List[str]  # up to 3

# Endpoint (new):
@router.get("/v1/compare")
def compare_stocks(tickers: List[str]) -> ComparisonResponse:
    """Return side-by-side fundamental comparison."""
    data = {}
    for ticker in tickers:
        data[ticker] = fetch_live_fundamentals(ticker)
    return data

# UI (new):
class ComparisonMatrixScreen extends StatelessWidget {
  final List<String> tickers;  // e.g., ["AAPL", "MSFT"]
  ...
}
```

**Metrics to compare:**

| Metric | AAPL | MSFT |
|---|---|---|
| P/E | 28.5 | 32.0 |
| Dividend | 3.5% | 0.8% |
| Market Cap | $2.4T | $3.1T |
| 52-week range | $150–$195 | $300–$350 |

---

## Not building at Alpha / Tier 1–2

The informal path is functional and addresses the need. When user feedback shifts the priority, we revisit.
