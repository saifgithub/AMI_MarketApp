# DEF367-LESSONS hand-off (coder.local)

TRACK: coder.api · ROLE: coder.local · LANE: DEF367-LESSONS

## Scope
Close 6 wire surfaces (lessons + ai_coach). Test-only lane, no product code touched.

## New test file
`backend/tests/unit/test_def367_lessons_wire.py` — covers:
- GET  /v1/ai_coach/search                     -> CoachSearchHit
- GET  /v1/lessons/activations/$userId         -> AgentActivationRecord
- GET  /v1/lessons/progress/$userId            -> ProgressSummary
- GET  /v1/lessons/progress/$userId/by_lesson  -> LessonStatus
- GET  /v1/lessons/requirements/$userId        -> AgentUnlockRequirement
- POST /v1/lessons/quiz                        -> QuizResult

## Status (in progress — updating as steps complete)
1. `uv run pytest tests/unit/test_def367_lessons_wire.py -q` → **6 passed, exit 0**.
2. Full suite (`sh orchestration/dispatch/run_full_suite.sh`) — running in background, polling.
3. Gate (`verify.py` / `--update-baseline`) — pending step 2.

Will update this file with SUITE_EXIT, baseline before/after count, and pushed SHA before stopping.
