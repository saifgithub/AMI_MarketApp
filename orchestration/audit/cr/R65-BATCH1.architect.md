<!--
R65-BATCH1.architect.md — architect submission lane. State derives from round numbers here vs
R65-BATCH1.auditor.md.
GATE: none was used while building — this is the batch catch-up submission Saiful asked for
("send all the fast tracked development to the auditor as one batch"). Every item below was
built and self-verified directly by the Architect with NO independent review at build time.
That is the whole reason this lane exists: seven items are asking for their first outside look
at once, and none of them has had one.
-->

# R65-BATCH1 — audit lane (7 fast-tracked items, one lane)

> Round 1 submitted at `af0aeb77`; the live round line is at the foot of this file.

**SHA:** `af0aeb777ef3020553370c94747f3c1faf3b45ce` (`main`, pushed to origin)
**SCOPE:** chunk — seven independent items, not one CR's definition-of-done. Judge each on its own.
**depends-on:** none

**Item:** the AT:R65 work built directly by the Architect since the last dispatch accept
(`99169da8`), i.e. everything fast-tracked past the CR052 dispatch/audit gate:
**DEF195, DEF160, DEF201, DEF200, DEF117, CR105, CR127.**

Precedent for the shape: `REL58.architect.md` (20 items, one lane, by stakeholder instruction).

## How to reproduce my evidence — and the trap I deliberately avoided

Every number below was measured in a **detached worktree at the submitted SHA**, not in my
shared checkout:

```
git worktree add --detach .claude/worktrees/<yours> af0aeb77
cd <worktree>/backend && "/Volumes/Extreme Pro/AMI_MarketApp/backend/.venv/bin/python" -m pytest tests/unit/ -q
cd <worktree>/mobile  && /opt/homebrew/bin/flutter test -r compact
```

| Check | Result at `af0aeb77`, detached |
|---|---|
| backend `pytest tests/unit/ -q` | **1860 passed**, 0 failed, 8 warnings, 270.55s |
| mobile `flutter test -r compact` | **402 passed**, All tests passed |
| mobile `flutter analyze --no-fatal-infos` | exit 0, 5 pre-existing infos |
| `gen_registers.py verify` | DEF OK 205 rows · CR OK 130 rows, identical to live |
| `scripts/def200_sync_io_census.py` | reproduces **75/93** (see DEF200 below) |

**This matters, and it is the DEF159 trap that bounced REL58 round 1.** My shared checkout is
dirty with another track's uncommitted CR084-ALPHA work (`backend/app/api/webhooks.py`,
`backend/tests/unit/test_cr084_revenuecat_webhook.py`, 3 build scripts). Run there, the suite
reports **1866 passed / 1 failed** — 7 extra tests from that uncommitted file, one of them red.
Neither number describes the repository. **1860/0 is the SHA's truth**; the failure is not mine
and is not at this SHA at all. I had earlier quoted the 1866/1 figure in conversation before
re-measuring detached — that quote was wrong in exactly the way DEF159 documents.

---

## Verify these hardest — the two weakest items in the batch

### DEF195 — schema-parity gate: **no tests, and no caller**

`scripts/check_release_schema_parity.py` (+191 lines, `c6262ac1`) is a mechanical client-vs-backend
schema parity checker. Two things I want challenged rather than taken on trust:

- **There is no test file for it.** `ls backend/tests/unit/ | grep -i "def195\|schema_parity"` → nothing.
  Its own correctness rests on my having run it by hand against the `+61` near-miss. Independently
  decide whether a 191-line release gate with zero automated coverage is acceptable as-is, or a MAJOR.
- **Nothing calls it.** `grep -rn check_release_schema_parity scripts/ backend/ .github/` returns
  only the file itself. It is a gate that never runs. The reason is real (`scripts/build_*.sh` are
  mid-edit under another track's uncommitted CR084-ALPHA work, so I could not wire it without
  colliding), but the *effect* is a shipped no-op — the DEF063/DEF038 "dark for months" class this
  project has been bitten by twice, which CLAUDE.md calls out by name. I think that is at least a
  MAJOR against this item; I am submitting it rather than quietly holding it because the disclosure
  is the point.

### DEF201 — concurrency cap: stateful singleton, full lifecycle unverified

`ConcurrencyLimiter` (`backend/app/services/rate_limit.py`, `32e4f63c`) is a **module-level
singleton holding per-user counters** — exactly the stateful construct PROTOCOL.md's trust-critical
contract says to audit across its full lifecycle, not just first construction.

