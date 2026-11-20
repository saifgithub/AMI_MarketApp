# ISS001 — VERDICT

**Judged:** 2026-11-20 by a delegated judge agent (protocol step 6), all four folders read in full.
**Criterion (invite):** which design plausibly stops the 21st instance, and can a reviewer check that it does.
**Status:** recommendation. Implementation is a new CR (not CR185); the DEF308 unfreeze is the founder's call (§5).

---

## 1. Ranking

**sonnet5.5 > kimi-k2 > opus5.0 > gemini-3.6-flash.**

1. **sonnet5.5 — winner.** The only submission whose control checks that the constraint *works*, not just that one exists. Driver-level tripwire (no model inference, sees ORM/Core/text/bulk), `claim()` as the sanctioned atomic insert, `schema_truth()` over live metadata.
2. **kimi-k2 — runner-up.** Same reframe, best verification discipline (canary tests, three full-suite runs, shipped logs). Loses on one structural point: its collidable registry and `put()` trust any unique constraint to be effective.
3. **opus5.0 — instrument, not a control.** Best at producing facts (which sites execute, how often); explicitly detect-only; 40 flagged with ~15 known false positives.
4. **gemini-3.6-flash — rejected as designed.** Right direction, unmeasured, and its escape hatch recreates the problem.

---

## 2. What I verified (re-run, not trusted)

