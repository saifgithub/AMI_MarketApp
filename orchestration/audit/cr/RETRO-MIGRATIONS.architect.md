<!--
RETRO-MIGRATIONS.architect.md — audit lane. State derives from round numbers here vs
RETRO-MIGRATIONS.auditor.md. RETROACTIVE audit under programme CR231 / decision D-072
(2026-09-24): six weeks (2026-08-13 -> 09-24) of largely-unaudited work is being brought under
independent audit before external beta opens. This lane is CR231's Phase 1 lane 4 ("MIGRATIONS —
single alembic head, plus a fresh-DB upgrade from base to head. Covers DEF337, DEF406, DEF411 and
the CR219/CR222 migrations"). GATE: independent. This submission is not a build; it is the record
assembled for the auditor to verify migration-chain integrity that was never independently
checked.
-->

# RETRO-MIGRATIONS — audit lane (alembic chain integrity, retroactive)

**SCOPE:** chunk — the migration chain as a whole (DEF337, DEF406, DEF411, and every migration
added or edited since 2026-08-13), not one CR's Definition-of-Done. DoD table not applicable at
this grain.

**TIER: A.** Migrations that alter or backfill existing rows are named explicitly in the
escalation-tiers binding (gap-fill 8) as Tier A. Two of the items here (DEF406, DEF411) are
exactly the failure mode that Tier A exists for: a forked/edited migration chain that would have
either failed a live promotion mid-deploy or silently diverged between what a database actually
ran and what the repo's history claims it ran. Independent audit, rounds uncapped until COMPLETE.

**SHA:** current `main` HEAD —

```
34941fa19cdc5bfa1a4739d5ad79386c75583232
```

(moved from `8c43c88e` while this lane file was being written, same as RETRO-PM-FLOOR's own note
— the one intervening commit, `34941fa1`, is `docs(governance): CR231 stabilisation programme +
DEF416-418 + D-072/D-073 + back-filled review log`, the governance doc that authorizes this very
retroactive audit. It does not touch any file this lane discusses.)

This is a shared checkout, other lanes active concurrently — do not attribute commits below to
this lane that are not listed. Nothing in this lane's own scope needed a fix commit; this is a
review-and-assemble submission over already-shipped work, same shape as RETRO-PM-FLOOR and
RETRO-SIM-OPTIONS.

**depends-on:** none.

**Promoted:** yes — all migrations discussed here are already applied or superseded on Alpha as
of `alpha-2026-09-24-1` (CR231's own sweep: "Alpha holds all backend work; nothing is waiting to
promote"). This lane is retroactive record-verification, not a pending deploy.

## Current chain state

```
cd backend && .venv/bin/python -m alembic heads
cr230a0order0log (head)
```

**Single head, confirmed.** `cr230a0order0log_alpaca_order_audit.py` (CR230, already under its
own separate audit lane, COMPLETE) is the tip. The chain walks CR230 → CR222 → CR221 → CR219 →
DEF335 → ... with no fork at current HEAD.

Also confirmed via the repo's own guard rather than trusted from the CLI alone:
`test_def406_single_migration_head.py::test_the_chain_reaches_a_single_head` parses the version
files independently of `alembic`'s own `ScriptDirectory` (deliberately — `postflight.py` runs
under whatever bare `python3` the operator has on melehost, so it cannot assume the venv's
`alembic` package is importable there) and both readings agree: one head.

## Migrations added since 2026-08-13

```
git log --since=2026-08-13 --name-status --oneline -- backend/alembic/versions/
```

Every `A` (added) migration file in that window, chronological:

