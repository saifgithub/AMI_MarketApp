# WP01 — Class A: personas denying LIVE sheet fields (R1–R7)

The core bug: analyst personas assert data is unavailable while the fact sheet in the
same prompt carries it marked `(LIVE)`. Measured effect: margin trend cited in 24.2% of
turns vs 95.5% for the undenied margin-structure line (`../evidence/analysis/
citation_rates.py`). Fix mechanism per Saiful's R8 ruling: **hand-fix the prose, guard
catches drift** — do NOT build a generated availability block (that proposal was
rejected; see `../issue_register.md` R8).

**Files**: `content/agents/fundamentals_analyst.md`, `market_analyst.md`,
`news_analyst.md`, `social_media_analyst.md`. Drafting base: `../GLM/
03_target_prompt_set.md` §3 (per-analyst target shape) — but the register disposition
below is the acceptance rule wherever they differ.

**Process rules for this WP**
- One persona per commit; the matching guard entries/fixtures (WP02) land in the SAME
  commit, so no commit leaves a persona unguarded.
- After every commit: `backend/.venv/bin/python ../evidence/analysis/verify_citations.py`
  must exit 0 (persona edits move the line numbers the CR doc cites).
- The sheet renderer is `_format_profile` (`backend/app/services/room_prompts.py:1882`)
  with lanes at `:1771` — read the rendered sheet for each agent
  (`../evidence/rendered/sheets/<agent>.txt`, regenerate via `../evidence/dump_sheets.py`)
  before editing, so every prose claim is checked against what that agent actually
  receives.

## R1 — findings #1–2: margin trend denied outright (fundamentals)

The persona says no margin-trend/history data exists; the sheet carries
`Margin trend, YoY (LIVE)` with two dated points. **Rewrite to a two-point rule**: the
analyst may quote the bps figures and their two basis dates, and must never extend the
direction beyond those two points (no "improving trajectory" language past the second
date). Acceptance: denial gone; two-point rule present; WP02 fixture asserts the old
denial phrase fails the guard if reintroduced.

## R2 — finding #3: buybacks / capital returned / M&A (fundamentals)

Split the blanket denial three ways: **buybacks and capital-returned are claimable**
(both on the sheet; capital-returned must be flagged as AMI's own sum, not a filing
line), **M&A stays denied** (nothing fetches it — goes on the guard's known-absent
list with collision markers, R7/R12).

## R3 — finding #4: "no history for any of them" (fundamentals)

The blanket "no history" sentence is false for exactly 6 multi-period figures the sheet
states. Narrow the sentence to name what is still true; the 6 citable ones are citable.
Enumerate them from the rendered sheet, not from memory.

## R4 — findings #5–6: market analyst series/trend denials

The persona denies having any trend/series; the sheet states a 64-day window, a primary
trend, and relative strength. **Allow citing the window and primary trend + RS by
name.** Indicator *trajectories* ("RSI is clearing", "MACD crossing") stay denied —
the sheet gives point-in-time values only. This split (level: yes, trajectory: no) is
the acceptance test.

## R5 — finding #7: news analyst "not supplied consensus estimates"

Delete the sentence. Replace with a use-mention rule: the analyst may *name* the
Street's consensus estimate as context the sheet supplies, distinct from claiming an
estimates feed. (The sheet's consensus line is LIVE.)

## R6 — finding #8: social "no historical baseline" — handle with care

**Narrow, don't delete.** The mention-count trend does baseline mention *volume*; it
does not baseline *sentiment*. Rewrite to say exactly which of the two is baselined.
⚠️ **Do NOT use Antigravity's proposed rewrite** — four reviewers flagged it as
granting a false sentiment-baseline claim (register R6). This is the weakest-evidence
row in Class A: if the rendered sheet contradicts any wording you're about to write,
stop and check `../evidence/rendered/sheets/social_media_analyst.txt` first.

## R7 — the denials that must STAY

Three denials are TRUE and remain: **peer-basket P/E** (fundamentals), **MACD/Bollinger**
(market), **Twitter/X** (social). Keep the prose sentences, and register each in the
WP02 guard's known-absent list with collision markers (R12) — e.g. the Twitter/X entry
carries markers that go red if a Twitter source line ever appears in the rendered
sheet. That way the denial self-invalidates the day the data ships.

Note: if WP06's R37 (historical multiples) ships a peer/historical multiple line, the
peer-basket P/E denial's collision marker MUST fire and force a rewrite — that firing
is the mechanism working, not a test bug.
