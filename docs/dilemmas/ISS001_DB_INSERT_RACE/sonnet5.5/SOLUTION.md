# ISS001 — sonnet5.5 submission

**Blindness:** I did not open `ISS001_STATE.md`, any sibling subfolder, or any commit touching them. `DEF499.row.md` read for its symptom text only. (`ls` of the ISS001 folder showed sibling folder *names*; nothing inside.)

**Contents:** this file; `prototype/` (`ami_claim.py` ~430 lines, `test_prototype.py` 19 tests, `mutate.py`, `observe_plugin.py`, `evidence/`). Nothing outside this folder was changed.

## Summary

1. **Mechanism:** every INSERT into a table the DB can make collide must go through `claim()` (atomic `INSERT … ON CONFLICT DO NOTHING`, caller picks skip / update / raise) or an explicit, reasoned `unclaimed()`; enforced at the driver (`before_cursor_execute`), not by reading source.
2. **Class:** *prevents* for any key the DB enforces (a naked insert raises in CI at first execution; `claim()` refuses a key with no effective unique index, which is also how DEF499 would have been stopped). *Detects*, test-only, for keys with no constraint.
3. **Reframing:** the guard was blind, not ignored (v3 still passes with DEF499 in the tree), and the DEF499 constraint existed but could never fire (NULL `run_id`). "Has `except IntegrityError`" is a proxy that dead code satisfies.
4. **Named blind spot:** an INSERT that no test ever executes, and a business key with neither a constraint nor a read in the same session. Suite measurement: 42 of 43 collidable constructor sites are executed today.
5. **Cost:** ~46 one-time declarations on the real tree (not 11); an ordinary new insert is one `claim(...)` line, shorter than today's check-then-insert. Prod mode `log` vs `raise` is Saiful's call (§5.4). Postgres behaviour is design, not measurement (§4.4).

---

## 0. Where I think the framing is wrong

1. **The guard was not ignored; it was blind.** §3.3 reads as "rule documented, guard green, still written three times". All three post-guard sites are the `row = Model(...)` / `session.add(row)` form (`client_release_floor.create_floor_raise` is: `row = ClientReleaseFloorRow(...)` at line 220). v2 could not see that form. The guard stayed green because it could not see them. The lesson is "any control that infers semantics from syntax has an unbounded blind-spot set", not "agents disobey".
2. **The 21st instance is already in the tree and passes v3.** `sim_engine.ensure_portfolio` reads through a helper (`self._load_portfolio_row`) and then `s.add(SimPortfolioRow(...))`. It is not in `_UNREVIEWED`, and `test_p15_check_then_insert_guard.py` is green (I ran it: 4 passed). That is DEF499. v3 has the *same class* of blind spot as v1 and v2, one level up (read hidden in a helper). Widening v3 again is the pattern the brief says not to repeat.
3. **A second, independent hole is not an AST problem at all: the constraint exists and does nothing.** `uq_portfolio_user_kind_run = UNIQUE(user_id, kind, run_id)` with `run_id` NULL for every training portfolio. NULLs are distinct (SQLite always; Postgres < 15 default and, absent `NULLS NOT DISTINCT`, 15+), so the constraint never fires for exactly the rows the app writes. Even a *perfect* detector plus a *perfect* `except IntegrityError` would have passed DEF499: the handler can never run. Six unique keys in `models.py` have this shape (§7.2; measured). One is live proof: `portfolio_nav_daily.py:237` has `except IntegrityError`, the P15 guard counts it as handled, and for `run_id IS NULL` (the training series) it is dead code.
4. **"Has an `except IntegrityError`" is a proxy, and the proxy is satisfiable by dead code.** A control must check what is actually true: *is there a key the DB enforces, for this row's actual values, and does the insert go through it atomically?*
5. **The constraint-less sites (§3.1 correction: apple_id, google_id, device_user_id) and `games_service.ensure_field` (a business key — one open field per cadence/period — with *no* unique index at all) show a third class:** no collision surface exists, so nothing a "catch the violation" control does can matter.

So three things must be true for a check-then-insert to be safe, and today we check at most one (a keyword in a `try`): **(a)** an effective unique key exists; **(b)** the insert is atomic against it; **(c)** the loser does the right thing. My proposal gives each one an owner.

