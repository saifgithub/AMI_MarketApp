"""CR219 R59 phase-2, lane A3 — the numeric-provenance registry + its guard.

R13's exhaustive-guard shape (`test_cr135_notification_type_parity.py`,
`test_config_compose_parity.py`), applied to numerics instead of enum members
or config keys: every numeric the user can read declares its provenance class
in a registry, and a numeric that reaches a render site without a registry row
fails the build red. The value is not in classifying today's fields — the
phase-1 audit (`docs/forward_planning/CR219_room_prompt_contradictions/
dev_instructions/R59_numbers_audit.md`) already did that — it is in making
tomorrow's *new* numeric field impossible to add silently. That is the
DEF038/DEF063 degrade-loudly lesson from CLAUDE.md, one domain over: a field
that ships undeclared is a field nobody decided about.

## Registry shape

One row per user-visible numeric, keyed by (surface, field). `Provenance` is
the audit's own three-value classification:

  * `COMPUTED` — the value is built in code; a model, if consulted at all, may
    only be overridden by the deterministic figure (e.g. a minted stop/target).
  * `CODE_CHECKED` — the value may originate with a model but is verified,
    clamped, or rewritten in code before render. The row names the callable
    that does it, checked importable by `test_numeric_provenance_guard.py`.
  * `LLM_UNVERIFIED` — free model output reaches the render site with no
    code-side check of any kind. A row carrying this value is not a defect by
    itself — it is a passing, honestly-labelled row. The defect is a numeric
    surface with NO row at all.

Every row also carries `site`, a string naming the checking/computing
function and its module (or, for a value that is genuinely never checked, the
render site that ships it unverified) — the registry's own citation, so a
"where does this get verified" question never has to be re-derived by reading
`room_runner.py` again. Citations are `module.callable` strings, not live
imports, on purpose: importing everything a citation might name would pull
half the service layer into this module for no functional reason, and the one
place an import genuinely matters — a `CODE_CHECKED` row's claimed checker —
is exercised directly by check 3 below.

## The three enforcing checks (all in `test_numeric_provenance_guard.py`)

1. **Exhaustiveness over the schema (the red-fail).** Walks
   `Verdict.model_fields` and `CostedStructure.model_fields` — precisely those
   two classes, per the WP16 A3 lane spec, not a deeper recursion into every
   schema the app owns — selects every field whose annotation is numeric (or a
   container of numerics, including a nested Pydantic model that itself has at
   least one numeric leaf), and asserts each has a registry row under the
   `verdict` or `costed_structure` surface respectively. **A new numeric field
   on the verdict card or the costed-structure wire shape fails the build
   until someone classifies it.** This is the whole point of the guard and the
   only part that must be exact.
2. **No silent downgrade.** A row may not move from `COMPUTED` or
   `CODE_CHECKED` to `LLM_UNVERIFIED` without the test being edited in the same
   commit — i.e. the registry is the thing a reviewer reads to see a guarantee
   being given up. Same idea as `test_inline_compose_defaults_match_settings`'s
   "a declared thing must stay declared", not a new mechanism.
3. **Declared-checker-exists.** Every `CODE_CHECKED` row names a callable, and
   the test asserts that callable is importable from the module `site` names.
   This is what would have caught DEF288's shape — an annotation claiming a
   rewrite happened when the rewriter had matched nothing.

## What this guard deliberately does not do

(Audit §5, "What the guard deliberately does not do" — reproduced near
verbatim; this is the part that must survive every future edit of this file,
because a green registry misread as "every number is verified" is exactly the
CR040 failure this whole CR is chasing.)

  * **It does not check prose.** F1 (analyst prose numerals), F3
    (stance-envelope `HEADLINE:`) and F5 (the 1-on-1 surface, now closed by
    lane A1) are prose-surface findings and a field registry cannot reach
    them — `Verdict.reason`, `kill_criterion`, and every transcript turn's
    `content` are typed `str`, so the schema walk correctly never selects them
    as numeric fields to register. They need the checker proposed in F1 (not
    yet built as of this module). Saying so explicitly matters, because a
    green registry could otherwise be read as "every number is verified",
    which would be the CR040 failure this whole CR is chasing — a control
    that reports a guarantee it does not provide.
  * **It does not veto.** Consistent with DEF059: `enforce_safety_floor`
    (`app/agents/safety_floor.py`) is the sole vetoer. This guard is a
    build-time check, not a runtime one — it never runs against a live Room
    convene, only against the schema and the registry at test time.
  * **It does not enforce correctness, only declaration.** A row saying
    `LLM_UNVERIFIED` is a passing row. The guard's job is that the class is a
    decision on the record, not an accident.

## Field-by-field classification: where this module's rows come from

Classified exactly per the audit's §2.1-§2.4 inventory tables, current as of
this module's writing (`6394a3dc` + lane A1's F5 fix + lane A2's F2 fix, both
landing concurrently — see the two `LLM_UNVERIFIED` rows below for how this
registry treats a field whose fix is a DIFFERENT, not-yet-landed lane).
`time_horizon_days` is recorded `LLM_UNVERIFIED` (F4) because that is the
truth as of now — its plausibility-band fix is lane B2's job, not this
module's, and this registry is a record of current provenance, not a
prediction of a future one. The same applies to F2's `key_number` /
`decisive_number`: this module was written concurrently with lane A2's
check-or-strike fix for those two fields; they are recorded `LLM_UNVERIFIED`
here because that is what `backend/app/services/risk_officer.py` did at the
moment this row was written, not because A2's fix is doubted. **If A2's fix
has landed by the time you read this and `risk_officer.py` now checks or
strikes those fields, this is check 2 firing correctly** — upgrade the row
type in the same commit that changes the renderer, per the no-silent-downgrade
rule (which binds a downgrade; an upgrade from `LLM_UNVERIFIED` to
`CODE_CHECKED` is always welcome and never blocked by check 2 — see
`test_no_silent_downgrade_pin` for why only the harmful direction is pinned).
"""

