# ISS001 — kimi-k2 submission

**Independence statement:** I read the problem statement, `DILEMMA_PROTOCOL.md`, the invite
prompt, and the repo (backend code, models, guards, defect rows, tests). I opened **no** other
contributor's folder. Everything below is derived from the repo and from the runnable artifacts in
this folder, all of which I executed on this machine.

---

## 0. The reframe the evidence is asking for

Three guard versions failed the same way: each was a **grammar** for recognising check-then-insert
in source text — by name (v1), by inline shape (v2), by variable binding (v3). Each widening covered
the instance just found, not the pattern, because *the set of Python constructions that land a row in
a session is unbounded* (factories, helpers, comprehensions, `add_all`, `merge`, bulk APIs, Core
`insert()`, raw SQL — and the next refactor nobody has thought of yet). A v4 dataflow rule is the
same bet with longer odds. This is P16 exactly: rules validated against their motivating examples.

The pattern is not a property of source text. It is a **runtime event**: an INSERT reaching a table
that has a uniqueness constraint, without a declared collision outcome. That event has a closed,
enumerable set of doors:

| Channel | How a row reaches the DB | Status in `backend/app/` today (grep-verified) |
|---|---|---|
| ORM `add` / `add_all`, any syntax | object enters `session.new` → flush | the only insert style in use (~all sites) |
| `session.merge()` | insert arm lands in `session.new` | zero usage |
| Core `session.execute(insert(...))` | ORM-enabled execute | zero usage |
| `bulk_insert_mappings` / `bulk_save_objects` | **fires no session event** (measured, §4) | zero usage |
| `text("INSERT ...")` / driver SQL | raw string | one `text()` in the tree: `SELECT 1` |

A control attached to those doors cannot be dodged by syntax, because there is no syntax in it.

---

## 1. The proposal — three pieces, one registration point

### 1.1 A collidable-model registry derived from the schema, not parsed from source

`backend/app/db/collidable.py` (new, ~60 lines): walk `Base.metadata`; a table is collidable if it
has a `UniqueConstraint`, a unique `Index`, a `unique=True` column, or a defaultless (natural)
primary key — the same rule the AST guard encodes, but computed from the schema SQLAlchemy actually
enforces. `verify_registry.py` runs this against the real models: **32 collidable tables, exactly
the detector's measured 32** — with no AST, no drift surface, and it widens itself: the day anyone
adds a model with a unique constraint, it is in the registry at next import. The one kind of
widening this control needs is the kind that happens automatically.

### 1.2 Enforcement at the flush chokepoint (`GuardedSession`)

Three lines in `app/db/session.py:get_engine()`, beside the only sessionmaker (which the test
fixture also rebuilds — so the whole suite runs guarded for free):

- `before_flush`: for each object in `session.new`, if its class is collidable and it does not carry
  the `_ami_put_managed` stamp (see 1.3) → raise `UnmanagedCollidableInsertError` naming the model,
  the constraint columns, and the fix. Fires at explicit flush **and** at commit (verified —
  `autoflush=False` is this codebase's default, and the hook catches both).
- `do_orm_execute`: Core `insert()` into a collidable table is blocked outright, with a
  `session.info` opt-in flag for reviewed scripts.
- `bulk_insert_mappings` / `bulk_save_objects`: **measured on 2.0.49 — they fire no session event
  at all, and `after_bulk_insert` was removed in SQLAlchemy 2.0.** So they are banned structurally:
  `GuardedSession(Session)` overrides the two methods to raise unless the opt-in flag is set. Two
  named, grep-stable methods, overridden — no grammar involved. (The 2.0 migration path is Core
  `insert()`, which the `do_orm_execute` hook does see.)
- `session.merge()`: check-then-insert packaged as an API; its insert arm lands in `session.new`
  and is caught by the flush hook (verified). Merge-updates of persistent rows are untouched.

No enable/disable env flag. A flag is how this class of control rots silently (CR040), and the
canary (1.4) makes removal visible anyway.

### 1.3 `put()` — one helper, four declared outcomes

```python
put(session, Model, *, key={...}, values={...}, on_collision=<mandatory>,
    on_update=fn, retry=fn, conflict_error=SomeDomainError(...)) -> (row, created)
```

- Pre-check SELECT (kept: it is the fast path, and every site already writes it).
- Insert inside `begin_nested()` — **always**, because the load-bearing lesson of DEF220 is that
  several sites run inside a caller's transaction with uncommitted state (`_claim_or_create` has the
  challenge-consume pending; `ensure_desk_users` loops six inserts; `ensure_field` runs inside tick
  loops). Remembered rules are what failed; the savepoint becomes structural.