---

## 1. What I propose

**Classification, stated plainly:**
- For any table whose uniqueness the DB enforces: **prevents** — a naked INSERT cannot execute without raising in CI, and a sanctioned one is atomic by construction. A new instance has to be *both* un-executed by any test *and* in a path where the only protection left is the prod-log tripwire (§5).
- For a business key with no DB constraint: **detects** (test-only observer), only when the code reads before inserting in the same session.
- For code no test ever executes: **neither**. Named blind spot #1, §5.

The unit of enforcement moves from *"is this function shaped like check-then-insert?"* (semantic, inferred from source, widened three times) to *"is this INSERT statement, observed at the driver, into a table that has an arbiter, sanctioned?"* (mechanical, decided from DB metadata and the SQL verb, nothing to teach).

### A. `claim()` — the one sanctioned insert for a row that can collide

```python
c = claim(s, Model, key={"user_id": u, "kind": "training", "run_id": None},
                    values={"starting_capital": 10000, ...})
c.row, c.created           # Claimed(row, created)
c.or_skip()                # the row existing IS the goal               (badge, cache, watchlist add)
c.or_update(lambda r: ...) # the loser still has a change to apply      (device re-key, edit counter, adopt-existing user)
c.or_raise(Exc(...))       # a collision is a bug / a 409               (release-floor duplicate)
```

Implementation (`prototype/ami_claim.py::claim`): `INSERT … ON CONFLICT (<arbiter>) [WHERE <pred>] DO NOTHING RETURNING pk`, via the dialect `insert` (both `postgresql` and `sqlite` ≥ 3.24 are in the stack). Created ⇒ return it; not created ⇒ `SELECT` the winner (bounded 2 retries, then `ClaimVanished`). It is **atomic against the constraint** — there is no read-then-write gap to race. On Postgres, `ON CONFLICT DO NOTHING` also *waits* for an in-flight conflicting insert instead of erroring, so the loser neither raises nor duplicates.

**Arbiter validation on every call (this is what closes holes (a) and DEF499):** `claim()` looks up, in live metadata, a unique key that deduplicates *exactly this key, including its NULLs*. A key containing `None` is accepted only by a partial unique index over the non-NULL columns whose predicate says `<col> IS NULL`. Otherwise it raises `NoArbiter` — **on the first, happy-path execution**, with the list of arbiters it did find. So:
- `claim(SimPortfolioRow, key={user_id, kind, run_id=None})` on today's schema raises `NoArbiter`. The developer must add the partial index (§7.1) before the code runs. DEF499 cannot be written *again* in the shape that produced it.
- `claim(User, key={"device_user_id": d})` raises `NoArbiter` (index-only). Same for `GameFieldRow` natural key. The constraint becomes a *precondition of the sanctioned API*, not a separate chore somebody remembers.

Per-site behaviour (§2) is a *method choice at the call site*, not a global policy. `claim()` has no default for what a collision means — the caller picks `.or_*`, or reads `.created` directly.

### B. `install_tripwire()` — the driver boundary

