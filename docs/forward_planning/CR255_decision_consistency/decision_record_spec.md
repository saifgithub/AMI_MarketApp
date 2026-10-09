# CR255 — Structured decision record (Phase-B discovery layer)

**Status:** proposed · **Owner:** harness V2 builder (track K) · **Spec:** AT:K3 · **Opened:** 2026-10-10

## Problem (measured, CR255 register + dsv4 tooling)

The Room verdict layer narrates but does not record: `verdict.reason` is free
prose, so every consistency question (why did R3 approve this and R4 pass it?
why did rep1 flip?) is answered by re-reading text. The CR255 register already
quantifies the noise (flip rate 17% uncapped / 21% size-pinned; net-support
r=+0.19 with zero threshold lift; approvals 5/11/22/27/17 uncapped) — but the
Phase-C evidence bar (C7) and the standing regression (Phase D) need the
decision decomposed into machine fields at verdict time, not reconstructed
afterwards.

## What to build (spec only — NO production code in this CR)

Extend the Room verdict schema with a `decision_record` object alongside the
existing CIO/PM narration. Rule: **every field is either computed
deterministically from evidence already in the room, or explicitly
LLM-reported** — no field may be both silently. Computed fields are derived by
the same tools that score the room (Jev scorer + the two classifiers in
`docs/tools/room_investigation_V2/tools/`, `net_support.py` /
`decision_factors.py`), so the record and the regression tooling can never
drift apart. The LLM narrates; the machine channel carries the auditable
quantities.

### Fields

**`net_thesis_support`** — number in [-1, +1].
Definition: bull-desk mean Jev support − bear-desk mean Jev support, where
support = well_supported 1.0 / partially_supported 0.5 / unsupported 0.0
(`no_clear_claim` excluded), bull desk = {bull_researcher,
fundamentals_analyst, trader}, bear desk = {bear_researcher,
aggressive_debator, conservative_debator}. Absent desks degrade to the
remaining members (the dsv4/cap1 logs carry no debator turns — bear mean is
bear_researcher alone there; the field records the desk membership used).
Source: **computed** at verdict time from the room's Jev-scored turns
(tools/net_support.py; join on (arm_key, risk_score) — arm_key alone is not
unique across levels).
Phase-C feed: the C7 measured evidence bar is a *directional* threshold on
this field per risk level (never on raw direction-agnostic room mean — the
dsv4 measurement showed raw mean anti-correlates at r=−0.36). Also the primary
feature of the Phase-D standing regression (per-model r tracked, red blocks
promote).

**`unresolved_objections_count`** — integer ≥ 0.
Definition: count of bear-desk turns whose core-claim score is
`unsupported` or `no_clear_claim` — i.e. objections raised in the room that
the evidence pass did not clear. (partially_supported objections count 0.5 is
rejected: the disposition vocabulary speaks in whole objections; keep it an
integer, regression can weight it.)
Source: **computed** from the same Jev log.
Phase-C feed: second feature for the C7 bar — the CR253 disposition text
already phrases the per-level bar as "one unresolved objection is a pass";
this field makes that phrase a number the bar can reference, and the Phase-B
factor regression tests whether objections clear monotonically with the risk
level (they should not — measured dsv4 support is flat ±0.05 across levels).

**`catalyst_proximity_days`** — integer or null.
Definition: days from the room's as-of date to the nearest forward-dated
binary catalyst on the fact sheet (earnings date in the 90-day window, FOMC
countdown). Null when the sheet carries no dated catalyst.
Source: **computed** from fact-sheet fields where present (earnings date,
FOMC countdown are already structured lines); **LLM-reported, flagged
`"source": "llm"`**, only when the sheet lacks the datum — the grounding
directive (CR034/CR056 class) forbids assumed dates, so a missing datum must
be null, never invented.
Phase-C feed: `catalyst_wait` is the dominant PASS factor (130/158
high-support passes, dsv4). Phase-B regression: is the wait-for-catalyst pass
rate explained by genuine proximity (this field) or by the PM using "wait" as
a generic soft-pass? Distinguishes a rational bar from prose habit before C7
is fit.

**`primary_factor`** — enum {catalyst_wait, technical_setup, valuation,
insider, balance_sheet, risk_language, other}.
Definition: first-match keyword classification of the verdict reason over the
ordered class list (exact definitions in tools/decision_factors.py; the list
is versioned in the tool, and the record stores the tool version + keyword
set hash so replays classify identically).
Source: **computed** from `verdict.reason` (the classification is
deterministic; the LLM writes the reason, the classifier assigns the factor —
no self-reporting).
Phase-C feed: the factor × level approval-rate table (dsv4: catalyst_wait
22% overall vs valuation 83%) is the Phase-B regression's grouping variable;
flip pairs where the factor flips with the verdict (12/26 dsv4) identify
non-thesis noise C9 (CIO ensemble hardening) must absorb.

**`size_rationale`** — string, required on APPROVE, null on PASS.
Definition: one sentence — why this `size_pct` and not the level cap (or why
the full cap). Populated by the PM on approve; the C6 sub-cap policy (largest
supported size below cap) needs to read *why* size was discounted, not just
that it was.
Source: **LLM-reported** (the one genuinely judgment-shaped field; prose is
appropriate here).
Phase-C feed: C6 regression — sub-cap usage rate and its stated reasons; if
the sub-cap discount reasons cluster on a factor the evidence bar already
captures, C6 and C7 collapse into one mechanism (build the cheaper one).

**`sub_cap_flag`** — boolean.
Definition: `size_pct < level_cap` on APPROVE; false on PASS (no size
decision made). Trivially derivable from `size_pct`, stored denormalized so
the Phase-D regression reads one column.
Source: **computed**.
Phase-C feed: C6's headline metric (sub-cap usage rate) and the Phase-D
suite's size-worthiness decoupling check (CR253 line: size ≠ worthiness).

### Record shape

```json
"decision_record": {
  "tool_version": "net_support.py:1,decision_factors.py:1",
  "net_thesis_support": 0.17,
  "bear_desk_members": ["bear_researcher"],
  "unresolved_objections_count": 1,
  "catalyst_proximity_days": 24,
  "catalyst_source": "computed",
  "primary_factor": "catalyst_wait",
  "size_rationale": "…",
  "sub_cap_flag": false
}
```

## Acceptance

- Every field above lands in the verdict schema with its source marked;
  computed fields are produced by the checked-in tools, byte-identical to what
  the offline tooling computes from the same Jev log (round-trip check on the
  dsv4 + cap1 matrices: recompute from stored logs, diff = 0).
- Phase-B regression can run factor × level × verdict on any new matrix arm
  with zero text re-processing.
- No change to what the PM writes (reason prose stays), no change to any
  agent persona, DEF059 holds (record informs, never vetoes).

## Boundaries

No production prompt files touched by this spec — the schema extension is a
harness-side concern and lands with the CR255 Phase-B build CR. The
measurement-side tooling (net_support.py, decision_factors.py) already exists
under `docs/tools/room_investigation_V2/tools/` and is the reference
implementation for the computed fields. Target-curve policy (what SHOULD the
R1–R5 slope be) remains the hard Phase-C gate set by Saiful — this record
supplies the features, not the policy.