- On `IntegrityError`: the loser's pending INSERT is expunged (so the outer commit can never
  re-attempt it — verified end-to-end), then the declared policy runs:
  - `SKIP` — re-read the winner, return `(row, False)`. (badge, cache, desks, activations)
  - `RE_READ_AND_UPDATE` — re-read the winner, apply `on_update(row)`. The loser still lands its
    change. (device re-key, quiz attempt merge, edit counter)
  - `RETRY_THEN_RAISE` — `retry(session)` recomputes key/values from now-visible state; one more
    attempt; a second collision raises the named `conflict_error`. (mandate/overlay version
    sequences — already fixed under DEF220; `put()` hosts their shape, their tests stay the pin)
  - `RAISE` — raise the site's domain error (`ReleaseFloorDuplicateError` → 409, not a naked 500).
- `on_collision` has **no default**. Forgetting to think is a `TypeError`, not a silent skip.
- The policy is chosen **per call site**, not per model — §3.5's constraint. `AgentActivationRow`
  legitimately wants SKIP in `_check_agent_unlocks` and re-read-return in `grant_activation`.

A batch variant `put_many(..., on_collision=SKIP)` serves the two caller-handled batch sites
(price history, ticker reference) — per-row savepoints, per-row created flags, so a raced row is
skipped individually and the returned counts stay truthful (today a lost race marks the whole
refresh `skipped_concurrent`; with `put_many` the other ~13k rows land).

This also repairs §3.4. After the retrofit, every file a coder opens to copy house style shows
`put(...)` with a named outcome. The inverted docstring dies with `_upsert_user_device`'s rewrite.
Local, precise, and correct is what beats background knowledge — so make the local text the safe one.

### 1.4 The control carries its own proof: canary tests

The killer detail in the brief: *"Neither failure was ever detected by the guard failing."* So the
shipped CR includes `test_iss001_guard_fires.py`:

- For each constraint kind (composite unique, unique column, natural PK, unique index): bare
  `session.add(...)` **must** raise `UnmanagedCollidableInsertError`. If the hook is deleted,
  muted, or the registry derivation breaks, these tests go red. The guard has to fail when the
  pattern is present — the property no AST version ever had to demonstrate.
- Grammar-freedom pins: inline add, variable-bound add, factory-built add, `add_all` comprehension,
  Core `insert()`, bulk, merge — all must raise (mirrors prototype checks B1–B5, I, M1–M3).
- Registry parity: the derived set must contain known members (`users`, `badges`, …) and the count
  is logged at boot. The set is designed to grow (P6b), so the test asserts a floor plus known
  members, and the boot log line makes every widening visible.

**Fate of the AST guard:** keep it exactly as-is until the DEF308 retrofit lands (its exact pin is
what freezes the 11 sites). Once the runtime hook is live and canary-green, retire the shape rule:
post-hook, its green means "not checked" while contributing nothing the canary doesn't cover, and a
green that means "not checked" has already cost a week twice. Its name-rule sibling goes with it.

---

## 2. Prevents, detects, or makes impossible — precisely

- **Makes impossible to execute unexamined:** an unmanaged collidable insert raises at the flush, on
  first execution, in any environment — test, dev, or prod. The 21st instance can still be *typed*
  (nothing short of removing `session.add` from the language stops that); it cannot *run* without
  producing a named, instructive error.