from __future__ import annotations

from enum import Enum


class Provenance(Enum):
    """How a user-visible numeric got the value it renders with."""

    COMPUTED = "computed"
    CODE_CHECKED = "code_checked"
    LLM_UNVERIFIED = "llm_unverified"


class ProvenanceRow:
    """One registry entry: a class plus the site that earns it.

    `site` is a citation string (`"module.callable"`, or a short prose note
    for a value that genuinely has no single checking function — e.g. a
    minted default computed inline). It is read by humans and by check 3 when
    `provenance is CODE_CHECKED`; it is never imported or executed by this
    module itself.
    """

    __slots__ = ("provenance", "site")

    def __init__(self, provenance: Provenance, site: str) -> None:
        self.provenance = provenance
        self.site = site

    def __repr__(self) -> str:  # pragma: no cover - debugging aid only
        return f"ProvenanceRow({self.provenance.name}, {self.site!r})"


# ── The registry ─────────────────────────────────────────────────────────────
#
# Keyed (surface, field). Two surfaces — "verdict" and "costed_structure" —
# are what check 1's exhaustiveness walk covers (they mirror the two Pydantic
# classes the WP16 A3 lane spec names: `Verdict.model_fields` and
# `CostedStructure.model_fields`). The remaining surfaces
# ("risk_rung", "stance_envelope") extend the registry to the audit's §2.3
# Room-transcript inventory outside those two schemas, but are NOT walked by
# check 1, because they are not Pydantic model fields on the two named
# classes. They are registered anyway because a registry that only covers
# what one automated check happens to reach would itself become the kind of
# undeclared gap this guard exists to close, and because F2/F7's rows live
# here, not on `Verdict`.
NUMERIC_PROVENANCE: dict[tuple[str, str], ProvenanceRow] = {
    # ── surface: verdict (Verdict.model_fields) — check 1 walks this ────────
    (
        "verdict", "size_pct",
    ): ProvenanceRow(
        Provenance.CODE_CHECKED,
        "app.services.room_runner._parse_pm_verdict — parsed, then clamped to "
        "the mandate risk-tier ceiling from "
        "app.services.room_runner._risk_tier_size_ceiling",
    ),
    ("verdict", "entry"): ProvenanceRow(
        Provenance.CODE_CHECKED,
        "app.services.room_runner._parse_pm_verdict — LLM-stated, else "
        "substituted with the Trader's number; provenance recorded in "
        "level_provenance",
    ),
    ("verdict", "stop"): ProvenanceRow(
        Provenance.COMPUTED,
        "app.services.room_runner._parse_pm_verdict — LLM-stated, else minted "
        "in code at entry * 0.94 and disclosed in `reason`",
    ),
    ("verdict", "target"): ProvenanceRow(
        Provenance.COMPUTED,
        "app.services.room_runner._parse_pm_verdict — LLM-stated, else minted "
        "in code at entry * 1.13 and disclosed in `reason`",
    ),
    ("verdict", "time_horizon_days"): ProvenanceRow(
        Provenance.LLM_UNVERIFIED,
        "R59 audit F4 — app.services.room_runner._parse_pm_verdict parses "
        "horizon_days with no range check; fix is lane B2 (a plausibility "
        "band mirroring _level_is_implausible), not yet landed as of this row",
    ),
    ("verdict", "approve_votes"): ProvenanceRow(
        Provenance.COMPUTED,
        "app.services.room_runner._vote_pm_samples — counted in code over the "
        "self-consistency samples",
    ),
    ("verdict", "samples"): ProvenanceRow(
        Provenance.COMPUTED,
        "app.services.room_runner._vote_pm_samples — counted in code over the "
        "self-consistency samples",
    ),
    ("verdict", "scripted_turns"): ProvenanceRow(
        Provenance.COMPUTED,
        "app.services.room_runner._compute_agent_text — counted in code from "
        "its nested _fall_back_to_script fallback path",
    ),
    (
        "verdict", "structure",
    ): ProvenanceRow(
        Provenance.COMPUTED,
        "app.schemas.options.costed_structure — the whole nested "
        "CostedStructure subtree (contracts, days_to_expiry, legs, metrics, "
        "greeks, payoff_curve, spot) is built by option_strategist off a "
        "chain the server read; the PM only picks an index, bounded by the "
        "grammar (app.services.room_prompts, pm_verdict_schema's structure_id "
        "enum). Registered as ONE row per the audit's own structure.* "
        "grouping, matching CostedStructure's own registration below rather "
        "than duplicating a per-leaf breakdown here",
    ),
    # ── surface: costed_structure (CostedStructure.model_fields) — check 1 ──
    ("costed_structure", "contracts"): ProvenanceRow(
        Provenance.COMPUTED,
        "app.services.option_strategist — computed off the read option chain; "
        "schemas/options.py's CostedStructure docstring: 'None of it is ever "
        "model-stated'",
    ),
    ("costed_structure", "days_to_expiry"): ProvenanceRow(
        Provenance.COMPUTED,
        "app.services.option_strategist — computed off the read option chain",
    ),
    ("costed_structure", "legs"): ProvenanceRow(
        Provenance.COMPUTED,
        "app.services.option_strategist — every LegOut (right, strike, "
        "quantity, premium, multiplier) is priced off the read chain; "
        "app.schemas.options.leg_out is the wire-shape builder",
    ),
    ("costed_structure", "metrics"): ProvenanceRow(
        Provenance.COMPUTED,
        "app.trading_math.option_strategy (StrategyMetrics) via "
        "app.schemas.options.costed_structure — net_cost, max_loss, max_gain, "
        "break_evens, collateral_required, shares_locked all computed, never "
        "model-stated",
    ),
    ("costed_structure", "net_greeks"): ProvenanceRow(
        Provenance.COMPUTED,
        "app.trading_math.option_strategy — delta/gamma/theta/vega/rho "
        "computed from the priced legs, never model-stated",
    ),
    ("costed_structure", "payoff_curve"): ProvenanceRow(
        Provenance.COMPUTED,
        "app.schemas.options._payoff_curve (app.trading_math.option_strategy."
        "payoff_curve) — server-computed piecewise-linear vertices so the "
        "drawing and the printed max_loss/break_evens share one derivation",
    ),
    ("costed_structure", "spot"): ProvenanceRow(
        Provenance.COMPUTED,
        "app.schemas.options.costed_structure — passed in by the caller from "
        "the market read at costing time; None only when the source genuinely "
        "could not state it, never defaulted to 'now'",
    ),
    # compliance: ComplianceOut is NOT a row here — it has zero numeric leaves
    # (passed: bool, violations/advisories/not_evaluated: list[str],
    # blocked_by: str | None), so it does not select under check 1's "numeric,
    # or a container of numerics" rule. Listed for completeness of the
    # exclusion reasoning, not because a row was forgotten.
    #
    # ── surface: risk_rung (backend/app/services/risk_officer.py rendering,
    #    backend/app/trading_math/option_ladder.py LadderOption) — NOT walked
    #    by check 1 (not a Verdict/CostedStructure field); registered for
    #    completeness of the audit's §2.3 inventory and because F2's headline
    #    rows live here.
    ("risk_rung", "size_pct"): ProvenanceRow(
        Provenance.COMPUTED,
        "app.trading_math.option_ladder.build_option_ladder — the model may "
        "only quote a rung; render_officer_turns iterates the ladder's own "
        "rows, so an invented size has no rung and is dropped",
    ),
    ("risk_rung", "contribution_pts"): ProvenanceRow(
        Provenance.COMPUTED,
        "app.trading_math.risk.drawdown_contribution via "
        "app.trading_math.option_ladder.build_option_ladder",
    ),
    ("risk_rung", "headroom_after_pts"): ProvenanceRow(
        Provenance.COMPUTED,
        "app.trading_math.option_ladder.build_option_ladder",
    ),
    ("risk_rung", "share_of_cap_pct"): ProvenanceRow(
        Provenance.COMPUTED,
        "app.trading_math.option_ladder.build_option_ladder",
    ),
    ("risk_rung", "reward_risk"): ProvenanceRow(
        Provenance.COMPUTED,
        "app.trading_math.option_ladder.reward_to_risk via build_option_ladder",
    ),
    ("risk_rung", "recommended"): ProvenanceRow(
        Provenance.CODE_CHECKED,
        "app.services.risk_officer.render_officer_turns — LLM-stated but only "
        "renders when it matches a real ladder rung (F7, noted not a finding)",
    ),
    ("risk_rung", "confidence"): ProvenanceRow(
        Provenance.CODE_CHECKED,
        "app.services.risk_officer.render_officer_turns — LLM-stated, "
        "enum-validated against _CONFIDENCE_VALUES (F7, noted not a finding)",
    ),
    ("risk_rung", "key_number"): ProvenanceRow(
        Provenance.LLM_UNVERIFIED,
        "R59 audit F2 — app.services.risk_officer, free text explicitly asked "
        "to be 'a quotation from the fact sheet' (build_risk_officer_"
        "instruction), never verified against the sheet or the ladder before "
        "rendering (render_officer_turns) or before promotion into the comb "
        "headline slot. Fix is lane A2 (check-or-strike against the sheet + "
        "ladder), landing concurrently with this row and not yet reflected "
        "here — see this module's docstring for how a landed A2 should update "
        "this row",
    ),
    ("risk_rung", "decisive_number"): ProvenanceRow(
        Provenance.LLM_UNVERIFIED,
        "R59 audit F2 — app.services.risk_officer.render_officer_turns, same "
        "unverified-quotation shape as key_number, promoted into the balanced "
        "call's headline. Fix is lane A2, same caveat as key_number above",
    ),
    # ── surface: stance_envelope (backend/app/services/room_runner.py
    #    parse_stance_envelope) — NOT walked by check 1; the SIZE: field on
    #    every agent's trailing envelope, distinct from a verdict's size_pct.
    ("stance_envelope", "argued_size_pct"): ProvenanceRow(
        Provenance.CODE_CHECKED,
        "app.services.room_runner.parse_stance_envelope — bounded "
        "0 < x <= 100; a measurement channel only (AgentMessage."
        "argued_size_pct), not rendered on the transcript",
    ),
}


def is_numeric_provenance_declared(surface: str, field: str) -> bool:
    """True if (surface, field) has a registry row. Reads better at a call
    site than a bare `in NUMERIC_PROVENANCE` — this module's one convenience
    export beyond the registry and the enum themselves."""
    return (surface, field) in NUMERIC_PROVENANCE
