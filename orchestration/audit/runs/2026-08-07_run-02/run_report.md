# Run report — 2026-08-07_run-02 — DEF225 (round 1)

Item: DEF225, `fix(tests): DEF225 — anchor two AST guards to the test file,
not the cwd`. SHA under audit `b29d5656`, parent `6ea166a6`.

## Setup

```
git worktree add .claude/worktrees/audit-DEF225-before b29d5656~1
git worktree add .claude/worktrees/audit-DEF225-after  b29d5656
```

Both removed (`git worktree remove --force`) at the end of the run.
Interpreter: absolute `backend/.venv/bin/python` (DEF159 — never bare
`pytest`, no `.venv` in a scratch worktree).

## Commands run, and raw output

1. `before`, repo root:
   `backend/.venv/bin/python -m pytest backend/tests/unit/ -q`
   → `2 failed, 2363 passed, 13 warnings in 315.82s (0:05:15)`. Failures:
   `test_cr136_health_gate.py::test_the_tiles_route_never_calls_enforce_gate`,
   `test_cr136_health_gate.py::test_the_gate_module_never_imports_the_journal_enum`.

2. `before`, from `backend/`:
   `.venv/bin/python -m pytest tests/unit/ -q`
   → `2365 passed, 13 warnings in 377.32s (0:06:17)`.

3. `after`, repo root:
   `backend/.venv/bin/python -m pytest backend/tests/unit/ -q`
   → `2536 passed, 13 warnings in 339.13s (0:05:39)`.

4. `after`, from `backend/`:
   `.venv/bin/python -m pytest tests/unit/ -q`
   → `2536 passed, 13 warnings in 359.88s`.

5. `after`, repo root, targeted 3-file command from the submission's §4:
   `pytest backend/tests/unit/test_cr136_health_gate.py
   backend/tests/unit/test_def225_tests_are_cwd_independent.py
   backend/tests/unit/test_cr124_compose_hardening.py -q`
   → `227 passed in 9.57s` — exact match to the submission's pasted output.

6. Mutation proof, reproduced on the real broken tree: copied
   `test_def225_tests_are_cwd_independent.py` from `after` into `before`
   (unmodified pre-fix source) and ran it there:
   `pytest tests/unit/test_def225_tests_are_cwd_independent.py -q`
   → `2 failed, 169 passed in 8.32s`. Failures name
   `test_cr124_compose_hardening.py` (the latent instance) and
   `test_cr136_health_gate.py` (the original defect) by parametrize id.

7. Vacuity mutation, `after` worktree: patched
   `_relative_source_path_literals` to unconditionally `return []`, ran the
   guard file alone:
   → `1 failed, 170 passed in 14.30s`. Only
   `test_the_guard_would_catch_the_original_defect` fails; all 170
   parametrised per-file cases pass vacuously. Reverted via file restore from
   backup.

8. Guard-bypass probe: imported `_relative_source_path_literals` directly and
   fed it 11 hand-written AST snippets covering variable-assigned strings,
   `Path()`-then-`/`-join, `open()` with no `Path`, f-strings,
   `os.path.join`, string concatenation, and the `pathlib.Path` attribute
   form. Results in DEF225.auditor.md §4 — 6 of 8 non-baseline forms bypass
   the guard entirely.

9. `parents[2]` resolution check, `after` worktree:
   `Path('backend/tests/unit/test_cr136_health_gate.py').resolve().parents[2]`
   → `.../backend` — confirmed correct.

10. False-positive check: `test_def225_tests_are_cwd_independent.py` alone,
    `after` worktree → `171 passed`, 0 offenders across all 170 real
    `test_*.py` files in `backend/tests/unit/`.

11. Scope check: `grep -rn "File(" mobile/test/` (excluding tmp/temp) — found
    3 files with cwd-relative `File(...)` source reads (DEF225.auditor.md
    §9). Judged OUT-OF-SCOPE per BINDINGS' single documented `flutter test`
    invocation directory (no dual-invocation ambiguity like the pytest case).

## Register / drift check

`docs/defect/def_list.md:289` DEF225 row present, `fixed`, matches
`DEF225.row.md` content and `AT:R66` tag. `git show b29d5656 --stat` — 5 files
touched, matches the submission's declared file list exactly.

## Concurrency note

A prior local commit `9f7ae961` had already put a `COMPLETE` verdict on
`DEF225.auditor.md` but was never pushed to origin and never got a run report
or trail row — not delivered per PROTOCOL.md. `orchestration/audit/runs/2026-08-07_run-01/`
was independently claimed by a concurrent track-U session working CR132 in
the same window; this report uses `run-02` to avoid collision, per the same
disjoint-path principle the lane files rely on.

## Verdict

COMPLETE (round 1). Full findings + severities in
`orchestration/audit/cr/DEF225.auditor.md`.
