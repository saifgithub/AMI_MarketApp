# ISS001 — opus5.0

**Proposal: detect the pattern at RUNTIME, keep the source scanner for the handler, and make the
two disagree loudly.** Working prototype included and measured against the full 4,223-test suite.

---

## 1. What I propose

### The core claim

The source scanner has failed twice for one reason: **it has to infer which model
`session.add(row)` refers to.** That inference is the whole bug — v1 matched function names, v2
matched one construction syntax and missed 12 of 20 sites. Every fix widened it to cover whichever
instance a human had just spotted.

At runtime there is nothing to infer. `session.new` holds the **real objects**; `Base.registry` holds
the **real constraints**. A factory, a helper, a comprehension, a bulk API, a syntax nobody has
invented yet — all identical.

### The rule, stated precisely

Not *"this model can collide"* — that was my first attempt and it was useless (§3.1). The rule is the
pattern's own definition:

> **this session SELECTed model X, and is now INSERTing model X, with nothing in scope to catch a
> constraint violation.**

An append-only insert never read the model first, so it is silent **by construction**, not by
allowlist. That distinction is what makes the control tolerable to live with.

### Mechanism — three SQLAlchemy listeners, one file, zero app changes

| Event | Purpose |
|---|---|
| `do_orm_execute` | record which models this session has SELECTed |
| `transient_to_pending` | capture the frame that called `add()` — **while it still exists** |
| `before_flush` | if model was read AND is now inserted AND no savepoint → flag |

`transient_to_pending` matters more than it looks. `before_flush` fires at **commit**, by which time
the calling frame has returned: v1 attributed 15 sites to `app/db/session.py:82 in get_session`, the
context manager's own `__exit__`. That is a detector naming the wrong code, which is worse than
naming none.

**Prototype:** [`prototype/insert_race_observer.py`](prototype/insert_race_observer.py). Runs as a
pytest plugin, modifies no application code and no existing test:

```bash
cd backend
PYTHONPATH=../docs/dilemmas/ISS001_DB_INSERT_RACE/opus5.0/prototype \
  .venv/bin/python -m pytest tests/unit/ -q -p insert_race_observer
```

`ISS001_MODE=observe` (default) records; `ISS001_MODE=enforce` raises.

### It detects — it does not prevent

Stated plainly because §4 of the brief asks. This finds instances and can fail a build. It does not
make the pattern impossible to write. I considered a mandatory chokepoint helper and rejected it:
enforcing "all inserts go through `insert_or(...)`" requires knowing which `session.add()` calls are
exempt, which is the same type-inference problem, back again.

---

## 2. Measured results — full suite, 4,223 tests

| | v1 (naive rule) | v3 (final) |
|---|---|---|
| Collidable models (from live metadata) | 32 | 32 |
| Distinct insert sites executed | 70 | 65 |
| Correctly silent (append-only) | 8 | 17 |
| **Flagged** | **62** | **40** |
| Test failures caused by the observer | 0 | 0 |
| Added runtime | — | ~0 (504s vs 496s baseline; noise) |

**Of the 40 flagged in v3:**

| Group | Count | Verdict |
|---|---|---|
| **All 11 DEF308 sites** | 11 | **true positives** — caught every one, including the 4 `User` auth inserts |
| Sites in **no register at all** | 14 | mixed — several genuine, several false (§3.2) |
| `unknown` frame | 13 | attribution failure (§3.3) |
| `upsert_daily_bars`, `upsert_reference` | 2 | **false positives** — handler is in the caller's frame |

**The headline finding: it caught real sites the source scanner has never seen.** The largest by
execution count:

| Executions | Model | Site |
|---|---|---|
| 739 | `SimPortfolioRow` | `sim_engine.py:729 in ensure_portfolio` |
| 436 | `GameEntryRow` | `games_service.py:855 in enter_field` |
| 331 | `SimHoldingRow` | `sim_engine.py:2412 in _apply_buy_row` |
| 31 | `LeagueMemberRow` | `league_service.py:213 in _assemble_week` |
| 13 | `GameDuelRow` | `games_duels.py:218` and `:229 in pair_field` |
| 7 | `DailyChallengeAttemptRow` | `api/daily_challenge.py:184 in attempt` |

I hand-checked `ensure_portfolio`: it calls `self._load_portfolio_row(...)` (a SELECT), then
`s.add(SimPortfolioRow(...))`, and `SimPortfolioRow` carries `UniqueConstraint(user_id, kind,
run_id)`. **The static scanner missed it because the read happens inside a helper method** — its rule
is "one function reads model X and adds model X", and the read is one frame away. That is a *third*
distinct blind spot, different from the two already known, and it was found by running the code
rather than by reading it.

`daily_challenge.attempt` sits in `app/api/`, which the scanner does not scan at all.

---

## 3. What this MISSES, and what it gets wrong

The brief says a submission claiming total coverage will be read as not having looked. Here is where
mine breaks.

### 3.1 My first version was useless, and the failure is instructive

v1's rule was "collidable model inserted outside a savepoint". It flagged **62 of 70 executed
sites** — because most are legitimate append-only inserts on models that merely happen to carry some
unique column. A control that fires on 62 correct things to catch 11 wrong ones is not a control; it
is a nuisance people route around, which is DEF277's shape exactly. I would have shipped that if I
had reasoned instead of measured.

### 3.2 It cannot see an `except IntegrityError` in the caller's frame

`_protected()` only detects a SAVEPOINT. Real protection written as a plain `try/except
IntegrityError` around the call is invisible to it. Confirmed false positives include
`notification_service.notify` and `journal_store.append` — both **have** handlers.

This is precisely where the source scanner is *better*: lexical scope is exactly what an AST can see
and a runtime hook cannot. It is the strongest argument in this document for keeping both, and I did
not expect it when I started.

### 3.3 Frame attribution still fails 13 times

13 flagged rows report `unknown`. `transient_to_pending` fixed the common case, but objects added
via cascade or relationship append never pass through it. Those rows name a real risk with no
address, which is a weak signal.

### 3.4 Coverage is bounded by tests — and by *branches*

The worst limitation, and I only found it because my own prototype had a bug.

`ensure_anonymous` has two paths: with a device id it SELECTs first; without, it inserts a fresh
`uuid4` that cannot collide. My first aggregation kept **whichever branch ran first** — 528
executions filed under the safe reading, and the site vanished from the report. Fixing it to
aggregate (`check_then_insert` ORed, `protected` ANDed) moved the count from 23 to 40 and pulled
`ensure_anonymous` back in.

Two lessons, both against my own proposal:

- A runtime detector reports on **executed branches**, not on code. An untested path is invisible.
- A detector whose verdict depends on **test order** is worse than one that is merely incomplete,
  because it is incomplete differently on every run. Any implementation must aggregate, and must be
  tested for that.

### 3.5 What stops *this* being widened three times like the last one?

The honest answer: **partly nothing.** The collidable-model derivation is total (live metadata, not
AST), and the read-tracking is total for ORM queries. But raw `session.execute(text(...))`, a bulk
`insert()` bypassing the ORM unit of work, or a read cached in the identity map would all slip
through — and each would be "one more variant to add", which is the exact trap.

What is structurally different: **the failure mode is inverted.** The source scanner's blind spots
made it silently pass. This one's blind spots make it silently *miss a site that never executed* —
but the moment that code path runs in any test, it is seen, without anyone teaching it a syntax. It
degrades toward under-reporting on cold code rather than toward false assurance on written code.

---

## 4. How a reviewer verifies every claim above

Nothing here is asserted without a means of checking it:

| Claim | Check |
|---|---|
| Catches all 11 DEF308 sites | run the plugin; grep the JSON for the 11 function names |
| Finds sites the scanner never has | compare `observations_full.json` against `_UNREVIEWED` + `_HANDLED_AT_CALLER` |
| Costs no test time, breaks nothing | 4,222 passed with the plugin loaded; the single failure is unrelated register drift from an uncommitted row |
| Distinguishes fixed from unfixed | smoke run: flags `watchlist_store.add`, stays silent on `mandate_store.upsert` and `overlay_store.save_new_version`, both DEF220-fixed |
| Append-only inserts stay silent | 17 sites classified append-only and never flagged |
| The false positives are real | `notification_service.py:115` and `journal_store.py` contain `except IntegrityError` |

Raw data: [`prototype/observations_full.json`](prototype/observations_full.json).

---

## 5. Per-site collision behaviour (brief §4.2)

The detector deliberately takes **no position** on what a site should do. It asks one question — *is
this an undeclared check-then-INSERT?* — and the four outcomes DEF220 established (skip / re-read and
update / retry then raise / raise) remain the author's choice.

The `enforce` message is worded to demand a decision rather than suggest one: *"Declare the collision
outcome."* A site satisfies it by wrapping in a savepoint and choosing, which is the same work DEF220
did by hand, now with the site handed to you instead of discovered a year later.

---

## 6. Cost to the next developer

- **Writing an ordinary append-only insert: nothing.** Never read the model, never flagged.
- **Writing a genuine check-then-insert: a savepoint and a one-line comment** naming the outcome.
- **Failure mode when the control is wrong:** in `observe` mode, a JSON row nobody reads — harmless
  and useless. In `enforce`, a failed test naming the model, the site and the constraint. Loud, and
  never silent-green, which is the failure this whole exercise is about.

**Deployment shape I would actually recommend:** `observe` in CI for two weeks to build the
allowlist of caller-handled sites honestly, then `enforce`. Going straight to enforce would
immediately fail on the ~15 false positives in §3.2/§3.3 and teach everyone to disable it in week
one.

---

## 7. Retrofit plan for the 11 open sites

The detector is what makes this ordered by evidence rather than by guesswork.

1. **Land the observer in `observe` mode first.** It is additive, breaks nothing, and produces the
   real list — including the 14 sites nobody has registered.
2. **Fix the 4 `User` auth sites first.** Highest consequence: `User.email` / `apple_id` / `google_id`
   are unique, and the loser of that race is a duplicated or orphaned account. The outcome is already
   written in `_claim_or_create`'s own comment — *"an existing row matching the verified email always
   wins"* — so on collision: re-read by the identity column and adopt. Same result the non-race path
   produces.
3. **Triage the 14 unregistered sites** into "already handled in the caller" (allowlist, with the
   handler's location recorded) and "genuinely open" (fold into DEF308). `ensure_portfolio` at 739
   executions is the one I would look at next after auth.
4. **Fix the remaining 7 DEF308 sites**, each declaring its outcome.
5. **Flip to `enforce`.** The gate is only meaningful once the known set is zero.
6. **Keep the source scanner.** It covers code the tests never run, and it sees caller-frame handlers
   that the runtime cannot. Where the two disagree, that disagreement is itself the signal worth
   reading — a site the scanner calls guarded and the observer calls unprotected is either a
   caller-frame handler or a real hole, and both are worth knowing.

---

## 8. What I would tell the judge

The strongest thing in this submission is not the mechanism. It is that **two of my three
conclusions came from measurement contradicting what I expected**: the naive rule was useless at
62/70, and the runtime approach turned out to be *strictly weaker* than the source scanner at seeing
caller-frame handlers. I would have argued both wrongly from first principles.

So if this loses to a better idea, the part worth keeping is the observer as an **instrument** rather
than as a gate — it is the only thing here that produced facts about which sites actually execute,
how often, and under what protection. Any proposal, including a competitor's, can be checked against
it.
