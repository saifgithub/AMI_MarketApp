<!-- auditor lane — track U (Kimi). CR052 / orchestration/audit/PROTOCOL.md. -->
# R65-BATCH1 — auditor

VERDICT: COMPLETE (round 2)

Round 2 audited `b1c3b17f` (4 source/test files + 2 register rows over
`af0aeb77`; the five cleared items confirmed untouched). Round 1 audited
`af0aeb77` — see below. Both rounds from scratch worktree
`.claude/worktrees/audit-R65-BATCH1`, detached at the submitted SHA.

---

## Round 2 — both MAJORs closed; one deferral recorded, signed scope

**M2 closed, proven in both directions.** `one_on_one.py` now carries
`except BaseException: release; raise` alongside the 402 handler. The
`BaseException`-over-`Exception` choice is correct, not pedantic:
`asyncio.CancelledError` descends from `BaseException`, and a client
hanging up mid-`spend()` leaks by the identical mechanism — `except
Exception` would have closed half the hole. Re-`raise` unconditional,
nothing swallowed; no double-release on the 402 path (a raise inside a
sibling except isn't re-caught; and `release()` is a tested safe no-op
on over-release anyway). The new test asserts through the CONTRACT
(next request at cap=1 is 200, not 429), not the private counter — the
right pin. My own mutation (removed only the release line, kept the
except) → exactly **1 RED** (that test), reverted byte-identical,
targeted 21/21 re-green. **`brief.py` twin guarded too — scope
judgment:** upheld, not creep. The counter is shared across both
surfaces, the leak class identical, the cost four disclosed lines;
fixing the reported instance while knowingly leaving its twin is how a
class becomes a recurrence — his words, and he's right.

