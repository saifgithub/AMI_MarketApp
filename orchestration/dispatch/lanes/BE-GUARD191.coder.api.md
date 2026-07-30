<!-- lane hand-off — coder.api. CR052. -->
# BE-GUARD191 — hand-off (round 1)

STATUS: READY_FOR_AUDIT (round 1)

Branch: `lane/BE-GUARD191.coder.api`, worktree `.claude/worktrees/coder.api-BE-GUARD191`.

## DEF191 — the four-leg invariant guard now derives its subjects instead of enumerating them

**The problem, restated with the measurement:** the guard test
(`test_cr101_be1_settable_risk_caps.py::test_every_enforced_limit_field_is_enforced_disclosed_and_settable`)
hand-enumerated its three subject fields. CR101-BE2 added five more enforced
limits; the guard picked up none of them and stayed green — a positive,
misleading signal, not a missing one.

**Design decision — a per-field `Field(json_schema_extra=...)` marker, not a
class-level registry.** Both shapes were named in the row. Picked the marker
because the declaration then lives *next to the field itself*, where someone
adding a new enforced limit is already looking and editing — a separate
registry module is one more file a developer has no reason to visit unless
they already know it exists, which is the exact tribal-knowledge failure
CR038 already names ("prompt instructions are not controls" generalizes to
"conventions are not controls" — a registry nobody is forced to touch is a
convention). The tradeoff, stated up front because it matters for acceptance
4: a marker does **not**, by itself, force anyone to visit `mandate.py` at
all when adding a field — nothing stops a field from existing unmarked. See
below for the mitigation and its limits.

**Touch points:**

1. `backend/app/schemas/mandate.py`:
   - `ENFORCED_LIMIT_MARKER = "enforced_limit"` constant, with a docstring
     recording the design decision above.
   - All eight currently-enforced fields carry
     `Field(json_schema_extra={ENFORCED_LIMIT_MARKER: True})`:
     `max_drawdown_pct`, `sector_cap_pct`, `single_name_cap_pct` (CR101-BE1)
     and `post_loss_cooldown_hours`, `max_open_positions`,
     `max_trades_per_day`, `max_trades_per_week`, `max_open_risk_pct`
     (CR101-BE2).
   - `enforced_limit_field_names() -> list[str]` — walks `Mandate.model_fields`
     for the marker, sorted. This is the derivation the guard now calls
     instead of a hand list.