- **Detects at the moment of commission:** the error fires before the constraint, on the first run,
  even with no race — the detector is the code's own execution, not a parser.
- **Prevents the harmful outcome:** every collidable insert that does run carries a declared,
  reviewed collision outcome implemented correctly once (savepoint, recovery, expunge), instead of
  hoping twenty sites each remembered.

It also unlinks DEF200 from DEF308 structurally: the day properly-threaded handlers (or a second
Cloud Run instance) arrive, every site is already routed through a declared outcome — the arming
event stops existing. And it leans on the database's constraint plus per-transaction savepoints, so
it is correct under N workers and N instances, unlike the per-process throttle that accidentally
protects Alpha today.

---

## 3. Per-site differences (§3.5) — handled by construction

DEF220 proved the correct collision behaviour differs per site and produced four answers. Those four
*are* the enum. The helper is where the subtle parts live once — savepoint placement, loser
expunge, winner re-read — and the call site carries exactly one decision: which outcome. The
retrofit table (§6) assigns each of the 16 sites its outcome; the spread across all four policies in
sixteen sites is itself the argument against any blanket behaviour.

---

## 4. How a reviewer verifies every claim

All artifacts are in this folder and were executed on this machine:

1. **Mechanism** — `prototype_guard.py` (SQLAlchemy from `backend/.venv`, synthetic models mirroring
   every constraint kind in `models.py`). Run:
   `backend/.venv/bin/python docs/dilemmas/ISS001_DB_INSERT_RACE/kimi-k2/prototype_guard.py`
   Result when run: **19/19 checks pass**. Including: unmanaged inserts blocked under four different
   syntaxes (inline / variable-bound / factory / comprehension) and at commit-time; the race
   reproduced deterministically on the unguarded factory (DEF220's `BlindOnce` technique, no flaky
   threads); each policy's recovery behaviour; Core/bulk/merge channel behaviour; the outer-commit
   cleanliness proof after recovery; overhead measurement.
2. **The phenomenon** — `demo_race.py` (stdlib sqlite3 only):
   `python3 docs/dilemmas/ISS001_DB_INSERT_RACE/kimi-k2/demo_race.py`
   Result: without a handler the loser eats `IntegrityError` in **20/20** barrier-widened trials;
   with the declared outcome, 0 errors and 20/20 recoveries. This is the post-DEF200 / Cloud Run
   shape: two connections, one constraint, no accidental serializer.
3. **Registry truth on the real schema** — `verify_registry.py`:
   derives **32/32** against the AST guard's measured 32, exit 0, and prints the `users` collision
   keys — which exposes the schema finding in §5.1.
4. **The suite-as-detector measurement** — `iss001_guard_plugin.py` arms the flush hook over the
   real 4,223-test suite with zero retrofit (`pytest -p`, no repo file modified). Two modes, both
   actually run on this machine (logs: `baseline_run.log`, `guarded_run.log`, `observe_run.log`):
   - **Enforce mode** (raise on unmanaged collidable insert): `cd backend && PYTHONPATH="docs/dilemmas/ISS001_DB_INSERT_RACE/kimi-k2:$PWD" .venv/bin/python -m pytest tests/unit -q -p iss001_guard_plugin`
   - **Observe mode** (record a histogram, never raise): same command, current plugin file.
   Measured numbers: **see §8.**
5. **Cost** — prototype check L: 3,000 insert+flush cycles of an append-only model, guarded vs
   unguarded sessionmaker: **×1.03** on sqlite `:memory:`. The hook is a dict lookup over
   `session.new`; append-only paths are untouched by construction.
6. **Post-CR acceptance** — full suite green with the hook armed; canary file red-if-removed;
   DEF308's 11 pins deleted from `_UNREVIEWED` as each site converts; a deliberately-written
   unguarded site (the audit move that beat v1) now fails the build by *execution*, not by matching.

---

## 5. What this solution will miss — stated, not discovered later

### 5.1 Schema-side blind spot the inventory itself has wrong

Measured via `verify_registry.py` against `models.py:73-76,121,168,197`:

- `users.apple_id` and `users.google_id` are **not unique** (plain nullable columns). The brief's
  inventory says "apple_id unique"/"google_id unique" — that is not today's schema. Two concurrent
  first-time Apple sign-ins with no email claim produce **two user rows with the same `apple_id` and
  no error at all** — silent duplicate identity, strictly worse than a 500, and invisible to every
  IntegrityError-shaped control including this one. Same class: `ensure_anonymous` races on
  `device_user_id` (index-only) produce duplicate anonymous accounts silently, and
  `ensure_field` has **no constraint on `(cadence, kind, starts_on)`** — the detector flags it via
  the `join_code` unique, which that insert leaves NULL; a lost race there is two live game fields,
  not an IntegrityError.

  **Consequence:** the invariant has a schema-side twin nobody stated — *every collision surface must
  actually have a constraint*. The retrofit therefore includes three small Alembic migrations:
  unique on `apple_id`, `google_id` (with a duplicate pre-check), and a partial unique index for the
  one-live-field-per-cadence rule (precedent for partial uniques: `journal_entries`,
  `career_events`, `game_duels`). `device_user_id` uniqueness is flagged as a product-identity
  decision for the CR, not assumed. Until these land, those three hazards are outside any
  IntegrityError-based control's reach — including this one. This is my largest named gap.

### 5.2 The runtime blind spots

1. **Paths never executed anywhere.** The hook fires on execution. A collidable insert on a path
   with no test and no Alpha traffic stays dormant until first run — but its first run anywhere is
   loud (and pre-constraint), whereas today its first *raced* run is a raw 500. Residual, bounded by
   suite coverage, shrinking as coverage grows. The AST guard's blindness was unbounded *and its
   green asserted otherwise*; that asymmetry is why I retire it rather than keep both.
