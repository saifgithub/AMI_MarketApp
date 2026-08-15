# ISS001 — "look if the row exists → if not, insert it"

**Opened:** 2026-08-15 · **Status:** open for contributions · **Convened by:** Architect (track R)

> **This brief deliberately contains no proposed solution — not even the convening agent's.**
> Symptoms, evidence and analysis of the *problem* are here. Every idea about what to *do* lives in
> a contributor's own subfolder, unread by the others. See
> [`../DILEMMA_PROTOCOL.md`](../DILEMMA_PROTOCOL.md).

---

## 1. The problem in one paragraph

Across this backend, code repeatedly does: **SELECT to see whether a row exists; if it does not,
INSERT it.** With one writer this is correct. With two it is not — both reads land before either
commits, both branches decide to insert, and the second INSERT violates a UNIQUE constraint and
raises. We have written this pattern **20 times**. We have documented it as a named failure class,
built an automated guard for it, and filed two defects against it. It kept being written anyway,
including **three times in the week after the guard went live**.

The question this Dilemma asks is not "how do we fix these 20 sites." It is: **what would actually
stop the 21st from being written?**

---

## 2. Why it has never bitten us in production

This matters, because it explains both the low urgency and the low pressure to get it right:

- Alpha runs **one** container, one uvicorn, **no `--workers`**.
- Separately, **DEF200** (open) records that synchronous DB I/O still runs on the asyncio event loop
  across ~93 handlers. Blocking calls on the event loop mean requests effectively **serialize**.
- CR136-M01's auditor measured **0 races in 60 trials** on this stack.

So the protection is real, and it is **accidental** — a deployment fact and a performance defect, not
a guard. Two independent, already-planned changes remove it:

| Change | Effect |
|---|---|
| **Cloud Run** (the documented Beta stack) | multiple instances, no shared process state — every site becomes reachable |
| **Fixing DEF200** | properly threading those handlers lets requests genuinely interleave *inside one container* |

Nothing links DEF200 and DEF308 today. Whoever fixes DEF200 arms this, and would have no reason to
know.

---

## 3. Evidence

### 3.1 Full inventory — every known site

Produced by the current detector (widened 2026-08-15) over `backend/app/`. **A solution must be
retrofittable to all of these**, and the inventory is also how a reviewer checks whether a proposal
covers the awkward cases rather than only the tidy ones.

Current totals: **32 collidable models**; **13 sites unguarded in place**; **7 fixed under DEF220**.

| # | File (`backend/app/services/`) | Function | Model | Constraint | State |
|---|---|---|---|---|---|
| 1 | `auth_service.py` | `_claim_or_create` | `User` | `email` unique | **DEF308 — open** |
| 2 | `auth_service.py` | `ensure_anonymous` | `User` | `email`/`phone`/`device_user_id` unique | **DEF308 — open** |
| 3 | `auth_service.py` | `sign_in_with_apple` | `User` | `apple_id` unique | **DEF308 — open** |
| 4 | `auth_service.py` | `sign_in_with_google` | `User` | `google_id` unique | **DEF308 — open** |
| 5 | `games_desks.py` | `ensure_desk_users` | `User` | `desk_key` unique | **DEF308 — open** |
| 6 | `lessons_service.py` | `grant_activation` | `AgentActivationRow` | `uq_activation_user_agent` | **DEF308 — open** |
| 7 | `lessons_service.py` | `mark_started` | `LessonProgressRow` | `uq_lessons_user_lesson` | **DEF308 — open** |
| 8 | `lessons_service.py` | `submit_quiz` | `LessonProgressRow` | `uq_lessons_user_lesson` | **DEF308 — open** |
| 9 | `games_service.py` | `ensure_field` | `GameFieldRow` | `join_code` unique | **DEF308 — open** |
| 10 | `client_release_floor.py` | `create_floor_raise` | `ClientReleaseFloorRow` | `min_build` unique | **DEF308 — open** |
| 11 | `watchlist_store.py` | `add` | `SimWatchlistRow` | `uq_watchlist_user_ticker` | **DEF308 — open** |
| 12 | `price_history.py` | `upsert_daily_bars` | `PriceHistoryDailyRow` | composite | handled **at the caller** |
| 13 | `ticker_reference.py` | `upsert_reference` | `TickerReferenceRow` | natural PK | handled **at the caller** |
| 14 | `auth_service.py` | `_upsert_user_device` | `UserDeviceRow` | `device_install_id` unique | fixed (DEF220) |
| 15 | `lessons_service.py` | `_check_agent_unlocks` | `AgentActivationRow` | `uq_activation_user_agent` | fixed (DEF220) |
| 16 | `mandate_store.py` | `upsert` | `MandateRow` | `uq_mandate_user_version` | fixed (DEF220) |
| 17 | `overlay_store.py` | `save_new_version` | `OverlayEditCounter` | `uq_overlay_count_user_agent` | fixed (DEF220) |
| 18 | `overlay_store.py` | `save_new_version` | `UserOverlayRow` | `uq_overlay_user_agent_version` | fixed (DEF220) |
| 19 | `reputation_service.py` | `_award_badge` | `BadgeRow` | `uq_badge_user_key` | fixed (DEF220) |
| 20 | `social_context.py` | `_cache_write` | `SocialSentimentCacheRow` | natural PK `ticker` | fixed (DEF220) |

