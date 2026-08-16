# ISS001 — state of the exercise

**Last updated:** 2026-08-16 · **Status:** three submissions in, **field kept open for a 4th
contributor** · **CR185**

This is the resume point. Read it first, then only what it points you at. It exists because ISS001
spans sessions: contributors arrive days apart and judging happens later still.

---

## 1. The problem, in one line

`backend/` writes "SELECT to check, then INSERT if absent" — a race under two writers. The pattern
has a documented failure class (**P15**), an automated guard, and two defects (**DEF220** fixed 7
sites; **DEF308** pins 11). It was still written **three more times in the six days after the guard
went live**. Full evidence: [`ISS001_problem_statement.md`](ISS001_problem_statement.md).

The exercise asks several agents, blind to each other, what would actually stop the 21st instance.

---

## 2. Where it stands

| | |
|---|---|
| Brief + invite written | ✅ `fca69ce3` |
| Convening agent's own solution (written before anyone was invited) | ✅ `opus5.0/`, `842798eb` |
| Contributors invited by Saiful | `gemini-3.6-flash`, `kimi-k2` |
| Submissions landed | **3 of 3** — committed `0d5ff502` |
| Judging | **not started — field stays open.** Saiful's call 2026-08-16: wants a 4th contributor before judging opens. No `VERDICT.md` exists |
| The 11 DEF308 sites | **FROZEN** — Saiful's ruling, 2026-08-15 |

**Nobody has been asked to judge.** The invite deliberately never asks a contributor for a verdict —
a contributor who ranks the others has read the others, which is the one thing the invite forbids.
Judging is Saiful's, or an agent he delegates it to (protocol step 6).

---

## 3. The three submissions

All three independently reached the same reframe: **the pattern is a runtime event, not a source-text
grammar.** None proposed a v4 AST rule. That unanimity is itself a finding — it is the strongest
available evidence that widening the scanner a fourth time is the wrong move.

Where they differ is what the runtime hook is *for*.

### `opus5.0/` — detect, and keep the scanner
- Rule: *this session SELECTed model X and is now INSERTing model X with nothing in scope to catch a
  violation.* Append-only inserts are silent **by construction**, not by allowlist.
- Three listeners (`do_orm_execute`, `transient_to_pending`, `before_flush`); `observe` / `enforce`.
- Measured on the full suite: 32 collidable models, 65 sites executed, **40 flagged** = all 11 DEF308
  sites + 14 unregistered + 13 unknown-frame + 2 caller-handled false positives. ~0 runtime cost.
- Explicitly **declines** to build a chokepoint helper, and argues for keeping the AST scanner
  because lexical scope (a caller-frame `except IntegrityError`) is exactly what a runtime hook
  cannot see and an AST can.
- Names its own v1 as useless (62 of 70 sites flagged) and says so.

### `gemini-3.6-flash/` — prevent, via a `safe_insert()` chokepoint
- Rule: *any collidable model in `session.new` without a marker* → raise. Not read-then-write.
- `safe_insert(session, obj, on_conflict=SKIP|UPDATE|RETRY|RAISE)` with `fetch_existing_fn` /
  `update_fn` / `retry_fn` callbacks; escape hatch `with with_conflict_handler():`.
- Retrofit policy assigned to each of the 11 DEF308 sites (checked — all 11 match the inventory).
- Builds the chokepoint opus5.0 rejected, and makes the guard the thing that forces you through it.
- **Not measured against this codebase**: 3 synthetic models, 6 tests, 0.13s. No suite run.

### `kimi-k2/` — make it impossible to *run* unexamined, and close every channel
- Schema-derived collidable registry (`verify_registry.py`: **32/32**, matching the detector's
  measured 32, with no AST).
- `GuardedSession` closes **all** insertion channels — `session.new` at flush, ORM-execute Core
  `insert()`, and `bulk_insert_mappings` / `bulk_save_objects` **banned by method override**, because
  it measured that those fire no session event on 2.0.49 and `after_bulk_insert` was removed in 2.0.
- `put()` with **mandatory** `on_collision` — no default, so forgetting is a `TypeError`.
- **Canary tests that go red if the guard is deleted** — its answer to the brief's *"neither failure
  was ever detected by the guard failing"*. No previous version had this property.
- Ran **three full 8-minute suites** and shipped the logs: baseline `4223 passed / 500.51s`; observe
  `4223 passed / 493.12s` (invisible to a green suite); enforce `4226 errors / 343s`, all at setup,
  first sighting `tests/conftest.py:66` seeding `TickerReferenceRow` with a bare `session.add` — a
  site the AST guard structurally cannot see because it only scans `app/services/`.
