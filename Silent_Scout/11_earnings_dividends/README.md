# 11 — Earnings & Dividend Calendar Chip (Tier 2)

**Folder:** `11_earnings_dividends/`  
**Purpose:** Surface per-ticker earnings dates and dividend ex-dates as an inline chip on the holding detail screen.  
**Scope:** yfinance payload fields, backend endpoint, chip widget.  
**Status:** ✅ **DELIVERED** (AT:R41) — Chip widget built, backend `/v1/sim/earnings` wired with 6h cache, tests passing, integrated into holding detail.  
**Fit:** ★★★ (Tier 2 — S). One yfinance call; no new data source. Host is 08_holding_detail.

---

## What exists today

- `yfinance` `Ticker.info` returns `earningsDate` (unix timestamp or None) and `exDividendDate` (similar)
- No backend endpoint to surface these
- No Flutter chip to display them on the holding detail

---

## Locked decisions

- **Inline chip only** — not a separate calendar tab (per gap analysis locked decision)
- **Chip is hidden if date is None** — no "Coming soon" fallback
- **Data source:** yfinance only; no paid calendar API (e.g., FactSet, S&P Global)

---

## Agent connections

- **News Analyst:** expects earnings context in its tools list. This chip surfaces real earnings data so the analyst can reason about forward catalysts.

---

## Scope boundaries

**DO design:**
- yfinance field reliability (earningsDate, exDividendDate)
- Backend endpoint `GET /v1/ticker/{ticker}/earnings`
- Chip widget design (appearance, height, interaction)

**DO NOT implement:**
- Code the endpoint (→ production session)
- Code the chip widget (→ production session)
- Integrate into holding_detail_screen.dart (→ production session)

---

## Sub-folders

- `01_data_shape/` — yfinance field survey
- `02_chip_design/` — chip appearance and interaction

---

## Production references

- [gap_analysis.md](../05_agent_alignment/gap_analysis.md) — earnings calendar as unlock for News Agent
- [twelve_agents.md:66](../../docs/02_agents/twelve_agents.md) — News Analyst agent profile

---

## Next steps (Tier 2 implementation)

After this section is researched, a future session will:

1. Extend `backend/app/services/fundamentals.py::fetch_live_fundamentals()` to include earnings/dividend fields
2. Wire endpoint `GET /v1/ticker/{ticker}/earnings`
3. Write the Flutter `EarningsChip()` widget
4. Add to `holding_detail_screen.dart` (08_holding_detail)