1. `sonnet5.5/prototype`: **19 passed** (0.85s). `mutate.py`: **6 killed, 0 survived**. Real-tree `schema_truth(Base.metadata)` returns **6 findings**, exactly as claimed, including `sim_portfolios.uq_portfolio_user_kind_run` (nullable `run_id` — DEF499's root cause) and `portfolio_nav_daily.uq_nav_user_run_date`. `collidable_tables` = **40** today.
2. `kimi-k2/prototype_guard.py`: **ALL 19 CHECKS PASSED**; `verify_registry.py` runs. Its note that apple_id/google_id are not unique is **stale**: DEF416 (`b51147f2`) added `uq_users_apple_id` / `uq_users_google_id`.
3. `gemini-3.6-flash/test_prototype.py`: **6 passed** (0.24s) — on 3 synthetic models only.
4. Not re-run: the full-suite observer/tripwire runs of opus5.0 / kimi-k2 / sonnet5.5 (8–35 min each). I checked their committed artefacts instead: `opus5.0/prototype/observations_full.json` contains `ensure_portfolio`; `sonnet5.5/prototype/evidence/suite_dryrun.json` has the tripwire (39), observer (54), `schema_truth` (6) sections it cites. Counts in the submissions are therefore *plausible, artefact-consistent, not re-measured by me*.
5. Staleness found while checking: DEF308 is **9** pinned sites now, not 11 (`_UNREVIEWED` in `test_p15_check_then_insert_guard.py`; apple/google fixed under DEF416). Sonnet5.5 noticed this; the others (written earlier) cannot have. The suite is now ~8.8k tests, not 4,223 (kimi's/opus's timings are from August).

---

## 3. DEF499 (instance #21) — honest check

DEF499: `sim_engine.ensure_portfolio`; `UNIQUE(user_id, kind, run_id)` never fires because `run_id` is NULL; two Alpha users hold duplicate training portfolios.

| Submission | Written | Would it have **flagged** the code? | Would it have **prevented the corruption**? |
|---|---|---|---|
| opus5.0 | before | Yes — its own run lists `ensure_portfolio` at 739 executions (hand-checked in the doc) | **No.** Remedy it prescribes is a savepoint + declared outcome. With a vacuous constraint the handler never runs; duplicates still land |
| kimi-k2 | before | Yes — measured it as a 21st/22nd/23rd instance | **No.** `put()` pre-checks, inserts in a savepoint, waits for `IntegrityError`. NULL `run_id` never raises. Silent duplicate. Kimi names "invariants not expressible as unique constraints" as out of scope, but did not see that an *existing* constraint can be vacuous |
| gemini-3.6-flash | before | Would raise at flush (it never ran on the real suite) | **No.** Same dead-handler problem. `OnConflict.SKIP` with `fetch_existing_fn` still races on NULL |
| sonnet5.5 | **after** (read DEF499's symptom text; says so) | Yes — observer status `VACUOUS`, 728 hits, found through the helper | **Yes, by two independent paths:** (a) `schema_truth()` flags the vacuous constraint statically, with no code executed; (b) `claim(key={..., run_id: None})` raises `NoArbiter` on first execution until a partial unique index exists |

Caveat the reader must hold: sonnet5.5 had the DEF499 symptom text, so "it catches DEF499" is partly by construction. What is *not* by construction: `schema_truth` also finds five *other* vacuous keys it was not told about (journal_entries, notifications, career_events, news_archive, portfolio_nav_daily), and the observer found DEF499 without the answer. The NAV table is live proof: `portfolio_nav_daily.py` has an `except IntegrityError` that the P15 guard counts as "handled" and that is dead code for `run_id IS NULL`.

**Finding that reshapes the problem (all four missed it before DEF499; only sonnet5.5 absorbed it):** the invariant is not "handle IntegrityError". It is *"a unique key the DB enforces, for this row's actual values, and an insert that goes through it atomically."* A handler can be satisfied by dead code.

---

## 4. Per-submission reasons

### 4.1 sonnet5.5 (1st)
Right:
1. Driver-boundary tripwire (`before_cursor_execute`): INSERT verb + table in schema-derived collidable set + no `ON CONFLICT` + no active sanction. Inputs are SQL text and metadata, both exact. Nothing to widen. Fails closed on an unparseable INSERT. Sees Core/text/bulk (tested), which kimi had to cover with method overrides.
2. `claim()` is atomic (`INSERT … ON CONFLICT DO NOTHING`): no savepoint, no poisoned transaction, no read-to-write gap. Strictly simpler than kimi/gemini's savepoint-and-recover `put()`/`safe_insert()`.
3. Arbiter validation (`NoArbiter`) makes "the constraint must really exist" a precondition of the sanctioned API — it absorbs the schema-side twin the STATE doc found.
4. `app_frames_only` option scopes the tripwire off test fixtures — answers the cost kimi hit (4,226 setup errors on first contact).
5. Mutation harness; install-test so "tripwire installed nowhere" is red; ban-by-grep for `.merge(`.
6. Honest measurement: ~46 declarations, not 11. Postgres behaviour labelled design-not-measurement.

Wrong / weak:
1. 46-site retrofit is the real cost; most are mechanical but the auth/`ensure_field` ones are not.
2. **Postgres unverified** (partial-index `ON CONFLICT` inference, 2-connection race). Must be settled before any prod-path conversion.
3. `ON CONFLICT` anywhere is trusted by the tripwire (own gap #5). `unclaimed(why=)` is reviewable, not enforced.
4. Observer is noisy (`NO-ARBITER` ~2/6, `PARTIAL-KEY` noise); correctly demoted to report-only except `VACUOUS`.
5. Suite timing (34 min) not attributable to hooks (no clean baseline).

### 4.2 kimi-k2 (2nd) — what to absorb
1. **Canary tests** that go red if the guard is deleted/muted ("neither failure was ever detected by the guard failing"). Sonnet has an install test; kimi's per-constraint-kind canaries are stronger. **Take them.**
2. **No env flag to turn the guard off** (CR040). Take for CI; prod mode is separate (§6.4).
3. Mandatory outcome with no default (`TypeError`). Sonnet's `.or_*` is equivalent; keep the "no default" rule.
4. Full-suite enforce measurement: the first sighting being `tests/conftest.py:66` is the proof the AST scope was latent-blind.
5. Three schema-side facts (verify_registry) — now partly resolved by DEF416.
Rejected from kimi: savepoint-based `put()` (more moving parts than `ON CONFLICT`; the per-site enum is already carried by `.or_*`); `GuardedSession` method overrides (the driver hook already sees bulk); raising in prod for an untested path (turns a working path into a 500).

### 4.3 opus5.0 (3rd) — what to absorb
1. Observer as an **instrument**, observe-first rollout, and its warning that aggregation must OR across branches (test-order-dependent verdicts are worse than incomplete ones). Sonnet's observer should be tested for that.
2. Its self-measurement (v1 useless at 62/70) is the right culture; its call to **keep the AST scanner** is the one disagreement with kimi/sonnet — see §6.5.
Rejected: detect-only (the brief wants prevention where cheap), and the savepoint-only "protection" notion — a savepoint around an insert guarded by a vacuous key protects nothing.

### 4.4 gemini-3.6-flash (4th)
1. `with_conflict_handler()` is a thread-local blanket bypass; any wrapped block passes with no check that a handler exists. It is the new "rename the function" escape.
2. `OnConflict.RAISE` permits direct insertion with no savepoint — the old pattern with a label.
3. Retrofit table is wrong at checkable points: `create_floor_raise` → SKIP (the code already raises `ReleaseFloorDuplicateError` on duplicate; SKIP would silently swallow), `ensure_field` → RETRY on `join_code` (that insert leaves `join_code` NULL; the key is not the business key), apple/google listed as open (fixed under DEF416).
4. Never run against the real suite (3 synthetic models), so its `before_flush`-on-everything rule has no measured fixture cost; kimi's measurement of the same rule shows 4,226 setup errors.
5. Right about one thing: the 4-outcome enum (shared by all submissions).

---

## 5. Recommended design (sonnet5.5 core + kimi canaries + opus observe-first)

Kind of control: **prevents** for any key the DB enforces (first execution in CI raises); **detects** (test-only) for keys with no constraint; **neither** for code no test runs.

Components, in `backend/app/db/`:
1. `ami_claim.py` — sonnet's `claim()`, `unclaimed(Model, why=)`, `arbiters()`, `collidable_tables()`, `schema_truth()`. Port from `sonnet5.5/prototype/ami_claim.py`.
2. Tripwire on the **app engine instance** in `get_engine()` (not the `Engine` class; alembic must stay unpoliced). `mode=raise` in tests, `log` in prod to start (§6.4). `app_frames_only=True` in tests.
3. Observer (test-only, opt-in in CI): gate only on `VACUOUS`; `NO-ARBITER` report-only. Aggregate across branches (opus).
4. Canary tests (kimi): per constraint kind (composite unique, unique column, natural PK, unique index, **partial/NULL key**) a bare insert must raise; deleting the hook, or breaking the registry, turns them red. Plus sonnet's install test and `schema_truth() == []` as a suite test.
5. Literal-grep pins: `unclaimed(` count and non-empty reasons; `.merge(` absent from `app/`.

**Founder decisions this triggers (recommendations):**
1. **Unfreeze DEF308 — recommended, but only after Phase 1 lands.** The freeze exists so the 11 (now 9) sites remain the proving ground. After Phase 1 the tripwire in log mode *is* that proof (they must appear in its output). Unfreeze at the moment Phase 1's acceptance is green, then convert in Phase 3. Until then nothing in Phases 0–2 touches them.
2. **Retire the AST scanner at S3** (sonnet/kimi), not keep it (opus). Reason: once the tripwire runs in CI the scanner adds a green that means "not checked" and its pins block cleanup. Interim: keep it unchanged through Phases 1–2 as a backstop. This is a standing-cost call and Saiful's (STATE decision 3).
3. Prod mode `log` vs `raise` (sonnet §5.4). Recommend `log` + a stable log key the bug-monitor reads, flip to `raise` on Alpha once CI has been green two weeks. Saiful's call.
4. DEF416 already resolved the apple/google uniqueness question (STATE decision 4 is closed for those two). `device_user_id` and `ensure_field` arbiters remain a product decision.

### Phases (smallest first)

**Phase 0 — DEF499, independent of the mechanism (can run in parallel).**
1. Read-only preflight SQL on melehost (sonnet §7.1), needs Saiful's explicit go.
2. Migration: dedupe rule (abort naming ids if the loser has children) + partial unique indexes `(user_id, kind) WHERE run_id IS NULL` on `sim_portfolios` and `(user_id, as_of_date) WHERE run_id IS NULL` on `portfolio_nav_daily` (both `postgresql_where` and `sqlite_where`).
3. `ensure_portfolio` → `claim(...).or_skip()` once Phase 1 exists; until then the index alone turns the silent duplicate into a loud `IntegrityError`. Deleting rows is a prod write — Saiful's go.

**Phase 1 — the control, observe-only. No frozen site touched. (The first phase.)** See §7.

**Phase 2 — close the other `schema_truth` findings.** One decision per finding from the owning lane: `info={"null_means_no_key": "<why>"}` on the column, or a partial index. Four are expected "NULL means no dedupe" (journal_entries, notifications, career_events, news_archive). Convert the non-frozen sites the measurement found: `sim_engine._apply_buy_row`, `league_service._assemble_week`, NAV writers, the 5 caller-handled beyond-inventory sites, and test fixtures (via one stamped seeding helper or `app_frames_only`).

**Phase 3 — retrofit DEF308 (needs the unfreeze).** Order: four-`User`-site group first, alone, `GATE: independent` (the auth path); then the lessons/watchlist/desk/release-floor sites; `ensure_field` last (needs `NoArbiter` resolved: partial unique index for non-rolling cadences, `pg_advisory_xact_lock` for rolling; measure duplicates first). Outcome per site as in sonnet §7.3, with `create_floor_raise` = `.or_raise(ReleaseFloorDuplicateError)` and `ensure_anonymous` = `unclaimed(why="fresh uuid4 mint")`. Mandate/overlay stay hand-written under `unclaimed(why=version-sequence…)` (out of scope).

**Phase 4 — flip to enforce, retire the P15 shape rule** and its `_KNOWN`/`_UNREVIEWED` pins in the **same** commit (a pin of a deleted rule is a stale-pin trap). Add the guard to P15 in `failure_patterns.md` and update DEF220/DEF308/DEF499 rows. Decide prod mode.

---

## 6. What this design still misses (named)

1. **Code no test ever executes.** The tripwire fires on execution. Measured by sonnet: 42/43 collidable constructor sites executed by the suite (one counter-example, `BacktestRunIndexRow`). Prod `log` mode names such a path on first real use; it does not stop it.
2. **A business key with no constraint and no same-session read** (blind insert assuming uniqueness). No metadata says it matters. A read in a *different* session (helper opening its own `get_session()`) also escapes the observer.
3. **Hand-written `ON CONFLICT (wrong_cols)`** passes the tripwire. Cheap hardening not yet built: require the conflict target to match an arbiter. Put this in Phase 1.
4. **Wrong outcome choice passes every control** (e.g. SKIP where an update was needed). Review act; the control only makes the choice mandatory and diff-visible.
5. **`unclaimed()` abuse and a mis-declared `null_means_no_key`** — visible in the diff, still human review.
6. **Raw driver writes outside the app engine** (COPY, the separate `ami_website` role, triggers).
7. **Postgres semantics are unmeasured** for `claim()` (partial-index inference, READ COMMITTED re-read, true 2-connection race). A gate, not a footnote: Phase 3 may not convert a prod path before this is run on a throwaway schema.
8. **The vacuous-key check is NULL-only.** Other ways a constraint can fail to guard the real invariant (case-sensitivity: `email` normalisation; functional keys) are not covered. `claim()` normalising case before the key is a per-site item in Phase 3.

---

## 7. First phase — implementable now, touches no frozen site

**Phase 1 acceptance-scoped work order** (a normal CR; reference ISS001, DEF499):
1. Port `sonnet5.5/prototype/ami_claim.py` to `backend/app/db/ami_claim.py` (new file with docstring); add the arbiter-target check for hand-written `ON CONFLICT` (§6.3).
2. Install the tripwire in `get_engine()` on the engine instance, `mode=log` in prod, `mode=raise` + `app_frames_only` when a test flag is set; **no frozen site edited and no `_UNREVIEWED` change**.
3. New tests: `test_iss001_canaries.py` (kimi-style: per constraint kind incl. the NULL-key case; red if hook removed), tripwire-installed test, `schema_truth` test that **pins the 6 current findings as an owned list with owners, so a 7th fails and a resolved one forces removal** (not a silent allowlist).
4. Observer plugin as an opt-in CI job (report-only except `VACUOUS`); output JSON committed to the CR folder as the retrofit checklist.
5. Output: the log-mode report listing every un-claimed insert site — which must contain all 9 DEF308 sites and `ensure_portfolio`, or Phase 1 has failed.

**Acceptance (how a reviewer checks):**
1. `pytest backend/tests/unit/ -q` **full suite** green (refactor rule; do not run targeted only), with the tripwire on in `log` mode: zero outcome change vs baseline; take a clean no-plugin baseline timing, which sonnet did not.
2. Canaries: delete the `event.listen` line → canaries red. Mutation harness (`mutate.py` adapted to the ported module): 0 survivors.
3. The report contains the 9 DEF308 sites + `ensure_portfolio` + `_apply_buy_row` + `_assemble_week` (all three submissions' independent discovery). `schema_truth` yields exactly the 6 pinned findings.
4. **Write a deliberately unguarded new insert on a collidable model via a factory function, in a branch, and show the suite fails by execution** (the audit move that beat v1). Repeat for a vacuous-NULL composite key.
5. Aggregation test: same site reached on two branches in either order gives the same verdict (opus's lesson).
6. Postgres: one run of sonnet's thread test on a throwaway schema on melehost (read-only apart from one rolled-back txn) — needed before Phase 3, ideally done in Phase 1. Needs Saiful's go.
7. `test_config_compose_parity.py` green if any new env setting (prod mode) is added; forward it in `docker-compose.yml`'s `api-alpha` block.

**Dependency weight:** none. SQLAlchemy events and dialect `insert` only; stack stays lean.

**Effort shape:** one ~430-line module, ~3 lines in `session.py`, one test file, observer plugin. Phase 3 (~46 call sites + migrations) is the real cost and the reason for the founder unfreeze decision.

---

## 8. What each losing idea was right about (protocol step 6)

1. opus5.0: measurement beats reasoning about it (62/70); the observer is the only thing that produced facts; caller-frame handlers are where the AST is better.
2. kimi-k2: guard must fail when removed; mandatory outcome; run the real suite in enforce mode; check the schema, not the brief.
3. gemini-3.6-flash: the four outcomes are the enum; nothing structural beyond that.
4. All four: widening the scanner a fourth time was the wrong move, and the 21st instance is already in the tree.
