# CR060 Phase 3 — stale-row re-validation (2026-07-23)

Before any P1 correction is handed to the education lane, every classification row whose lesson
file was edited by another lane since Phase 2 (`817be62`) must be re-checked against the *current*
file — the `exact_change` column quotes strings and line numbers that may no longer exist.

**Scope:** 31 lesson files were edited by other lanes since `817be62`; 27 of my classification rows
sit on them (20 P1, 6 P2a, 1 P2b). This doc records the re-validation of the **20 P1 rows**. The 7
P2 rows are bulk-genericize/soften work that re-reads each file at apply time anyway, so per-row
re-validation there is deferred to the apply step.

**Dominant cause of staleness:** the DEF083/DEF079 lane rewrote quiz *explanations* to name each
distractor by its content instead of by position ("the first"/"the last"/"the fourth"). That
independently **fixed the positional half of every quiz-poison finding** — the half where a correct
learner was told they were wrong. What survives is the *substantive* half: wrong facts, phantom
Mandate fields, fabricated tickers/dates, wrong arithmetic.

## Verdict summary (20 P1 rows)

| verdict | n | rows |
|---|---|---|
| **Stays P1** | 13 | 075, 100, 110, 111, 260, 274, 276, 277, 279, 013(RISK 1), 108(RISK 13), 139(TECH 39), 201(SENT 4) |
| **Downgrade → P2a** | 5 | 019(EDGE 2), 101(RISK 7), 103(RISK 9), 045(SENT 1), 202(SENT 5) |
| **→ ESCALATE (SME)** | 1 | 351(SHARIA 5) |
| **→ new repo-truth defect** | 1 | 355(SHARIA 9) |

Post-re-validation bucket totals: **P1 142 · P2a 107 · P2b 18 · ESCALATE 5 · repo-truth(CR069) 1.**

## The 5 downgrades — quiz poison fixed, only prose residue

DEF083 fixed the mis-key; what's left is genericize/soften, which is the P2 bulk pass:

- **019 EDGE 2** — Q1 explanation now names "the 'press your edge after wins' one," key {0} stands.
  Residue: TSLA-dated Fed anecdote (genericize), "gambler's fallacy in reverse" wording nit, 90%/
  1-in-4 falsifiable stat (soften).
- **101 RISK 7** — Q2 names the "same dollar risk" distractor, key {0} stands. Residue: Bursa
  board-lot prose (4,166/2,777 shares break the 100-unit lot), AIRASIA→Capital A rename.
- **103 RISK 9** — Q2 names the "tighter trail = closer to peak" distractor, key {3} stands.
  Residue: "$7 above the chandelier-set price" prose slip; named-ticker genericize.
- **045 SENT 1** — Q1 names the "crowd has new information" distractor, key {0} stands; the quiz
  itself is already generic ($50/$60). Residue: prose NVDA $115 / late-2024 anecdote (genericize).
- **202 SENT 5** — Q1 names "cutting losses is the only adult move," key {1} stands. Residue:
  NVDA/META named quiz stems + prose META/$110/$98 fabrication → genericize (key not mis-graded).

## The 13 that stay P1 — narrowed, widened, and code-verified

Two findings **widened** on re-read, and the phantom-field cluster is now **verified against live
code**, not the manifest lead:

- **Phantom Mandate fields, verified absent from `backend/app/schemas/mandate.py`.** The schema has
  `risk_score, max_drawdown_pct, halal, no_fossil_fuels, long_only` — no `max_position_pct`, no
  `max_single_name_notional_pct`. The real per-name cap is `risk_tier_cap()` in
  `backend/app/trading_math/sizing.py:22`: **{1:1.5, 2:1.5, 3:3.0, 4:4.5, 5:4.5}** %, with a fixed
  `SINGLE_NAME_ABSOLUTE_CAP_PCT = 50.0` backstop. So the proposed replacements ("risk 3 → 3% cap",
  "risk 4 → 4.5%", "risk 2 → 1.5%") are **code-accurate** — dual-pass-clean against the repo itself.
  Affected: **075, 274, 277, 279** (`max_position_pct`) and **110** (`max_single_name_notional_pct`,
  a NEW find at L63 not in the original row).
- **110 EDGE 30 widened.** 5σ event given as "~14,000 trading days" — off ~250× (true ≈3.5M trading
  days / ~14,000 *years*); plus the new phantom notional field. Both are non-genericizable false
  facts. The quiz "30–100×" is uncorroborated but **not mis-keyed** (P2b soften), and the Aug-2024
  "12% swing" (that was the Nikkei, not the S&P) + NVDA wrong date are P2a.
- **201 SENT 4** has a **live internal contradiction inside a graded quiz**: quiz 3's stem says the
  position is "+18%" while option[2] says selling at $150 "locks the +8.7%" — the same position
  can't be both. DEF083 fixed only the positional pointer. Fix: genericize NVDA out + reconcile the
  percentages.
- **100, 111, 013, 108, 260, 276, 139** — substantive defects (Kelly math, ruin exponent, +72%-vs-
  +34% recovery, correlation model contradiction, SIPC scope, NVDA "non-dividend payer", fabricated
  AMZN/CIMB) all confirmed present; positional halves already fixed where applicable.

## 351 SHARIA 5 → ESCALATE

DEF084-CONTENT already removed the flagrant in-body "AAOIFI's formula" attribution and the dead
`purification_amount` code reference. What remains is a **methodology-provenance question** — is
sourcing the pro-rata-of-dividend purification formula to *AAOIFI SS-21* correct, or is it the
Dow Jones Islamic / S&P Shariah index-provider method? That is an Islamic-finance judgment, not a
mechanical fix. Escalated to Saiful/SME; never auto-fixed, never the education lane.

## 355 SHARIA 9 → new repo-truth defect (route to CR069/content lane)

The original finding is obsolete. Timeline:

1. `5790c15` (07-22 16:28) — DEF084-CONTENT rewrote 355 to honestly describe the Option-2 state:
   a curated seven-ticker demonstration allowlist (AAPL, MSFT, NVDA, GOOGL, META, TSLA, AMZN).
2. `1504621` (07-23 04:49, ~12h later) — CR069 **retired that allowlist** and rewired all five halal
   enforcement sites to a **sourced S&P Sharia universe** (`app/services/sharia_universe.py`), with
   a degrade-loudly pause when no sourced universe is available (`safety_floor.py:159`).

So 355 now **describes a mechanism the code deleted**, and its `sources:` names
`DEFAULT_HALAL_DEMO_UNIVERSE` — which `sim_engine.py:74` explicitly marks *"gone."* Both quiz keys
certify the retired seven-ticker architecture. This is a lesson that was correctly fixed and then
re-broken by a code change three commits later — the exact failure mode the Phase 6 repo-truth
detector exists to catch (and 355's **second** wrong-vs-code occurrence, which by the house rule
earns a guard). Routed to the CR069/content lane since it owns 351/355 and the domain; not in my
P1 batch.

## Method note for Phase 6

Three silent-drop classes surfaced across Phase 2–3 and each needs a guard: (1) the committed JSON
carried pre-re-triage buckets while the doc carried post — counts must derive from one source;
(2) 8 overlay rows had `id`/`code` emitted swapped, matching no join — assert join integrity;
(3) a lesson can be fixed then re-staled by a later code change — repo-truth detector on every
lesson that names a code symbol or product field.
