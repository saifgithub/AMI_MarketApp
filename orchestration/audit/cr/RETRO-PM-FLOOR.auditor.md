<!--
RETRO-PM-FLOOR.auditor.md — audit lane verdicts. Auditor-owned; the architect never writes here.
Newest round at the bottom. State derives from round numbers here vs RETRO-PM-FLOOR.architect.md.
-->

# RETRO-PM-FLOOR — auditor verdicts (PM/safety-floor compliance perimeter, retroactive)

## Round 1 — auditor U68

**SHA audited:** `34941fa1`, in a detached scratch worktree `audit-U68-PMFLOOR` per DEF159.
Worktree verified clean after every probe and mutation was reverted (probe files were
untracked scratch, deleted with the worktree).

**What is live, measured rather than assumed.** Alpha runs `alpha-2026-09-25-1` (`1fa5d9e5`, image
`GIT_SHA`), not the `alpha-2026-09-24-1` the lane names. It does not matter here: the three
PM-path files are byte-identical across the lane SHA, both tags and the running container:

```
safety_floor.py  8faa7841fea3  (lane = a24 = a25 = in-container /app)
room_runner.py   5e4be4379156  (same)
schemas/room.py  00218fd9a355  (same)
```

Live flags, read with `printenv` inside `ami_api_alpha`: `PM_SELF_CONSISTENCY_SAMPLES=5`,
`ROOM_JSON_CONSTRAINTS_ENABLED=true`, `ROOM_TRADER_REGEX_ENABLED=true`,
`ROOM_RISK_OFFICER_ENABLED=true`, `ROOM_MAX_SCRIPTED_TURNS=4`. **The vote branch is therefore
the live PM path on every convene**, which is what makes DEF384 the load-bearing fix in this lane.
Grammar is enforced, not requested: `llm_audit` last 7 days, read-only —
`room_pm | enforced | 351`, `room_risk_officer | enforced | 70`, zero `unsupported` /
`rejected` / `truncated`.

**Tier A.** The question audited is the one the lane poses: can any Room verdict reach a user
without the deterministic floor, and can any path soften it.

### The LLM-output paths: the floor holds on every one

Read `room_runner.py:5499-5719` at the SHA. `_parse_pm_verdict` (`:2410-2651`) can only emit
`APPROVE` or `PASS` (`_normalize_pm_action` collapses `MODIFY`/`BUY`/… to those two, `:1980-2013`);
the vote (`_vote_pm_samples`, `:6641-6695`) returns one of those parsed samples; the reformat
retry only ever lifts to an `APPROVE` that then re-enters the same tail (`:5642`); outage is a
hard-coded `PASS` (`:5613-5618`); every other branch reaches the single `enforce_safety_floor`
call at `:5696`. After the floor, the verdict is only ever *downgraded* (`:5798`, R51's
`NO_VERDICT`) or has `reason` rewritten (`:5821-5835`). `risk_officer.py` constructs no `Verdict`
(grep: zero `Verdict(` outside `room_runner.py`/`safety_floor.py`); `_run_risk_officer`
(`:6401-6560`) only yields transcript turns.

Then driven, not read — the real `RoomRunner.run`, a PM that always APPROVEs, a mandate that
blocklists the ticker, across every path the lane names:

```
2 sample counts {1,5} x 3 reply shapes {clean JSON, prose -> reformat, JSON + trailing "}" prose}
x grammar {off,on} x Risk Officer {off,on} = 24 runs
PROBE samples=5 mode=clean grammar=True officer=True -> REJECT overridden=True votes=5 ...
PROBE samples=5 mode=prose grammar=True officer=True -> REJECT overridden=True votes=None reformat_calls=1 ...
24 passed          (every one REJECT, violation 'ticker MSFT in user blocklist')
```

