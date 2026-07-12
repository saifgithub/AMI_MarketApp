# Constraints from production

## Mandate audit spec (lifecycle.md:120)

> **Sector concentration** — any sector > 40% (default) → triggers audit flag

This is already designed as part of the mandate compliance rules but has zero UI surfacing.

---

## Concentration safety floor (safety_floor.py:147)

```python
blocked_by = "concentration"  # current implementation
# Single-name concentration cap exists; sector-level does not
```

The safety floor can check `if portfolio.tech_weight > 0.40: block_trade()` — we just need to compute `tech_weight`.

---

## Risk Agent blind spot (overlay_generator.py:198)

```python
def _risk_block(self):
    # References sector compliance without data:
    # "Given the portfolio's 20% exposure to energy, 
    #  and the mandate's halal classification, 
    #  is this holding compliance?"
    # But portfolio.energy_exposure is not computed.
```

The agent needs the sector breakdown in its context.

---

## yfinance sector field

- `yf.Ticker(ticker).info['sector']` returns: "Technology", "Healthcare", "Industrials", etc.
- ~95% coverage on US equities
- Free tier; no rate limits for sector field
