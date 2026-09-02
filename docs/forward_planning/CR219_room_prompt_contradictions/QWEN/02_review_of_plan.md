# 02 — Review of the CR219 plan (Scope + Acceptance)

The CR's Scope has 6 items and Acceptance has 5 criteria. Reviewed against the
stated aim: *"a set of prompts that will be the best at evaluating a ticker."*

## What the plan gets right (keep as-is)

1. **Structural over prose (CR038).** The guard fix (Scope 5 / Acceptance 1-2) is the
   highest-value item in the CR. The failure mode is mechanical — a CR adds a sheet
   field, its test asks "does it render?", nothing asks "does anything deny it?" —
   and only a build-breaking check closes it. The proposed guard (every negative claim
   checked TRUE against the rendered sheet, whole-file scan, red-fixture demo) is the
   right shape and mirrors the existing CR104/CR105 pattern, so it's low-risk to land.
2. **Leg 4 applied to #13/#14.** Precomputing the drawdown contribution instead of
   handing over operands plus an arithmetic ban is exactly the rule CR179 Leg 4
   already states, and the codebase already has the machinery
   (`_drawdown_snapshot_line`, `_share_of_cap_phrase`). This is applying an existing
   house rule, not inventing one.
3. **Honest measurement limits.** The plan refuses to over-read the arms (verdict
   column declared non-interpretable at n=1, ~19.7% flip rate). The banked corpus as
   a free before-arm (Acceptance 4) is smart — it's the one outcome measurement that
   costs nothing.
4. **Keeping the 3 true denials.** Naming what must *stay* prevents the fix-pass from
   over-correcting — the classic failure of a "fix all contradictions" sweep.
5. **#15 deletion is cheap and correct.** CR146 already deleted four identical
   demands from the market-analyst block on the same evidence; the fundamentals one is
   the last of the class. Delete, don't back — backing it would mean fetching
   earnings-revision data, which is a different (expensive, unproven) CR.

## Where the plan falls short (six gaps)

### Gap 1 — The plan fixes coherence but the aim is evaluation quality

Every Scope item makes the existing prompt set internally consistent. None of them
makes the Room *better at evaluating a ticker*. Meanwhile the CR's own data-gap
table — 102 requests, the #1 one at 21× from 9/12 agents — plus the "free ones"
section (interest coverage, capex, buyback pacing computable from bytes already in
memory at zero network cost) describe a large, cheap quality gain that the plan
explicitly defers ("should be its own CR"). **Ruling: all changes ride CR219** — the
free fields, the stop anchor, and goal-branching are now Phases 3b/4 of this CR,
sequenced after the persona fixes so the Acceptance-4 citation measurement isn't
confounded by new fields appearing mid-sweep. The measurement design (Gap 5) is what
the deferral must never include, and the improved plan supplies it.

### Gap 2 — No derivation policy, and the sheet already contains a live experiment proving one is needed (RULED 2026-09-02)

