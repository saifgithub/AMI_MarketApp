# WP04 — Surfaces: overlay↔field alignment, downstream briefs, 1-on-1 lane (R21, R23, R24)

## R21 — finding #15: short/medium overlay demand (ruled 2026-09-02: fetch-backed)

Current state: `backend/app/agents/overlay_generator.py` `_fundamentals_block` (~`:437`)
short/medium branch emits *"Emphasise momentum in fundamentals (earnings revisions,
surprise history), guidance."* — and nothing fetches revisions or surprise history, so
the demand asks agents to analyze data they don't have.

Saiful's ruling: **the demand stays; the data ships** (see
`DECISIONS_2026-09-02.md` §1). Order of work:

1. **Wait for WP06's R21-DATA** (earnings revisions + surprise history fields on the
   sheet, from yfinance `eps_revisions` / `earnings_dates`).
2. Then rewrite the branch line to demand exactly what the sheet now renders, in the
   sheet's own vocabulary — e.g. revisions direction over the stated window, last-N
   surprise record, next consensus-EPS date.
3. **Drop "guidance" from the demand entirely** — the sheet's own disclaimer says
   guidance is not supplied; the WP02 R22 forbidden-phrase check enforces this
   permanently.
4. WP02's R11 demand↔field mapping is the acceptance: every phrase in the rewritten
   branch resolves to a rendered `field_state` key.

Until step 1 lands, do not touch the branch (a half-fix that deletes the demand now
would contradict the ruling; the interim dishonesty is closed by sequencing, and WP06
is scheduled inside the same CR).

## R23 — Class D: 8 downstream agents hold the sheet, briefs never mention it (ruled)

The researchers, manager, trader, debators, and PM all receive the **full** fact sheet
(`../evidence/rendered/sheets/trader.txt` is byte-identical to `__FULL__.txt`), but
their `## Inputs` sections never say so — so the sheet is under-used and numbers get
re-derived from the transcript. Ruling (GLM R3 + QWEN converged): **name the sheet in
each of the 8 briefs + add a "quote, don't re-derive" numbers rule** — the cheap half
now; lane-gating downstream agents is explicitly NOT in scope (a separate measured
change if ever).

- Files: `content/agents/{bull_researcher,bear_researcher,research_manager,trader,
  aggressive_debator,conservative_debator,neutral_debator,portfolio_manager}.md`.
- Drafting base: `../GLM/03_target_prompt_set.md` §5 (downstream briefs — target
  shape).
- The numbers rule is R20's policy sentence — same wording, one source of truth; if
  WP03 already added it to the shared tail, the briefs just reference it, don't
  duplicate it.
- One commit for all 8 is acceptable here (identical mechanical insertion), but run
  the banked-corpus comparison after: this is the change most likely to shift
  downstream citation behavior, and the 66-turn before-arm
  (`../evidence/` + `citation_rates.py`) is the baseline AC4 measures against.

## R24 — Class E: 1-on-1 lane gap (convergent)

The 1-on-1 chat surface hands every agent an ungated live-data block:
`build_live_data_block` (`backend/app/services/fundamentals.py:1436`) — so the
fundamentals analyst receives price/momentum data its persona forbids it to use.
Fix: **lane-gate the 1-on-1 block with the same `_AGENT_LANES` map the Room uses**
(`backend/app/services/room_prompts.py:1771`) — filter the block's sections by the
requesting agent's lanes before rendering. Keep one lane map; do not fork a second
lane table for the 1-on-1 surface.

Acceptance: unit test rendering the 1-on-1 block for `fundamentals_analyst` shows no
price-prediction/momentum section; for `market_analyst` it still does;
`test_prompt_data_parity.py` still green; the WP02 guard's known-absent truth checks
run against the 1-on-1 surface too (a denial true in the Room must not be falsified
by the 1-on-1 block).
