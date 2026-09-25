<!--
RETRO-SECURITY.auditor.md — audit lane verdicts. Auditor-owned; the architect never writes here.
Newest round at the bottom. State derives from round numbers here vs RETRO-SECURITY.architect.md.
-->

# RETRO-SECURITY — auditor verdicts (credit/prompt/auth security defects + Alpaca custody, retroactive)

## Round 1 — auditor U68

**SHA audited:** `8c43c88e`, in a detached scratch worktree `audit-U68-SEC` per DEF159. Worktree
verified clean after every probe and mutation was reverted. (`8c43c88e..34941fa1` is 12 docs/
register files, no source — the backend suite below was run at `34941fa1` and covers this SHA's
code byte-for-byte.)

**Tier A.** Credits, auth, secrets. My effort went where money moves.

### DEF369 — the lock works on real Postgres; it is the only lock on the column

The builder named the gap honestly: the guard asserts compiled SQL because SQLite ignores
`FOR UPDATE`, so the property had never executed in this repo. I executed it — a throwaway
`postgres:15-alpine` on melehost (isolated docker network, built by `alembic upgrade head`,
removed afterwards), the app's own `credit_service`, two threads, an 0.8 s pause injected after
the balance read to hold the window open:

```
PROBE spend_spend:        start=1 results=[('402', 0), ('OK', 0)] final_balance=0 successes=1
PROBE spend_spend_nolock: start=1 results=[('OK', 0), ('OK', 0)] final_balance=0 successes=2
```

Lock in: one of two concurrent spends lands, the other is a 402. Lock removed: both land on a
1-credit balance — the double-spend DEF369 describes, reproduced. The fix is real and
load-bearing. Mutation on the unit guard (drop `with_for_update=True`) -> `2 failed, 3 passed`.

### MAJOR-1 — the same race survives on every other writer of `users.credit_balance`

`with_for_update` appears once in `app/` (`credit_service.py:278`). Every other read-modify-write
of the balance reads unlocked and writes a Python-computed literal:

```
credit_service.py:554  refund()                          old + amount
credit_service.py:438  add_credit_pack()   (RevenueCat)  old + amount
credit_service.py:412  set_plan_and_grant_allowance()    = allowance
credit_service.py:508  carry_billing_on_merge()          = merged
credit_service.py:217  _ensure_period() via balance_for() = allowance (no lock on that path)
reputation_service.py:494  streak award                  old + credits
api/admin.py:616       admin set                          = new
```

A locked `spend` cannot lose their writes (it re-reads under the lock), but they can lose its.
Measured, same throwaway Postgres, a refund racing a spend:

```
PROBE refund_vs_spend: start=5, +1 refund, -1 spend, expected=5, final_balance=6
```

The spend was erased — a free credit, DEF369's exact harm through a different door. Refunds are
not rare events: `room_runner.py:5960` refunds every failed convene and `one_on_one.py:265` every
failed 1-on-1 turn, while DEF205 made 1-on-1/Brief spends reachable 12x/min. Two unlocked writers
racing each other is worse in the other direction: a streak award or refund landing across a
RevenueCat pack credit can overwrite the **paid** pack (same mechanism; reasoned, not driven).

DEF369's row closes "the double-spend"; the class is lost-update on one column, and one of seven
writers is fixed. CLAUDE.md's rule for a second occurrence is an entry with a guard.

**Fix:** make every writer atomic — `with_for_update=True` on each load, or better an in-SQL
`UPDATE users SET credit_balance = credit_balance + :n … RETURNING`, which removes the read. Guard
it structurally (the DEF305 registry shape): an AST scan that fails when any function assigns
`.credit_balance` without locking or using the atomic helper. Drive one refund-vs-spend race on
Postgres before closing.

### MAJOR-2 — a failed Brief turn is charged and never refunded; both surfaces charge for an HTTP-error reply