`event.listen(engine, "before_cursor_execute")` on the **app engine instance** (in `get_engine()`; not on the `Engine` class, so alembic's engine can still insert seed data). For every statement beginning `INSERT` (or `WITH … INSERT`): parse the table name; if the table is *collidable* — derived from `Base.metadata`: has any unique constraint / unique index / `unique=True` / PK without a default — and the statement is not `ON CONFLICT`, and the table is not sanctioned by an active `claim()` / `unclaimed()` scope (a `ContextVar`) ⇒ `UnclaimedInsert`.

- Sees **every** API: ORM `session.add`, `add_all`, Core `insert()`, bulk, `text("INSERT …")`, `exec_driver_sql`. No model inference, no variable tracking, no factory/helper/comprehension to be "taught". (Tested: `test_tripwire_sees_inserts_the_orm_never_saw[core|text|bulk]`.)
- **Fails closed** on an INSERT it cannot parse (`table='?'`).
- Mode `raise` in the test suite (the gate). In prod `log` ⇒ `logger.error("unclaimed_insert", table, stack)`, row is still written — see §5 for why not `raise` in prod and what Saiful should decide.
- `unclaimed(Model, why="…")` is the **only** escape hatch: for sites that legitimately own their collision handling (mandate/overlay retry-then-raise, out of scope per brief) or that cannot collide by construction (fresh `uuid4()` in the unique column — `ensure_anonymous`'s mint path). Empty `why` raises. A test `grep`s for the token and pins the count — a literal text match, not an inference, so it cannot go blind the way v1–v3 did. Each addition is a deliberate, reviewable edit carrying its reason.

### C. `schema_truth()` — the unique keys must mean what they say (exact, no AST)

Introspected from `Base.metadata`: a composite unique key over a nullable column does not deduplicate rows where that column is NULL ⇒ finding, unless the column carries `info={"null_means_no_key": "<why>"}` (declared next to the column in `models.py`, where a reviewer reading the model sees it) or the index is partial with `<col> IS NOT NULL`. Single-column nullable unique keys (email, phone, apple_id) are exempt: NULL there means "no value". Run as a unit test against live metadata; today it reports **6 findings** (§7.2, measured) — one is DEF499, one is the dead-handler NAV table.

Companion (not prototyped, cheap): assert that **migrated** schema == model arbiters. The test DB is built with `create_all`, so a constraint that exists in `models.py` but not in the migration chain is invisible to the whole suite. A `alembic upgrade head` on an empty sqlite + `inspect().get_unique_constraints/get_indexes` vs `arbiters(table)` closes it. And at boot, `init_schema` already compares revisions; it should also `logger.error("db_arbiter_missing")` for any model arbiter absent from the live DB (CR040).

### D. `install_observer()` — test-only semantic detector for keys with no constraint

Hooks `Session` events (`do_orm_execute`, `after_attach`, `before_flush`): records equality predicates of every SELECT per session, and when a flush inserts a row whose values equal a previous read's predicate on the same table, reports `(table, cols, status, site)` with `status ∈ covered | VACUOUS | PARTIAL-KEY | NO-ARBITER`. It doesn't care that the read hid inside `_load_portfolio_row` — it sees the SELECT the DB would. **Gate only on `VACUOUS`; report-only for `NO-ARBITER` and `PARTIAL-KEY`** (`PARTIAL-KEY` = read narrower than the key, e.g. `max(version)+1` sequences, the mandate/overlay shape, out of scope). Why only one status gates: measured precision, §8.2. This is the only part that approaches the old detector's job, and it is **advisory and runtime, never a pinned AST inventory**: each finding is a fact about an executed query pair (§4 measures what it finds on the real suite).

### E. `serialize(session, "field", cadence)` — for invariants no index can express (spec only, not prototyped)

`SELECT pg_advisory_xact_lock(hashtextextended(:name, 0))` for sites like `ensure_field`'s rolling lobbies ("exactly one entry-accepting field per cadence", derived from timestamps because the state column goes stale). Cannot be proven on sqlite (no-op there). It is accepted by the tripwire as a sanction like `claim()`. I list it so the design does not pretend every site fits `claim`.

---

## 2. Per-site differences (§3.5's four behaviours)

| Behaviour | Mechanism | Sites |
|---|---|---|
| **skip** | `claim(...).or_skip()` | badge, social cache, watchlist add, `grant_activation`, `ensure_desk_users` |
| **re-read and update** | `.or_update(fn)` / read `.created` | device re-key, edit counter, `_claim_or_create` (loser must *adopt* the winner: run `gate_sign_in`, re-key the orphan's devices), `mark_started`/`submit_quiz` (apply progress to the row either way) |
| **retry, then raise** | stays hand-written under `unclaimed(Model, why="version sequence: retry-then-raise (DEF220)")` — out of scope; `PARTIAL-KEY` observer still reports them | mandate, overlay |
| **raise immediately** | `.or_raise(ExcType(...))` | `create_floor_raise` → `ReleaseFloorDuplicateError(min_build)` |
| *invariant not index-expressible* | `serialize(...)` + `unclaimed` | `ensure_field` rolling cadences |
| *cannot collide* | `unclaimed(why="fresh uuid4 in unique column")` | `ensure_anonymous` mint path |

The point: the mechanism does **not** choose the behaviour; it makes choosing mandatory and the choice a one-token word at the call site. Nobody can write "skip" by omission.

---

## 3. What stops *this* from being widened three times

1. The tripwire's rule is "INSERT verb + table in `collidable_tables(metadata)` + not sanctioned". Its inputs are the SQL string and DB metadata, both **exact**. There is no model-inference step, no syntax shape, no allow-list of names. A new construction (factory, comprehension, Core, text, bulk) is not an unrecognised shape; it is an INSERT.
2. The only configuration is `unclaimed()` (pinned by a literal-token grep; requires a reason) and `null_means_no_key` (a column-level declaration beside the column). Neither is a place to "widen to cover the instance just found".
3. The observer is where an inference lives, so it is **demoted**: advisory/gating only on two statuses, test-only, never an exact pin on an inventory. If it has a blind spot, the tripwire still holds for any table with an arbiter.
4. Tripwire installation is itself tested (`event.contains(engine, "before_cursor_execute", handler)` on `get_engine()`'s engine) so "installed nowhere" fails loud — the green-means-not-checked trap the brief names.
5. Mutation check ships in `prototype/mutate.py`: 6 load-bearing lines broken one at a time; all 6 turn the prototype suite red (§4).

---

## 4. How a reviewer verifies

All commands from repo root; no Postgres, no network.

1. **Prototype claims** — `backend/.venv/bin/python -m pytest docs/dilemmas/ISS001_DB_INSERT_RACE/sonnet5.5/prototype -q` → 19 passed. Maps one-to-one:
   - naive pattern on the DEF499 shape silently writes 2 rows; on a real constraint the loser raises → `test_naive_*`.
   - `claim()` refuses a vacuous key / an unconstrained key → `test_claim_refuses_a_key_nothing_enforces`.
   - `claim()` on a partial index is atomic for the NULL key; 8 real threads × 15 rounds → exactly one creator, one row → `test_claim_on_partial_index…`, `test_claim_under_eight_real_threads…`.
   - tripwire blocks naked ORM, Core, text and bulk inserts; leaves append-only tables alone → `test_tripwire_*`.
   - observer finds a helper-hidden read→insert with no arbiter and the vacuous-NULL case; quiet on unrelated pairs.
2. **Mutation** — `python prototype/mutate.py` (runs on temp copies): expect `6 killed`, no `SURVIVED`. A survivor means a claim above is decorative.
3. **Against the real tree, nothing changed** — `prototype/observe_plugin.py` runs the *entire* existing backend suite with the tripwire in log mode and the observer on, writing a JSON summary:
   ```
   cd backend
   PYTHONPATH=../docs/dilemmas/ISS001_DB_INSERT_RACE/sonnet5.5/prototype ISS001_OUT=/tmp/iss001.json \
     .venv/bin/python -m pytest tests/unit -q -p observe_plugin
   ```
   Result committed at `prototype/evidence/suite_dryrun.json`; summary in §8. A reviewer re-running it gets the same site list modulo test additions.
4. **Not verifiable here, so say so** — Postgres behaviour: (i) `ON CONFLICT (user_id, kind) WHERE run_id IS NULL` index inference against the real partial index; (ii) `claim`'s re-read under READ COMMITTED; (iii) a true 2-connection race. Recipe for melehost (read-only apart from one rolled-back txn): run `prototype`'s thread test pointed at a throwaway schema in the Alpha Postgres. I did not run it. Treat claims (i)–(iii) as design, not measurement, until someone does.

---

## 5. What it would miss (named, not hedged)

1. **Code no test executes.** The tripwire fires when an INSERT *runs*. In CI, an untested path never trips. Mitigation, not a cure: the insert you write is the happy path of the feature, which the author's own test nearly always executes; the race *branch* (what the old controls tried to verify) is what nobody runs. That asymmetry is the bet. Measured support (§8.3): the existing suite executes 42 of the 43 constructor sites of collidable models. One counter-example exists (`BacktestRunIndexRow`, `room_runner.py:8028`), so the bet is "nearly always", not "always". In prod the tripwire logs (below) so an un-executed-in-CI path is at least named on first real use.
2. **A business-unique key with no DB constraint and no read in the same session** — a blind `INSERT` that "assumes" uniqueness. No metadata says the key matters; the observer needs a read. (Also: a read in a *different* session from the insert, e.g. a helper that opens its own `get_session()`.)
3. **Observer limits**: equality predicates only (not `IN`, ranges, joins, `.get()` identity-map hits); ORM-enabled selects only. It will not see `WHERE lower(email) = :e`.
4. **Prod mode is `log`, not `raise`** (recommended): the alternative is turning an untested-but-working path into a 500 for a real user. Trade-off belongs to Saiful: if he prefers hard-fail on Alpha (stealth-alpha testers), flip one env var. `log` is only as loud as whoever reads the `unclaimed_insert` ERROR line (the 6-hourly `/bug-monitor` could — I did not verify it reads this log key).
5. **`ON CONFLICT` anywhere is trusted.** A hand-written `ON CONFLICT (wrong_cols) DO NOTHING` passes the tripwire. Cheap hardening: require the conflict target to match an arbiter. Not done.
6. **`unclaimed()` can be abused** (wrap blindly). It is one grep-able token with a mandatory reason and a pinned count, so abuse is visible in the diff — but this is still a human review step. I do not claim otherwise.
7. **Bulk paths outside the cursor hook**: `COPY` via `copy_expert`, DB-side triggers, other services writing the same DB (the separate `ami_website` DB role).
8. **`claim` assumptions**: dialect has `ON CONFLICT` (pg, sqlite ≥ 3.24); READ COMMITTED; PK columns returned via RETURNING; values keyed by column name.
9. **A mis-declared `null_means_no_key`** silences `schema_truth` for that column. Mitigation: the declaration lives on the column in `models.py`; every entry needs a reason; the finding list is short (7) so every entry can be read once.
10. **Not covered**: SQLAlchemy `session.merge()` (it does SELECT-then-INSERT internally; the tripwire catches the INSERT if the table is collidable; `merge` is also `unclaimed`-able but wrong for the same reason — ban it by grep, see §7.4).

---

## 6. Cost to the next developer, and behaviour when the control is wrong

Ordinary insert, three cases:
1. **Append-only table (uuid PK, nothing unique):** nothing. Tripwire ignores it. (`test_tripwire_leaves_append_only_tables_alone`.)
2. **Table with a unique key:** write `claim(s, M, key=…, values=…).or_skip()` — this is *shorter* than today's `select` + `if None` + `add` + `flush` + `try/except IntegrityError` + `begin_nested`. Forgetting ⇒ the first test that executes the insert fails with a message that names the fix (`claim(...)` / `unclaimed(...)`) and the calling frame.
3. **Key has NULLs or no constraint:** `NoArbiter` names what's missing; cost is one migration with a partial unique index — which is the *correct* cost; today that migration is the thing nobody writes.

When the control is wrong:
- **False positive** (a safe insert trips): **loud**, fix = `unclaimed(why=…)`, one line. The retrofit run shows how frequent this is (§7.3). If it is frequent for one table, that is a design signal (e.g. mandate/overlay), not noise to suppress.
- **False negative** (a racy insert passes): **silent** — blind spots 1–3 above. I cannot make this loud; I can make it rare and name it.
- **`claim()` mis-specified** (conflict target doesn't match the index): **loud** — Postgres/SQLite reject `ON CONFLICT` with no matching unique index; and `NoArbiter` fires first.
- **Tripwire not installed**: loud via the install test (§3.4).
- Runtime cost: one `str.lstrip().upper().startswith("INSERT")` per statement; a stack walk only on violation.

---

## 7. Retrofit plan

State today (`_UNREVIEWED` in the guard): **9** pinned sites, not 11 — `sign_in_with_apple` / `sign_in_with_google` were fixed under DEF416 (partial unique indexes + `begin_nested` recovery). Plus **DEF499** (`ensure_portfolio`, invisible to the guard), plus the guarded-but-dead NAV writers, plus the "fixed" DEF220 sites, which will trip the tripwire (plain `add`) and be converted or declared.

### 7.1 DEF499 — instance #21, and the two existing duplicate rows

**Root cause is two failures, not one:** (1) `uq_portfolio_user_kind_run` is vacuous for `run_id IS NULL`; (2) `ensure_portfolio` reads via `_load_portfolio_row`, so the guard never saw it.

**Fix (in order — a migration before code, so the DB is the first line):**
1. **Read-only preflight on melehost** (I did not run it: no DB on this Mac):
   ```sql
   -- every duplicated training portfolio, with what hangs off it
   WITH d AS (SELECT user_id FROM sim_portfolios
              WHERE run_id IS NULL AND kind='training' GROUP BY 1 HAVING count(*) > 1)
   SELECT p.id, p.user_id, p.created_at, p.starting_capital, p.current_cash,
     (SELECT count(*) FROM sim_holdings              x WHERE x.portfolio_id=p.id) holdings,
     (SELECT count(*) FROM sim_trades                x WHERE x.portfolio_id=p.id) trades,
     (SELECT count(*) FROM portfolio_value_snapshots x WHERE x.portfolio_id=p.id) snaps,
     (SELECT count(*) FROM sim_resting_orders        x WHERE x.portfolio_id=p.id) resting,
     (SELECT count(*) FROM sim_short_positions       x WHERE x.portfolio_id=p.id) shorts,
     (SELECT count(*) FROM game_short_positions      x WHERE x.portfolio_id=p.id) gshorts,
     (SELECT count(*) FROM sim_option_legs           x WHERE x.portfolio_id=p.id) opt_legs,
     (SELECT count(*) FROM sim_option_trades         x WHERE x.portfolio_id=p.id) opt_trades
   FROM sim_portfolios p JOIN d USING (user_id)
   WHERE p.run_id IS NULL AND p.kind='training' ORDER BY p.user_id, p.created_at;
   -- same hole, second table: training NAV rows duplicated for one (user, day)
   SELECT user_id, as_of_date, count(*) FROM portfolio_nav_daily
   WHERE run_id IS NULL GROUP BY 1,2 HAVING count(*) > 1;
   ```
2. **Migration (one transaction — Postgres DDL is transactional):** (a) deterministic dedupe, (b) `CREATE UNIQUE INDEX uq_portfolio_user_training ON sim_portfolios (user_id, kind) WHERE run_id IS NULL` (both `postgresql_where` and `sqlite_where`, as `models.py:123` already does), and the same for `portfolio_nav_daily (user_id, as_of_date) WHERE run_id IS NULL`.
3. **Dedupe rule for the two known pairs.** Survivor = the portfolio with the most child rows; tie ⇒ earliest `created_at`; tie ⇒ lowest `id`. The loser is deleted **only if** it has zero children across all 8 FK tables **and** `current_cash = starting_capital`. Otherwise the migration **aborts, naming the ids** — merging two live ledgers (cash, holdings, lots) is a human decision, not a rule I will invent. Expectation, labelled inference not measurement: since 2026-09-28 every `_load_portfolio_row` for these users has raised `MultipleResultsFound`, so neither row should have been written to after creation and the loser should be empty. The preflight settles it before anything is deleted. Deleting is a write to Alpha ⇒ needs Saiful's go.
4. **Code:** `ensure_portfolio` ⇒ `claim(SimPortfolioRow, key={user_id, kind, run_id}, values={…}).or_skip()`. With the partial index present `claim` validates the training key (`run_id=None`) against it, and game rows (`run_id` set) against the full constraint — both paths covered. `_load_portfolio_row` keeps `scalar_one_or_none()`; it is now correct because the DB forbids what made it raise.
5. **Order matters:** migration first. With old code and the new index a race yields a loud `IntegrityError` on the loser instead of a silent second row — strictly better — and the new code removes that too.

### 7.2 `schema_truth` — the six findings (live `models.py`, measured)

`career_events.uq_career_event_stipend_period(user_id, period_key)`, `journal_entries.uq_journal_dedupe(user_id, entry_type, dedupe_key)`, `news_archive.uq_news_archive_item(ticker, source, url, published_at)`, `notifications.uq_notifications_dedupe(user_id, type, source_ref)`, `portfolio_nav_daily.uq_nav_user_run_date(user_id, run_id, as_of_date)`, `sim_portfolios.uq_portfolio_user_kind_run`.

Each needs one decision from the owning lane: *NULL means "no dedupe wanted"* ⇒ `info={"null_means_no_key": "<why>"}` on the column; *NULL is a real value that must dedupe* ⇒ partial unique index. I expect `sim_portfolios` and `portfolio_nav_daily` to be the latter and the rest the former — that is my reading of docstrings, not a verified fact. Six is the number of places a reviewer must look **once**, not six defects.

### 7.3 The pinned sites and the guarded ones

| # | Site | Key / arbiter today | Conversion | Notes |
|---|---|---|---|---|
| 1 | `_claim_or_create` (`User`) | `email` unique | `claim(User, key={"email": e}, values=…).or_update(adopt)` | Loser must **adopt** the winner (`gate_sign_in`, `_rekey_devices_to`); the existing email-match branch already does — route both through one function. Normalise case *before* the claim or the key won't dedupe. Own slice, `GATE: independent` (auth path). |
| 2 | `ensure_anonymous` (`User`) | none on `device_user_id` | `unclaimed(User, why="mint path: fresh uuid4 PK and device_user_id")` | The only insert is a fresh-uuid mint; there is no key to collide on. The race is two orphan anon rows for one install — benign by current design, now *written down*. Optional: `SELECT device_user_id, count(*) … HAVING count(*)>1`; if 0, add a partial unique index. |
| 3 | `sign_in_with_apple` | `uq_users_apple_id` (DEF416) | `claim(…key={"apple_id": sub}).or_update(_attach_apple_sub)` | Replaces the `begin_nested`/re-read recovery with the shared primitive; **deletes** code. DEF416's tests run unchanged. |
| 4 | `sign_in_with_google` | `uq_users_google_id` | same | same |
| 5 | `ensure_desk_users` | `desk_key` unique | `.or_skip()` | |
| 6 | `grant_activation` | `uq_activation_user_agent` | `.or_skip()` | Build the record from `.row` either way. |
| 7 | `mark_started` | `uq_lessons_user_lesson` | `claim(…values={"started_at": now})`; if not created and `started_at is None`, set it | Loser applies its change ⇒ `.or_update`. |
| 8 | `submit_quiz` | same | `claim(…)` then update attempts on `.row` unconditionally | Progress is applied to the row whoever created it. |
| 9 | `ensure_field` | **none** for the business key | `NoArbiter` forces the issue: non-rolling cadences get `UNIQUE (cadence, starts_on) WHERE kind='open' AND state <> 'abandoned'`; rolling cadences use `serialize(session, "field", cadence)` | The hard one: the rolling-lobby invariant lives in timestamps (state goes stale). Needs the owning lane and a duplicate-count measurement before the index. If either fails: `unclaimed(why=…)` + `serialize`. |
| 10 | `create_floor_raise` | `min_build` unique | `claim(…).or_raise(ReleaseFloorDuplicateError(min_build))`; drop the pre-`SELECT` | |
| 11 | `watchlist add` | `uq_watchlist_user_ticker` | `.or_skip()` | |
| — | `ensure_portfolio` | §7.1 | | DEF499 |
| — | NAV writers ×2 | `uq_nav_user_run_date` (vacuous for NULL) | index per §7.1, then `claim(…).or_skip()` | the dead handler becomes live, then disappears |
| — | DEF220's six | various | badge / social cache ⇒ `.or_skip()`; device / edit-counter ⇒ `.or_update`; **mandate / overlay ⇒ `unclaimed(why="version-sequence retry-then-raise (DEF220), out of scope")`** | version-sequence logic untouched |
| — | `upsert_daily_bars`, `upsert_reference` | PK / composite | handled at the caller today ⇒ `ON CONFLICT DO UPDATE` (as `persona_telemetry.py` already does) or `claim().or_update()` | I did not read these two in depth. |

**Slices** (each a normal CR, laned):
1. **S0** migrations — index + dedupe (§7.1, §7.2).
2. **S1** land `ami_claim` + tripwire in **log mode** + `schema_truth` + observer report-only. No behaviour change; its output is the retrofit checklist.
3. **S2** convert in groups; the four `User` inserts alone, with an independent audit.
4. **S3** flip the tripwire to `raise` in CI and delete the P15 shape rule and its `_KNOWN`/`_UNREVIEWED` pins in the same commit (an exact pin of a thing that no longer exists is a stale-pin trap).
5. **S4** decide prod mode (§5.4).

**What S3 puts in the suite so "green" cannot mean "not checked":** (i) `get_engine()`'s engine carries the tripwire — a test asserts the listener is present; (ii) `schema_truth(Base.metadata) == []`; (iii) the `unclaimed(` token count and non-empty `why`s; (iv) a conftest hook fails the *session* if the observer saw `VACUOUS` (precision 1/1 in the dry run; `NO-ARBITER` stays report-only — §8.2); (v) a literal-grep test that `.merge(` does not appear in `app/` — `Session.merge` is a SELECT-then-INSERT inside SQLAlchemy that a read-side detector cannot see (zero uses today, so the ban is free; the tripwire still sees its INSERT).


---

## 8. Measured on the real tree

Setup: `prototype/observe_plugin.py` loaded into the **unmodified** backend suite (no repo file touched): tripwire in `log` mode, observer on. Result: **8774 passed, 9 skipped, 0 failed, 34m18s** — the hooks change no outcome. Raw output: `prototype/evidence/suite_dryrun.json`. (A first run with `traceback.extract_stack` in the hooks was ~4x slower and I killed it; the second uses `sys._getframe`. I did not take a clean no-plugin baseline on this loaded machine, so I cannot attribute the 34 min vs the documented ~8.5 min to the hooks versus the machine. The tripwire itself is one slice + one `startswith` per statement; the observer is test-only and should be opt-in in CI.)

### 8.1 Tripwire: the size of the decision surface

**46 distinct (table, application function) INSERT sites into 34 collidable tables**, versus the AST inventory's 20 + DEF499 + 2 caller-handled. That is the honest retrofit count: **~46 declarations, not 11**. Most are mechanical (`.or_skip()`, or `unclaimed(why=…)` for append-with-unique-key tables such as `journal_entries`, `career_events`, `notifications`, `ratio_baselines`, `verdict_outcomes`); the ones that need thought are §7.3's. I put this plainly because it is the main cost of the proposal: *the tripwire's rule is simple precisely because it does not try to decide which of these 46 is a race.* S1 (log mode) produces this list as the checklist before anything fails.

### 8.2 Observer: what it found with no knowledge of the answer

54 distinct read→insert observations: 23 `covered`, 24 `PARTIAL-KEY`, 6 `NO-ARBITER`, **1 `VACUOUS`**.
1. **The `VACUOUS` one is `sim_engine.ensure_portfolio` on `sim_portfolios (kind, run_id, user_id)` — DEF499, 728 hits**, found through the `_load_portfolio_row` helper that hides it from the AST rule. It was found without being told. That is the strongest single result here.
2. **`NO-ARBITER` (6), triaged honestly:** `sim_short_positions (portfolio_id, ticker, state)` from `open_short` — a business rule "one open short per ticker" with **no constraint**, not in any inventory (I read `open_short`, not its caller's check: *plausible, unverified*); `leagues (week)` from `_assemble_week` — no unique on week, real if the weekly roll can run twice (*plausible, unverified*); `room_runs (id)`, `sim_option_legs` ×2, `subscription_events` — I judge benign (status/log reads) but did not read each. So precision on `NO-ARBITER` is roughly 2 plausible of 6 — too low to gate on, hence report-only. Precision on `VACUOUS` is 1/1, small-n.
3. `PARTIAL-KEY` (24) is noise by design (version sequences, `max()+1`, per-user scans) and is not a gate.

### 8.3 The blind-spot-1 check

`prototype/evidence/coverage_check.py`: 43 constructor sites of collidable models in `app/`; the suite's tripwire saw an INSERT from **42** of them (matched at table+file granularity — a file with two sites of one table counts once, so this is slightly generous). Not executed: `BacktestRunIndexRow` at `room_runner.py:8028`.

### 8.4 Schema truth

`schema_truth(Base.metadata)`: 6 findings, listed in §7.2.