2. `backend/tests/unit/test_cr101_be1_settable_risk_caps.py` — acceptance 6
   rewritten:
   - The eight per-field behavioural checks (the actual "is it enforced /
     what units / what overlay text / does PATCH work" business logic, which
     is inherently field-specific and can't be generic) are now named
     functions in `_FOUR_LEG_PROBES: dict[str, callable]`, not inline blocks
     in one giant test body — the "hand-written blocks left alongside" the
     assignment warned against. No duplication: refactor, not addition.
   - `test_every_enforced_limit_field_is_enforced_disclosed_and_settable` now:
     (1) asserts `enforced_limit_field_names()` is non-empty — **the vacuity
     leg**, so a broken derivation fails loudly instead of passing on zero
     subjects; (2) asserts the derived set and `_FOUR_LEG_PROBES`' keys match
     exactly, naming any derived field with no probe (or any stale probe
     whose field lost its marker); (3) runs every probe.
   - New: `test_no_unmarked_numeric_field_is_referenced_by_enforcement_code`
     — acceptance 4's mitigation, see below.

## Acceptance 3 — proven live (add throwaway marked field, missing leg, red, revert)

Added `throwaway_test_limit_pct: float | None = Field(default=None,
json_schema_extra={ENFORCED_LIMIT_MARKER: True})` next to `max_open_risk_pct`
— marked, no probe. Ran the guard test:

```
missing_probes = sorted(set(derived) - set(_FOUR_LEG_PROBES))
assert not missing_probes, (...)
E       AssertionError: ['throwaway_test_limit_pct'] carries Field(json_schema_extra=
{'enforced_limit': True}) but has no entry in _FOUR_LEG_PROBES above — add one
covering all four legs (enforced / disclosed own-units / disclosed overlay /
settable) before this can pass.
1 failed in 0.58s
```

Red, naming the exact field. Reverted; `git diff` on `mandate.py` afterward
carries no trace of it (confirmed with `grep -n throwaway`, clean).

## Acceptance 4 — the harder half — DISCLOSED PARTIAL, DEF191 stays `open`

Per the assignment: *"if your design cannot catch that, say so explicitly
rather than implying the class is closed."* Doing that here.

**What I built:** `test_no_unmarked_numeric_field_is_referenced_by_enforcement_code`
— a heuristic cross-check, not a proof. It collects every numeric
(`int`/`float`/`Optional[...]`/numeric `Literal`) `Mandate` field not in a
small `_NON_LIMIT_NUMERIC_FIELDS` exemption set (`version`, `risk_score`,
`credit_balance`, `credit_allowance`, `room_cost` — resolver inputs and
server-stamped entitlement state, not limits), then greps a fixed list of
enforcement-adjacent source files (`safety_floor.py`, `overlay_generator.py`,
`sector_allocation.py`, `room_runner.py`, `room_prompts.py`,
`risk_limit_backfill.py`, `api/mandate.py`) for a literal `mandate.<field>`
attribute read. An unmarked field found there fails, naming the field and
the file.

**Proven live:** added `unmarked_throwaway_pct: float | None = None` (no
marker) to `mandate.py`, and a throwaway `mandate.unmarked_throwaway_pct`
read inside `safety_floor.py`. Ran the cross-check test:

```
AssertionError: unmarked numeric Mandate field(s) referenced by
enforcement-adjacent code: {'unmarked_throwaway_pct': ['app/agents/safety_floor.py']}
— add Field(json_schema_extra={'enforced_limit': True}) to declare it an
enforced limit (...), or add it to _NON_LIMIT_NUMERIC_FIELDS with a reason
if it genuinely isn't one.
1 failed in 0.36s
```

Red, naming the field and the file. Reverted both edits;
`git diff --stat backend/app/agents/safety_floor.py` shows no diff.

**What this does NOT catch, stated explicitly (why 4 is a partial):** the
cross-check only sees a literal `mandate.<field>` token in one of seven
listed files. It will miss a field that's enforced by reading
`mandate.model_dump()` and indexing by key, aliased to a local variable
before use ("`sc = mandate; ... sc.new_field`" still matches the regex
against `sc.` not `mandate.`, so even a rename of the local defeats it), or
wired into an enforcement site outside the seven-file list. The class DEF191
exists to close is "a developer who forgets the checklist" — a developer who
forgets the marker *and* happens to route enforcement through one of the
unusual paths above defeats both legs of the guard (the four-leg test can't
see it because it's not derived, and the cross-check can't see it because it
doesn't grep-match). That combined failure is not closed by this design.

Per the assign's own instruction, **DEF191 is left `open`**, not flipped to
`fixed` — the row's DESCRIPTION column (not the status cell — DEF203) now
records exactly what's proven and what remains, matching this hand-off.

## failure_patterns.md P12

Added a paragraph to the existing enforcing-checks bullet recording the
DEF191 measurement and the derivation fix, so P12 no longer cites the old
hand-enumerated test as if it were sound.

## Full suite

`"./backend/.venv/bin/python" -m pytest backend/tests/unit/ -q` — run from
repo root as instructed; result pending in this session (long-running,
reported separately once it completes). The lane's own file
(`test_cr101_be1_settable_risk_caps.py`, 31 tests) passes clean, and the two
new/changed tests were exercised live under mutation above.

## Fences honoured

Touched only `backend/app/schemas/mandate.py`,
`backend/tests/unit/test_cr101_be1_settable_risk_caps.py`,
`docs/initial_specs/08_tech/failure_patterns.md`,
`docs/defect/_registry/DEF191.row.md` + regenerated `docs/defect/def_list.md`,
and this hand-off file. No change to what any limit enforces, resolves to,
or discloses — `ResolvedCaps`/`_with_plan_state` untouched. Did not touch
`backend/app/agents/*` (beyond the throwaway mutation-test edit, reverted),
`content/agents/*`, `journal.py`/`reputation_service.py`/`api/sse.py`,
`api/room.py`, or `mobile/`.

ASSIGNED: coder.api round 1
DISPATCH: OPEN
