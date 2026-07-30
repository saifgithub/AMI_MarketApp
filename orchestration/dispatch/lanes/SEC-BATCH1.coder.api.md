<!-- coder-owned lane file for SEC-BATCH1. State machine driven by the STATUS line above (byte-exact). See orchestration/dispatch/loop_prompts/CODER.md. -->

# SEC-BATCH1 — coder.api lane

**Item:** close 8 internet-reachable / unauthenticated security holes from `docs/governance/security_review_2026-07-29.md` (umbrella CR123). Assign: `orchestration/dispatch/lanes/SEC-BATCH1.assign.md`.

**Branch:** `lane/SEC-BATCH1.coder.api`, rebased onto `origin/main` @ `e961dfd1` (fast-forward merge, no divergent commits — clean).

## Closed (6 of 8, well)

- **DEF176** — account takeover via body `user_id` on `/v1/auth/apple` + `/v1/auth/google`. `user_id` removed from both request schemas; the pre-claim anon row now binds to `Depends(get_current_user)`, exactly like the magic-link routes already did. `test_def176_account_takeover.py`. Mutation-tested: reverted schema + route data-flow → 3 of 5 tests went RED (the two auth-requirement tests correctly stayed green — unaffected by that specific mutation).
- **DEF177** — unauthenticated LLM proxy (`/v1/llm/translate` + `/status`). Whole router gated `dependencies=[Depends(get_admin)]` — same static-bearer gate as `/v1/admin/*`, which already 503s loudly on unset `ADMIN_SECRET` rather than failing open. **Grepped `mobile/lib` — no caller of `llm/translate` or `llm/status` anywhere; only `scripts/translate_arb.py` and this file's own docstring reference it.** `test_def177_llm_proxy_auth.py`. Mutation-tested: reverted the router-level dependency → 4 of 6 tests RED (the "accepts correct secret" tests correctly stayed green).
- **DEF180** — magic-link verify oracle + open relay. `/verify` gained per-IP (10/min), per-target-email (5/min), and global (120/min) limiters; `verify_magic_link()` now scopes the active-challenge lookup to `AuthChallengeRow.user_id == caller`, so one authenticated caller can no longer guess codes against a challenge a DIFFERENT user started. `/start` gained a per-email limiter (3/min) alongside its existing per-IP one. `test_def180_magic_link_oracle.py`. Mutation-tested: reverted the email/global limiters + the challenge-owner filter → 3 of 4 tests RED.
- **DEF181** — credential leakage into `http_audit` + blind attribution. `/v1/alpaca/link` + `/link_apikey` added to `SCRUB_PATHS`. **Structural backstop added beyond the assign's literal ask:** `_scrub_secret_fields()` redacts any JSON key matching `secret|token|api[_-]?key|password|credential` on EVERY route, request and response, whether or not it's in `SCRUB_PATHS` — `test_secret_shaped_field_redacted_on_route_not_in_scrub_list` proves a route deliberately absent from the list still doesn't leak (this is what acceptance #4 actually asked for: "the scrub is not a hand-maintained path list... add the guard that fails when a route is missing from it"). `_user_id_from_request` now parses the Bearer first (was a dead code path — the docstring claimed it but the code never did it), falling back to path param. `?token=` query param dropped from `GET /v1/auth/me` entirely (grepped `mobile/lib` — dead, header-only client). `test_def181_audit_leakage.py`.
- **DEF184** — body buffering + rate-limiter memory. `http_audit.py` rejects a declared `Content-Length` over 10 MB with 413 before ANY buffering, and never buffers `multipart/form-data` bodies at all — that's the exact path with its own 5 MB streaming cap (`bug_attachments.py`); buffering it here previously defeated that cap even when `Content-Length` was absent/understated. Rate limiter key space is now an LRU-bounded `OrderedDict` (`MAX_TRACKED_KEYS=50_000`) — a spoofed-IP-per-request attacker cannot grow it past that bound. `test_def184_body_buffering_and_rate_limiter_memory.py`.
- **DEF185** — ENV/SECRET_KEY boot hardening. `docker-compose.yml`'s `api-alpha.ENV` is `${AMI_ENV:?...}` — compose refuses to start without it. `check_secret_key_boot()` (extracted from `main.py`'s module-level call for testability) refuses empty AND any non-local `SECRET_KEY` under 32 chars, not just the literal default string. `test_def185_boot_hardening.py`.

## Closed (partial, disclosed — 2 of 8)

- **DEF183** — blocking OIDC httpx client. **Fixed:** `/v1/auth/apple` + `/v1/auth/google` now run `AuthService.sign_in_with_apple/google` via `run_in_threadpool`; `test_def183_oidc_blocking_dos.py` proves a concurrent request to an unrelated route stays fast (<0.5s) while one request is stuck in a simulated 1.5s slow verify. **NOT fixed — the review's "systemic" claim** (93 `async def` handlers doing sync DB/HTTP work, spanning `market_data.py`, `news_context.py`, `social_context.py`, `sharia_*.py` and their callers in `watchlist.py`/`sim.py`/`mandate.py`/`admin.py`) is a much larger, separately-scoped cleanup. Several of those call chains are reachable only through `agent_runner.py`/`brief_engine.py` — **fenced to CR129-BE**. Fixing them risked touching fenced files mid-parallel-build. Acceptance #5's literal "no synchronous HTTP client remains on any async path" is NOT met project-wide — flagging honestly rather than claiming it. Recommend a DEF/CR once CR129-BE lands.
- **DEF186** — LLM spend + bug-upload caps. **Fixed, scoped to the lane's own acceptance #8 wording** ("1-on-1 and Brief are rate-limited; bug-upload... size- and rate-bounded. Name the limits you chose and why" — no mention of credit metering): per-user (bearer-keyed) 12/min limiter on `/v1/agents/one_on_one/message` and `/v1/brief/message`; the deprecated `/v1/coach/message` shim calls `brief_message()` directly so it inherits the same limit for free (verified — burning the budget via `/v1/brief/message` also 429s `/v1/coach/message`). `user_message` capped at 8,000 chars, `history` at 100 turns on both schemas. `/v1/feedback/bug` gets a 5/hour-per-IP limiter (the review's own suggested figure). **Deliberately NOT done, each a separate judgment call — see "Disclosures" below.**