- `agent_stream_concurrency_limit` captures `max_concurrent` from `settings` **at import time**.
  I found this the hard way: tests that monkeypatched `settings` had no effect and passed a
  `200 == 429` assertion until I switched them to patch the instance attribute. **A config change
  therefore does not take effect without a process restart.** I judged that acceptable (compose
  restarts on promote) — independently decide if that is right, and whether it should degrade loudly.
- **Release paths are the risk.** `acquire()` happens before `spend()` so a 429 never charges; the
  generator's `finally` releases. But the DEF113 402 branch never runs that `finally`, so it needed
  an *explicit* release — I added one. **Please look for a fourth path I missed** (client disconnect
  mid-stream, an exception between `acquire()` and the `try`, a task cancellation). A leaked slot is
  permanent for that user until restart, and there is no eviction or TTL on the counter dict.
- **Never exercised under real concurrency.** Every test is sequential. There is no test that two
  genuinely concurrent requests see the cap correctly, and the counters are plain dict mutations with
  no lock. FastAPI's event loop makes the acquire/release pair non-atomic only if a suspension point
  falls between them; I believe none does, but I did not prove it.
- **The janitor is unwired.** `backend/scripts/prune_bug_attachments.py` (+114, `9ace7eaa`) is built
  and tested (6 tests) but nothing invokes it — no cron, no compose command. Same shipped-no-op
  shape as DEF195 above. It also *cannot* run host-side on melehost: bare `python3` there has neither
  `pydantic` nor `pydantic_settings` (confirmed live 2026-07-30), so it needs
  `docker exec ami_api_alpha python -m scripts.prune_bug_attachments`, which needs the new
  `./backend/scripts:/app/scripts:ro` mount (`docker-compose.yml:258`) — **committed but NOT live on
  melehost**, since no promotion has run since. Verify that mount claim independently.
- **The volume cap counts real on-disk files.** `_current_total_bytes` filters to attachment
  suffixes. That filter is load-bearing, not cosmetic: without it the tests' sqlite tempfile (same
  `tmp_path`) got counted and the cap tripped at 516096 bytes. Worth confirming the suffix set
  actually covers every extension `_ALLOWED_MIMES` can produce.

---

## The other five — verify at normal depth

- **DEF160** (`5ae267c1`, mobile) — threads `restart: true` from the Floor through
  `OnboardingNotifier` → `ApiClient.confirmReadback` to the backend's DEF160 fix. 5 new tests.
  **The subtle part:** `isRestart` had to be added to `copyWith` as well as the constructor —
  omitting it silently resets the flag to `false` on every later state transition, which I proved
  by mutation. Two collateral repairs in the same commit: `widget_test.dart`'s fake `ApiClient`
  (`invalid_override` once the param existed) and `confirm_restart_onboarding_test.dart`'s DEF152
  guard, whose regex was pinned to the literal `.reset()` and had to widen to `\.reset\(`.
  **Judge that regex widening** — it is a guard I loosened, and a loosened guard is worth a look.
- **DEF200** (`e464ec4a`) — a **census, not a fix**; the defect stays open by design. Re-runnable
  script, 11 tests. First draft found 21/93 handlers (direct `get_session()` in the handler body)
  and I rejected it as answering a narrower question than DEF200 asks. Rebuilt against a 23-module
  sync-I/O registry (19 auto-discovered every run via `grep -rl get_session`, 6 hand-verified) with
  AST import resolution → **75/93**. **Explicitly one-hop only**, not a transitive call graph — the
  18 unflagged handlers are *not* certified clean. One judgement worth checking: I deliberately do
  NOT flag `Depends(get_current_user)`, because FastAPI threadpools a plain `def` dependency; if
  that is wrong the census under-reports.
- **DEF117** (`bcb08a57`, content) — 4 daily-challenge items whose scenario numbers contradicted
  their own explanations (a candle described as red that was green with a ~10.4x wick ratio while
  claiming ~5x; a loss cap that didn't match its own stop distance; an FCF line subtracting capex
  twice; a position claimed under a 6% cap it was 6.03% over). **This is graded quiz content** —
  arithmetic was dual-passed per the CR060 sweep record's own instruction. Answer keys, ids and
  schema untouched. AR/MS flagged in `content/_authoring/cr060_dc_glossary_retranslate.md`.
  **Re-do the arithmetic independently** rather than reading my note — that is the whole risk here.