That is the measurement the lane asked for ("the floor vetoes an LLM APPROVE identically at
both settings"), on the real runner. I did not convene on Alpha: a convene writes `room_runs`,
journal and credit rows, and live-DB writes are outside this audit's remit. Byte-identity above
is what carries the local result to the live process.

**Mutations, mine, each reverted with `git checkout` and the tree re-checked clean:**

| Mutation | Result |
|---|---|
| DEF384: vote `APPROVE` skips the tail (`… == APPROVE and _voted is None`) | `3 failed` — both DEF384 behavioural tests + `test_room_live_pm_enforce_safety_floor_rejects_a_post_loss_cooldown_approve` |
| DEF383: `action=parsed.action.value` | `2 failed` (`'str' object has no attribute 'value'`, run fails) |
| DEF059: outage verdict `PASS` -> sized `APPROVE` | `test_room_pm_llm_outage_fails_safe_to_pass` red |
| DEF067: reformat accepts any `reparsed` | `test_room_pm_reformatter_refusal_never_becomes_verdict` red |
| DEF398 leg 1: `raw_decode` disabled | `5 failed` in `test_def398_pm_json_contract_break.py` |
| R51: scripted-turn cap disabled (`if False:`) | `6 failed` in `test_cr219_r51_partial_outage_honesty.py` |

On the architect's worry that DEF384's AST guard pins a *count*, not *reachability*: the file
also carries two behavioural tests driving the real runner at `samples` 1 and 5, and
`test_cr101_be2_round2_room_wiring`'s live-PM test runs at the shipped default of 5 — mutation 1
turns all three red. Reachability is pinned.

### MAJOR-1 — a respawned convene runs the floor against a fabricated $100k, 0%-drawdown portfolio

`_respawn_run_from_row` (`room_runner.py:4532-4536`) calls:

```python
async for ev in self.run(
    run_id=p.run_id, user_id=p.user_id, ticker=p.ticker, mandate=mandate,
):
```

No `portfolio_value`, no `current_drawdown_pct`. `run()` defaults them (`:5036-5037`):

```python
portfolio_value: float = 100_000.0,
current_drawdown_pct: float = 0.0,
```

Both are floor inputs. `current_drawdown_pct=0.0` means rule 7 (`safety_floor.py:638`) can never
fire on a respawned run, and `portfolio_value=100_000` is the denominator
`_build_room_risk_limit_context` and the sector cap measure existing exposure against — for a
$10k alpha user, existing open risk and sector weight read ~10x smaller than they are.
`api/room.py:180-189` exists specifically to stop this ("DEF051: resolve the user's real
sim-portfolio state server-side — never trust a client-suppliable override for a
compliance-check input"); the respawn path never got the same treatment.

Driven — the same user (drawdown 50% against the default mandate's 30% cap), the same always-APPROVE
PM, two entry points:

```
PROBE api-path     pv=5000.0 dd=50.0 max_dd=30 -> REJECT viol=['current drawdown 50.0% already at/exceeds cap 30%']
PROBE respawn-path real pv=5000.0 dd=50.0 max_dd=30 -> APPROVE viol=[]
```

The respawned verdict is persisted and journalled (`:4546-4568`), so it reaches the user.

**Reachable, measured:** `room_runs` read-only on Alpha — 4 rows with `retry_count=1` (3
`completed` PASS, 1 `failed`, latest 2026-08-14). Rare, and none has yet approved; but the sweep
(`:4408-4470`) claims any run still `running` 30 min after start at the next container boot, and
every promotion is a boot.

**The consequence, bounded honestly.** AMI's own ticket re-checks at submit with the real
portfolio (`sim_engine.py:1452-1475`, `_compliance_context`), so a respawned APPROVE cannot be
filled on the sim ledger. What escapes is the verdict itself: an APPROVE the mandate forbids,
shown on the card, written to the journal, and banked in the CR219 calibration ledger
(`verdict_outcomes.BANKABLE_ACTIONS` includes `APPROVE`) as a call the Room made. DEF384 was
graded on the same basis — the verdict surface is where "uncoachable" is promised. (`start_run`
carries the same defaults, `:4776-4777`; its only default-relying caller is the admin backtest
route, synthetic users only.)

Pre-existing (AT:R34 respawn), not introduced by the nine items. It is in scope because the lane
exists to answer *whether any verdict reaches a user without the floor holding*, and a COMPLETE
here would certify that it cannot.

**Fix:** resolve `sim.valuation_snapshot(p.user_id)` in the respawn (off-loop, as `api/room.py`
does) and pass both values; better, drop the two defaults from `run()`/`start_run()` so a caller
cannot omit them — the CR101-BE2 lesson, a default that looks like a real value. Pin it with the
respawn-path test above (drawn-down user, APPROVE-ing PM, expect REJECT).

### MAJOR-2 — a sector-context failure silently switches off the max-open-positions cap

`_build_room_sector_context` (`room_runner.py:1783-1806`) returns `[], {}, None, {}` on **any**
exception. The floor receives `holdings=ctx.sector_holdings` (`:5704`) — now `[]`, a real empty
book, not an absent one. `check_mandate_compliance`'s own contract (`safety_floor.py:235-239`) is
that `holdings=None` means "not supplied, block loudly" and a real value is never `None`; 6d
(`:531-545`) then counts zero held tickers and passes. The sector cap is skipped too (`sector_map`
is `None`), which the builder's docstring intends; the position-count cap going with it is not
intended by anything — CR101-BE2 round 2 fixed exactly this shape for the risk context
(`_build_room_risk_limit_context`, `:1937-1952`, returns sentinels on failure) and left its
sibling returning real-looking empties.

Driven — user holds AAPL + GOOG, `max_open_positions=2`, PM APPROVEs MSFT:

```
PROBE sector_map_fails=False -> REJECT viol=['opening MSFT would exceed the max open positions cap (2) — 2 already held']
[warning] room_sector_context_failed  error='sector snapshot unreadable'
PROBE sector_map_fails=True  -> APPROVE viol=[]
```

The only trace is a `warning` log line. Any exception inside the helper does it: the sector-map
store read, the marks fan-out, or `allocate_by_sector`. Live rate not measurable — the container
restarted 2h before this audit, there is no retained log history, and no Room ran since. Same
bound as MAJOR-1: the sim ticket re-checks with `portfolio.holdings` and calls
`default_sector_map()` unguarded (a failure there is a loud 500), so the fill is refused; the
forbidden APPROVE still reaches the card, the journal and the calibration ledger.

**Fix:** fetch holdings independently of the sector resolver (a resolver failure should cost the
sector cap only), and on a holdings failure return `None`, not `[]`, so 6d blocks loudly as its
contract says. Disclose the skipped sector cap on the verdict rather than only in a log (the
DEF419 `unmeasured_rules` shape). Pin with the probe above.

### MINOR-1 — a vote in which no draw was readable ships one reformatted draw, unlabelled

With `samples=5` (live), if every draw and every replacement is unparseable, `_voted` is `None`
and the tail parses the *first* raw draw, reformat-retry included (`:5608-5653`). Measured:

```
[warning] room_pm_draws_replaced lost=5 recovered=0
PROBE zero-readable vote -> APPROVE samples= None approve_votes= None reformat_calls= 1
PROBE reason: PM: APPROVE.
```

The verdict carries `samples=None`, which the schema defines as "self-consistency is off"
(`schemas/room.py:91-95`) — false — and DEF397's "(Only N of M independent reads were readable…)"
disclosure never fires for N=0. It also sidesteps CR228's graded bar: a risk-score-2 user whose
vote needs 4/5 gets one reformatted draw's APPROVE. The floor still applies (the matrix above
proves it), and under live grammar enforcement an all-unparseable vote is near-unreachable,
hence MINOR. **Fix:** on `_cands == []` with `_pm_samples > 1`, set `samples=_pm_samples`,
`approve_votes=0`-or-`None`-with-a-disclosure, and say in `reason` that no independent read was
readable.

### MINOR-2 — DEF398's "first object wins" turns a retracted draft APPROVE into the verdict

`extract_json_object` (`llm_json.py:141-156`) now `raw_decode`s the first complete object. A
reply carrying a draft `APPROVE` then a final `PASS` reads as `APPROVE`; before DEF398 the same
reply was unparseable and failed safe to `PASS`:

```
'Draft: {"action":"APPROVE",…} -- on reflection I decline. {"action":"PASS",…}' -> APPROVE
'{"action":"APPROVE",…}\nCorrection: {"action":"PASS",…}'                       -> APPROVE
pre-DEF398 llm_json (886355e4^), same two replies                                -> None, None
```

`test_the_first_object_wins_not_the_last` pins this deliberately, and the floor still applies to
the resulting APPROVE — so this is decision fidelity, not a floor bypass. Unreachable while the
grammar is enforced (every live PM call above); reachable on any provider the gateway marks
`unsupported`. **Fix:** when the tail after the first object contains a second object with a
different `action`, fail safe (treat as unparseable) — two decisions in one reply is an
uncertain decision, and DEF059's direction for those is PASS.

### Architect's open items, closed

- **Compose parity (the gap flagged "most wanted").** All forwarded:
  `ROOM_RISK_OFFICER_ENABLED`, `ROOM_JSON_CONSTRAINTS_ENABLED`, `ROOM_TRADER_REGEX_ENABLED`,
  `PM_SELF_CONSISTENCY_SAMPLES`, `ROOM_MAX_SCRIPTED_TURNS` each appear in `docker-compose.yml`
  and in the running container's env with the values above.
- **DEF383 `use_enum_values=True`** — confirmed, `schemas/room.py:74`.
- **`risk_officer.py` hidden verdict path** — none (see above).
- **CR210 `constraint_status` states** — `enforced` / `unsupported` / `rejected` / `truncated` /
  `NULL`, `llm_gateway.py:1263-1280,1354-1379`, `audit.py:109`.
- **DEF398 leg 2 live** — confirmed by env and by the 351/351 `enforced` rows.
- **Is CR210's grammar closing the class?** On the enforced provider, yes: the PM reply is one
  schema-valid object with `action ∈ {APPROVE, PASS}`, so the unparseable-reply → PASS class
  cannot occur there. The tolerant parser remains the contract on an `unsupported` provider,
  and MINOR-2 lives exactly there.
- **Commit counts** — re-derived at the SHA: CR219 114, CR201 23, CR210 19, DEF352 3, DEF398 6,
  DEF230 12, CR197 25 raw = 15 with `CR197` in the subject + 10 body-only cross-references. The
  15/10 split holds.
- **CR199** — `git show --stat 0d39b918`: scripts + docs only, no `app/` file.
- **DEF230** — no code; the over-blocking question it raises is outside "can the floor be
  bypassed". Not scored.

### Evidence, run bare in the pinned worktree

```
pytest test_safety_floor.py test_room_runner.py test_def384_vote_reaches_safety_floor.py \
       test_def398_pm_json_contract_break.py test_def352_trailing_prose_after_json.py \
       test_cr197_{pm_self_consistency,risk_officer,size_envelope,option_ladder}.py \
       test_cr201_risk_officer_room.py test_cr210_{constraint_plumbing,outcome_taxonomy,room_wiring,schemas}.py \
       -q -p no:cacheprovider
333 passed in 159.12s        EXIT=0
```

Matches the submission's 333.

Full backend unit suite, `34941fa1`, on melehost (the deploy target) — `git archive` tree in a
throwaway container built from the Alpha API image plus pytest, `/tmp` on tmpfs, split into three
file-shards capped at 0.9 CPU each so live Alpha kept a core; run bare, exit code read from each
shard's own log:

```
shard 0   2103 passed, 2 skipped                         EXIT=0
shard 1   2194 passed, 2 skipped, 2 failed               EXIT=1
shard 2   2433 passed, 5 skipped, 4 failed, 4 errors     EXIT=1
total     6730 passed, 9 skipped, 6 failed, 4 errors
```

All ten non-passes are one environmental cause: the image has no `git` binary
(`FileNotFoundError: [Errno 2] No such file or directory: 'git'`) and those files shell out to it
— `test_def278_…immutable`, `test_def405_…`, `test_cr216_…`, `test_def178_…`, `test_p30_…`.
Re-run bare on the Mac in the pinned worktree, where git exists:

```
pytest test_def278_… test_def405_… test_cr216_… test_def178_… test_p30_… test_cr175_readiness.py
42 passed, 2 failed
FAILED test_p30_registers_name_things_that_exist.py::test_every_file_a_register_row_claims_actually_exists
FAILED test_p30_registers_name_things_that_exist.py::test_no_new_register_identifier_is_absent_from_the_codebase
```

Those two are real and belong to `34941fa1` itself — the CR231 governance commit this lane rests
on added DEF416–418 rows with `../../../backend/…` links and an uncited identifier
(`check_dry_run_compliance`). Already fixed on `main` by `8e550a57`; not this lane's code, not a
finding here. At `8c43c88e` those rows do not exist. (An earlier unsharded attempt also tripped
`test_cr175_readiness::test_unstamped_build…` because the image carries `GIT_SHA`; with it unset
the test passes, as it does on the Mac.) Totals reconcile to 6749 of the 6751 the Mac collects for
this tree; the two-test gap is untraced.

Nothing product-side fails at this SHA.

FOREIGN: not run — no `foreign/RETRO-PM-FLOOR.r1` branch exists, and this audit's brief limits
writes to the lane, run and ledger files. Not a clean bill.

### Verdict

Every LLM-output path the lane names — vote, reformat, grammar, Risk Officer, outage — meets the
floor or cannot produce an APPROVE, and I proved it on the real runner rather than by reading;
DEF384's fix is right and its guards are genuinely load-bearing. But the lane's question is
whether any verdict reaches a user without the floor *holding*, and two do: a respawned convene
is judged against a portfolio that does not exist (MAJOR-1), and a failure in an unrelated
helper quietly empties the book the position-count cap reads (MAJOR-2). Both are the floor being
fed a real-looking value in place of a missing one — CR101-BE2's round-1 BLOCKER shape, surviving
on two call paths it did not reach.

VERDICT: AWAITING_FIXES (round 1)