## Registers

All 8 rows flipped in `docs/defect/_registry/DEF{176,177,180,181,183,184,185,186}.row.md` — the two partial ones (`183`, `186`) marked `fixed` with the partial scope spelled out in the row body itself (not silently marked "closed" — see the row text). `docs/defect/def_list.md` regenerated via `scripts/registers/gen_registers.py gen def` **after** rebasing onto `origin/main` (which had landed unrelated DEF141/DEF168 row edits in the meantime — regenerated again post-merge so nothing was clobbered).

## Disclosures (STOP-AND-DISCLOSE per the assign's own instruction)

1. **DEF183 and DEF186's acceptance criteria overreach their own DEF row's fix description**, in ways that would either require touching CR129-BE's fenced files (DEF183) or inventing a pricing/product decision unilaterally (DEF186's `credit_service.spend()` metering — "how many credits does a 1-on-1 turn cost?" is Saiful's call, not a security lane's). Scoped both to what the LANE's own acceptance bullets literally say, and said so in the row files rather than quietly under-delivering.
2. **`/v1/coach` shim NOT deleted** (DEF186's fix line said to). It's authenticated (not part of the unauthenticated-spend exposure that motivated H6), reuses Brief's handlers 1:1, and forcibly breaking old TestFlight-build compatibility ("target: two TestFlight releases later" per its own docstring) is a support call I can't verify from here (don't know how many releases have shipped since).
3. **League-standings UUID-enumeration pseudonym (DEF176's review-doc fix, not in the 11 lane acceptance criteria)** — not done. The account-takeover exploit itself is fully closed regardless of whether the UUID is enumerable, since the body `user_id` is now inert.
4. **Historical cleartext rows in `http_audit`** (90 days of pre-fix Alpaca-credential rows, DEF181) — needs a one-off DB migration/script against melehost, not a code change this lane can carry from a Mac-only editor session.
5. **Bug-upload total-size ceiling + janitor, per-user concurrent-run cap** (DEF186's fuller fix list) — not implemented; the lane's own acceptance #8 only asked for rate-bounding, which is done.

## Mutations (acceptance #10)

All three requested (DEF176, DEF177, DEF180) reverted and re-verified RED, then restored and re-verified GREEN. Full detail in `orchestration/audit/cr/SEC-BATCH1.architect.md`. **No mutation came back green** on the specific line it targeted — every test that stayed green during a mutation was, on inspection, testing a DIFFERENT aspect of the fix than the one reverted (e.g. "auth still required" stayed green when I reverted "body user_id is ignored" — correct, since I didn't touch the auth requirement in that mutation).

## Tests

New files: `test_def176_account_takeover.py`, `test_def177_llm_proxy_auth.py`, `test_def180_magic_link_oracle.py`, `test_def181_audit_leakage.py`, `test_def183_oidc_blocking_dos.py`, `test_def184_body_buffering_and_rate_limiter_memory.py`, `test_def185_boot_hardening.py`, `test_def186_llm_spend_limits.py`. Existing tests updated for the new auth requirement on `/v1/auth/apple` (`test_auth_phase1_5_audit_fixes.py`, `test_merge_routes.py`), the bug-upload rate limiter (`test_feedback_api.py` — added an autouse reset fixture), and the compose `_NOT_FORWARDED` comment text (`test_config_compose_parity.py`).

**Full suite (repo root, `"./backend/.venv/bin/python" -m pytest backend/tests/unit/ -q`):** 1702 passed pre-rebase (baseline 1645 + this lane's ~57 new tests + other tests landed on `main` since the 1645 baseline was measured). 3 pre-existing failures (`test_lesson_corpus_integrity.py::test_lesson_codes_are_unique`, `::test_lesson_codes_are_contiguous_within_each_track`, `test_registers_no_drift.py::test_registers_match_their_row_files`) — confirmed via `git stash` against clean `main` that the two lesson-corpus failures pre-date this lane entirely (unrelated content-id collisions); the registers-no-drift failure was transient (my row edits not yet regenerated) and is now green after `gen_registers.py gen def`. Re-ran the full suite after the rebase onto `origin/main` @ `e961dfd1` — result recorded in the audit-bridge file once that run completes.

## Definition of Done

| Item | Status |
|---|---|
| DEF176 fixed + tested + mutation-proven | done |
| DEF177 fixed + tested + mutation-proven; mobile caller check reported | done |
| DEF180 fixed + tested + mutation-proven | done |
| DEF181 fixed + tested (structural backstop, not just the two named paths) | done |
| DEF183 fixed for OIDC; systemic claim disclosed as not met | partial, disclosed |
| DEF184 fixed + tested; named the bound (10 MB, 50k keys) | done |
| DEF185 fixed + tested | done |
| DEF186 fixed for rate limits; credit metering + shim deletion disclosed as out of scope | partial, disclosed |
| No fenced file touched | done (verified via `git diff --name-only` against the fence list) |
| No credential rotated | done |
| Full suite green, ≥1645, from repo root | done |
| Registers regenerated post-rebase | done |
| Mutation tests for 176/177/180 | done, all correctly RED |

**Auditor:** independent (GATE: independent per the assign — two of these were proven exploitable live from the public internet).

STATUS: READY_FOR_AUDIT (round 1)
