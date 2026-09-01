# CR216 — change-to-test selection by import graph, not by name

**Status:** done · **Owner:** Architect · **Filed:** 2026-09-01 · **Tag:** `(AT:R75 CR216)`

## Why

On 2026-09-01, DEF387 added a supervisor guard to `backend/scripts/backtest_sweep.py`. The author
checked it with a targeted `-k` run on the obvious terms — `sweep`, `backtest` — got green, and
promoted. It had broken `test_def358_completion_sentinel_counts_the_batch.py`, which calls
`sweep.main()` in-process and therefore hit the new refusal. Their own commit message says it
plainly:

> My own `-k` filter missed this before the promotion: the file is named for DEF358 and matches
> neither "sweep" nor "backtest", so the subset I ran to check the guard could not have caught it.
> The full suite did.

This is not carelessness. **Tests in this repo are named after the defect they pin, not the module
they exercise** — `test_def358_…`, `test_def389_…`, `test_cr215_…`. That convention is good for
traceability and it makes `-k <module-name>` structurally blind to a module's own callers. No amount
of care fixes a filter that cannot follow an import edge.

The cost is asymmetric and already measured twice in one day: the full suite here is **~900s**, so
the incentive to narrow is real, and narrowing by name is the obvious way to do it.

## What shipped

**`backend/scripts/tests_for_changed.py`** — parses every `import` / `from` under `backend/{app,scripts,tests}`
(637 files), inverts the graph, and reports the test files that reach the changed modules, directly
or transitively.

```
python backend/scripts/tests_for_changed.py                  # uncommitted work vs HEAD
python backend/scripts/tests_for_changed.py --since HEAD~3   # a range
python backend/scripts/tests_for_changed.py app/services/room_runner.py --why
```

Resolution detail that matters: `from app.services import room_runner` names the *package* in the
AST node and the *submodule* in the alias, so both spellings are resolved. Resolving only the node
would drop precisely the edges that matter and under-select silently.

## Non-Python changes — derived, not guessed

An import graph cannot see `docker-compose.yml`, the registers, or the lesson corpus, and this repo
has many tests that read exactly those. The first cut answered "full suite required" for any
non-Python change — correct, useless, and indistinguishable from the status quo: dogfooding it on a
real working tree escalated on untracked checkpoint memos alone.

Writing a glob table (`docker-compose.yml` → `test_config_compose_parity.py`, …) would have been the
same species of guess this CR exists to replace. Instead the tool **collects the string literals the
tests themselves contain** and matches changed paths against them. So a compose change selects
`test_config_compose_parity.py` because that test names the file — a fact, not an assumption.

Precision matters here: the first version matched bare path segments, so the literal `"mobile"`
in fifteen unrelated tests attributed every `Podfile.lock` change to all of them. An over-loose
floor is still a wrong answer, it just fails in the tiring direction — and a selector people learn
to distrust is one they stop running. Matching is now exact path, exact basename, or a
multi-segment suffix.

**Reporting clean for something it cannot reason about** remains the failure to avoid. A *tracked*
non-Python file that no test names has an unknown blast radius, so it **exits 3 and demands the full
suite**; untracked ones (new files nothing references yet) are listed but do not escalate. Every run
prints its own caveat: *"This is a FLOOR, not a proof: static imports only."*

## Asserting the gap instead of assuming it The guard test pins not only that the selector
finds `test_def358_…` from a change to `backtest_sweep.py`, but that a name filter genuinely does
**not** — so if someone later renames that test to contain "sweep", the pin says the motivating
example needs updating rather than quietly passing on a premise that stopped being true.

## Verified

| Check | Result |
|---|---|
| The historical miss | `tests_for_changed.py backend/scripts/backtest_sweep.py` returns all **3** importers, `test_def358_completion_sentinel_counts_the_batch.py` among them |
| Transitivity | `app/core/config.py` → 237 test files, via chains like `overlay_store → db/__init__ → db/session → config` |
| Non-Python attribution | `docker-compose.yml` → selects `test_config_compose_parity.py` (the CR040 drift guard names it) |
| Degrade loudly | a tracked non-Python file no test names → exit **3**, empty selection, "FULL SUITE REQUIRED" |
| Exit codes | 0 selection · 2 bad path · 3 full suite required |
| Guard test | `test_cr216_test_selection.py` — 8 pins, green; 2 mutations applied, 2 killed |

## The guard test caught itself

The first draft of the "an unattributable file must exit 3" pin hardcoded `mobile/ios/Podfile.lock`
— which put that basename **into the haystack the selector searches**, so the test named the very
file it asserted was unnamed, and the assertion inverted. The example is now derived from
`git ls-files` at runtime and never written as a literal. Same shape as the P30 baseline that listed
absent identifiers and thereby made them present; recorded here because it is the second instance.

## Definition of Done

| Row | Disposition |
|---|---|
| **Scope** | Selector + guard test + failure_patterns **P32**. No change to any existing test or module. |
| **Enforcing check** | `backend/tests/unit/test_cr216_test_selection.py`, 8 pins incl. the "a name filter really does miss it" assertion. Mutation-proved: loosening the match and downgrading the exit-3 path each fail a pin. |
| **Degrade loudly** | Non-Python change exits 3; the floor-not-proof caveat is on every run and pinned by a test. |
| **Regression risk** | None — the tool is additive and read-only; it runs no tests and edits nothing. |

## Not in scope

- **Wiring it into `/promote-to-alpha` as a gate.** That is the obvious next step and the place the
  DEF387 miss would actually have been caught — but it changes the promotion path, which is the
  riskiest surface in the project, and the memo for 2026-09-01 already records two
  HEAD-moved-mid-promotion incidents on this shared checkout. Deliberately left as a separate,
  evidenced decision rather than smuggled in behind a tooling CR.
- Dynamic-dependency detection (subprocess, `importlib`, fixture data files). Named as a limit in
  the tool's own output rather than half-solved.
- Extending the graph to `mobile/` (Dart) or `website_api/`.
