# yfinance sector fields

## Reliable sectors (US equities)

yfinance classifies US stocks into ~11 sectors (following GICS):

- Technology
- Healthcare
- Financials
- Industrials
- Consumer Discretionary
- Consumer Staples
- Energy
- Utilities
- Real Estate
- Materials
- Communication Services
- (Other / Unknown)

---

## Field access

```python
import yfinance as yf

ticker = yf.Ticker("AAPL")
sector = ticker.info.get('sector')  # "Technology"
```

**Coverage:** ~95% for US major exchanges; ~60% for OTC / micro-caps.

---

## Handling None / Unknown

If `sector` is None or missing:
- Place holding in "Other" bucket
- Log the ticker as unmapped
- Do not error

---

## Caching strategy

Fetch sector once per ticker per session (sector rarely changes). Cache for the entire holding-detail session or indefinitely (sectors don't update).

---

## Example responses

| Ticker | Sector | Notes |
|---|---|---|
| AAPL | Technology | Major cap |
| JNJ | Healthcare | Major cap |
| AIG | Financials | Major cap |
| XYZ | Unknown/None | Micro-cap; sector not in yfinance |

---

## Aggregation by sector

Given holdings:

```python
holdings = [
  {ticker: "AAPL", quantity: 100, current_price: 150, sector: "Technology"},
  {ticker: "JNJ", quantity: 50, current_price: 160, sector: "Healthcare"},
  {ticker: "XYZ", quantity: 200, current_price: 10, sector: None},
]

# Compute allocation
tech_value = 100 * 150 = 15,000
health_value = 50 * 160 = 8,000
other_value = 200 * 10 = 2,000
total = 25,000

allocation = {
  "Technology": 0.60,  # 15k/25k
  "Healthcare": 0.32,  # 8k/25k
  "Other": 0.08,       # 2k/25k
}
```

No changes to `SimHolding` schema; all computed client-side or server-side in a helper function.