2. **Raw SQL.** `text("INSERT INTO ...")` with the table name in a literal is greppable (advisory CI
   check; today exactly one `text()` call exists and it's `SELECT 1`). SQL built by string
   concatenation, or a future direct-psycopg2 connection, escapes every layer here. Named, owned by
   code review. Malice is out of scope; the failure history is habit.
3. **Wrong policy choice passes every control.** The hook forces a *declared* outcome; it cannot
   force a *correct* one. `submit_quiz` retrofitted as SKIP passes everything and silently drops a
   quiz attempt the user made. What the control buys: the choice is a mandatory, one-line,
   diff-visible argument (`on_collision=SKIP`) instead of an absent thought. That decision remains a
   review act — no mechanism at this layer can change that, and any submission claiming otherwise is
   overselling.
4. **Stamp forging.** `_ami_put_managed` is a Python attribute; hand-setting it bypasses intent.
   That is sabotage, not habit — code review's job, like deleting a test.
5. **Post-recovery lost-update window.** `RE_READ_AND_UPDATE` re-reads under READ COMMITTED; a third
   writer between re-read and commit is the standard lost-update anomaly — a different failure class
   (isolation level), named here so it is not "discovered" later, deliberately not solved in this
   proposal.
6. **Invariants not expressible as unique constraints** (e.g. "at most one live field per cadence"
   *before* the partial index lands) are outside this control entirely.

---

## 6. Retrofit plan — the 11 open sites, the two caller-handled ones, and the three the measurement found

Order: (1) ship `collidable.py` + `GuardedSession` + `put()` + canaries; suite must show failures
concentrated at known sites (the §8 measurement is the baseline); (2) convert sites in dependency
order below; (3) delete each `_UNREVIEWED` pin as its site converts (the pin going stale fails the
build — by design); (4) retire the AST shape rule; (5) the three schema migrations ride the same CR
as gated sub-decisions.

| # | Site | Key (conflict target) | Policy | Notes |
|---|---|---|---|---|
| 1 | `auth_service._claim_or_create` | `users.email` (fallback `id`) | RE_READ_AND_UPDATE | on_update = adopt winner + `_rekey_devices_to`; savepoint is load-bearing (challenge-consume pending in the same txn) |
| 2 | `auth_service.ensure_anonymous` | fresh uuid PK | RETRY_THEN_RAISE (re-mint uuid) | practically unreachable; the written-down answer is the point. `device_user_id` silent-dup hazard → product decision (5.1) |
| 3 | `auth_service.sign_in_with_apple` | `users.apple_id`, then `email` | RE_READ_AND_UPDATE | **requires** the `apple_id` unique migration; on_update attaches `apple_id` to the winner |
| 4 | `auth_service.sign_in_with_google` | `users.google_id`, then `email` | RE_READ_AND_UPDATE | same shape as Apple |
| 5 | `games_desks.ensure_desk_users` | `users.desk_key` | SKIP → return winner's id | savepoint **per desk**, inside the 6-iteration loop (DEF220's `_check_agent_unlocks` lesson); also collides on `handle` |
| 6 | `lessons_service.grant_activation` | `(user_id, agent_id)` | SKIP → return existing | already idempotent-by-SELECT; loser gets exactly what the found-branch returns |
| 7 | `lessons_service.mark_started` | `(user_id, lesson_id)` | RE_READ_AND_UPDATE | on_update sets `started_at` if null — same as the else-branch |
| 8 | `lessons_service.submit_quiz` | `(user_id, lesson_id)` | RE_READ_AND_UPDATE | on_update = the quiz-merge (bump attempts, OR passed, set score/completed_at). The site where SKIP would silently drop a user action |
| 9 | `games_service.ensure_field` | `(cadence, kind, starts_on)` | RE_READ → return winner | **requires** the partial-unique-index migration first (5.1); until then no IntegrityError exists to recover from |
| 10 | `client_release_floor.create_floor_raise` | `min_build` | RAISE → `ReleaseFloorDuplicateError` | converts a raced duplicate from 500 to the designed 409 |
| 11 | `watchlist_store.add` | `(user_id, ticker)` | SKIP → return winner | also replaces the old-style full-`rollback()` handler with the savepoint idiom |
| 12 | `price_history.upsert_daily_bars` | `(ticker, date)` | `put_many` SKIP | deletes the caller's try/except + the hand-maintained `_HANDLED_AT_CALLER` allowlist entry; re-read stays |
| 13 | `ticker_reference.upsert_reference` | PK `symbol` | `put_many` SKIP | per-row created flags → counts stay truthful instead of whole-batch `skipped_concurrent` |
| 14 | `sim_engine.ensure_portfolio` | `(user_id, kind, run_id)` | SKIP → return winner | **found by the §8 measurement**, not by any guard version — cross-frame read. Game-entry hot path |
| 15 | `sim_engine._apply_buy_row` | `(portfolio_id, ticker)` | RE_READ_AND_UPDATE | **found by the §8 measurement** — in-memory "check" over `p_row.holdings`. On_update = the weighted-average merge the else-branch already is. Trading hot path |
| 16 | `league_service.weekly_roll` / `_assemble_week` | `(user_id, week)` | SKIP (per member row) | **found by the §8 measurement** — scheduler path, unguarded today |

The five already-handled beyond-inventory sites (`enter_field`, `award`, `freeze`, `post_career_event`, the two `app/api/` handlers) convert to `put()` opportunistically within the same CR — each conversion deletes a hand-rolled handler and one more wrong thing to imitate — or are stamped as reviewed; either way they join the registry's coverage. Test fixtures route through one stamped seeding helper.

The seven DEF220-fixed sites convert mechanically to `put()` with their already-chosen outcomes
(device, counter → RE_READ_AND_UPDATE; mandate, overlay → RETRY_THEN_RAISE with their named conflict
errors; badge, cache → SKIP). Their eight behaviour tests remain the pin — they exercise the real
constraint, which `put()` still hits.

Estimated shape of the CR: one new module (~150 lines), three lines in `session.py`, one canary
test file, sixteen call-site rewrites (most shrink), one stamped fixture-seeding helper, three
migrations, one guard deletion. No new dependencies — SQLAlchemy events are already in the stack.

