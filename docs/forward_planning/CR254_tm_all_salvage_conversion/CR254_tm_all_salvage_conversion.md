# CR254 — tm-all salvage conversion (re-minted from CR253 — ID taken by the parallel agent's data-lane CR) (mandate-compliant re-implementation)

**Status:** proposed · **Owner:** AT:K3 · **Opened:** 2026-10-08
**Constraint:** PLANNING ONLY until items 3 (CR252 heuristics fold-in) and
4 (data/weighting fixes) land from the parallel agent. Then this specks the
conversions against the new baseline.

## The root cause (one sentence)

Every Oct-6 refusal traces to the same implementation flaw: **the suite
stated mandate-derived values as prompt prose instead of reading them from
the mandate.** The constitution's "these directives supersede any
conflicting instructions" then made that prose win.

## Conversion principle

**Mandates are data, not prose.** No prompt text may restate a value the
mandate system computes. Prompts reference the injected parameter by name
(`{{mandate.horizon_days}}`, `{{single_name_cap_pct}}`); the value has one
source of truth. Any salvaged module that fails this test gets its constant
deleted, not reworded.

## Per-element conversion specs

### 1. Hardcoded horizon (refused D2) → mandate-referenced

- Delete `HORIZON_MANDATE: 180–730d` entirely. No default range in prose.
- Prompts say: "the horizon is the mandate's stated horizon" — the mandate
  block already parameterizes it (risk-level dependent).
- Failure test that made it refuse: V's trade emitted `time_horizon_days=
  180` under an R3 mandate. Acceptance: 100% of trade params' horizons
  equal the mandate horizon across the gate.

### 2. TIER sizing ontology (refused D15) → vocabulary, not values

- TIER labels survive as *argumentation vocabulary only*: TIER_1 = within
  the computed cap; TIER_2 = only with explicit cap-headroom
  justification; TIER_3 = unreachable, the cap is absolute (DEF059).
- The SIZE in an envelope or trade MUST equal `resolved_single_name_cap_pct`
  output — tiers may describe, never set.
- Failure test: aggressive argued 5.0% vs the 3.0% computed cap.
  Acceptance: zero argued sizes exceed the cap in any gate room.

### 3. Trader wide-stop rule (NO-GO) → already converted by CR249

- The concept (horizon-appropriate width) is sound; the implementation
  lacked a bound. CR249's repair gate now enforces the bound
  arithmetically (DEF237 plausibility + one re-placement attempt).
- Conversion remaining: none structural. Optional prompt line restating the
  intent WITH the bound reference — bounded by the gate, never instead of it.

### 4. All-JSON output demands (partial NO-GO on GLM)

- Any salvaged JSON block is subordinate to the STANCE envelope: envelope
  stays the sole machine channel; JSON is presentation.
- GLM PM-draw unparseability is provider-side (constraint unsupported);
  the CR143 tolerant parser + reformat retry is the existing conversion.

### 5. SCS 0–100 floats → drop

Dead weight in every measurement (zero appearances). No conversion.

### 6. PM kill_criterion verbosity → trim only

Bound already exists (240 chars, over-bound is warning-level). No mandate
interaction. Trim at fold-in time if the module being converted carries
verbose examples.

## Sequencing

1. Wait for items 3 & 4 (parallel agent) → new production baseline.
2. Convert modules one at a time (horizon + TIER first — they touch trade
   params; the rest are cosmetic).
3. Each conversion: D26 gate (AAPL+V R3) → stance census + trade-param
   audit vs BASELINE.md → then fold.
4. When all conversions land: full 30×5 matrix per the CR251 diff protocol
   (analysis_r3) — that run becomes the pre-Phase-2 reference.

## What this is NOT

Not a tm-all revival. The wholesale suite stays rejected; this CR converts
the salvageable ideas into mandate-compliant form and measures each one.