- **CR105** (`7fc09420`) — the amended 5-item scope only. Deleted 3 unfulfillable prompt
  instructions; replaced a bare `50%` cap literal with deference to the floor + a new guard that
  scans the **assembled** PM prompt (demonstrated red against a synthetic repro of the old shape
  first); doc sweep across `safety_floor.md` / `twelve_agents.md` / `mandate_overlays.md`; RM
  3-part structure scoped to 1-on-1; new analyst-Inputs↔`field_state` alignment guard.
  **`trader.md` deliberately untouched** (DEF095's `_LEVEL_PATTERNS` matches its labels) and
  `test_room_prompt_parity.py` untouched — the CR's own governance says editing either means the
  lane left scope. **Acceptance #7 is NOT met and cannot be from the Mac:** the CR requires a
  post-promotion re-measure of the PM action distribution over ≥50 live convenes, because these
  edits change assembled-prompt bytes. Nothing has been promoted. Treat CR105 as green-suite-only.
- **CR127** (`972c0a0a` then `d17676de`, mobile) — the Room board's `THE PM DECIDES — THIS IS NOT
  A VOTE` caption removed, and the reasoning block retitled as the PM's own card. **Read both
  commits**: the first re-attributed the hero (`THE ROOM APPROVED` → `THE PM APPROVED`) and Saiful
  rejected that; the second reverts it and moves the PM identity onto the reason card instead. I
  verified the revert is byte-identical to pre-CR127 by diffing `_HeroTile` and all four
  `roomHero*` strings across en/ar/ms against `972c0a0a^` — **re-run that diff yourself**, it is
  the one claim in this item that would be embarrassing to have wrong. 4 tests; header hidden when
  `reason.trim().isEmpty` (T-BACKFILL).

## Not verified — stated plainly

- **No live/melehost verification of anything in this batch.** Mac is a pure editor. Nothing here
  has been promoted, so DEF201's caps, CR105's prompt bytes and DEF195's gate have never executed
  on the deploy target. `NEEDS-DEVICE-CHECK` for DEF160 + CR127 (both mobile-only, not on any
  tester's phone until the next store build).
- **AR/MS strings in CR127 are mine, not a translator's.** Composed from renderings already
  attested elsewhere in the same ARB rather than invented, and flagged in
  `content/_authoring/cr127_room_hero_retranslate.md` — but no native speaker has read them.
- **DEF201 janitor + DEF195 gate are both unwired**, disclosed above. Neither is a discovery I am
  asking you to make; both are judgement calls I want a second opinion on.
- **Two items are deliberately partial**: DEF200 (census only, defect stays open) and DEF201
  (2 of 3 parts; credit-metering split to DEF205 as a Saiful pricing decision).
- **DEF204** was investigation-only (a live support-email pipeline found running on melehost with
  a hardcoded credential; nothing touched, filed for Saiful's ruling). No code, so it is not in
  this lane — flagging it because it is AT:R65 work an auditor might expect to see here.
- **The docs-only commits in this range are not submitted** (register flips CR053/CR058/CR059,
  the DEF204/DEF205 filings, other tracks' CR109/CR134/CR027 work). Governance-exempt per
  CLAUDE.md. The CR053/058/059 flips were status corrections for work shipped weeks ago — I
  verified each against git history and live code before flipping, and that verification is
  itself unaudited.

---

## Round 2 — `b1c3b17f`

SUBMITTED: round 2

Both MAJORs closed. Diff vs the round-1 SHA is 4 source/test files + 2 register
rows — the five items you cleared are untouched (`git diff af0aeb77..b1c3b17f`).

### M2 — fixed. You were right, and the trigger is real

`one_on_one.py:send_message` now carries, alongside the 402 handler:

```python
except BaseException:
    agent_stream_concurrency_limit.release(concurrency_key)
    raise
```

**`BaseException`, not `Exception`** — deliberate, and worth your judgement. A
`CancelledError` (client hangs up while `spend()` is mid-commit) leaks the slot
by exactly the same mechanism, and asyncio's `CancelledError` descends from
`BaseException`, so `except Exception` would have left the cancellation half of
this hole open. The re-`raise` is unconditional, so nothing is swallowed.

**Test:** `test_a_non_402_spend_failure_releases_the_slot_rather_than_leaking_it`
— patches `spend()` to raise a `RuntimeError`, asserts the 500, then asserts the
**next** request at `cap=1` is not 429. Asserted through the **contract**, not
`_counts`: the private counter is an implementation detail, and the thing that
actually harms a user is the permanent 429.

**Mutation:** removed the `release` line, kept the `except` → exactly **1 RED**
(that test), 12 others green. Restored byte-identical, 13/13 re-green.

**Also fixed in `brief.py`, which you did NOT scope into M2.** Brief has no
`spend()`, so its acquire→generator window is only `StreamingResponse`
construction — much narrower, and I could not construct a trigger for it. I
guarded it anyway because the leak class is identical and it wedges the *same
shared counter*; fixing the reported instance while knowingly leaving its twin
is how a class becomes a recurrence. **Judge whether that was scope creep** — I
would rather be told off for the extra four lines than explain the twin later.

**One thing I could not close, stated rather than left for you to find:** if
Starlette abandons the returned `StreamingResponse` without ever iterating the
generator, that generator's `finally` never runs and the slot leaks. I could not
produce that state in a test and I do not know whether Starlette can reach it.
Structurally it would be closed by acquiring *inside* the generator, but that
weakens the cap (a burst would all pass the check before any slot is claimed),
so I did not. Flagging it as a known gap rather than claiming the path is proven
safe.

### M1 — two of three parts closed; the third is a decision, not a task

**Done:** `backend/tests/unit/test_def195_release_schema_parity.py`, 8 tests.

- Five drive the gate's **logic** off fixture OpenAPI docs: passes on parity;
  fails on a dropped top-level key; fails on a dropped nested compliance key;
  fails **closed** on a spec with no `Mandate` schema; fails **closed** on an
  unreachable host. Mutation: blinded `missing_top` to `[]` → exactly 1 RED
  (the dropped-key test). Restored, re-green.
- One is a **real caller that runs on every suite run** —
  `test_client_patch_keys_all_exist_in_this_checkouts_schema` builds this
  checkout's own OpenAPI via `get_openapi(app)` and asserts every scraped client
  PATCH key exists in it. That also puts the gate's logic in CI, since
  `.github/workflows/deploy-beta.yml` runs `pytest tests/unit/ -q`.

**NOT done, and explicitly not claimed: the release-time call against the
DEPLOYED backend.** The new test is not a substitute and its own docstring says
so — it compares the client to the schema *in this repo*, and DEF195 exists
precisely because a client can be in parity with `main` and still ahead of what
is **promoted**. That is the `0.1.0+61` near-miss. Only
`--base-url <live host>` inside `build_testflight.sh` / `build_playstore.sh` /
`publish_playstore.sh` closes it, and all three are **still dirty** under another
track's uncommitted CR084-ALPHA edits (re-verified at round 2). Editing them
would sweep that work into my commit, which this repo's governance forbids.

Per your own round-2 scope this is the "or a documented deferral Saiful signs"
branch. **It is his call and I have not made it** — surfaced to him alongside
this resubmission. If you would rather hold the whole lane AWAITING_FIXES until
the wiring exists, say so and I will not argue.

### MINOR m1 — accepted, not fixed, same blocker

The janitor stays uninvoked. Your grading is right that the live volume cap
bounds the disk meanwhile. It wires at the same promotion that brings the
`./backend/scripts:/app/scripts:ro` mount live — recorded on the DEF201 row so
it is not lost. **Your "two unwired deliverables in one batch — the class is
forming a habit" is the more useful finding than either item**, and I have not
tried to argue it away.

### Corrections to my own round-1 submission

- **"plain dict mutations with no lock" was wrong.** You checked and an `RLock`
  is held across both acquire and release. I undersold my own code and you had
  to spend time disproving a worry I invented.
- The three upheld judgment calls (import-time capture, suffix filter, locking)
  are accepted as you graded them; no argument.

### Re-measured, detached at `b1c3b17f`

| Check | Round 1 | Round 2 |
|---|---|---|
| backend `pytest tests/unit/ -q` | 1860 passed / 0 | **1869 passed / 0** (+9 new) |
| `gen_registers.py verify` | DEF 205 / CR 130 | DEF 205 / CR 130 OK |
| mobile | 402 passed | untouched this round |

Mobile, `flutter analyze` and the DEF200 census are unchanged from round 1 —
this round's diff is backend-only.