| commit | date | migration file | item |
|---|---|---|---|
| `eba1dcaf` | 08-14 | `a170a000001a_cr170_sim_resting_orders.py` | CR170-BE |
| `dd8a4f3f` | 08-14 | `a171a000001b_cr171_sim_short_positions.py` | CR171-BE |
| `1ecc0e63` | — | `a309a000001c_def309_resting_order_retired_at.py` | DEF309 |
| `e7014816` | 08-?? | `b4c1d2e3f501_cr192_vllm_cache_samples.py` | CR192 (deleted below, DEF337) |
| `4e6ba740` | 08-20 | `c192f000001d_vllm_cache_samples_def337.py` | DEF337's replacement (see below) |
| `950fa9f6` | — | `c102a000001e_cr102_broadcasts_inbox_messages.py` | CR102 |
| `7cbe3cb0` | — | `a135a000001f_cr135_notification_preferences.py` | CR135 |
| `5e81e310` | — | `a181a000002a_cr181_persona_events.py` | CR181 |
| `67f0b850` | — | `b200a000001b_cr200_admin_audit.py` | CR200 |
| `8eaab9a0` | — | `a172a000001e_cr172_option_tables.py` | CR172 |
| `e09ea4f2` | — | `cr202a0d0e0f1_cr202_drop_alpaca_credentials.py` | CR202 |
| `795b960e` | — | `cr203a0b0c0d1_cr203_alpaca_link_state.py` | CR203 |
| `9331d15b` | — | `def360a0b0c0d1_notification_push_outcome.py` | DEF360 |
| `127d6bd9` | — | `cr194a0b0c0d1_trade_price_provenance.py` | CR194 |
| `9b6e758d` | — | `cr210a0b0c0d1_llm_audit_constraint_status.py` | CR210 |
| `1d7985b0` | 09-?? | `def335a0b0c0d2_ticker_splits.py` | DEF335 |
| `0aba79fb` | 09-03 | `cr219a0b0c0d3_verdict_outcomes.py` | **CR219 verdict-outcome ledger** |
| `98e1b36f` | 09-11 | `cr221a0b0c0d4_edgar_8k_items.py` | **CR221 slot 2 (I1)** — edited after commit, see below |
| `6159a62b` | 09-11 | `cr222a0b0c0d4_training_toll.py` | **CR222 slice C training toll** — edited after commit, see below |
| `d7d71755` | — | `cr230a0order0log_alpaca_order_audit.py` | CR230 (own audit lane, COMPLETE) |

`c192f000001d` is included because it *replaces* `b4c1d2e3f501` inside this window (both DEF337
commits — the broken original and its fix — land 2026-08-20, inside scope); see DEF337 below for
why replace-not-edit was the correct move there and how it differs from the two edited-in-place
cases.

## Migrations edited after their first commit (within window)

Read directly off `test_def278_migrations_are_immutable.py`'s own `_PRE_GUARD_EDITS` allowlist —
the guard is an exhaustive, mechanically-verified scan (`git log --diff-filter=A` vs `git log -1`
per file, over every `.py` in `backend/alembic/versions/`), not a manually-curated list, so its
comments are load-bearing evidence, not narrative. Five entries total across the whole repo
history; three predate this window (`8a4ce4f8abc3`, `a9d1c7e80006`, `c109g000007a` — all
2026-05/06, DEF278's own subject, out of scope). **Two fall inside 2026-08-13→present:**

### 1. `cr221a0b0c0d4_edgar_8k_items.py` — repaired

- Committed `98e1b36f` (2026-09-11), created `ix_edgar_8k_items_ticker_filed`.
- Edited `94fc8619` (2026-09-11, 48 minutes later — the CR221 I1 review round), renamed the index
  to `ix_edgar_8k_items_cik_filed`. `git diff 98e1b36f..94fc8619 -- backend/alembic/versions/cr221a0b0c0d4_edgar_8k_items.py`
  confirms: one `op.create_index`/`op.drop_index` pair changed name and column list
  (`["ticker", "filed"]` → `["cik", "filed"]`), nothing else in the file moved.
- **Filed as DEF278/DEF407, repaired by `77ad0df7`** (`e221i000009c_edgar_8k_cik_index_repair.py`)
  — a new revision that drops the stale ticker-index (if present) and creates the CIK one, by
  inspection, so a database that ran the first form and a fresh database that only ever sees the
  second form both converge on the same schema.
- Correctness of the rename itself: items are read through the scan row's CIK (GOOG and GOOGL
  share one CIK, different tickers), so `(cik, filed)` is the right index for the actual read
  path — the edit fixed a real defect. The DEF278 violation is procedural (editing a committed
  revision instead of shipping a new one), not that the destination state is wrong.

### 2. `cr222a0b0c0d4_training_toll.py` — baselined, no repair

- Committed `6159a62b` (2026-09-11, 07:05Z), `down_revision = "cr219a0b0c0d3"`.
- Edited `839c3283` (2026-09-11, 16 minutes later — DEF406), re-parented to
  `down_revision = "cr221a0b0c0d4"`. `git diff 6159a62b..839c3283 -- backend/alembic/versions/cr222a0b0c0d4_training_toll.py`
  confirms: the docstring's `Revises:` line and the `down_revision` value are the only changes —
  no column, table or index statement differs.
- **Why re-parented:** CR221 slot 2 and CR222 slice C both branched off `cr219a0b0c0d3`
  independently — each lane verified "single head" against its own pre-merge branch and each was
  right at the time, since the fork exists only once both merge into `main`. DEF406 fixed the fork
  by re-parenting CR222 onto CR221 (arbitrary choice between the two siblings; they touch disjoint
  tables so ordering cannot interact) — filed as its own defect: `065f0bae`,
  `839c3283`.