DEF205 ported 1-on-1's charge to Brief (`brief.py:136-152`) but not 1-on-1's refund
(`one_on_one.py:258-267`, DEF113: *"never let a provider blip silently eat a turn the user never
got"*). `brief.py`'s `event_stream` catches the failure, emits an error event, and refunds
nothing. Measured through the real route, TestClient, fake gateway:

```
PROBE brief mode=raise               status=200 charged_for_failed_turn=1  body: event: error / data: vLLM host unreachable / done {"chars": 0}
PROBE brief mode=http_error_sentinel status=200 charged_for_failed_turn=1  body: token "[AMI error: HTTP 503 from the upstream provider (vllm)…]"
PROBE 1on1  http_error_sentinel      status=200 charged=1
```

The second and third lines are the same defect on both surfaces: on a non-200 the provider does
not raise, it yields the sentinel text as a normal chunk (`llm_gateway.py` OpenAI-compatible
`stream_chat`, `if resp.status_code != 200: … yield "[AMI error: HTTP …]"`), and neither route
treats that as failure — so the user pays a credit for an error message rendered as the
answer. At price 0 that cost nothing; DEF205's price flip made it live on 1-on-1 too. The
outage case is not hypothetical — DEF413 is a vLLM host losing its route.

`test_def205_brief_credit_gate.py` has no failure/refund test; `test_def113`'s refund test covers
only a raised exception.

**Fix:** refund in `brief.py`'s `finally` on failure, mirroring `one_on_one.py`, with the DEF113
test's twin. Have the gateway mark a non-200 / in-band error in `meta` (the Anthropic path already
sets `meta["stream_error"]`; the OpenAI-compatible path does not) and have both routes refund
when it is set. Test both surfaces for both failure shapes.

### MINOR-1 — DEF361's fail-closed does not cover `/concierge/message`, which the row says it does

`turnstile.py:36-51` fails closed outside `local` — verified, and verified live: `ami_website_api`
runs `ENV=prod` with `TURNSTILE_SECRET` unset, and its own logs show
`turnstile_not_configured … refusing` -> `POST /contact 403` (2026-08-22, 2026-08-26).
But `concierge.py:43-52` only verifies a token *when one is supplied*; a caller that omits it is
never checked — by design, per the route's docstring (multi-turn chat vs single-use tokens,
5/min/IP limiter as the primary control). The row's "all three public POSTs … would have accepted
every caller" remains true of the LLM-backed one after the fix. Record correction, not a code bug;
the endpoint is bound to `127.0.0.1:8001` (though `ami_tunnel` does reach it on `ami_internal` —
two `HEAD /` probes in its log).

### MINOR-2 — DEF370: one feed field left raw, and a partial glyph list

The control that matters — no line separator survives — holds against every separator I threw
at it (`\n`, `\r`, U+2028, U+2029, U+0085, VT, FF): all flattened to one line. Two gaps:
`news_context.py:434` interpolates `item.publisher` unsanitised beside the sanitised title and
summary (aggregator-supplied, less attacker-authored than a headline, same feed item); and
`_STRUCTURE_GLYPHS` is a hand list — U+2506 `┆`, U+257C `╼`, U+2574 `╴` pass through. With
line breaks gone they cannot open a new section, hence MINOR. **Fix:** sanitise `publisher`;
drop the whole U+2500–U+259F block by range rather than enumerating it. Mutation on the unit
guard (remove the whitespace collapse) -> `6 failed, 3 passed`.

### MINOR-3 — the submitted "68 passed" is a shared-tree number (DEF159)

In the pinned worktree the same command gives `67 passed, 1 skipped`: the DEF328 live-file test
skips when `infra/alpha.env` is absent, which it is in any clean checkout. The shared tree has the
file, so it ran there. The skip is correct behaviour, but it means DEF328's live-file guard only
ever runs on the promoting Mac — I ran it there against the real file: `5 passed`.

### Verified and sound

- **DEF371** — no create route remains on the journal router (`GET`/`POST …/note`/`DELETE`/
  restore only); `_activity_days` counts `created_at` of journal rows, which a note does not
  create. Streak re-bucketing by the user's own timezone is possible at the margin (a uniform shift
  can bridge a sub-48h gap) but not farmable at scale; not raised.
- **DEF372** — `html_escape` per line in `notify_team` (`email_service.py:144`); `request_type`
  enum-validated before it reaches the ack HTML. Mutation (drop the escape) -> `1 failed`.
- **DEF361** — mutation (`if settings.env == "local"` -> `if True`) -> `4 failed, 2 passed`.
- **DEF373** — nonce from `Random.secure()`, 32 bytes, held per `_OAuthTabState` instance,
  compared before the code is read, cleared on use; https-only registrable-domain allowlist;
  unparseable url -> prevent. The callback can only arrive through this WebView: no OS handler
  for `amitrade://` is registered (Info.plist / AndroidManifest: 0 matches). And shipped builds
  pass no `ALPACA_CLIENT_ID`, so the OAuth tab renders "OAuth not available yet" — the code is
  dormant for users today. `flutter test` both files: `+19: All tests passed!`, exit 0.
- **DEF381** — melehost `~/ami_trade/infra/` holds only `*.env.example` today (re-checked, not
  carried from 08-28). The live `~/ami_trade/.env` is mode 644 but inside a 750 home on a host
  with one human account; not a finding.
