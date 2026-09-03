# WP12 — R59 phase 1: the numbers audit (READ-ONLY)

**Worker model: Opus.** **Wave 1, parallel-safe: this WP changes NO code.**

## Objective

`../fable/05_further_improvements.md` §13: enumerate **every number the user
reads** from the Room and classify its provenance. The RO-precompute half already
shipped (R20/WP03); this is the general audit that was parked and is now ruled
built ("Build all", 2026-09-03). Phase 2 (fixes + the guard) is dispatched
separately after the dispatcher reviews your findings — do not fix anything in
this pass, and do not write the guard yet.

## Surfaces in scope

1. **The verdict card** — every numeric field in the Room-run API response the
   mobile client renders (walk the response schema + the banking site; list every
   field).
2. **The Room transcript** — the numeric *classes* inside turn prose: stance
   envelope headline figures, the Trader block (Entry/Stop/Size/R:R), RO ladder
   figures, analyst-cited sheet figures, PM reason figures.
3. **The 1-on-1 surface** — same classes where they appear.

Journal/lessons/other app surfaces are OUT of scope (different pipelines).

## For each numeric: classify and evidence

- **computed-in-code** (e.g. `trading_math`, the R20 RO precompute, DEF234/242
  money formatting) — name the computing function `file:line`.
- **code-checked/rewritten** (LLM emits it, code verifies or rewrites it — e.g.
  the R:R narration rewrite) — name the checking site.
- **LLM-unverified** — the model states it, nothing checks it. These are the
  findings. For each: where it lands in the UI, worst plausible error, and a
  one-line proposed fix class (precompute / check-and-rewrite / strip).

## Deliverable

ONE file: `docs/forward_planning/CR219_room_prompt_contradictions/dev_instructions/R59_numbers_audit.md`
— the inventory table (surface · field/class · provenance · evidence `file:line`),
the LLM-unverified findings list ranked by user harm, and a short proposed design
for the phase-2 guard (registry shape: every verdict-card numeric declares its
provenance class; an undeclared new field fails red — the R13 exhaustive-guard
pattern applied to numerics). Also flag: whether §13(a)'s per-rung dollar-risk
extension is already covered by R20's shipped precompute or remains open — read
the R20 code and say which, with the line.

Every `file:line` citation must be real — the dispatcher spot-checks them the way
`verify_citations.py` does for the evidence folder.

## Lane discipline

- Write ONLY the one deliverable file. No code edits, no test edits, no register
  edits.
- Commit it alone: `git add <the file> && git commit -m "research(CR219): R59
  numbers audit — phase 1 inventory (AT:R75 CR219)" -- <the file>`.
- Read anything you need; run nothing that writes (some scripts write despite
  read-sounding names — `i18n_coverage_report.py` is the canonical trap).