---

## 7. What it costs the next developer, and how it fails when wrong

- **Ordinary insert into an append-only model:** nothing changes. `session.add` + flush as today;
  measured overhead ×1.03. 16 of the 48 tables are non-collidable — among them the high-volume
  append-only ones (room runs, trades, audit rows) — and the hook costs them one dict lookup per
  new object.
- **Insert into a collidable model:** one helper call and one explicit outcome choice. Write the old
  pattern from habit and the **first execution anywhere** raises
  `UnmanagedCollidableInsertError: User unique_keys=[('desk_key',), ('email',), ('handle',),
  ('phone',)] — go through put(session, User, key=..., on_collision=...)`. Loud by construction;
  there is no silent mode, no flag, no "green means unchecked".
- **When the control itself is wrong** — registry over-flags a model whose insert "can't collide"
  (the `ensure_anonymous` fresh-uuid case): the developer does not work around it; they write
  `put(..., on_collision=RETRY_THEN_RAISE)` and one line of reasoning. The escape valve *is* the
  declaration, so the workaround is the reviewed artifact. Contrast with today, where the escape
  from the AST guard is renaming a function.
- **When the control is removed:** the canary file goes red. Every previous version of this guard
  could be widened past or deleted without any test noticing; this one cannot.

---

## 8. Measured suite results (real backend, hook armed, zero retrofit)

All three runs on this machine, `backend/.venv`, sqlite tempfile fixtures. Logs are in this folder.

**Baseline (no plugin):** `4223 passed, 3 skipped in 500.51s`, exit 0.

**Enforce mode (hook raises on every unmanaged collidable insert):** all 4,226 tests errored at
setup in 343s. The very first fixture fires it: `tests/conftest.py:66` seeds `TickerReferenceRow`
(natural PK) with a bare `session.add`. Two readings. (a) The hook works on the real stack with
zero code change — one global listener, and the whole suite is covered because every session flows
through it. (b) Its *first sighting* is a site the AST guard structurally cannot see: the detector
scans `app/services/` only, and this is a collidable insert in `tests/`. The stated latent weakness,
demonstrated on first contact. (Post-retrofit, fixtures go through a stamped seeding helper; that
helper is one function, and converting ~40 fixture sites is mechanical.)

**Observe mode (hook records, never raises):** `4223 passed, 3 skipped in 493.12s`, exit 0 — the
observer is invisible to a green suite. 117 distinct `(model, origin)` insert sites recorded. The
map:

- **Every pinned site is exercised.** 11/11 DEF308-open sites appear with their exact service
  frames (`auth_service.py:461/646/742/798`, `games_desks.py:381`, `lessons_service.py:564/624/830`,
  `games_service.py:435`, `client_release_floor.py:232`, `watchlist_store.py:71`); 8/8 DEF220-fixed
  inserts; 2/2 caller-handled sites. The suite-as-detector claim is therefore not aspirational: a
  regression at any known site executes the hook.
- **Three unguarded app sites the AST guard has never seen, in one run:**
  - `sim_engine.ensure_portfolio` (`sim_engine.py:714`) — check-then-insert on
    `SimPortfolioRow(uq_portfolio_user_kind_run)`, **no IntegrityError handler anywhere in the
    file**. Invisible to v3 because the SELECT lives in `_load_portfolio_row`, another function —
    the rule is intra-function. Called from `enter_field`, the game-entry hot path.
  - `sim_engine._apply_buy_row` (`sim_engine.py:2412`) — check-then-insert on
    `SimHoldingRow(uq_holding_portfolio_ticker)`, no handler. Invisible because the "check" is an
    in-memory scan of `p_row.holdings` — there is no `select(Model)` in the frame at all. The
    trading hot path.
  - `league_service.weekly_roll`/`_assemble_week` (`league_service.py:141/211`) — `LeagueMemberRow`
    inserts in a nested loop, no handler in the file. Scheduler-only today — a deployment fact, the
    same caveat as the rest.
  These are the 21st/22nd/23rd instances — already written, sitting in the tree. Three versions of
  the source guard never saw them; one 8-minute runtime pass did. That is the whole argument for
  moving the control off source text.