- Retrofit table covers **16** sites, not 11, plus three Alembic migrations (§5.1 below).
- Would **retire** the AST scanner — the opposite of opus5.0's recommendation. That disagreement is
  the sharpest open question for the judge.

---

## 4. What is independently confirmed, across submissions

**Two runtime approaches, blind to each other, found the same three unguarded sites** that three
versions of the AST guard never saw:

| Site | Why every AST version missed it |
|---|---|
| `sim_engine.ensure_portfolio` (`SimPortfolioRow`, `uq_portfolio_user_kind_run`) | the SELECT lives in `_load_portfolio_row` — one frame away; the rule is intra-function |
| `sim_engine._apply_buy_row` (`SimHoldingRow`, `uq_holding_portfolio_ticker`) | the "check" is an in-memory scan of `p_row.holdings` — there is no `select(Model)` in the frame at all |
| `league_service._assemble_week` (`LeagueMemberRow`) | scheduler path, no handler in the file |

These are the 21st/22nd/23rd instances, already in the tree. They are **not** in DEF308 and are
**not** covered by the freeze — they were unknown when it was set. Convergent discovery by two
independent methods is much stronger evidence than either finding alone.

## 5. The brief's own evidence was wrong, and it changes the problem

`kimi-k2` checked the inventory against `backend/app/db/models.py` instead of trusting it. Verified
independently at [`models.py:73-76`](../../../backend/app/db/models.py#L73-L76) and `:121`:

- `apple_id` — plain nullable column. **Not unique.**
- `google_id` — plain nullable column. **Not unique.**
- `device_user_id` — `index=True`, a non-unique index.

Only `email`, `phone`, `desk_key` and `handle` are unique on `users`. So two concurrent first-time
Apple sign-ins produce **two user rows with the same `apple_id` and no error at all** — silent
duplicate identity, strictly worse than the 500 this whole exercise was worried about, and outside
the reach of *every* proposal on the table, because there is no constraint to violate. Same shape for
concurrent anonymous starts on one `device_user_id`, and for `ensure_field`, where `join_code` is
unique but that insert leaves it NULL and nothing constrains `(cadence, kind, starts_on)`.

**The invariant has a schema-side twin nobody stated: every collision surface must actually have a
constraint.** The brief has been corrected in place with a dated note. Any implementation CR needs
migrations before the auth sites can be fixed at all.

---

## 6. What is frozen, and what the rules still are

- **DEF308's 11 sites: do not fix by hand, do not lane.** Saiful's ruling — the real sites stay the
  proving ground for whatever wins. Holds until he picks a winner or reopens it.
- **Never edit another contributor's folder.** `gemini-3.6-flash/` and `kimi-k2/` are read-only to
  the convening agent, as `opus5.0/` is to them.
- **Do not write `VERDICT.md` until Saiful says judging starts.**
- The AST guard (`backend/tests/unit/test_p15_check_then_insert_guard.py`) stays exactly as-is; its
  `_UNREVIEWED` pin is what freezes the 11 sites.

---

## 7. Resuming — what to do, in order

1. Read this file (done).
2. Ask Saiful which of the two open decisions he wants (below). Do not assume.
3. **If judging:** read all three `SOLUTION.md` files in full plus their artifacts, then write
   `VERDICT.md` per protocol step 6 — what won, what the runners-up were right about that the winner
   must absorb, and what was rejected and why. Judge against the goal (does it stop the 21st
   instance, and can a reviewer check that) not against elegance.
4. **If implementing:** it is an ordinary laned CR referencing ISS001, not more Dilemma work.
   Mint a new `CR###`; do not extend CR185, which covers the protocol and the exercise.

## 8. Decisions owed by Saiful

| # | Decision | Why it is his |
|---|---|---|
| 1 | ~~Are more contributors coming, or is the field closed at three?~~ **DECIDED 2026-08-16: field stays open, a 4th contributor comes before judging.** Awaiting Saiful to name/invite them. | Judging cannot start while submissions are open |
| 2 | Judge it himself, or delegate to an agent? | Protocol step 6 gives him both options |
| 3 | Keep the AST scanner alongside the runtime control, or retire it? | opus5.0 and kimi-k2 disagree directly; it is a standing-cost call, not a technical one |
| 4 | Do the three schema migrations (§5) ride the same CR, or become their own defect? | `apple_id`/`google_id` uniqueness is a product-identity decision, not just a constraint |

---

## 9. Commits

| Commit | What |
|---|---|
| `fca69ce3` | Dilemma protocol + ISS001 brief + invite prompt |
| `842798eb` | `opus5.0/` solution + prototype + measurements |
| `0d5ff502` | `kimi-k2/` and `gemini-3.6-flash/` submissions, plus the §5 correction to the brief |