**M1 closed to the extent this repo can close it; the live residue is
the deferral branch my round-2 scope offered.** 8 new tests: five drive
the gate's logic off fixture OpenAPI docs (including fail-closed on a
spec with no `Mandate` schema and fail-closed on an unreachable host —
the two silent-failure shapes), one proves the client-key scrape isn't
vacuous, and one is a REAL caller running on every suite run
(`get_openapi(app)` on this checkout, asserting every scraped client
PATCH key exists) — which puts the gate's logic in CI, since the beta
workflow runs the suite. What does NOT exist: the release-time call
against the DEPLOYED backend (`--base-url` in the three build scripts,
still dirty under CR084-ALPHA — editing them would sweep another
track's uncommitted work into the commit, correctly refused). That is
the "documented deferral Saiful signs" branch of my round-2 scope,
surfaced to him by the architect; I record it here as the third party
to the handshake. **One nit:** the deferral should also land on the
DEF195 register row (the architect did exactly this for the janitor on
the DEF201 row) so the residue survives the lane files' attention
span.

**Known gap, his disclosure, recorded:** if Starlette abandons the
returned `StreamingResponse` without ever iterating the generator, its
`finally` never runs and the slot leaks. Unproven either way; the
structural fix (acquire inside the generator) would weaken the cap, so
it stays open with eyes open.

**MINOR m1 (janitor):** accepted-not-fixed, recorded on the DEF201 row,
wires at the promotion that brings the mount live. Grading stands.

**Re-measured, detached at `b1c3b17f`:** backend **1869/0** (264.33s —
matches the bridge's +9-new claim exactly); registers DEF 205 / CR 130
OK; targeted (DEF195 + DEF201 files) 21/21. Mobile untouched this round
— round-1 mobile results stand.

---

## Round 1 (superseded verdict: AWAITING_FIXES)

Five of seven items are clean. Two MAJORs, both in items the bridge
itself flagged as weakest — one pre-judged by the architect and upheld,
one found by the hunt he explicitly asked for.

---

## MAJOR M1 — DEF195: a release gate with no tests and no caller is a shipped no-op

Independently confirmed both halves, not taken on the bridge's word:

- `grep -rn check_release_schema_parity scripts/ backend/ .github/
  .claude/` → only the file itself. Nothing invokes the gate.
- `ls backend/tests/unit/ | grep -i "def195\|schema_parity"` → nothing.
  A 191-line mechanical gate with zero automated coverage; its only
  evidence is a hand-run against the `+61` near-miss.

The script itself is real (`--help` runs, the parity logic reads
sane) — that is not the finding. The finding is the CLASS: a gate that
never runs is DEF063/DEF038 "dark for months", the exact failure shape
CLAUDE.md names. The blocking reason (build scripts mid-edit under
CR084-ALPHA) is real but temporary; the effect ships now. Fix: wire it
into a build script or CI the moment CR084-ALPHA's edits land, and give
it at least a smoke test (a fixture OpenAPI doc + a known-mismatched
client key set, asserting nonzero exit). The architect pre-judged this
MAJOR against his own item; I independently agree.

## MAJOR M2 — DEF201: the fourth release path exists — a non-402 `spend()` failure leaks the slot permanently

The bridge asked for exactly this hunt ("look for a fourth path I
missed — an exception between `acquire()` and the `try`"). Found, by
reading, not hypothesized:

`backend/app/api/one_on_one.py:send_message` — `acquire()` runs, then
`spend()` runs inside `try/except InsufficientCredits` (the 402 path,
which releases correctly — my mutation proved that pin). But `spend()`
(`credit_service.py:234`) opens `get_session()`, does `s.get(User,
...)`, and commits — any DB failure (`OperationalError` & friends) is
NOT an `InsufficientCredits`, escapes the except, the `event_stream()`
generator (whose `finally` releases) never runs, and the acquired slot
leaks. The counter dict has no TTL, no eviction, no recovery — the leak
lasts until process restart.

Blast radius at alpha: cap is 2/user. Two DB-error-window spends
permanently wedge a user's 1-on-1 into 429
`concurrency_limit_exceeded` — a state that survives the DB recovering
and has no log line tying the 429 to the earlier failure. Fix is 2–3
lines: a broad `except Exception: release; raise` alongside the 402
handler (or equivalent teardown around the acquire→spend region), plus
a test that raises a non-402 error from `spend()` and asserts the slot
is free.

## The clean five

- **DEF160** (mobile restart signal): `isRestart` threaded constructor →
  `copyWith` → `confirmReadback` — the copyWith-omission trap he
  mutation-tested is genuinely handled. **The loosened DEF152 guard,
  judged:** `\.reset\(\)` → `\.reset\(` still proves exactly one call
  site, and the second assertion still proves the confirm precedes it.
  The singleton-door invariant survives the widening; upheld.
- **DEF200** (sync-I/O census): re-ran `def200_sync_io_census.py`
  myself → **75/93**, reproducing the bridge's number exactly.
  Judgments upheld: not flagging `Depends(get_current_user)` is correct
  (FastAPI threadpools plain `def` dependencies); one-hop-only scope is
  disclosed, so the 18 unflagged are honestly not certified. Census,
  not fix — defect stays open by design.
- **DEF117** (4 graded-content number fixes): **all arithmetic redone
  independently**, not read-and-trusted. (1) NVDA candle: body 0.30,
  upper wick 1.50 = exactly 5.0x, lower wick 0.15, close < open — red,
  5x, tiny, all true; shooting-star key intact. (2) Pullback: 6.60 /
  412.40 = 1.60% stop distance now matches the quoted 1.6% cap; R:R
  19.60/6.60 = 2.97 ≈ 1:3.0 consistent. (3) TNB: OCF 3.2 − capex 12 =
  −8.8B, "sharply negative" is honest; yield 0.50/14.80 = 3.38% ≈ 3.4%
  and payout 0.50/0.71 = 70.4% ≈ 70% re-verified while at it. (4) TSLA:
  18 × 266.50 = 4,797 = 5.996% — under the 4,800 cap by $3, the single
  intended violation is now the only violation. Keys/ids/schema
  untouched per the diff.
- **CR105** (prompt copy drift): the new guard builds the REAL
  assembled PM prompt via `build_agent_prompt` and asserts exactly 2
  single-name-cap mentions, both equal to the resolved value — with the
  anti-self-defeat `resolved != 50` check so the test can't pass
  vacuously. `trader.md` and `test_room_prompt_parity.py` confirmed
  untouched (absent from the diff). Acceptance #7 (post-promotion
  re-measure of the PM action distribution) is unmeetable from the Mac
  by the CR's own terms — treated as green-suite-only; the re-measure
  is OWED at next promotion. Recorded, not a finding.
- **CR127** (PM card / vote caption): **re-ran the byte-identical
  check myself** — `git diff 972c0a0a^ d17676de` on
  `mobile/lib/widgets/room/room_board.dart` shows exactly one added
  line in the hero region, a doc comment; all four `roomHero*` strings
  across en/ar/ms are unchanged vs pre-CR127. The revert is genuine.
  NEEDS-DEVICE-CHECK for the visual, and the AR/MS strings are
  architect-composed (disclosed, flagged for translator) — both
  recorded as the item's stated limits, not findings.

## Upheld judgment calls (invited, no finding)

- DEF201 import-time settings capture: acceptable — the var is
  forwarded in `docker-compose.yml:229` and compose restarts on
  promote; a tuning knob needing a restart is fine when every tune
  rides a restart anyway.
- DEF201 suffix filter: `_ATTACHMENT_SUFFIXES` is derived from
  `_ALLOWED_MIMES.values()` — coverage is structural, cannot drift.
- DEF201 no-lock counters: `RLock` IS held across both acquire and
  release mutations — the bridge's "plain dict mutations with no lock"
  worry undersells its own code; the async-suspension analysis stands
  (no await inside the critical sections).

## Reproduced measurements (all detached at `af0aeb77`)

| Check | Bridge | Auditor | Result |
|---|---|---|---|
| backend full suite | 1860/0, 270.55s | **1860/0, 278.60s** | match |
| flutter suite | 402 passed | **402 passed** | match |
| flutter analyze | exit 0, 5 infos | exit 0, 5 infos | match |
| registers verify | DEF 205 / CR 130 | DEF 205 / CR 130 OK | match |
| DEF200 census | 75/93 | 75/93 | reproduced |

Blind mutation (mine): removed the 402 explicit release in
`one_on_one.py` → exactly **1 RED**
(`test_402_insufficient_credits_releases_the_slot_rather_than_leaking_it`),
11 others correctly green. Reverted byte-identical, 12/12 re-green.

## MINORs

- **m1 — DEF201's janitor is the second shipped no-op** (built + 6
  tests, nothing invokes it; the `./backend/scripts:/app/scripts:ro`
  mount is committed at `docker-compose.yml:258` — verified — but not
  live until next promotion). Lesser than M1 because the volume cap IS
  live in the write path and bounds the disk meanwhile; wire it at the
  same promotion that brings the mount live. Not a MAJOR on its own;
  flagged because with M1 it makes TWO unwired deliverables in one
  batch — the class is forming a habit.

## Round 2 scope

M1 (wire + smoke-test the parity gate, or a documented deferral Saiful
signs) and M2 (the broad-except release + its test). Everything else
stands as audited. DoD enforcement waived per standing instruction.
