# 17 — Stock Comparison View (Tier 3 — Deferred)

**Folder:** `17_stock_comparison/`  
**Purpose:** Document the deferral of a dedicated stock comparison screen.  
**Status:** Explicitly deferred; informal comparison already works via 1-on-1 chat.

---

## Why deferred

The product already supports comparison via 1-on-1 agents. `fundamentals.py:47` extracts up to 3 tickers per message and injects live data for each:

```
User: "compare AAPL and MSFT"
Fundamentals Agent fetches data for both, compares in the 1-on-1 response.
```

A dedicated comparison screen adds UI surface for niche use case (most users compare informally in chat).

---

## Current informal path

1. User opens 1-on-1 with Analyst
2. User asks: "How does AAPL compare to MSFT?"
3. Analyst extracts both tickers, fetches data, provides comparison

**This works today.** Adding a dedicated screen is a nice-to-have, not a blocker.

---

## Pre-conditions for dedicated comparison view

1. **Users request it** (feedback from Alpha testers)
2. **Use case patterns emerge** (is comparison a 20% of interactions or 5%?)
3. **Design clarity** (comparison matrix? side-by-side cards? split screen?)

Until then, the 1-on-1 path is sufficient.

---

## What a dedicated view would need

- Multi-ticker data fetch (leverage existing `extract_tickers()`)
- Comparison matrix (Metric × Ticker columns)
- Visualization (parallel sparklines? valuation scatter?)
- Agent commentary (Analyst picks key differences)

---

## See also

- [fundamentals.py:47](../../backend/app/services/fundamentals.py) — `extract_tickers()` (up to 3 at a time)
- [twelve_agents.md](../../docs/02_agents/twelve_agents.md) — Fundamentals Analyst capabilities
