# WP14 — R53 + R57: turn telemetry (data-gaps tail + envelope emission rates)

**Worker model: Sonnet.** **Wave 2 — do NOT start until the dispatcher says
"WP13 accepted"** (WP13 owns `room_runner.py` in wave 1; P33 co-edit sweeps are
the reason for the queue).

## R53 — permanent DATA GAPS telemetry tail (fable/05 §7)

The arms experiment's one-off gap report produced the project's best data-roadmap
evidence (interest coverage: 21 asks from 9/12 agents). Institutionalize it as
telemetry:

- Prompt: the FOUR analyst turns only (`AgentId.FUNDAMENTALS_ANALYST`,
  `MARKET_ANALYST`, `NEWS_ANALYST`, `SOCIAL_MEDIA_ANALYST`) gain one instruction
  line: end the turn with `GAPS: <up to 3 short items, or "none">` — data the
  agent lacked THIS turn. Telemetry framing, not user copy.
- Parse + strip: in the runner's answer post-processing, parse the `GAPS:` line
  (tolerant the way the envelope parser learned to be — bold/emphasis variants,
  optional terminator; read the DEF147/CR106 block at `room_runner.py:3008` for
  the hard-won idiom), **strip it from the user-visible answer**, and store the
  structured list in that turn's dict inside the `transcript` JSONB
  (`data_gaps: [...]` — no schema migration; the column is already JSONB,
  `models.py:665`). Compose cleanly with the envelope strip — test both orders
  and absence.
- Missing/malformed tail ⇒ `data_gaps` absent for that turn, never a crash, and
  the aggregation counts emission vs omission (degrade loudly: an analyst that
  stops emitting shows up as a rate, not a silent zero).
- Aggregation: `backend/scripts/aggregate_data_gaps.py`, modeled on the arms
  prototype (`../evidence/scripts/aggregate_arms.py` — READ it, don't run it):
  reads the DB, ranks gap items by (item, ticker, agent) counts, respects the
  standing Alpha exclusions (CR035 synthetics + seed rows — same filter WP11
  hunts down; coordinate via the dispatcher if WP11 found it first).
- Measure the cost: one harness replay of a single convene with/without the tail;
  record the prompt-token delta in your results note (no extrapolation — the
  measured number, labeled).

## R57 — envelope-emission telemetry (fable/05 §11), NOT grammar forcing

The ruling that survives "Build all": the two pinned decisions stand — the CR210
wiring test pins *no prose agent is ever grammar-constrained*, and DEF251's
comment declares the envelope a **measurement channel, never a control**. What
"Build all" builds here is the MEASUREMENT LEG the parked row's wake-up condition
demanded:

- At envelope parse time, record `envelope_parsed: true/false` into each turn's
  transcript dict (same no-migration JSONB ride as R53).
- The aggregation script reports per-agent emission rates over real Alpha
  convenes (same exclusions).
- Your results note ends with the revisit rule, verbatim: *"If any debator's
  emission rate sustains <75% over ≥100 real convenes, surface it at a daily
  review — amending the two pins is Saiful's decision, made on this data."*
- You do NOT touch CR210 grammar wiring, `pm_verdict_schema`, or any prompt
  instruction about the envelope itself.

## Tests

Parse/strip units (well-formed, variant-formatted, missing, >3 items truncated,
strip-order composition with the envelope), storage shape (turn dicts carry
`data_gaps`/`envelope_parsed`), aggregation unit on a fixture DB (exclusion
filter honored), and the four analyst prompts carry the instruction line exactly
once (extend the existing prompt-assembly tests' idiom).

## Results note

`docs/forward_planning/CR219_room_prompt_contradictions/dev_instructions/R53_R57_results.md`
— token delta measured, emission-rate table from whatever banked runs exist (or
"no live rows yet — script verified on fixtures" if Alpha hasn't produced
post-deploy rows), the R57 revisit rule.

## Lane discipline (shared checkout, 30+ live sessions)

- Touch ONLY: `room_runner.py` (parse/strip/store seam), `room_prompts.py`
  (analyst instruction line), your new script + tests + results note.
- Pathspec-commit only (`…(AT:R75 CR219)`); `git add <exact path>` first for new
  files; never bare / `-am` / `add -A`. Never edit the registers.
- Tests: `backend/.venv/bin/pytest backend/tests/unit/ -q`; pass from both repo
  root and `backend/` CWDs.
- Report commit hashes + test tail; dispatcher verifies and announces "WP14
  accepted" to unblock WP15.
