<!--
DEF084-BE.architect.md — builder (coder.api) hand-off lane. State derives from round
numbers here vs DEF084-BE.auditor.md (see PROTOCOL.md). Built by coder.api.
-->

# DEF084-BE — audit lane (builder: coder.api)

**Item:** DEF084 — the `halal` mandate flag is enforced by a hardcoded 7-ticker allowlist
(`{AAPL, MSFT, NVDA, GOOGL, META, TSLA, AMZN}`), while backend copy told the user a Sharia
compliance screen ran. The real `sharia_screen()` in `trading_math/screening.py` is dead code.
**Fourth occurrence of the CLAUDE.md "degrade loudly" class** (DEF038 / DEF063 / DEF082).
Register: [`docs/defect/def_list.md`](../../../docs/defect/def_list.md) DEF084. Spec:
[`DEF084_halal_flag_is_an_allowlist_not_a_screen.md`](../../../docs/defect/DEF084_halal_flag_is_an_allowlist_not_a_screen/DEF084_halal_flag_is_an_allowlist_not_a_screen.md).

**Product decision (Saiful, 2026-07-22): Option 2 only** — tell the truth about the allowlist.
Do NOT wire `sharia_screen()` (Option 1). Do NOT withdraw the flag. This lane = backend only
(DEF084-MOBILE and DEF084-CONTENT are separate).

**depends-on:** none. **HOT-FILES touched:** `sim_engine.py`, `safety_floor.py` (signatures kept
byte-stable — `coder.room` consumes them), `api/mandate.py`.

**Head SHA:** `bd5c74d`.

## What was done

Relabelled the halal-flag set everywhere a backend surface called it a Sharia screen, so it now
reads as a **curated demonstration universe, explicitly not a compliance screen**. Enforcement
behaviour is byte-for-byte unchanged — same 7 tickers, same membership check; only the *labels /
copy / docs* changed.

1. **`sim_engine.py`** — constant `DEFAULT_HALAL_UNIVERSE` → **`DEFAULT_HALAL_DEMO_UNIVERSE`**
   (same members). New comment block states it is a demonstration universe, not a screen, and that
   `trading_math.screening.sharia_screen` is wired to nothing on this path (names DEF084). Both call
   sites (`submit()`, `preview()`) updated.
2. **`api/mandate.py`** — import + the `/audit` call site updated to the renamed constant.
3. **`safety_floor.py`** — the two **user-facing** violation strings a client renders changed from
   `"ticker {t} fails Sharia compliance screen"` →
   `"ticker {t} is outside AMI's curated demonstration universe (halal flag; not a Sharia screen)"`
   (in both `check_mandate_compliance` and `check_holdings_against_mandate`). The
   `"halal screen requested but halal_universe not provided"` string →
   `"halal flag set but demonstration universe not provided"`. Docstring + the `# 4)` comment
   relabelled. **`halal_universe` parameter name and all signatures unchanged** (frozen surface —
   `coder.room` calls `check_mandate_compliance(..., halal_universe=...)` unmodified).
4. **`trading_math/screening.py`** — module docstring gains a NOT-REACHABLE paragraph naming DEF084
   and pointing at `DEFAULT_HALAL_DEMO_UNIVERSE` as the actual mechanism. **Docstring-only, no code**
   (this edit is outside coder.api's normal owned paths — `trading_math/` — but the assign lane
   directs it explicitly; behaviour-neutral).

## GUARD (required — verified RED before the fix)

New structural guard `tests/unit/test_def084_halal_flag_copy_guard.py`, encoding the house rule:
*a mandate flag's user-facing rejection copy must describe the mechanism that actually enforces it.*
Two tests:

- `test_halal_flag_enforcement_is_a_literal_set_not_a_screen` — asserts the mechanism is a literal
  set (`DEFAULT_HALAL_DEMO_UNIVERSE` is a non-empty set) and that the real ratio screen is NOT
  imported into either enforcement module (`safety_floor`, `sim_engine`). If someone wires Option 1
  in, this trips so the copy guard is revisited at the same time.