Note rows **17 and 18**: two collidable inserts **in the same function**. The detector saw one and
not the other for months.

### 3.2 The detector has been wrong three times, the same way each time

| Version | Rule | How it failed | Found by |
|---|---|---|---|
| v1 (2026-08-05) | match call sites **by name** (`upsert_*`) | enforced a naming convention, not the pattern. An auditor added a check-then-insert not named `upsert_*`; the guard passed | CR136-M01 round-2 auditor |
| v2 (2026-08-05) | match by **shape**: function reads model X and `session.add`s model X | only recognised `session.add(Model(...))` built **inline**. `row = Model(...); session.add(row)` was invisible — **12 of 20 sites** | a DEF220 sanity check, 2026-08-15 |
| v3 (2026-08-15) | v2 + track variable assignment | *unknown* | — |

Each widening covered **the instance that had just been found**, not the pattern. Neither failure was
ever detected by the guard failing; both were found by a person reading the rule.

**Known remaining limits of v3, stated rather than discovered later:**

- It scans `backend/app/services/*.py` only. Measured 2026-08-15: scanning all of `backend/app/`
  finds the same set, so this is a latent weakness, not an active blind spot **today**.
- It cannot see a handler that lives in the **caller's** frame — rows 12 and 13 are correct code that
  the rule reports as unguarded, and they are suppressed by a hand-maintained allowlist.
- It infers a model from local syntax. Any construction it has not been taught — a factory, a helper,
  a comprehension, a bulk API — is invisible by default.

### 3.3 The rule existed, was automated, and was ignored — with dates

| Date | Event |
|---|---|
| 2026-08-05 | Pattern **P15** written into `failure_patterns.md`; automated guard built (`64d1e1a1`) |
| 2026-08-06 | **DEF220** filed, naming 6 unguarded sites explicitly |
| 2026-08-07 | `client_release_floor.create_floor_raise` lands — **new** unguarded site (`04be4b91`) |
| 2026-08-11 | `games_service.ensure_field` lands — **new** unguarded site (`75ca3b1c`) |
| 2026-08-11 | `games_desks.ensure_desk_users` lands — **new** unguarded site (`dfa8011a`) |

Three new instances in six days, with the rule documented, the guard running green, and a defect open
against the exact pattern.

### 3.4 The codebase actively taught the wrong thing

`_upsert_user_device`'s docstring, shipped and unchallenged for three months, read:

> *"UNIQUE on device_install_id keeps this safe under races."*

The constraint is the thing that makes it **raise**. Any coder — model or human — opening that file
to match house style read a confident, specific, inverted claim. A general principle held in
background knowledge loses to a precise local statement.