- **DEF411 (2026-09-17) is the accounting of that edit against DEF278's immutability rule.**
  Baselined with no repair revision, on two measured grounds recorded in the guard's own comment
  block: (a) the DDL is byte-identical between the two forms — AST digest of `upgrade()` and
  `downgrade()` match exactly (`f17148e6de849606` / `fb351fc49dfbbe14`), only `down_revision`
  differs, so any database stamped `cr222a0b0c0d4` holds the same three `toll_charged` columns
  regardless of which form it ran; (b) measured directly against Alpha's live `ami_postgres`
  (`alembic_version` table), 2026-09-17: stamped at `cr219a0b0c0d3`, one revision *before* this
  file, with `information_schema` showing no `toll_charged` column and no `edgar_8k%` table
  anywhere — no database had run either form of this migration at measurement time, so there is
  nothing to reconcile. A repair revision was judged to have no target.
- Authority for lifting the standing deferral is named explicitly in both the guard comment and
  DEF411's row: DEF407 left the guard failing as CR222's own call; Saiful lifted it 2026-09-17
  ("do 1. I need alpha up!") against the measurement above, after an earlier attempt to allowlist
  it without that authority was refuted 3/3 by independent reviewers.

**What the auditor should re-verify, not take on my word:** the AST-digest claim (I did not
re-run the hash myself this round — the guard's own comment states it and the guard's own test
passes, see below, but an independent re-derivation of `f17148e6de849606`/`fb351fc49dfbbe14` from
both file versions is cheap and would close this without relying on the comment's arithmetic);
and the live Alpha measurement (DEF411's row states a single point-in-time read on 2026-09-17 —
seven days stale relative to this submission; the auditor has melehost access and should re-query
`alembic_version` + `information_schema.columns` directly rather than trust a week-old snapshot,
especially since Alpha has since promoted to `alpha-2026-09-24-1`).

## No other migration in the file added since 08-13 shows a second commit

Checked mechanically, not by inspection: for every file under `backend/alembic/versions/`, count
of commits touching it via `git log --follow`. Files with more than one touch, repo-wide:

```
8a4ce4f8abc3_notifications_price_alerts.py   (2 — pre-window, DEF278 baseline)
a9d1c7e80006_admin_backoffice.py             (2 — pre-window, DEF278 baseline)
c109g000007a_cr109_slice4_placement.py       (2 — pre-window, DEF278's own subject)
cr221a0b0c0d4_edgar_8k_items.py              (2 — in-window, see above)
cr222a0b0c0d4_training_toll.py               (2 — in-window, see above)
```

Every other migration touched in this window — including `cr219a0b0c0d3_verdict_outcomes.py`
(CR219's ledger, `0aba79fb`) and `def335a0b0c0d2_ticker_splits.py` (DEF335, `1d7985b0`) — has
exactly one commit each. Neither was edited after commit.

## DEF337 — the third migration item, a different failure shape entirely

Not an edit-after-commit; a migration that **could never apply anywhere**, so DEF278's own
reasoning ("never applied is not a property you can verify and rely on") does not forbid
replacing it outright. `b4c1d2e3f501` (CR192, `e7014816`) declared `sampled_at` with
`index=True` inside `op.create_table` AND then ran an explicit `op.create_index` with the
identical canonical name — a self-collision that failed live on `alpha-2026-08-20-1`
(`DuplicateTable`, transactional DDL rolled back, DB verified still at the prior head with no
remnant). Fixed by deletion + re-mint: `4e6ba740` deletes `b4c1d2e3f501` and adds
`c192f000001d_vllm_cache_samples_def337.py` with `index=True` as the only index-creation
statement, `down_revision` unchanged (`a309a000001c`). Guard:
`test_def337_migration_self_collision.py` — AST scan of every migration, per-function
(upgrade/downgrade are separate apply contexts), simulating create/drop order.

## Guards covering this lane, run individually

```
cd backend && .venv/bin/python -m pytest tests/unit/test_def278_migrations_are_immutable.py tests/unit/test_def337_migration_self_collision.py tests/unit/test_def406_single_migration_head.py -q
14 passed in 8.04s
```

```
cd backend && .venv/bin/python -m pytest tests/unit/test_p15_check_then_insert_guard.py tests/unit/test_def220_check_then_insert_outcomes.py -q
12 passed in 5.36s
```

## Correction to this lane's own brief: DEF401, DEF220, DEF308 do not touch the migration chain

The dispatching brief for this lane named DEF401, DEF220, DEF308 alongside the migration items.
Checked directly — **none of the three touches any file under `backend/alembic/versions/`**:

- **DEF401** (`5ee0051f`, CR219's ledger) fixes a check-then-INSERT race in
  `services/verdict_outcomes.py` (re-read-and-update on `IntegrityError` inside a `begin_nested()`
  SAVEPOINT). Touches `verdict_outcomes.py`, `test_cr219_verdict_outcome_ledger.py`,
  `test_p15_check_then_insert_guard.py`. No migration file in the diff.
- **DEF220** (`5854fcf9`) fixes six check-then-INSERT sites across
  `auth_service.py`/`lessons_service.py`/`mandate_store.py`/`overlay_store.py`/
  `reputation_service.py`/`social_context.py`. No migration file in the diff.
- **DEF308** (`d4ca6dce`) is docs-only — it records that the P15 guard's own blind spot (only
  catching `session.add(Model(...))`, not `row = Model(...); session.add(row)`) hid 12 of 20
  collidable sites, and spins the 11 newly-visible-but-unfixed ones off into CR191. Zero code or
  migration files touched.

These three are real, correctly-scoped, already-`fixed` defects about the **same class of
concurrency bug** (P15, check-then-INSERT races) that DEF401 happens to touch inside CR219's
migration-adjacent ledger table — but "touches a table a migration created" is not "touches a
migration". I'm flagging this rather than padding the submission with unrelated material to match
a brief that doesn't match the repository: if the auditor believes these belong in scope anyway
(e.g. because the ledger table's integrity is migration-chain-adjacent), say so and I'll fold them
in properly with their own commit-level evidence: `5ee0051f` / `5854fcf9` / `d4ca6dce`. As filed,
Lane B (RETRO-CR221-S13) and RETRO-PM-FLOOR (which already lists CR219 in its own scope) are the
more natural homes for anything CR219-ledger-specific.

## Attack surface (named for the auditor, not defended here)

- **Fresh-DB base→head upgrade on real Postgres.** Nothing in this repo runs the actual alembic
  chain end-to-end against Postgres — `test_def278_migrations_are_immutable.py`'s own docstring
  states explicitly why: the chain contains Postgres-only DDL (`gen_random_uuid()` in the device
  backfill), so it cannot execute against the sqlite the unit suite uses, and gating on "a real
  Postgres is available" would make the check silently skip in CI (the exact DEF038/DEF063 shape).
  **This is the auditor's job, not mine** — per the dispatching brief, run `alembic upgrade head`
  from base against a **throwaway** database on melehost, never `ami_postgres` prod data. This is
  the single biggest untested claim in this lane: single-head and no-edits are necessary but not
  sufficient for "the chain actually runs clean start to finish."
- **Downgrade paths.** Not exercised anywhere in this submission or, as far as I can find, in the
  repo's test suite. A downgrade that doesn't reverse its own upgrade cleanly (e.g. an index name
  mismatch after the `cr221a0b0c0d4` repair) would only surface on an actual `alembic downgrade`
  run.
- **Edited-after-applied divergence between Alpha's actual state and the repo.** DEF411's
  baseline rests on a single point-in-time Alpha measurement (2026-09-17) showing no database had
  run either form of `cr222a0b0c0d4`. That measurement is now a week stale relative to this
  submission and Alpha has promoted twice since (`alpha-2026-09-18-1`, `alpha-2026-09-24-1`) — the
  auditor should re-confirm `alembic_version` on Alpha reads at or past `cr222a0b0c0d4` now, which
  would additionally confirm the DDL-identical argument by showing the `toll_charged` columns
  actually present.
- **Data backfills touching existing rows.** None of the migrations in this window run a backfill
  against existing rows — DEF335's `ticker_splits` table is additive with no existing-row writes,
  CR219/CR221/CR222/CR230 are all pure `create_table`/`add_column` with no `UPDATE` statements.
  Worth the auditor confirming this by reading each `upgrade()` directly rather than trusting this
  claim — I did not exhaustively grep every migration in the window for `op.execute` with an
  UPDATE/INSERT statement, only read the ones DEF337/DEF406/DEF411/CR219/CR221/CR222 named.

## Independent regression suite (full backend, run once, shared across this lane and Lane B / Lane C)

```
cd backend && python -m pytest tests/unit/ -q -p no:cacheprovider 2>&1 | tail -3
```

Run in the shared Mac checkout (not a scratch worktree — this is a record-assembly submission over
already-promoted work, same posture as RETRO-PM-FLOOR/RETRO-SIM-OPTIONS, both of which note "no
scratch-worktree measurement" as a stated limit rather than a silent gap). Six other full-suite
`pytest` invocations were running concurrently on this shared Mac from other tracks at the same
time — result below, appended once the run completed:

Full unit suite: not cited this round — 5 concurrent full-suite runs on the shared Mac checkout
(Architect's dispatch error); per-lane suites above are the builder evidence. Auditor re-runs the
independent suite on melehost per BINDINGS.

## Known limits, stated rather than left to be found

- **No scratch-worktree measurement**, same limit RETRO-PM-FLOOR and RETRO-SIM-OPTIONS both
  named — a retroactive record-review choice, not an oversight. The per-file test commands above
  were run in the shared Mac tree at current HEAD; `git status --short` was not re-verified clean
  immediately before each one, only before starting this pass.
- **The AST-digest claim behind DEF411's "DDL unchanged" argument was not independently
  re-derived** by me this round — I read the guard's own comment and confirmed the guard's test
  passes, but did not re-hash `upgrade()`/`downgrade()` from both file versions myself. Flagged
  above under Attack surface as the cheapest independent check available.
- **No live melehost/Alpha query run by me** — DEF411's live measurement is a week old relative to
  this submission; re-querying `alembic_version` and `information_schema` on current Alpha is
  squarely the auditor's job per binding ("Postgres-level checks are for the auditor on
  melehost"), not attempted here.
- **Downgrade paths not exercised**, named above and not run.
- **DEF401/DEF220/DEF308 scope correction** (above) means this lane is narrower than the
  dispatching brief implied. If the auditor disagrees with leaving them out, say so in round 1 and
  I'll fold them in with full evidence rather than treat the disagreement as a bounce.

SUBMITTED: round 1

## Architect disposition of round 1 (2026-09-25)

- **MAJOR-1 (chain ≠ Alpha; forced RLS on an unset `app.user_id`)** — accepted as real. Saiful ruled *"File as Beta blocker, decide at CR126."* Filed as **DEF421** (open, Beta blocker). No code change in this lane: Alpha does not carry the RLS and runs as superuser, so the external beta on Alpha is unaffected; the fix (implement per-request `app.user_id` or drop the RLS, plus schema-drift reconciliation) lands before CR126 builds any database from the chain.
- **MINOR-1** — to be handled with DEF421.

This lane therefore stays at the auditor's AWAITING_FIXES (round 1) until DEF421 is fixed; it is not resubmitted.

## Round 2 — rescope: Alpha chain in, fresh-DB chain carried by DEF421 (2026-09-25)

Correcting the line above ("not resubmitted"): leaving this lane at AWAITING_FIXES would keep
`dispatch.sh inbox` at exit 1 until DEF421 is fixed, and DEF421 is scheduled for CR126, after
the external beta. That would block every Alpha promotion between now and CR126. Waving the
gate through would also be wrong. So this round asks you to rule on a narrower claim, and if
you think narrowing is itself the mistake, say so and the gate stays shut.

**The claim this lane now makes:** the migration chain as it applies to the running Alpha
database is sound. Your round 1 already measured that:
- single head;
- base → head → base → head clean on real Postgres 15;
- DEF411's digest reproduces;
- Alpha's `alembic_version` is at head, with the DEF411 columns and index present.

The one migration added since your round, `m111a0def416x417` (the merge of DEF416's and
DEF417's heads), is a no-op merge. Its upgrade and downgrade are both `pass`, it is live on
Alpha, and `alembic current` there reads `m111a0def416x417 (head)(mergepoint)`.

**Moved out of this lane and tracked elsewhere:**
- **MAJOR-1:** the chain builds a database that Alpha is not. Forced RLS is keyed on an
  `app.user_id` the app never sets, and there is schema drift besides.
  - This is **DEF421**, open, recorded as a Beta blocker (Saiful: *"File as Beta blocker,
    decide at CR126"*).
  - It cannot reach the external beta. The beta runs on the existing Alpha database, which
    carries no RLS and connects as superuser.
  - Nothing builds a fresh database from the chain before CR126.
- **MINOR-1:** travels with DEF421.

**What would make this rescoping wrong, for you to probe:**
1. Can any path build or migrate a database from the chain before CR126? Look at CI,
   promotion, fixtures or scripts.
2. Does anything on Alpha today depend on the RLS policies or on `app.user_id`?
3. Is DEF421's row accurate and open, and does it name both findings?
   See `docs/defect/_registry/DEF421.row.md`.

SUBMITTED: round 2