The sheet's `Asymmetry` line says *"AMI's arithmetic on the two lines above"* —
i.e., the codebase already precomputes some derived figures and labels them. But
nothing states a **policy**: which numbers an agent may compute itself, which it must
take precomputed, and how derived numbers must be labelled. #13/#14 are symptoms of
the missing policy, not just missing precomputes: the Balanced RO was told to propose
a size *and* a stop while forbidden from multiplying them. Fixing two instances
without writing the rule guarantees the class returns at the next CR that adds two
operands and a ban. **Ruling: global ban + extended precompute pass** — agents
never do arithmetic on sheet figures; AMI mints every derived number and labels it
(the `Asymmetry` line's labelling is the template). See `03_improved_plan.md` Phase 2.

### Gap 3 — Class D was deferred without a decision frame (RULED 2026-09-02)

Scope 4 said Class D "wants its own before/after measurement" and stopped. The
question was decidable now: the 8 downstream agents hold the primary numbers and are
briefed to argue from prose. **Ruling: the cheap half ships now** — a one-line
"you also hold the fact sheet, cite it by field name" in each downstream brief
(nearly free, strictly reduces the contradiction surface); the expensive half
(lane-gating the sheet away from downstream agents) stays behind the golden-set
measurement. See `03_improved_plan.md` Phase 4.

### Gap 4 — No decision-theoretic content where the evaluation actually happens

The sharpest finding in the CR is buried in a table footnote: **the Execution Desk
must set a stop on every BUY and is given no volatility measure of any kind.** Both
cautious Risk Officers independently asked for gap statistics. Fixing the persona
denials (Scope 1) makes the Trader honest about numbers it still doesn't have. The
sheet already carries `Beta (LIVE)`, `Day move`, `Short interest … days to cover`,
and the 52-week range — enough for AMI to precompute a crude expected-day-move /
range-based stop anchor, labelled as AMI's arithmetic per Gap 2, at zero fetch cost.
That is a *quality* fix in the same Leg-4 shape as #13/#14, and it addresses the
single most consequential evaluation weakness the evidence surfaced: stops are
currently vibes. Same for the Trader's R:R: the asymmetry line exists for the room
but the grammar forces `N.NN:1` — check that the forced format can't pressure a
fabricated ratio when the levels don't support one (the CR210 docstring shows the
authors already thought in exactly this shape for `Entry: market`).

### Gap 5 — Acceptance 4 has no instrument

*"Re-run the corpus citation count on post-fix Alpha traffic; margin-trend and
buyback citation rates move toward their undenied neighbours"* — but:

- Citation rate is a **proxy** (did the agent mention the field), not an outcome
  (did the verdict improve). It's the right proxy for the *suppression* claim and the
  wrong one for "best at evaluating a ticker."
- Post-fix Alpha traffic is slow, confounded (market regime changes, other CRs
  landing), and n accrues at whatever rate users convene. There is no power analysis.
- There is no **golden set**: a fixed battery of tickers × mandates, run pre/post
  through the same harness (`convene_gemini.py` is 90% of it already), scored on
  deterministic checks (does the answer cite the LIVE trend when present? does the
  stop exist on BUY? does any reply contradict the sheet?) plus the existing
  fabrication guards. The arms infrastructure, the shared-profile pickle pattern, and
  the extraction scripts all exist; a scored battery is a thin layer on top.

Without this, Acceptance 4 is unfalsifiable on any useful timescale. The improved
plan makes the golden set the acceptance instrument and demotes corpus citation to
corroboration.

### Gap 6 — The guard fixes the wrong direction of one failure class

Scope 5's guard checks *negative claims* (persona denies a field) against the sheet.
Good. But the symmetric future failure — a **positive** claim reworded into a
denial-shaped sentence outside the `## Inputs` window, or a new persona file added
with no mapping at all — needs the guard to be *exhaustive by construction*: every
`.md` under `content/agents/` must appear in the mapping (positive or negative) or
the test fails. The CR105 guard's own docstring calls this the "allowlist blind
spot"; the new guard should invert the default (unknown file/section = red), which
is cheap and makes the concierge/Brief-Your-Agent sweep (Scope 6) a consequence of
the guard rather than a manual chore.

### Minor

- The stale #12 citation (see `01_verification.md`) should be re-pointed and added to
  `verify_citations.py`'s list.
- The "Open" item on `primary_goal` being rendered but never branched-on is a
  **degrade-loudly violation in the opposite direction**: the prompt prints a value
  and implies it matters (CR040 says config-gated features must fail visibly; here a
  *user answer* is displayed and silently ignored). **Ruled 2026-09-02: keep printing
  it, and land goal-branching soon inside CR219** (Phase 3b of the improved plan) so
  the printed value becomes true. Until then the mislead is accepted deliberately —
  this line is the record.
- Acceptance 5 ("evidence/ regenerates") is good hygiene but note `profile_CAT.pkl`
  is gitignored and market data moves — regeneration is *not* reproducible byte-for-
  byte across days. The acceptance should say "scripts run clean against a freshly
  built profile," not imply diff-identical output.