- **Five already-handled sites outside the pinned set**, confirming the true footprint exceeds 20:
  `games_service.enter_field`, `reputation_service.award`/`freeze`/`_award_badge`,
  `career_ledger.post_career_event`, and two in `app/api/` (`daily_challenge.attempt`,
  `webhooks.revenuecat_webhook` — the money-path idempotency key) that sit **outside the guard's
  scan scope entirely**.
- **~40 test-side sites** (conftest seeding, `_make_*` fixtures), invisible to any `app/`-scoped
  scan by design.

Attribution caveat, stated rather than discovered: commit-time flushes attribute to the innermost
`app/` frame, which is the `get_session()` plumbing (`session.py:82`) rather than the true call
site — 25 model buckets land there. Explicit-flush sites (every pinned site) attribute exactly.
Refining attribution means skipping plumbing frames; not needed for the claims above.

**Overhead:** prototype check L measured ×1.03 on 3,000 insert+flush cycles; the observe-mode suite
ran 493s vs baseline 500s (noise — and observe mode pays a stack walk per collidable insert, which
enforce mode never does).

---

## 9. Alternatives considered and rejected

- **v4 AST / dataflow guard.** Same bet as v1–v3 with a wider grammar. P16 says what happens; the
  next construction is one refactor away, and its green would again assert coverage it doesn't have.
- **Global `IntegrityError` → domain-error middleware.** Detection, not prevention; cannot express
  retry-with-recomputed-version or per-site update callbacks (they need application context); the
  loser's work is still silently dropped behind a nicer status code.
- **Postgres `ON CONFLICT` as the house idiom.** The right mechanism for SKIP and simple updates,
  and available to `put()` internally later if profiling ever justifies it. As the *control* it
  fails the same way the guard failed: a site that doesn't use the idiom is still unmanaged, and the
  dialect split (sqlite tests / postgres alpha) doubles every code path for zero behavioural gain at
  this load profile.
- **Process: PR checklist, required label, documented rule.** Empirically dead — three landings in
  six days with the rule written down, the guard green, and a defect open. The audience never asks
  the question at all (P14's lesson about acceptance lists applies: what isn't structural is
  optional in practice).
- **Concurrency fuzz harness.** Detection bounded by site enumeration — the same flaw as the AST
  guard, with flakiness added (the auditor's 0/60 measurement is why). Useful once, as a retrofit
  acceptance exercise; useless as the standing control.
- **DB-only (triggers / serializable everywhere).** Serializes the hot path to fix a rare event,
  changes isolation semantics app-wide, and still can't express per-site outcomes. Wrong layer.

---

## 10. Why this one doesn't get widened three times

The three historical widenings patched a *recogniser's grammar*. This control enumerates two closed
sets instead: **models**, derived from the schema (self-widening, and `verify_registry.py` proves
the derivation matches reality 32/32), and **insertion channels**, which SQLAlchemy closes for us —
`session.new` at flush, ORM-execute inserts, two named bulk methods (banned by override because they
provably fire no event), and raw SQL as a named residual. A future bypass requires a *new channel*,
not a new spelling — and new channels arrive as SQLAlchemy upgrades, which the canary suite
exercises on every run. The arms race ends because there is no grammar left to extend.

The §8 measurement is the empirical proof that this framing is the right one: asked to map the
pattern on the *real* suite, the runtime view immediately surfaced three unguarded sites that three
versions of the source guard never saw — one because the read lives in another function, one
because the read is an in-memory collection scan, one outside anyone's scan path. The next instance
of this class has always come from outside the previous rule's grammar. So the rule stops having a
grammar.

And the honest version of the goal: the 21st instance cannot be stopped from being **written**. It
can be stopped from ever running unexamined — and the moment it runs, the error message teaches the
fix. That is the property "documented rule + green guard + open defect" demonstrably lacked.
