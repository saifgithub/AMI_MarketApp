# BATCH-R75 — auditor.core verdict (round 2)

ROLE: auditor.core · BATCH: R75 · ROUND: 2 · SHA audited: 383e60f1
Diff: `git diff 7c07dc5b..383e60f1`

VERDICT: COMPLETE (round 2)

Scope of round 2: the two fixes that round 1 missed —
DEF394 (`backend/app/services/llm_gateway.py`) and
DEF395 (`mobile/lib/features/tour/ami_tour_overlay.dart`). DEF392, DEF367 and the
`tour_card.dart` semantics wrappers were cleared by both auditors in round 1 and the
round-2 diff does not touch them beyond the two named fixes.

## Findings

None at BLOCKER or MAJOR. One MINOR informational note (non-blocking), below.

1. [MINOR / informational] `mobile/lib/features/tour/ami_tour_overlay.dart:261`
   > `      _scheduleRectRefresh();`
   The unconditional re-arm starts a fresh post-frame chain from `_focus` (line 210)
   on every step transition without the previous step's chain terminating, so during
   an active tour the number of concurrently-armed `addPostFrameCallback` chains grows
   by one per `next()` — bounded by the step count (~5), each doing one read-only
   `_rectFor` per produced frame. This is benign: `setState` is conditional so the
   chains go dormant when idle (proven by `pumpAndSettle()` settling in the
   mid-display-vanish test rather than timing out), and every chain checks `_closed`
   at line 233 so all are reaped at `dispose`/`_close`. No leak past tour close, no
   busy loop, no user-visible defect. Recorded for awareness, not for action.

## Fix verification (what round 1 missed)

### DEF394 — Anthropic sibling kept the 60s literal inside the 180s guard — FIXED
- `AnthropicProvider.__init__` now takes `timeout_seconds: float | None = None` and
  resolves `timeout=_default_transport_timeout_s()` when the caller names none
  (`llm_gateway.py:410-414`). Registration at `:955` passes no override, so it derives:
  `settings.room_agent_timeout_s (180) + _TRANSPORT_TIMEOUT_MARGIN_S (180) = 360s`,
  strictly outside the 180s guard.
- Class-agnostic pin `test_every_provider_with_a_client_sits_outside_the_guard`
  (`test_def392_transport_ordering.py`) enumerates `gateway._providers` by the runtime
  `_client` attribute — it names NO class. It cannot pass vacuously: it asserts
  `"anthropic" in withclient` first (the DEF200 vacuity shape), then asserts
  `prov._client.timeout.read > settings.room_agent_timeout_s` for every provider that
  carries a client (vllm, anthropic, kimi, deepseek, qwen, gemini). Reverting the fix
  makes anthropic's `.read` 60 ≤ 180 → the assert fails, so the pin bites.
- `test_the_anthropic_provider_has_no_hardcoded_transport_literal` bans the literal
  shape in that constructor specifically.
- No THIRD transport budget written as a literal in `llm_gateway.py`. The only remaining
  numeric `timeout=` is `:856` `self._client.get("/metrics", timeout=5.0)` — a
  best-effort CR077 startup prefix-cache probe on `/metrics`, explicitly "instrumentation,
  not a request-path dependency". It is not a completion transport and correctly stays a
  short literal.
- The DEF392 boot validator still checks only `vllm_request_timeout_s`; that is
  sufficient because anthropic's timeout is no longer configurable-to-invert (it always
  derives from the guard), so no config can invert it and there is nothing for the
  validator to catch.

### DEF395 — overlay stopped watching once its target settled — FIXED
- Mid-display vanish is now observed: `_scheduleRectRefresh` re-arms while the tour is
  open (`:261`), and when the rect stays null past the settle window it hands back to
  `_focus(_index + 1)` (`:238-246`), which steps over the dead target and closes if none
  remain. Covered by `DEF395 a target that vanishes MID-DISPLAY closes the tour`.
- No unbounded frame loop: `setState` is conditional (`:248`), so a settled/idle tour
  requests no further frames and the chain goes dormant; `addPostFrameCallback` does not
  itself schedule a frame. The mid-display-vanish test uses `pumpAndSettle()` and
  completes — a busy loop would time it out.
- No setState-after-dispose: every callback body returns at `:233` on `!mounted || _closed`
  before any `setState`, and `_focus` re-checks `:203` after its `await`. `_closed` is set
  in both `dispose()` (`:159`) and `_close()` (`:165`).
- `_shownAny` correct: set true only when a live target is actually focused (`:208`);
  `skip()` closes with `finished:false` unconditionally (`:181`); a tour with only the
  LAST step mounted shows it (`_shownAny=true`) then finishes true on the "Got it" tap; a
  tour with every target unmounted closes `finished:_shownAny=false` — no toast, entry
  still torn down. Covered by `DEF395 onFinish does NOT fire for a tour nobody saw`.
- `_focus` iterates a `while` loop over consecutive dead targets (`:187-214`); it does not
  recurse, so several consecutive dead targets cannot blow the stack.
- Orientation is out of scope and correctly documented: `main.dart:69` locks the alpha to
  `DeviceOrientation.portraitUp`; the code comment (`:225-230`) records the future
  `didChangeMetrics` re-arm needed if that lock is ever lifted.

## FOREIGN DISPOSITION (CR215 gap-fill 9)

No round-2 foreign audit exists. Branch `foreign/BATCH-R75.r2` carries only the two fix
commits (DEF394 b88c6a5c, DEF395 383e60f1) — no
`orchestration/audit/foreign/BATCH-R75.r2.foreign.md` at any path in that tree. So I
disposition round 1 only. Round 1 (kimi-code/k3, `f8be15e2...`, FOREIGN-VERDICT
ADVISORY-CONCERNS) raised three findings; all three are now fixed and I re-verified each
against the round-2 code:

1. [blocking] DEF392/anthropic — 60s transport inside the 180s guard on the first fallback
   → REAL, correlated-error catch the same-family gate missed. FIXED as DEF394; verified
   above (derived timeout + class-agnostic non-vacuous pin). Disposition: **real**.
2. [question] DEF382 — mid-display target vanish leaves a full-screen dim; removal-on-vanish
   only ran at step transitions → REAL. FIXED as DEF395; the mid-display-vanish path now
   hands to `_focus`. Verified above. Disposition: **real**.
3. [question] DEF382 — all-targets-vanished path fired `onFinish` for a tour never seen
   → REAL. FIXED as DEF395 via `_shownAny` (`_close(finished:_shownAny)`). Verified above.
   Disposition: **real**.

Round-1 tally: 3 findings, **3 real, 0 false-divergence, 0 noise**. The foreign tier again
earned its keep — three real defects behind a Claude COMPLETE-with-zero-findings.

## Tests

- Backend full suite (`sh orchestration/dispatch/run_full_suite.sh`): **5601 passed, 8 skipped,
  15 warnings in 1214s; SUITE_EXIT=0** (observed — matches the architect's count).
- Mobile (`cd mobile && flutter test`): **1448 passed, exit code 0** (observed).