- **DEF328** — see MINOR-3; guard green against the real file.
- **CR202/CR203** — live `information_schema`: no credential column anywhere (`users.alpaca_linked_at`
  and CR230's two order-audit columns only). Live `openapi.json`: 3 Alpaca paths — `/link`,
  `/link_state` and CR230's `/order_log`; none carries a credential. `/link_state` writes only
  `current_user`'s row, behind `_require_claimed` (`api/alpaca.py:85-110`).
- **Secret history** — `git log -- infra/alpha.env` empty; ignored at `.gitignore:56`.
- **Out of scope, one line:** `send_contact_answer` still puts the LLM's answer raw into HTML sent
  to an arbitrary address (`email_service.py:84-101`) — the known M5 / CR123 backlog item; DEF372
  fixed the operator mail only.

### Evidence, run bare in the pinned worktree

```
pytest test_def369_spend_takes_a_row_lock.py test_def370_prompt_injection_sanitiser.py \
       test_def371_journal_append_removed.py test_def328_alpha_env_names_are_read_by_something.py \
       test_cr175_postflight.py test_def205_brief_credit_gate.py \
       test_cr202_no_host_side_credentials.py test_cr203_alpaca_link_state.py -q -p no:cacheprovider
67 passed, 1 skipped in 21.90s     EXIT=0
pytest website_api/tests/test_def372_… website_api/tests/test_def361_… -q -p no:cacheprovider
12 passed in 0.68s
flutter test test/screens/settings/def373_alpaca_oauth_test.dart test/services/alpaca/alpaca_credential_store_test.dart
+19: All tests passed!             EXIT=0
```

The source at `8c43c88e` is byte-identical to `34941fa1` (the 12 files between them are docs and register rows), so the full suite was run once, at `34941fa1`, for all four RETRO lanes.

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

Nothing product-side fails at this SHA or at `8c43c88e`.

FOREIGN: not run — no `foreign/RETRO-SECURITY.r1` branch exists, and this audit's brief limits
writes to the lane, run and ledger files. Not a clean bill.

### Verdict

The individual fixes are good and I proved the one nobody could — DEF369's lock stops a real
Postgres double-spend and removing it brings the double-spend straight back. But the lane's
subject is the credit ledger, and the ledger still loses writes (MAJOR-1: six unlocked writers
of the same column, a lost spend measured on Postgres) and still charges for turns that failed
(MAJOR-2: Brief never refunds; both surfaces bill an HTTP-error reply). Both are money moving the
wrong way with nothing telling the user.

VERDICT: AWAITING_FIXES (round 1)

---

## Round 2 — auditor U68

**SHA audited:** `ae468eff` (the `+112` integration merge; this lane's fix is `717cd8ff`).
Detached scratch worktree `audit-U68-R2` per DEF159, verified clean after every mutation. The
Postgres runs used a new throwaway `postgres:15-alpine` (`audit_u68_r2_pg`, isolated network,
built with `alembic upgrade head` -> `m111a0def416x417`), removed afterwards. **Not live yet:**
Alpha runs `alpha-2026-09-25-3`; these fixes ship in +112.

The builder listed the Postgres re-measurements as unresolved. I ran them.

### MAJOR-1 — still open for five of the six writers: the helper locks the row, then keeps using the old balance

`refund()` is fixed. It now loads the user with `with_for_update=True` in the same statement.
My round-1 race, re-run unchanged:

```
PROBE refund_vs_spend: start=5 +1 refund -1 spend expected=5 final=5      (round 1: 6)
```

The other five writers go through the new `_lock_user_row` (`credit_service.py:180-207`, the call at `:204`):

```python
locked = session.get(User, user.id, with_for_update=True)
```

Every caller has already loaded `user` earlier in the same session. The webhook uses
`session.get`, admin uses `_get_user_or_404`, the streak uses `select(User)`, and the merge
loads both rows. In SQLAlchemy 2.0.49 (the version in the venv and in the running container),
`Session.get(..., with_for_update=…)` skips the identity map and sends `SELECT … FOR UPDATE`
(`Session._get_impl`, `for_update_arg is None` guards the shortcut). **It does not refresh an
object already in the session.** `populate_existing` is not set, and the ORM does not overwrite
an already-loaded row's attributes. The lock is taken, and the balance read after it is still
the one from before the lock.

Driven on real Postgres through the real functions. A `spend(-1)` commits in the window between
the caller's own load and `_lock_user_row`:

```
PROBE pack_vs_spend  (webhook shape: s.get -> add_credit_pack): start=5 +10 pack -1 spend expected=14 final=15 (pack saw old=5)
PROBE admin_vs_spend (real api.admin.adjust_credits):          start=5 +1 admin -1 spend  expected=5  final=6
```

Control, with `populate_existing=True` added to that one `session.get` and nothing else changed:

```
PROBE pack_vs_spend  [populate_existing]: expected=14 final=14 (pack saw old=4)
PROBE admin_vs_spend [populate_existing]: expected=5  final=5
```

The spend is erased and the user keeps a free credit. This is round 1's harm, unchanged, on
RevenueCat pack credits and admin adjustments, which I measured. The streak award
(`reputation_service.py:272-292` loads, `:498` locks), the plan grant (webhook `:160` loads) and
the merge (`carry_billing_on_merge`) have the identical shape. I did not drive those three.

The new guard (`test_retro_security_credit_balance_lock_guard.py`) cannot see this. It checks
that each writer *calls* `_lock_user_row` and that the helper passes `with_for_update`. Both
are true, and the balance is still lost. The builder's own note records why it rewrote one
check. The same blind spot has one more level here: the property that matters only exists on
Postgres, and the unit suite runs on SQLite.

**Fix:** `session.get(User, user.id, with_for_update=True, populate_existing=True)` in
`_lock_user_row`. Make the guard assert `populate_existing` on that call, the same AST-keyword
way it already checks `with_for_update`. Re-run the two probes above on Postgres before closing.
(The atomic `UPDATE … SET credit_balance = credit_balance + :n` I offered in round 1 would have
removed the read altogether.)

### MAJOR-2 — fixed for Brief and the analyst 1-on-1; still open on the Concierge 1-on-1

The builder's tests replace the whole runner (`AgentRunner.stream_one_on_one_message` or a fake
engine), so they never exercise the real provider sending `meta["stream_error"]` back through
the real call chain. I did exercise it. I used the real `LLMGateway` and a real
`OpenAICompatibleProvider` with an `httpx.MockTransport` answering 503/429 or raising
`ConnectError`, went through the real routes, and read the balance before and after:

```
PROBE brief real-provider HTTP 503          charged=0        (round 1: 1)
PROBE brief real-provider HTTP 429          charged=0
PROBE brief real-provider ConnectError      charged=0        (round 1: 1)
PROBE 1on1 agent=fundamentals_analyst http503        charged=0
PROBE 1on1 agent=fundamentals_analyst connect_error  charged=0
PROBE 1on1 agent=concierge            http503        charged=1   tail: "[AMI error: HTTP 503 from the upstream provider (vllm)…]"
PROBE 1on1 agent=concierge            connect_error  charged=1   tail: a scripted Concierge reply
```

`stream_one_on_one_message` passes `meta` to the analyst branch (`agent_runner.py:238-246`) but
not to `_stream_concierge` (`:260`), whose own `self._llm.stream_chat(...)` call (`:303`) has no
`meta=`. So:

- an HTTP-error reply from the Concierge is billed as a real turn, which is round 1's finding
  unchanged on this surface;
- on a provider outage, `_stream_concierge` catches the exception and returns a scripted reply,
  so the route never sees a failure and bills a credit for a canned message. DEF113 put it as
  *"never let a provider blip silently eat a turn the user never got."*

The Concierge is the one 1-on-1 agent every Floor Pass user can reach without unlocking
anything (`one_on_one.py:125-132`), so this is the most-used 1-on-1 surface the fix missed.

**Fix:** thread `meta` into `_stream_concierge`'s `stream_chat` call. Set
`meta["stream_error"]` when that method falls back to the scripted reply on an exception.
Whether an empty-reply scripted fallback should bill is Saiful's call, and it should be decided
explicitly. Test through the real gateway and runner the way the probe above does, not by
replacing the runner.

### MAJOR-3 (round 2, new): the Brief refund blocks the event loop, and the full suite is red

The fix adds a synchronous `refund(...)` to the `finally` of `brief.py`'s
`async def event_stream` (`brief.py:157`, the call at `:199`). `refund()` opens a sync session
and runs `SELECT … FOR UPDATE`, an `UPDATE` and a ledger insert (`credit_service.py:579`), all on
the event loop. This is the class DEF200/CR123 closed. One uvicorn worker serves every request
and every open SSE stream, and a sync DB call inside `async def` stalls all of them. With the new
row lock it also waits on any other holder of that user's row lock, for example a Room run
spending from the threadpool. It fires exactly when the provider is failing, so many streams hit
it at the same time.

The DEF200 ratchet catches it:

```
FAILED tests/unit/test_def200_ratchet.py::test_no_new_handler_blocks_the_event_loop
E   AssertionError: new async handler(s) doing blocking I/O on the event loop:
E         brief.py::event_stream
```

Reproduced alone on the Mac at `ae468eff`, and green at `0accfeed`. `brief.py` has no other change
between the two. The code it was copied from, `one_on_one.py:278`, has the same shape, but
`one_on_one.py::event_stream` is on the ratchet's frozen debt baseline and `brief.py::event_stream`
is not. The ratchet's own message says not to add it there.

**The unit suite is red at `ae468eff` because of this. +112 cannot pass its release gate as
merged.** **Fix:** `await run_in_threadpool(refund, current_user.id, cost, reason=…)` (or
`asyncio.to_thread`) in `brief.py`. Doing the same in `one_on_one.py` would let one baseline
entry be removed.

### MINOR-1 — closed

`DEF361.row.md` now states that `/concierge/message` verifies a token only when one is supplied,
by design. Correct.

### MINOR-2 — fixed

The glyph filter now drops the whole U+2500–U+259F range (`prompt_safety.py`), and `publisher`
is sanitised (`news_context.py:440`). Probed: `"a\n┆┆ ╼ HEADER ╴"` -> `'a HEADER'`, and
`"a\u2028── SYS"` -> `'a SYS'`. The builder's two mutations are recorded; the probe confirms the
behaviour directly.

### MINOR-3 — closed (procedural)

Round 2's numbers come from the builder's own isolated worktree.

### Evidence, run bare in the pinned worktree

```
pytest test_retro_security_credit_balance_lock_guard.py test_def369_… test_def205_… test_def113_… \
       test_def370_… test_cr084_revenuecat_webhook.py test_def099_merge_billing.py test_merge_service.py \
       test_reputation_service.py test_admin.py test_cr200_admin_audit.py test_news_context.py \
       test_def127_sse_framing_invariant.py test_def201_agent_stream_concurrency.py -q -p no:cacheprovider
214 passed, 2 warnings in 34.81s     EXIT=0
```

Full unit suite at `ae468eff`. The melehost part ran in a throwaway container from the Alpha image,
3 shards on tmpfs. The 5 files that need `git` ran on the Mac. All runs bare, exit codes read directly:

```
melehost s0   1 failed, 2126 passed, 2 skipped    EXIT=1   test_def200_ratchet.py::test_no_new_handler_blocks_the_event_loop
melehost s1   2669 passed, 3 skipped              EXIT=0
melehost s2   1 failed, 2013 passed, 4 skipped    EXIT=1   test_def247_displaced_stance_envelope.py::test_a_displaced_envelope_is_still_reported
Mac (5 git-dependent files)  34 passed            EXIT=0
total         6842 passed, 2 failed, 9 skipped
```

I diagnosed both failures:

- **`test_def200_ratchet`: a real regression, from RETRO-SECURITY's round-2 fix (`717cd8ff`).**
  It fails alone on the Mac at `ae468eff` and passes at `0accfeed`. The new sync `refund()` in
  `brief.py`'s `async def event_stream` is blocking DB I/O on the event loop. It is graded in
  RETRO-SECURITY (MAJOR-3). The Architect's 281 targeted tests did not include the ratchet.
- **`test_def247…`: pre-existing and order-dependent, not caused by round 2.** It passes alone.
  I ran shard 2's first 95 files in their shard order on the Mac: it fails identically at
  `ae468eff` **and** at `0accfeed` (`1 failed, 1474 passed`). The event is emitted (it shows in
  captured stdout), but `structlog.testing.capture_logs` does not see it, because an earlier test
  in the same process caches the logger. It passes in the default full-suite order that the
  +111 gate ran. Recorded as out-of-scope; no fix is owed by this round.

FOREIGN: not run — no `foreign/RETRO-SECURITY.r2` branch exists. Not a clean bill.

### Verdict

Half of each MAJOR is genuinely fixed. `refund()` no longer races, Brief refunds every failure
shape through the real provider, and the analyst 1-on-1 does too. The other halves are the ones
no SQLite test and no replaced runner could reach. On real Postgres, five credit writers still
erase a concurrent spend because the lock does not refresh the balance the code then uses. The
Concierge 1-on-1 still charges for an error message and for an outage. Both are money moving the
wrong way without the user being told, which is why round 1 graded them MAJOR. The Brief refund
also runs on the event loop, and that turns the unit suite red at `ae468eff` (MAJOR-3). All
three fixes are small: one keyword argument, one `meta=` thread-through, and one
`run_in_threadpool`.

Counts, round 2: 0 BLOCKER, 3 MAJOR (MAJOR-1 and MAJOR-2 partly fixed, MAJOR-3 new), 0 MINOR
open (MINOR-1, 2 and 3 closed).

VERDICT: AWAITING_FIXES (round 2)

---

## Round 3 — auditor U68

**SHA audited:** `685dbdd0` (round-3 fixes `aa17a2d1` + `685dbdd0`). Detached scratch worktree
`audit-U68-R3` per DEF159, clean after every mutation. Postgres runs: new throwaway
`postgres:15-alpine` (`audit_u68_r3_pg`, isolated network, `alembic upgrade head` ->
`m111a0def416x417`), removed after. **Not live:** Alpha runs `alpha-2026-09-25-3` (`0accfeed`).

### MAJOR-1 — fixed for the six named writers; still open inside `_ensure_period` (the re-grant decision is made before the lock)

`_lock_user_row` now does `session.flush()` then
`session.get(User, user.id, with_for_update=True, populate_existing=True)`
(`credit_service.py:232-235`). My round-2 probes, unchanged, plus the three writers I did not
drive in round 2, all through the real functions on real Postgres, a concurrent `spend(1)`
committing between the caller's own load and its first lock:

```
PROBE refund_vs_spend        start=5 +1 refund -1 spend      expected=5   final=5
PROBE pack_vs_spend          start=5 +10 pack  -1 spend      expected=14  final=14  (round 2: 15)
PROBE admin_vs_spend         start=5 +1 admin  -1 spend      expected=5   final=5   (round 2: 6)
PROBE streak_vs_spend        start=5 +5 streak_7 -1 spend    expected=9   final=9
PROBE plan_renew_vs_spend    same period, no re-grant        expected=4   final=4   grant.old_balance=4
PROBE merge_vs_spend         real MergeService.execute       expected=11  final=11  (src 7 + tgt 5 - 1; orphan row gone)
```

The builder's self-found flush bug, sequential, on Postgres:
`rollover_pack_sequential` 160 = 150 + 10 ✓, `revoke_sequential` plan trader -> floor_pass,
balance 13 ✓. The flush also runs partway through `MergeService.execute` on Postgres, and the merge
completes (the probe above).

**Still open — `_ensure_period` decides on the pre-lock snapshot.** It computes `eff`,
`window_rolled` and `plan_drifted` from the caller's unlocked `user`, *then* calls
`_lock_user_row`, then writes `ALLOWANCE[eff]` unconditionally (`credit_service.py:261-285`, lock at `:277`, write at `:279`).
The lock refreshes the balance, but not the decision. When another writer rolls the window
in that gap, the re-grant runs a second time over it:

```
PROBE rollover_balance_for_vs_spend  concurrent spend rolls (->150) then -1   expected=149  final=150
PROBE rollover_pack_vs_spend         webhook _ensure_period+pack vs spend      expected=159  final=160
PROBE rollover_balance_for_vs_pack   concurrent PACK webhook rolls then +10    expected=160  final=150
PROBE rollover control, sequential                                             expected=149  final=149
```

The third line is the one that matters: a `GET /mandate` balance read (`balance_for`,
`api/mandate.py:216`) racing the RevenueCat pack webhook **erases the paid pack** — 10 credits
bought, 0 delivered, no error anywhere. The two calls are concurrent by design: the app re-reads
`GET /v1/mandate` straight after a purchase (`mobile/lib/state/purchase_providers.dart:79,96-100`)
while RevenueCat delivers the webhook. The reach is narrow: the pair must be the first credit touch
after a month rollover (for example, a purchase made just after midnight on the 1st while the app
was already open) or after a plan drift. I measured the rollover. Plan drift, such as a trial
expiring, goes through the same branch, but I did not drive it.
Control, `_ensure_period` re-evaluating `eff`/window/drift on the locked row and returning if no
longer due (nothing else changed):

```
PROBE rollover_balance_for_vs_spend_recheck_control   expected=149  final=149
PROBE rollover_pack_vs_spend_recheck_control          expected=159  final=159
```

This check-then-lock shape predates round 2; round 2 put the lock after the decision and I did
not catch it then — my miss, recorded. It is the same property MAJOR-1 is about (a credit writer
must never erase a concurrent write), on `_ensure_period`, one of the six writers round 1 named,
and it can take money from the user. Doubt resolves toward MAJOR. The AST guard cannot see it:
the lock is present, the order is wrong.
**Fix:** in `_ensure_period`, after `user = _lock_user_row(session, user)`, recompute `eff`,
`period`, `window_rolled`, `plan_drifted` from the locked row and `return eff` if no longer due.
Regression, sqlite-runnable the same way as the builder's re-read test: load in `s1` with a
last-month period, roll + spend in `s2` and commit, then `_ensure_period(s1, user)` -> assert
`allowance - 1`.

**Mutations, mine** (each reverted, tree re-checked clean): dropped `populate_existing=True` ->
`2 failed, 10 passed` (guard file); dropped `session.flush()` -> `9 failed, 33 passed`
(`test_cr084_revenuecat_webhook.py`, the builder's exact 9).

### MAJOR-2 — fixed

`meta` now reaches `_stream_concierge`'s own `stream_chat` (`agent_runner.py:141,268,313`), and its
outage branch writes `meta["stream_error"]` behind an `if meta is not None` guard
(`agent_runner.py:327-328`), so other callers of `_stream_concierge` are unaffected. My round-2
probe, unchanged (real `LLMGateway`, real `OpenAICompatibleProvider`, `httpx.MockTransport`,
real routes):

```
PROBE 1on1 agent=concierge            http503        charged=0   (round 2: 1)
PROBE 1on1 agent=concierge            connect_error  charged=0   (round 2: 1; user still gets the scripted reply)
PROBE 1on1 agent=fundamentals_analyst http503 / connect_error   charged=0 / 0
PROBE brief                           503 / 429 / ConnectError  charged=0 / 0 / 0
9 passed
```

**Mutation, mine:** removed the outage-branch `meta["stream_error"]` write only ->
`FAILED test_concierge_real_provider_connect_error_is_refunded_not_billed`, `1 failed, 13 passed`.

### MAJOR-3 — fixed

`refund` and `spend` in `brief.py` both go through `run_in_threadpool` (`brief.py:151-153,224-229`).
`test_def200_ratchet.py` -> `4 passed`. `brief.py::brief_message` left the frozen baseline
honestly: its only other call before the stream, `engine.get_session`, is an in-memory dict
lookup (`brief_engine.py:207-208`), so the census's whole-handler `run_in_threadpool` shortcut
is not hiding sync I/O here. The builder named that blind spot itself rather than ride it.
**Mutation, mine:** refund back to a bare sync call -> ratchet `FAILED`, `brief.py::event_stream`
newly flagged.

### OUT-OF-SCOPE (recorded, not scored)

- `one_on_one.py:278`'s refund (and its spend) are the same sync-in-`async def` shape, still on the
  ratchet's frozen debt baseline. The builder checked and disclosed it.

### Evidence, run bare in the pinned worktree

```
pytest test_u68r3_probe_refund.py (scratch) -q -p no:cacheprovider -s          9 passed      EXIT=0
pytest test_def200_ratchet.py -q -p no:cacheprovider                           4 passed      EXIT=0
```

Full unit suite at `685dbdd0`. The melehost part ran in a throwaway container from the Alpha
image, 3 shards on tmpfs. The 5 git-dependent files ran on the Mac. All runs were bare, and I
read the exit codes directly:

```
melehost s0   2128 passed, 2 skipped              EXIT=0   (test_def200_ratchet green; red at ae468eff)
melehost s1   2672 passed, 3 skipped              EXIT=0
melehost s2   1 failed, 2015 passed, 4 skipped    EXIT=1   test_def247_displaced_stance_envelope.py::test_a_displaced_envelope_is_still_reported
Mac (5 git-dependent files)  34 passed            EXIT=0
total         6849 passed, 1 failed, 9 skipped
```

The one failure is the order-dependent `test_def247` failure diagnosed in round 2. It is
pre-existing: it fails the same way in shard order at `0accfeed`, passes alone, and passes in
the default order. It was recorded out of scope there and is not caused by this round. Nothing
in the suite fails because of round 3.

FOREIGN: not run — no `foreign/RETRO-SECURITY.r3` branch exists. Not a clean bill.

### Verdict

Round 3 fixes what round 2 asked for, and I re-drove every one on real Postgres and the real
provider: all six credit writers now serialise against a concurrent spend (14, 5, 9, 4, 11, and
refund 5), the Concierge no longer bills an error or an outage, and the event loop is clear.
The builder also caught and fixed a data-loss bug its own first fix introduced. One path is still
open: `_ensure_period` decides whether to re-grant before it takes the lock, so when a balance
read and a pack purchase are the first credit touch after a month rollover, the purchase is
erased. The reach is narrow, but the user loses money they paid. The fix is a re-check after the lock, and my control proves it.

Counts, round 3: 0 BLOCKER, 1 MAJOR open (MAJOR-1, on `_ensure_period` only), 0 MINOR. MAJOR-2 and
MAJOR-3 are fixed.

VERDICT: AWAITING_FIXES (round 3)

---

## Round 4 — auditor U68

**SHA audited:** `6d3be5fc` (fix `90a3af56`). Detached scratch worktree `audit-U68-R4` per DEF159,
clean after every mutation. Postgres runs used a new throwaway `postgres:15-alpine`
(`audit_u68_r4_pg`, isolated network, `alembic upgrade head` -> `m111a0def416x417`), removed
afterwards. The round-3 tree (`685dbdd0`) ran next to it, so the same probes could be seen
failing before the fix. **Not live yet:** Alpha runs `alpha-2026-09-25-4` (`685dbdd0`).

### MAJOR-1 (residual, `_ensure_period`) — fixed

After `_lock_user_row`, `_ensure_period` now works out `eff`, `window_rolled` and `plan_drifted`
again from the locked row, and returns if a re-grant is no longer due
(`credit_service.py:292` lock, `:298-304` re-check, `:307` write). This is the same shape as my round-3 control.

On real Postgres, through the real functions, with a concurrent writer committing between the
caller's load and its lock:

```
                                                        685dbdd0 (r3)   6d3be5fc (r4)   expected
rollover  balance_for vs pack webhook                   150             160             160
rollover  balance_for vs spend                          150             149             149
rollover  webhook _ensure_period+pack vs spend          160             159             159
drift     balance_for vs pack webhook   (expired trial) 13              23              23
drift     balance_for vs spend          (expired trial) 13              12              12
drift     webhook _ensure_period+pack vs spend          23              22              22
drift     sequential control                            —               23 (re-tagged floor_pass)   23
```

The plan-drift variant is new this round: an admin-granted `trial_trader` whose trial has just
expired, so `eff` is `floor_pass` while the period is still tagged `trial_trader`. Before the
fix, the balance read wiped the paid pack out (13 instead of 23), the same loss as the rollover
case. After the fix, the balance is correct on both branches.

Nothing regressed. I re-ran every round-3 writer probe on the `6d3be5fc` tree:

- `refund` gives 5, `pack` 14, `admin` 5, `streak` 9 and `plan_renew` 4.
- A real `MergeService.execute` gives 11.
- `rollover_pack_sequential` gives 160 and `revoke_sequential` gives 13.

**Mutations, mine** (each reverted, tree re-checked clean):

- Kept the re-derived values but ignored them (`if False: return eff`): 2 failed, 12 passed.
  These are the builder's two new tests, for rollover and for drift.
- Dropped `plan_drifted` from the check after the lock: the guard file stays green (14 passed),
  because both of its race tests reach a rolled-or-resolved state on which the mutant still
  returns early. The mutant is caught one level up. Across the 24 credit-related test files it
  gives 1 failed, 420 passed, via
  `test_cr039_room_credit_gate.py::test_trial_lapse_regrants_immediately_not_at_month_rollover`.
  The full suite does guard it. Recorded, not scored.

### Evidence, run bare in the pinned worktree

```
pytest test_retro_security_credit_balance_lock_guard.py -q -p no:cacheprovider        14 passed   EXIT=0
```

Full unit suite at `6d3be5fc`. The melehost part ran in a throwaway container from the Alpha
image, 3 shards on tmpfs. The 5 git-dependent files ran on the Mac. All runs were bare, and I
read the exit codes directly:

```
melehost s0   2130 passed, 2 skipped              EXIT=0
melehost s1   2672 passed, 3 skipped              EXIT=0
melehost s2   1 failed, 2015 passed, 4 skipped    EXIT=1   test_def247_displaced_stance_envelope.py::test_a_displaced_envelope_is_still_reported
Mac (5 git-dependent files)  34 passed            EXIT=0
total         6851 passed, 1 failed, 9 skipped
```

The one failure is the same `test_def247` I diagnosed in round 2. It is already there at
`0accfeed`, fails only in shard order, passes alone and in the default order, and is recorded
there as out of scope. None of the failures comes from this round's change.

FOREIGN: not run — no `foreign/RETRO-SECURITY.r4` branch exists. Not a clean bill.

### Verdict

The last open MAJOR is fixed. The fix follows the pattern my control proved: lock the row,
then decide. I drove both branches on real Postgres. The rollover case the builder asked me to
re-measure now reads 160 and 149. The plan-drift case, which I had not driven before, erased a
pack before the fix and now keeps it. It fails on the round-3 tree and passes on this one, so
the probe does tell the two apart. Across four rounds, all six credit writers now serialise
against a concurrent write, and so does the re-grant decision. The Concierge and Brief no longer
bill a failure, and the event loop is clear. Nothing in the suite fails because of this round.

Counts, round 4: 0 BLOCKER, 0 MAJOR, 0 MINOR open.

VERDICT: COMPLETE (round 4)
