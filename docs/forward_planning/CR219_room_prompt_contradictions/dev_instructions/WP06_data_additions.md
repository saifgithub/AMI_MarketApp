# WP06 — Data additions (R33–R40 + R21-DATA)

R39 (convergent, every reviewer): **nothing here starts until WP01–WP03 are merged** —
contradiction fixes before new fields. R40 is now fully resolved (2026-09-02): all of
this rides CR219, including R37/R38.

**Rules for every field, no exceptions:**
- CR104 provenance: renders with `(LIVE)` when real, and an explicit absent state
  otherwise — never silently missing (CR040; DEF059 is what silent fallback does).
- Guard entry in the same commit (WP02): a new sheet line gets its `field_state` key
  in the R11 mapping; if it collides with a known-absent's markers (R12), that firing
  is correct — rewrite the stale denial in the same commit.
- Personas that should use the field get their `## Inputs` mention in the same commit
  (lane-appropriate, `_AGENT_LANES` at `room_prompts.py:1771`).
- Any new env setting → `docker-compose.yml` `api-alpha` block
  (`test_config_compose_parity.py` enforces).
- One field per commit, `(AT:R75 CR219)`.

## The free four (all convergent — statements already fetched, currently discarded)

Source: `_fetch_statement_facts_uncached` (`backend/app/services/fundamentals.py:210`)
already pulls quarterly statements; these are derivations of data in hand. Zero new
network calls.

- **R33 — interest coverage** (EBIT / interest expense). The #1 arm request: 21
  mentions from 9 of 12 agents; the CAT insolvency-risk narrative was built without
  it. Label the quarters used.
- **R34 — capex line.** Already implicit in rendered FCF — make it explicit so agents
  stop reverse-engineering it (which R20 now forbids).
- **R35 — buyback pacing.** The four-quarter repurchase series is fetched and
  discarded; render the pacing (accelerating/steady/paused + the four figures).
- **R36 — ATR(14)** for the Trader/Risk Officers — the Execution Desk currently sets
  stops with no volatility measure. Compute from the daily bars already fetched;
  **first confirm the fetched bar window covers ≥14 sessions** (Fable's caveat — if it
  doesn't, widening the window is a separate decision: flag, don't silently extend).
  Lane: execution/risk lanes, not the analysts.

## The ruled-in two (2026-09-02, see DECISIONS §2)

- **R37 — historical median multiples** (P/E, EV/EBITDA vs own history). The one gap
  with demonstrated verdict impact in the arms. yfinance yields ~4–5y of annual
  statements, not 10 — **label the window honestly** (`5y median (4 FYs available)`
  style), and compute EV components from the same statement set. When this line
  ships, WP01-R7's peer-basket-P/E collision marker may fire → rewrite that denial in
  the same commit (it will now be half-true: own-history multiples exist, peer basket
  still doesn't).
- **R38 — debt split: industrial vs captive finance.** Needs an SEC/EDGAR source —
  **a new data dependency** (house rule: flagged, deliberately lean stack; Saiful
  accepted it 2026-09-02). Process: write a one-page design note in the CR folder
  first (source endpoint, rate limits, cache strategy, failure mode), get it
  acknowledged in the daily review, then build behind a config flag that degrades
  loudly. If EDGAR integration balloons, stop and report back — the fallback ruling
  path is a declared-absent entry + its own CR, but that reversal is Saiful's call,
  not the worker's.

## R21-DATA — earnings revisions + surprise history (ruled fetch-backed, DECISIONS §1)

yfinance exposes `eps_revisions` / `eps_trend` (estimate revisions) and
`earnings_dates` (reported vs estimate = surprise history). Add both to the
fundamentals fetch, render as sheet lines (revisions direction over the stated window;
last-N surprise record with dates), CR104 provenance, guard mapping. **This unblocks
WP04-R21's overlay rewrite** — coordinate: field first, demand text second, R11 check
proves the join. Guidance is NOT part of this fetch (R22 forbids the demand; the sheet
disclaimer stands).

## Acceptance (per field and overall)

- Unit test per field: renders `(LIVE)` with sentinel data; renders the absent state
  (loudly) when the statement/bars lack it; `test_prompt_data_parity.py` extended.
- WP02 guard green with the new mapping entries; any fired collision marker resolved
  in-commit.
- After all fields: regenerate `../evidence/rendered/` snapshots
  (`dump_sheets.py`, `assemble_room.py`) and re-check the longest assembled prompt
  (PM at VERDICT) against the served context budget — the sheet grew; verify headroom
  and note the numbers in the closing commit.