- `test_halal_rejection_copy_does_not_claim_a_computed_screen` — a halal rejection's copy must
  positively name the "demonstration universe" AND must not *affirm* a `sharia screen` /
  `compliance screen` (explicit negated disclaimers like "not a Sharia screen" are allowed and
  stripped before scanning — the guard forbids claiming a screen ran, not denying one).

**RED proof (against unmodified `main`, SHA 44759a9):** copied the final guard into `main`'s test
tree and ran it — both tests fail:
```
E  AttributeError: module 'app.services.sim_engine' has no attribute 'DEFAULT_HALAL_DEMO_UNIVERSE'.
   Did you mean: 'DEFAULT_HALAL_UNIVERSE'?
E  AssertionError: halal rejection copy must name the curated demonstration universe (DEF084)
2 failed in 0.41s
```
The pre-fix copy (`"...fails Sharia compliance screen"`) neither names the demonstration universe
nor avoids the affirmative screen claim → RED, exactly the gap DEF063 left by shipping a guard never
seen to fail.

## Why this is safe / minimal

- **No enforcement behaviour changed.** Same 7 tickers, same set-membership check, same
  `blocked_by="compliance"` reason code, same signatures. A halal user gets the same accept/reject
  as before — only the words shown changed to stop asserting a computation that never ran.
- **Frozen surface intact.** `halal_universe` param name and every function signature in
  `safety_floor.py` are unchanged; `coder.room`'s call sites are unaffected (not touched).
- **`screening.py` left in place and unwired**, per the decision — docstring-only note added.
- **Out of scope, untouched:** `content/**`, `mobile/**`, the ratio/standard religious corrections
  (SME-only), and Option 1 wiring.

## Observed-but-not-touched (flagged for Architect)

`backend/app/agents/overlay_generator.py` still narrates "HALAL / Sharia screen REQUIRED" /
"Apply Sharia screen on every candidate" to agents (lines ~88, 157, 196, 300), and embeds ratio
thresholds (33% / 5%) that DEF084 flags as the wrong standard. I did **not** edit it: it is
agent-prompt narration entangled with the religious ratio/standard content the assign lane reserves
for Saiful/SME ("never yours"), and it is not among the lane's named HOT-FILES. Recommend a
follow-up lane (coordinated with the CONTENT ratio decision) rather than a silent copy edit here.

## Tests run (self-test)

- Full suite: `pytest backend/tests/unit/ -q` (from `backend/.venv`, Python 3.13) →
  **941 passed**, 1 pre-existing unrelated warning (`HTTP_422` deprecation in `test_sim_history`).
- Updated the three dependent assertions I own that keyed on the old "Sharia" copy
  (`test_safety_floor.py`, `test_sim_engine.py`, `test_mandate_audit.py`) to the truthful
  "demonstration universe" copy. (`test_overlay_generator.py`'s `"HALAL"/"Sharia"` assertion is
  untouched — overlay_generator not in scope.)

## Definition of Done

| Row | Disposition |
|---|---|
| **Scope** | Backend relabel only (Option 2): constant rename, user-facing copy, docstrings/comments in the 3 named HOT-FILES + `screening.py` docstring. No enforcement/behaviour change. |
| **Guard** | New `test_def084_halal_flag_copy_guard.py` (2 tests). Verified **RED** against unmodified `main` (output pasted above), **GREEN** post-fix. |
| **Tests** | `pytest backend/tests/unit/ -q` → **941 passed**. |
| **Frozen surface** | All `safety_floor.py` signatures + `halal_universe` param name unchanged; `coder.room` call sites untouched. |
| **Commit tag** | `bd5c74d` — `fix(mandate): DEF084 Option 2 … (AT:coder.api DEF084)`. |
| **Scope discipline** | One code commit, DEF084-BE only. No `content/**`, no `mobile/**`, no room-cluster edits, no Option-1 wiring. |

SUBMITTED: round 1
