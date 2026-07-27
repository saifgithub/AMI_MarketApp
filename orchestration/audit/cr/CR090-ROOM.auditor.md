<!--
CR090-ROOM.auditor.md — auditor lane file (track U owns). State derives from
round numbers here vs CR090-ROOM.architect.md (see PROTOCOL.md).
-->

# CR090-ROOM — audit lane (auditor)

**Item:** wire CR090-BE's live-data credit surcharge and the 3-state "paid feature withheld"
disclosure into the Room. CR090-BE shipped the contract; nothing consumed it — no user was
charged, no disclosure rendered. This lane closes that shipped-but-dark gap.

**Gate:** independent — D-5, money. This lane decides how many credits a user is actually
debited on every Room run.

**Audited SHA:** `e06ed4b`, tip of `lane/CR090-ROOM.coder.room` (base `main` @ `6d45741`).
**Provenance:** the coder.room worker exceeded its budget cap with the lane entirely
uncommitted — the Architect recovered and committed it, making one production change of their
own. Weighted the usual coder-self-report scepticism onto the Architect's own claims instead,
per their explicit ask. Audited in an isolated worktree `.claude/worktrees/audit-CR090-ROOM/`,
own venv.

## Round 1

### Reproduced independently

| Check | Result |
|---|---|
| Scope | `git diff 6d45741 e06ed4b --stat` — 5 files, **+658/−34**, exact match. |
| Full suite | `.venv/bin/pytest tests/unit/ -q` — **1332 passed**, 5 warnings, exit 0 (168–194s across two runs). Matches the Architect's post-fix claim exactly; confirmed from a clean isolated worktree the pre-fix `1 failed, 1331 passed` regression is genuinely closed, not suppressed. |
| D1 | Grepped `app/` for `spend(` — two textual call sites in `room_runner.py`, on mutually exclusive `if entitled: / else:` branches. Only one executes per run. No other file calls `spend`. |
| Architect's one production change | Read `_profile_for_ticker`'s news/social fallback branches in full and traced the production call chain (`room.py::stream_room` → `start_run()` → `_resolve_and_charge_feeds()` → `_pump()` threads the SAME feed objects into `run(news_feed=, social_feed=, credit_cost=)` → `_profile_for_ticker` renders exactly what was billed). The restored-symmetry fallback (entitled=True) is reachable only by direct/test callers that bypass `start_run` entirely — confirmed by reading the call sites myself, not the comment. The fix is correct: legacy behaviour preserved on a genuinely production-unreachable branch, not a billing bypass. |

### Mutation-tested every gap the Architect explicitly left open, plus one more

1. **D2 — winzip/402 keying** (Architect: "mutate to check"). `spend(user_id, None, ...)` →
   `spend(user_id, 0, ...)` (explicit 0 defeats the `amount is None` key both CR047 winzip and
   CR039 402 branch on) → `test_genuinely_broke_user_still_hits_the_402` failed. Confirms the
   test pins the keying mechanism, not just the surface outcome.
2. **D3 — finer per-test mutation pass** (Architect's own probe was presence-only: deleting the
   whole notice caught 9/12 tests but didn't prove per-test discrimination). Hardcoded the
   notice's `news`/`social` fields to always report `"live"` regardless of actual state → 4
   tests failed on the WRONG VALUE — a content-correctness check, distinct from the
   presence-only mutation. Confirms individual tests check what the notice says, not just that
   one fired.
3. **D4 — the money bug itself** (Architect explicitly did not mutate this — "please do").
   Dropped `news_feed=`/`social_feed=` threading from `_pump()`'s call into `run()` → the
   WITHHELD_PAID test case failed with `'live' == 'withheld_paid'`: a non-entitled user charged
   base-only would have the disclosure falsely claim their feed was live. This is the exact
   money bug D4 exists to prevent, and it's genuinely caught.
4. **The refund path** (Architect: "was not mutation-tested"). Dropped
   `credit_cost=charged_total` from the same call → `test_failed_run_refunds_the_full_charge_including_surcharge`
   failed. The refund-on-failure amount genuinely depends on this threading.

All four reverted individually; suite re-confirmed clean before the next probe. Final full
suite re-confirmed **1332/1332 clean**.

### FLAG 2 — independently re-confirmed, not relayed

Read `mobile/lib/services/api/api_client.dart:655` and `mobile/lib/state/room_providers.dart:111`
myself: both `switch` statements match on plain `String` values (no Dart-enum exhaustiveness
requirement) and neither has a `default:` case in the file. An unrecognised `live_data_notice`
kind genuinely falls through silently — no crash, no effect. Matches the Architect's claim
exactly.

Also independently confirmed the "no third channel" claim: `RoomRun` (`app/schemas/room.py:44-68`)
and `RoomRunRow` (`app/db/models.py:383-410`) both carry `credit_cost` but no live-data field —
a reopened past run cannot surface the disclosure retroactively either.

**This affirms the Architect's promotion-coupling ruling on my own independent verification,
not their say-so: the disclosure has no delivery channel to a real user today. Not a defect in
this lane's code** — D3 is implemented exactly as specified, structurally, model out of the
loop — **but a promotion-sequencing constraint I'm recording alongside my verdict:
CR090-ROOM must not reach Alpha ahead of CR090-MOBILE.**

### FLAG 1 — product call, recorded not resolved

Confirmed the mechanics: under D2's credits-only meter, free-tier traffic still reaches Adanos
(priced, not blocked), and `convene()` probes both feeds before pricing, so a can't-afford turn
still costs one probe. The 24h cache bounds this to ~1 call/ticker/day (from CR024's design,
not independently re-measured against a live Adanos quota by either of us). Agree this is a
reasonable, disclosed tradeoff — suppressing the probe would break the
WITHHELD_PAID/UNAVAILABLE distinction the CR exists for. Recording for Saiful's call per the
Architect's own request, not treating as a code defect.

### Findings

None against the delivered code — zero BLOCKER/MAJOR/MINOR. One promotion-sequencing
constraint affirmed (CR090-ROOM must not ship ahead of CR090-MOBILE) and one product-policy
flag recorded for Saiful (Adanos quota criterion reinterpretation, FLAG 1).

### Verdict

**VERDICT: COMPLETE (round 1)** — scope and full suite reproduced exactly, every gap the
Architect explicitly left open (D2 keying, D3 content-discrimination, D4 the money bug itself,
the refund path) closed via independent mutation testing on production code, the Architect's
own production change traced and confirmed sound, and the promotion-blocking claim (disclosure
has no delivery channel) independently re-verified rather than relayed.

Run report: [`../runs/2026-07-27_run-60/run_report.md`](../runs/2026-07-27_run-60/run_report.md)
