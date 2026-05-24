# 13 — Sector / Asset Allocation Breakdown (Tier 2)

**Folder:** `13_sector_allocation/`  
**Purpose:** Visualize portfolio concentration by sector; feed Risk Agent with sector-level allocation data.  
**Scope:** Design sector data lookup, aggregation algorithm (holdings × marks → sector weights), Portfolio screen chart (pie vs bar), and Risk Agent data feed. Renders on Portfolio screen, not holding detail.  
**Fit:** ★★ (Tier 2 — S). Mandated audit spec (`lifecycle.md:120`) already defines sector concentration rules but has no UI surfacing.

---

## Why this exists

- **Mandate audit gap:** `lifecycle.md:120` documents "Sector concentration | Any sector > 40% (default)" as a compliance check, but no code implements it.
- **Risk Agent data gap:** `overlay_generator.py:198` references halal sector compliance without data. The agent is reasoning about sector exposure blind.
- **Portfolio screen:** no visual breakdown by sector today.

---

## Locked decisions

- **Rendered on Portfolio screen** (Sim tab), not a separate tab
- **Chart type:** pie vs horizontal bar (to be decided via `02_chart_design/`)
- **Sector data source:** yfinance `info['sector']` (free, but incomplete for micro-caps)
- **Unknown sectors:** place in "Other" bucket
- **No schema change:** all data computable from existing holdings + yfinance calls

---

## Agent connections

- **Risk Analyst:** sector weights feed directly into the Risk Agent's prompt context. The agent can now reason about "25% in Tech, 15% in Healthcare" instead of guessing.

---

## Scope boundaries

**DO design:**
- yfinance sector field reliability
- Aggregation algorithm (sum of holdings per sector / total portfolio value)
- Chart UI spec (pie vs bar)
- Risk Agent data injection format
- Mandate compliance check (sector > 40%)

**DO NOT implement:**
- Code the aggregation endpoint
- Code the Portfolio chart widget
- Wire into the Portfolio screen
- Inject into Risk Agent prompt

---

## Sub-folders

- `01_constraints/` — production audit specs
- `02_data_source/` — yfinance sector field research
- `03_aggregation_design/` — algorithm design
- `04_chart_design/` — pie vs bar analysis

---

## Production references

- [lifecycle.md:120](../../docs/03_onboarding/lifecycle.md) — sector concentration audit spec
- [safety_floor.py:147](../../backend/app/agents/safety_floor.py) — concentration compliance block
- [overlay_generator.py:198](../../backend/app/agents/overlay_generator.py) — halal sector check (currently without data)

---

## Next steps (Tier 2 implementation)

After research completes, a future session will:

1. Write aggregation endpoint `GET /v1/portfolio/sector-allocation`
2. Implement `allocate_by_sector(holdings: List[SimHolding]) -> Dict[str, float]`
3. Write the Portfolio screen chart widget
4. Inject sector weights into Risk Agent prompt context
