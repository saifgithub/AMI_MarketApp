# BATCH-R75 audit — auditor.core, round 1

DIFF: `git diff 7c07dc5b..f8be15e2` — 25 files, +1638/-375. Three defects as one batch.
Audited the committed SHA `f8be15e2` in worktree `audit-BATCH-R75`.

## DEF392 — transport timeout must sit strictly OUTSIDE the Room's per-agent guard
- (a) EVERY OpenAI-compatible registration reaches the derived default: kimi, deepseek,
  qwen, gemini all pass NO `timeout_seconds` (llm_gateway.py:953/981/996/1013) → `None`
  → `_default_transport_timeout_s()` = `room_agent_timeout_s + 180` (:558-566, :603-604).
  vLLM passes `settings.vllm_request_timeout_s` explicitly (:919). All five verified via
  the objects that exist, not restated numbers (`test_..._sits_outside_the_guard`).
- (b) Explicit caller still wins: `timeout_seconds is None` is the ONLY override branch
  (:603); a non-None value flows straight to httpx (:628). vLLM's DEF389 pin at :919
  intact. `test_explicit_timeout_still_wins` confirms 1234.5 survives.
- (c) No remaining path constructs a client inside the guard: grep of `backend/app`
  finds only the five registrations; four default (guard+180 > guard always), vLLM's
  explicit value is itself validator-gated > guard. No literal timeout anywhere.
- (d) `model_validator(mode="after")` genuinely reachable on boot: `settings = Settings()`
  at config.py:928 runs at import; no `validate_assignment`/bypass. Rejects EQUALITY
  (`<=`, config.py:165) as well as inversion — `test_..._refuses_an_inverted_pair`
  covers both `45/800` and `180/180`.
- (e) Does not reject shipped defaults: `vllm_request_timeout_s=360 > room_agent_timeout_s=180`
  (config.py:127/151); `test_..._accepts_the_shipped_defaults` passes.
- Mutation note (arch): reintroducing `timeout_seconds: float = 60.0` kills 3/6. Not
  re-run; attacked the uncovered edges above instead — all hold.
RESULT: holds.

## DEF367 — three wire surfaces closed, baseline 35→32
- Baseline edit is a REAL shrink of exactly 3 (`unverified_baseline.json`): removed
  `POST /v1/lessons/quiz -> QuizResult`, `GET /v1/lessons/progress/$userId -> ProgressSummary`,
  `GET /v1/lessons/activations/$userId -> AgentActivationRecord`. count 35→32.
- All three closed surfaces drive a REAL `TestClient` (HTTP boundary), not a service
  function: `test_def367_lessons_wire.py` client.get/post at :85, :150, :171. No direct
  service calls → no false close.
- The other-three excuse is TRUE, not an excuse — confirmed against `api_client.dart`:
  * `lessonStatusByLesson` (:887) and `unlockRequirements` (:901) use
    `for (final e in (r.data ?? const []))`, NOT `.map(`; `discover_pairs.py`'s `is_list`
    heuristic recognizes only `.map(` (discover_pairs.py:111) → `is_list=False`.
  * `aiCoachSearch` (:1494) uses `r.data!['hits']`; `_ENVELOPE` regex
    `\bdata\s*\??\s*\[` (discover_pairs.py:49) matches `data?[`/`data[` but not `data![`
    → `envelope_key=None`. Genuine extraction gaps in the tooling, correctly left
    out-of-scope for a test-only lane.
RESULT: holds. (Runtime confirmation via verify.py against the fresh capture below.)

## DEF382 — tutorial_coach_mark replaced with ami_tour_overlay
- (a) `OverlayEntry` removed on EVERY exit path — removal is `widget.onDismiss()`
  (`entry.mounted` guarded, ami_tour_overlay.dart:99-101), reached only via idempotent
  `_close()` (`_closed` flag, :153-158): skip → `_close(false)` (:171); last-step next →
  `_close(true)` (:163-164); vanished/unmounted target → `_focus` walks past dead steps
  and `_close(true)` at end (:204, :177-203). `dispose()` sets `_closed` so no post-frame
  setState after teardown (:148-151). `ami_tour_overlay_test.dart` asserts findsNothing
  on skip, finish, and gone-target paths.
- (b) `MergeSemantics` + `Semantics(identifier: TourIds.skip/next)` wrappers preserved
  around real TextButtons with onPressed (tour_card.dart:72-90, :121-139). Load-bearing
  comments intact.
- (c) No pre-existing assertion weakened, only retyped: `tour_ids_test.dart` and
  `you_tour_journal_test.dart` drop the now-absent `previous()` override and rename
  `TargetFocus`→`AmiTourStep`, `keyTarget`→`target`, `contents!.first.builder!`→`builder`.
  The `same(journalKey)` and step-order assertions are unchanged in strength.
- (d) Every identify/radius/paddingFocus/align/absoluteTop value survived 1:1 across all
  five tour files (floor/journal/lessons/portfolio/you) — verified by extracting and
  diffing old vs new. `ContentAlign.custom` + `CustomTargetContentPosition(top:180)` →
  `absoluteTop:180` maps exactly (`_card` prioritizes absoluteTop, :283-285).
RESULT: holds.

SCOPE NOTE (out of scope, not a finding): DEF382's device-level accessibility-tree
measurement (tree size + nav count per tour × dismissal path on a booted simulator) is
unrun; the architect owns it per the batch brief. Not marked incomplete for it.

## Tests
- Backend full suite (`sh orchestration/dispatch/run_full_suite.sh`, background+polled to
  the terminal line): **5599 passed, 8 skipped, 15 warnings in 1531.17s — SUITE_EXIT=0**.
- Mobile (`cd mobile && flutter test`): **All tests passed — +1446, exit 0** (matches the
  architect's 1446).
- DEF367 independent runtime confirmation: `scripts/wire_contract/verify.py` against the
  fresh `_wire_capture.jsonl` from this suite run →
  **82 surfaces | 50 PASS 0 FAIL 32 UNVERIFIED — WIRE VERDICT: PASS**. 0 FAIL with exactly
  32 unverified (= the ratcheted baseline) proves the 3 removed surfaces now genuinely PASS
  through the HTTP boundary; a false-close would have surfaced as a FAIL over baseline.

## Findings
None. All three defects hold across static review, the full backend suite, the mobile
suite, and an independent wire-contract re-run. No BLOCKER, MAJOR, or MINOR.

VERDICT: COMPLETE (round 1)