### 3.5 What the last fix cost, and what it proved

DEF220 fixed 7 sites by hand. The relevant finding for anyone designing a solution is that **the
correct behaviour on collision was genuinely different per site** — four distinct answers were
needed:

- **skip** — the row existing *is* the goal (badge, cache)
- **re-read and update** — the loser still has a change to apply (device ownership re-keys on account
  claim; an edit counter gates a paid quota)
- **retry, then raise** — user-authored content under a version sequence (mandate, overlay)
- **raise immediately** — a collision means something is genuinely wrong

A single blanket behaviour would have been wrong at most of those sites. This is stated as a
*constraint on solutions*, not as a recommendation of any particular mechanism.

---

## 4. What a solution has to do

A submission is judged on whether it plausibly stops the **21st instance**, not on elegance.

**Must:**

1. Prevent, detect, or make-impossible a new check-then-insert on a collidable model — and say
   **which of those three** it does.
2. Accommodate that the correct collision behaviour differs per site (§3.5).
3. Be retrofittable to the 11 open sites in §3.1, including the four `User` inserts on the auth path.
4. State **how a reviewer verifies the claim**. Any assertion about coverage needs a means of
   testing it. "This catches all cases" without a check is not a proposal.
5. Say what it would **fail to catch**. Every previous version of this guard was confident and
   incomplete; a submission that claims total coverage without naming its own blind spot will be read
   as not having looked.

**Should address, because the history says these are where it goes wrong:**

- What stops *this* solution being widened three times to fit whichever instance someone spots?
- How does it behave when it is wrong — silently, or loudly? A green signal that means "not checked"
  has already cost us a week.
- What does it cost the next person writing an ordinary insert? A control routinely worked around is
  worse than none.

**Out of scope:**

- The `mandate` / `overlay` version-sequence logic — fixed, audited, not up for redesign.
- DEF200, the Cloud Run migration, and any change to the deployment topology.
- Redesigning the schema or removing UNIQUE constraints. The constraints are correct; the code is not.

---

## 5. Constraints for contributors

- **Access:** read the whole repo. **Write only inside your own subfolder**,
  `docs/dilemmas/ISS001_DB_INSERT_RACE/<your-model-name>/`. Change no application code, no tests, no
  shared documents.
- **You may touch anything in your proposal** — the DB layer, the session factory, the guards,
  migrations, conventions. **New dependencies are permitted if justified**: name the library, why it
  earns its place, and what it costs, given that this stack is deliberately lean.
- **Do not read another contributor's subfolder before submitting.** The whole value of this exercise
  is independence; reading another answer destroys yours. If you do read one, say so.
- **Stack:** Python 3.13, FastAPI, SQLAlchemy 2.0.49, Alembic, Postgres in Alpha, sqlite tempfile in
  tests (sqlite 3.53.2). 4,223 backend unit tests, ~8.5 min. Mac is a pure editor — no local backend
  or DB.

**Required output:** `SOLUTION.md` in your folder, covering §4's Must list. Anything else you want —
prototypes, tests, benchmarks, diagrams — is welcome alongside it.

---

## 6. Where the pieces are

| | Path |
|---|---|
| The detector | `backend/tests/unit/test_p15_check_then_insert_guard.py` |
| The pattern entry | `docs/initial_specs/08_tech/failure_patterns.md` → **P15** (and **P16**, on rules validated only against their motivating examples) |
| Models + constraints | `backend/app/db/models.py` |
| Session factory | `backend/app/db/__init__.py` |
| DEF220 (7 fixed, with the reasoning per site) | `docs/defect/_registry/DEF220.row.md` |
| DEF308 (the 11 open) | `docs/defect/_registry/DEF308.row.md` |
| The behaviour tests from the last fix | `backend/tests/unit/test_def220_check_then_insert_outcomes.py` |

**DEF308 is frozen** for the duration: the 11 sites stay pinned and unfixed, so they remain the
proving ground for the winning solution. The pin still blocks a 12th from landing.
