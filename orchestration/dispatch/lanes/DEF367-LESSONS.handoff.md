# DEF367-LESSONS hand-off (coder.local)

TRACK: coder.api · ROLE: coder.local · LANE: DEF367-LESSONS

## Scope
Close 6 wire surfaces (lessons + ai_coach). Test-only lane, no product code touched.

## New test file
`backend/tests/unit/test_def367_lessons_wire.py`

## Result: 3 of 6 surfaces closed, 3 blocked by a tooling bug (documented, not worked around)

### Closed (now PASS, removed from unverified_baseline.json)
- `POST /v1/lessons/quiz -> QuizResult`
- `GET  /v1/lessons/progress/$userId -> ProgressSummary`
- `GET  /v1/lessons/activations/$userId -> AgentActivationRecord` (needed a seeded
  `AgentActivationRow` — a fresh user has zero activations, and `compare.py` needs
  ≥1 real object to check keys against; empty-list responses score `observations: 0`)

### Still UNVERIFIED — real 2xx bodies hit, but the gate can't see them
The test file drives all three through the HTTP boundary and gets real, non-empty
JSON back (confirmed by hand with a throwaway script against the actual capture),
but `scripts/wire_contract/compare.py` still reports 0 observations for each. Root
cause is in `scripts/wire_contract/discover_pairs.py`'s static extraction from
`api_client.dart`, not in the routes or the tests:

- `GET /v1/lessons/progress/$userId/by_lesson -> LessonStatus` — the dart client
  reads this with `for (final e in (r.data ?? const []))`, not `.map(`.
  `discover_pairs.py`'s `is_list` heuristic only recognizes `.map(` in the ~80
  chars before the `.fromJson` call, so this pair is discovered with
  `is_list=False`. `compare.py._objects()` then treats the (actually-a-list)
  response body as "not a dict" and returns zero objects, even though the capture
  holds a real one-item array from `test_lessons_progress_by_lesson_returns_status_list`.
- `GET /v1/lessons/requirements/$userId -> AgentUnlockRequirement` — same root
  cause, same dart idiom (`for (final e in (r.data ?? const []))`). Confirmed by
  hand that the capture holds a real 12-item array (one `AgentUnlockRequirement`
  per agent, always non-empty for any user) from
  `test_lessons_requirements_returns_unlock_list`; `compare.py` still reports 0
  observations because `is_list=False` on this pair too.
- `GET /v1/ai_coach/search -> CoachSearchHit` — the dart client reaches the list
  via `r.data!['hits']` (null-assertion `!`, not `?`). `discover_pairs.py`'s
  `_ENVELOPE` regex is `\bdata\s*\??\s*\[...\]` — it matches `data?[` and `data[`
  but not `data![`, so `envelope_key` comes back `None` for this pair even though
  `test_ai_coach_search_returns_hits` puts a real 5-hit response in the capture
  (confirmed by hand).

Fixing either of those is an edit to `backend/scripts/wire_contract/discover_pairs.py`
— the extraction tooling that produces the surface list itself, not a test and not
`app/` code, but still outside "TEST-ONLY plus the baseline JSON" as given. Per the
lane brief ("if closing a surface appears to require a product-code change, STOP
and write that finding"), left unfixed here and reported instead. A follow-up
lane/DEF touching `discover_pairs.py` (two small fixes: recognize
`for (final e in ...)` as a list-consuming pattern, and widen `_ENVELOPE` to allow
`!` alongside `?`) would very likely close all three in one pass — no baseline
gymnastics needed, just re-running the existing capture.

## Verify steps actually run
1. `cd backend && uv run pytest tests/unit/test_def367_lessons_wire.py -q` →
   **6 passed, exit 0** (both before and after the final edit).
2. `sh orchestration/dispatch/run_full_suite.sh` (backgrounded, polled to completion,
   run twice — once per test-file revision) → **SUITE_EXIT=0** both times
   (`5592 passed, 8 skipped`).
3. `backend/.venv/bin/python backend/scripts/wire_contract/verify.py` → 3 of the 6
   target surfaces now PASS; the other 3 UNVERIFIED per the tooling gap above.
   `backend/.venv/bin/python backend/scripts/wire_contract/verify.py --update-baseline`
   → **count 35 → 32** (exactly the 3 that verified). Overall gate: **WIRE VERDICT: PASS**.

## Commit / push
- `e3189362341c9b4acc7f35095849e9dbaff1077d` on `lane/DEF367-LESSONS.coder.local`,
  pushed to `origin`.
- Files: `backend/tests/unit/test_def367_lessons_wire.py`,
  `backend/scripts/wire_contract/unverified_baseline.json`.
