# Rulings 2026-09-02 — the six register forks, closed

Saiful ruled the six open decisions from `../issue_register.md`'s roll-up in the Fable
review session, 2026-09-02 (AskUserQuestion, inline). These supersede the register's
FORK/OPEN statuses for the rows named; the register rows have been updated to match.
This file is the provenance record — if a WP instruction and an old reviewer doc
disagree, these rulings win.

## 1. R21 — short/medium overlay demand (finding #15)

**Ruled: back it with real fetches, inside CR219** (GLM ruling track upheld; QWEN track
and Fable's delete position overruled). The overlay's demand for earnings revisions /
surprise history stays, and CR219 ships the data that makes it honest (yfinance
`eps_revisions` / `earnings_dates`). Sequencing consequence: the demand text is only
touched in WP04 *after* WP06's R21-DATA field lands; the WP02 guard (R11) then proves
demand ↔ field mapping mechanically. "Guidance" stays out of the demand (R22 — the
sheet's own disclaimer forbids it; that part is a forbidden-phrase guard check).

## 2. R37 + R38 — historical median multiples, debt split

**Ruled: build BOTH inside CR219** (Kimi/Antigravity/GLM position; Fable's defer
dissent overruled). Notes carried into WP06: multiples window is labeled honestly
(yfinance yields ~4–5y of annual statements, not 10); the debt split needs an SEC/EDGAR
source — a new data dependency, flagged per house rule, built behind degrade-loudly
config with its own design note before code.

## 3. R31 — benchmark harness design

**Ruled: merged design** — QWEN's deterministic scorers + ticker×mandate golden-set
frame (`QWEN/03` Phase 5), run at Kimi/GLM's initial scale (4–5 cached profiles — the
only reproducible substrate, R46), mirroring the production 5-way PM vote (R32). Grow
to 8–10 tickers once the scorers hold.

## 4. R16 — Bull "end with CONVICTION" vs "once at the top" (finding #10)

**Ruled: disambiguate the vocabulary, keep both instructions** (Kimi/GLM/QWEN
position — now unanimous: Fable withdrew its delete dissent after verifying the
trailing CONVICTION is the code-parsed stance envelope, `room_runner.py:2902`, values
low|medium|high). The persona's top-of-case strength term is renamed (e.g. "case
strength") so CONVICTION belongs to the machine-parsed envelope alone.

## 5. R13 — exhaustive-by-construction guard

**Ruled: adopt.** Every prompt file must appear in the guard's mapping; an unmapped or
newly added file turns the guard red until mapped. Consequence: the R44 sweep of the
26 unswept prompts (concierge, Brief Your Agent) happens by construction.

## 6. R53, R57–R61 — the unruled second-pass rows

**Ruled: R61 rides CR219** (headline-framing check, folded into the WP02 guard);
**R53, R57, R58, R59, R60 are parked** to the future-CR parking lot, same treatment as
R55. See `PARKING_LOT.md`.

## Also settled in the same session (not forks, recorded for completeness)

- **R47 re-derived**: the original ask ("raise `pm_self_consistency_samples` from 1
  to 3") was built on a stale fact — the default has been **5** since CR214
  (`backend/app/core/config.py:751`, verified 2026-09-02). No config change ships.
  What remains of R47: the WP09 doc corrections (R27) and a WP07 harness measurement
  of residual verdict flip rate at n=5 (the ~19.7% figure was measured at n=1).
- **R30 treated as decided**: AC4 trails the merge (~1–2 weeks Alpha traffic, no fixed
  threshold, no revert on null result — a null is a new finding). Proposed by Fable,
  unopposed by any reviewer, consistent with how the register left it ("leaning
  decided").
- **Execution model**: coding is handed to Haiku/Sonnet/Opus worker sessions per the
  routing table in `README.md` (Saiful, 2026-09-02: "handover to haiku, sonnet/opus
  for the coding part").
