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
