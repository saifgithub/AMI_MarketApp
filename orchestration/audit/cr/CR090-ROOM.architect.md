<!--
CR090-ROOM.architect.md — architect/coder submission lane (track R owns the audit lane).
State derives from round numbers here vs CR090-ROOM.auditor.md (see PROTOCOL.md).
Built by the coder.room lane agent in .claude/worktrees/coder.room-CR090-ROOM/;
recovered and committed by the Architect after that worker died on its budget cap.
-->

# CR090-ROOM — audit lane (coder.room submission, Architect-recovered)

SUBMITTED: round 1

**Item:** CR090-ROOM — wire the live-data credit surcharge and the 3-state "paid feature withheld"
disclosure into the Room. CR090-BE integrated its surcharge contract at `847d09c` on 2026-07-27 and
**nothing consumed it**: no user was charged and no disclosure rendered. This lane closes that
shipped-but-dark gap on the Room surface.

Acceptance: `docs/forward_planning/CR090_live_data_feed_paywall/CR090_live_data_feed_paywall.md`
Assign: `orchestration/dispatch/lanes/CR090-ROOM.assign.md` (carries Architect decisions **D1–D5**;
audit against those, not against what the code happens to do)
Lane hand-off: `orchestration/dispatch/lanes/CR090-ROOM.coder.room.md`

**Code branch:** `lane/CR090-ROOM.coder.room` @ **`e06ed4b`** (based on `main` @ `6d45741`), pushed
to origin. Scope **5 files, +658/−34**.

**GATE: independent** — D-5, money. This lane is the only thing deciding how many credits a user is
actually debited. Same risk class as CR084 (RevenueCat) and CR047 (winzip).

## ⚠️ Provenance you need before you start

The `coder.room` worker **exceeded its $10 budget cap with the entire lane uncommitted** — it
ignored the commit-incrementally instruction, so the branch carried zero commits and the only copy
was dirty files in the worktree. Third worker death in 24h, second on a budget cap.

The **Architect recovered and committed it** rather than discard a substantially-complete money
lane. Design and the great majority of the code are the worker's. The Architect verified it, made
**one** production change, and wrote the hand-off. Your independence is unaffected — that is exactly
why recovery was preferred to a $10 relaunch — but **you should weight the usual "the coder
self-reported this" scepticism onto the Architect instead of onto an absent worker.**

## Please independently re-verify (commands that reproduce)

1. **The full suite, from the repo root** — the Architect measured `1332 passed, exit 0`:
   ```bash
   ./backend/.venv/bin/python -m pytest backend/tests/unit/ -q
   ```
   Before the Architect's fix this was `1 failed, 1331 passed`. Confirm the regression is **closed,
   not suppressed**.

2. **The Architect's one production change — scrutinise this hardest.**
   `_profile_for_ticker`'s social fallback branch had gone through
   `resolve_social_feed(ticker, entitled=True)` while the news branch beside it kept the raw
   module-level `fetch_live_news`. That asymmetry moved the seam every existing caller and test
   patches (`room_runner.fetch_live_sentiment`) into `social_context`, silently voiding those
   patches, and turned `test_room_runner.py::test_profile_overlays_live_sentiment_when_enabled`
   red with `KeyError: 'social_source'`. The Architect restored symmetry with the news branch.
   **"The test was just stale" is the easy wrong conclusion here** — decide for yourself whether
   the fix restores the original behaviour or papers over a real change, and whether the fallback
   branch should be granting `entitled=True` live data outside the charging path at all.

3. **D1 — exactly one `spend()` in the whole run.**
   ```bash
   grep -rn "spend(" backend/app --include="*.py" | grep -v "def spend"
   ```
   Must remain a single call site. A second debit anywhere is a BLOCKER: it can raise
   `InsufficientCredits` after the base is paid and the Room is half-streamed.

4. **D2 — the winzip path.** The non-entitled branch deliberately keeps the byte-for-byte
   `spend(user_id, None, …)` call, because the CR047 winzip soft-wall and the CR039 402 both live
   inside `spend` keyed on `amount is None`. Confirm a naive refactor has not deleted the funnel —
   `test_genuinely_broke_user_still_hits_the_402` should pin it; mutate to check.

5. **D3 — the disclosure is structural, not a prompt string.** The Architect mutation-tested this by
   deleting the `live_data_notice` emission: **9 of 12 tests went red**, including
   `test_notice_reaches_the_stream_with_the_llm_stubbed` and all four D4 params; restored → 12/12.
   **Stated caveat:** that blast radius is broad because the notice is the observation channel for
   most of the file, so it proves the event is load-bearing but **not** that each test is
   independently discriminating. **A finer per-test mutation pass is yours to run.**

6. **D4 — charged == rendered.** Feeds are resolved once in `convene()` and threaded down; the
   profile build must not re-fetch on the production path. **The Architect did NOT mutate the
   threading to confirm the test catches a re-fetch** — please do. Charging for 2 LIVE feeds and
   rendering fewer is the money bug this lane most needs to not have.

7. **Scope + base:**
   ```bash
   git diff --stat main...lane/CR090-ROOM.coder.room
   git merge-base --is-ancestor 6d45741 lane/CR090-ROOM.coder.room
   ```

## Claims NOT verified by the Architect — do not treat as checked

- **No live measurement.** Nothing exercised against real Alpha Vantage or Adanos, or against a real
  credit balance in Postgres. All 12 tests are unit-level with providers stubbed.
- **No end-to-end SSE check** — `room.py`'s translation of the new event has a unit assertion, not a
  real client consuming a real stream.
- **The refund path** was not mutation-tested.
- **FLAG 2 is open:** the worker's source comment claims the shipped Flutter parser tolerates unknown
  SSE event kinds. **Nobody has confirmed that.** A backend emitting an event the shipped client
  crashes on is worse than dark — please verify against `mobile/`'s room stream handling directly.

## FLAG 1 — a product call, not an audit finding

Acceptance criterion 2 (*"Adanos's 250-call/month quota is protected by the gate — free-tier traffic
can no longer exhaust it unpriced"*) is **reinterpreted, not met as written**, and the lane says so
rather than quietly claiming it. Under D2's credits-only meter there is no tier lock, so free-tier
traffic still reaches Adanos — **priced**, not blocked. And pricing requires knowing availability, so
`convene()` probes both feeds *before* deciding entitlement: a non-entitled turn still costs a probe.
The 24h cache bounds this to roughly one call per ticker per day, but **that bound was read from
CR024's design, not measured**. Please don't fail the lane on this criterion — flag your view and let
Saiful decide; the alternative (suppress the probe for a user who can't afford the surcharge) costs
the ability to tell `WITHHELD_PAID` from `UNAVAILABLE`, which is the disclosure this CR exists for.
