# Security Review — 2026-07-29 (v2, deepened 2026-07-30)

Static + **live** cybersecurity assessment of the AMI Trade implementation
(backend, mobile, website API, infra config).

- **v1 (2026-07-29)** — static, read-only, 10 parallel review clusters, two PoCs in
  `backend/.venv`. Reviewer: TRACK K · ROLE Kimi · AT:K1.
- **v2 (2026-07-30)** — critical re-review at Saiful's request ("not deep/secure enough").
  Resolved v1's open questions **against the live Alpha host and LAN**, ran permitted
  non-mutating PoCs (read-only GETs, malformed POSTs that 4xx before any state change,
  `SELECT 1` / Redis `PING` from the LAN — no writes, no LLM spend), corrected two
  false-safe entries, and added findings N1–N8. Reviewer: TRACK SEC · AT:SEC1.
- All findings below are first-hand verified (`file:line` or live command output). Every
  actionable item is filed as a DEF/CR (see **Filing map**) under umbrella **CR123**.

Ratings: **Critical** = remotely exploitable account takeover or direct unauthenticated
cost/credential/data exposure. **High** = privilege/paywall bypass, remote DoS, or severe
weakness needing one plausible precondition. **Medium** = real weakness with meaningful
mitigation in place. **Low/Info** = hardening.

> **Threat model for v2 is beta / public-launch readiness**, per Saiful. Items tolerable at
> a 3-tester Alpha (non-expiring tokens, plaintext mobile storage, thin rate limiting) are
> treated as **blocking** here.

---

## v2 headline: what changed from v1

1. **Two of v1's "open questions" flip severities once answered against the live host** —
   see the Live-verified table. C2 is confirmed **live and internet-reachable** (not
   theoretical); H3 is confirmed **remote-superuser-DB from any LAN device** and promoted to
   Critical for a launch bar.
2. **v1 listed two unsafe things as "verified-sound":** the 5 MB upload cap (defeated by the
   audit middleware — N3) and the audit trail (cannot attribute actions to a user — N5).
3. **v1's own remediations contain a self-inflicted trap:** every "rotate `SECRET_KEY`"
   instruction would silently brick Alpaca encryption, because the same key is reused and the
   crypto layer fails open (N1). A review whose fixes break the app is not deep enough.

---

## Live-verified facts (resolves v1's "Open questions")

From this Mac (on the LAN) and against `https://api-alpha.agenticmarketintel.ai`, 2026-07-30:

| # | Question | Answer (evidence) |
|---|---|---|
| Q1 | Alpha `env`? | **`staging`** — `/v1/health` → `{"env":"staging"}`. **H2's `local`-collapse is NOT live** — latent only. Keep the guard; re-rank H2 below the live items. |
| Q2 | Cloudflare Access in front of api-alpha? | **No.** `/v1/llm/status` → **200** unauthenticated; `POST /v1/llm/translate {}` → **422** (schema error, *not* 401 — proves no auth gate); control `/v1/league/standings` → **401**. `/docs` + `/openapi.json` → **200**. **C2 is live.** |
| Q3 | LAN ports open on melehost? | **Yes — 5434/6379/8000/8001 on `0.0.0.0` and `[::]`** (`ss -ltn`). From this Mac I connected to Postgres as **superuser `postgres`/`postgres` and read all 30 tables**; Redis answered `PING` unauthenticated. **H3 proven.** (Sibling `n8n` on the same host correctly binds `127.0.0.1` — the safe pattern is known and simply not applied to the AMI stack.) |
| Q6 | Edge security headers? | **None** — no HSTS/CSP/X-Frame-Options/X-Content-Type-Options/Referrer-Policy from the CF edge. On an auth host this is a High at a launch bar, not a Low. |

Still open (need operator / dashboard, not resolvable read-only from code):
**Q4** — has the leaked Adanos key been rotated? **Q5** — are `TURNSTILE_SECRET` /
`ALPACA_ENCRYPTION_KEY` set in the gitignored env files?

---

## Critical

### C1 — Account takeover via body-supplied `user_id` on `/v1/auth/apple` and `/v1/auth/google` · **DEF176**

Both social-login endpoints are unauthenticated and accept `user_id` in the body
(`AppleSignInRequest.user_id`, `backend/app/schemas/auth.py:113`; Google `:131`; routes have
no auth dependency, `backend/app/api/auth.py:173-215`).

**Verified exploit path** (code-traced in `auth_service.py`, v2 sharpening v1): the attacker
authenticates with **their own valid** Apple/Google identity token (passes OIDC) *and* sends
`user_id=<victim>`. The attacker's `sub` matches no `apple_id`/`google_id` row and no email
row, so resolution falls through to `if row is None and user_id is not None: row =
select(User).where(User.id == user_id)` (`:466-467` Apple, `:562-563` Google) → loads the
**victim** row → `:484 row.apple_id = apple_sub` **permanently writes the attacker's Apple ID
onto the victim** → returns the victim's bearer token (`:504`). So it is worse than "one
token per victim": the attacker gains **durable** re-entry (their own Apple sign-in now
resolves to the victim) and can lock the real user out.

Victim UUIDs are enumerable: `GET /v1/league/standings` returns `user_id` for every cohort
member (`backend/app/services/league_service.py:279`), verified.

**Fix (DEF176):** remove `user_id` from both request schemas; bind the claim to the caller's
Bearer via `Depends(get_current_user)` exactly like the magic-link routes already do
(`auth.py:130-159`); replace `user_id` in league standings with a display pseudonym.

### C2 — Unauthenticated, unrate-limited LLM proxy: `POST /v1/llm/translate` · **DEF177**

`backend/app/api/llm.py:37-54` declares no auth dependency and streams an arbitrary
`system_prompt` + `user_message` (up to 16,384 tokens) through the live gateway. `GET
/v1/llm/status` (`:32-34`) is also public and discloses provider config. **Confirmed live
(Q2):** `/status` → 200 from the internet returning `{"active_provider":"vllm",...}`;
`/translate` with `{}` → 422 (not 401). The gateway prefers on-prem vLLM but falls back to
Anthropic (direct cash) when vLLM is down.

**Exploit:** anyone on the internet loops POSTs — a free chatbot on our credentials, or a
starvation attack on the LAN vLLM host.

**Fix (DEF177):** gate the router behind `Depends(get_admin)` (it is operator tooling per its
own docstring — only `scripts/translate_arb.py` uses it); stop `/status` disclosing provider
identity to anonymous callers.

### C3 (was H3) — Postgres superuser (`postgres`/`postgres`), no-auth Redis, and API/website ports published on the LAN · **CR124**

`docker-compose.yml:26-31` (`POSTGRES_PASSWORD: postgres`, `"5434:5432"`), `:45-46` (Redis
`"6379:6379"`, no auth), `:210-211` (API `"8000:8000"`), `:299-300` (website `"8001:8000"`).
Compose publishes on `0.0.0.0`; Docker also bypasses ufw.

**Proven live (Q3), not asserted:** from an ordinary LAN device (this Mac) I connected to
Postgres as superuser with the default password and read all 30 tables (users, magic-link
challenges, journals, mandates), and Redis answered `PING` with no auth. "Alpaca rows are
encrypted" gives nothing here — the `SECRET_KEY` that derives the encryption key sits in the
same host's `.env` (see N1). `api-website` shares the Postgres **superuser**
(`docker-compose.yml:286`), so the marketing service is a direct pivot into the app DB. The
direct API port also bypasses Cloudflare edge policy and makes the rate limiter fully
spoofable (it trusts client-supplied `cf-connecting-ip`, `rate_limit.py:69` — see N4).

Promoted from v1's High to **Critical** at a launch bar: this is unauthenticated remote
compromise of the entire datastore from the LAN.

**Fix (CR124):** bind 5434/6379/8001 to `127.0.0.1` (the tunnel reaches the API over the
compose network — the pattern `n8n` already uses on this host); generate a real Postgres
password via env; add Redis `requirepass`; dedicated low-privilege `ami_website` role.

---

## High

### H1 — Paywall bypass: `plan` is client-writable via `PATCH /v1/mandate/{user_id}` · **DEF179**

`backend/app/api/mandate.py:89-99` takes a raw `dict[str, Any]` →
`mandate_store.py:91-113` shallow-merges and re-validates through the `Mandate` schema
(verified). `plan`, `credit_balance`, `trial_expires_at` are all valid `Mandate` fields
(`schemas/mandate.py`), so `{"plan":"floor_manager"}` **validates and persists** — schema
re-validation (DEF062) blocks only wrong *types*, not entitlement escalation. Two consumers
read the stored mandate's plan instead of server-side `users.plan`:

- 1-on-1 agent-lock gate reads `mandate.plan` directly
  (`backend/app/api/one_on_one.py:69-84`, verified) — patching unlocks all 12 agents free.
- Brief edit-cap/retention (`brief_engine.py:382-386`) — bypasses the Floor Pass 3-edit cap.
- Second vector needing no PATCH: `hydrate_brief_mandate` trusts the client `mandate_override`
  body (`brief_engine.py:536`).

Money paths (Room credits) are unaffected — `credit_service` uses `effective_plan_for_user()`.

**Fix (DEF179):** strip entitlement fields in `patch()` and the hydrate-override path; switch
the two consumers to `effective_plan_for_user(user_id)`.

### H2 — `ENV` defaults to `local` in compose; empty `SECRET_KEY` passes the boot check · **DEF185**

`docker-compose.yml:71` — `ENV: ${AMI_ENV:-local}`. **Latent, not live (Q1 says Alpha runs
`staging`).** But the failure mode is real: if `AMI_ENV` were ever unset, the tunneled
container boots `local`, which enables legacy unsigned scaffold tokens
(`auth_service.py:201-208`), returns magic-link debug codes in the API response
(`auth.py:144`), and disables the SECRET_KEY boot check (`main.py:50` fires only when
`env != "local"`). Compounding and **not** env-gated: `main.py:50` passes when `SECRET_KEY=""`
(only the literal default string is refused), and an empty key makes every bearer forgeable
(`HMAC(b"", user_id)`) **and** silently disables Alpaca encryption (N1). `/v1/health` leaks
`env` publicly, so any misconfig is remotely detectable.

**Fix (DEF185):** `ENV: ${AMI_ENV:?must be set}`; extend the boot check to refuse empty/short
keys in non-local; refuse `env=local` when a public hostname is configured.

### H4 — Credential/token leakage into `http_audit`; audit cannot attribute actions · **DEF181**

`SCRUB_PATHS` (`middleware/http_audit.py:38-45`) covers six auth routes but:

- `POST /v1/alpaca/link` and `/link_apikey` bodies (`{"api_key","api_secret"}` / OAuth code)
  are persisted **cleartext** to `http_audit.request_body` for 90 days — bypassing the DEF044
  encryption-at-rest control.
- `GET /v1/auth/me?token=` accepts a bearer as a query param (`auth.py:326`); the middleware
  records the query string verbatim (`:143`). Tokens are stateless HMAC with no `exp` and no
  revocation (`DELETE /v1/auth/session` is a no-op, `auth.py:312-320`), so a DB/backup read
  yields permanent access. The Flutter client uses the header — the query path appears unused.
- **N5 (new):** `_user_id_from_request` (`:163-178`) only reads `user_id`/`userId` **path
  params** and **never parses the bearer**, despite its docstring. Most sensitive routes
  derive the user from the token, so the audit record has `user_id = NULL` for nearly every
  authenticated action — the forensic trail you'd need after a breach is blind.

**Fix (DEF181):** add both Alpaca paths + a generic `*secret*/*token*/*api_key*` body-field
scrubber to `SCRUB_PATHS`; drop/scrub the `?token=` variant; purge historical rows; fix
`_user_id_from_request` to parse the bearer via `parse_scaffold_token`.

### H5 — Magic-link verify is an unthrottled, cross-user 6-digit-code oracle · **DEF180**

`/v1/auth/magic_link/verify` has **no rate limiter** (only `/start` is limited, 3/min/IP —
`auth.py:125-128`, verified). `verify_magic_link` looks up the active challenge by **email
only** (`auth_service.py:373-380`), not bound to a caller. There is a 5-attempt cap per
challenge (`MAX_MAGIC_LINK_ATTEMPTS`, `:55` — v1 credited this correctly), but an attacker
loops `/start` (mints a fresh challenge, attempts=0) then fires 5 guesses per challenge:
≈21,600 guesses/day/IP against a targeted account, and each wrong burst force-consumes the
victim's legitimate challenge → login-DoS. Adjacent (was M5): `/start` is also an
unauthenticated **email relay** — attacker-triggered AMI-branded mail to any address, a
deliverability/reputation risk that could take down *all* logins.

**Fix (DEF180):** rate-limit `/verify` per-IP **and** per-target-email; bind verification to
the challenge's `user_id`; throttle `/start` per-email (not just per-IP).

### H6 — Unmetered, unrate-limited LLM spend on 1-on-1 and Brief · **DEF186**

Only three rate limiters exist (`/auth/anon`, `/magic_link/start`, `/room/stream` —
`rate_limit.py:111-123`, verified). The only `credit_service.spend()` call sites are in
`room_runner.py`; 1-on-1 messages and Brief turns debit **zero** credits
(`api/one_on_one.py`, `brief.py`), and the deprecated `/v1/coach/*` shim doubles the Brief
surface (`coach.py`). `OneOnOneMessageRequest.user_message` has no `max_length` and
client-supplied `history` is passed verbatim to the LLM. No per-user concurrent-run cap
(dedup is per `(user,ticker)` only).

**Exploit:** one free anon token → unlimited LLM turns with megabyte histories (Anthropic =
cash on vLLM outage), held SSE connections, unbounded journal/audit growth.

**Fix (DEF186):** price 1-on-1/Brief turns via `spend()`; per-`user_id` rate limits; schema
length caps; per-user concurrent-run/stream caps; delete the `/v1/coach` shim.

### H7 — Live Adanos API key committed to git history (pushed to GitHub) · **DEF178**

`ADANOS_API_KEY_SECONDARY=sk_live_<REDACTED — see DEF178>` is committed verbatim in **two**
checkpoint memos (`.deliveryos/checkpoint_history/20260720T141647Z_*.md`,
`20260721T112511Z_*.md`) and was present in v1 of this review doc (redacted here). A
2026-07-25 memo confirmed the key **valid with 141/250 quota remaining**. It is on
`origin/main`. (Correction to a v2 first-pass note: the `sk_live_test` string in
`backend/tests/unit/test_def099_merge_billing.py` is a **placeholder**, not the live key.)

**Exploit:** anyone with repo read access burns the 250-call/month quota — silently darkening
the Social Analyst feed (CR024 gate) — or gets the account suspended.

**Fix (DEF178) — v1's "redact the memo" is insufficient (N8):** redaction of the working tree
does **not** unpublish a pushed secret. Required: (1) **rotate/revoke** both Adanos keys now
(operator — Saiful), (2) **rewrite git history** (BFG/`filter-repo`) and force-update
`origin/main`, (3) redact all working-tree copies, (4) add a `sk_live_`/`sk-ant-` pre-commit +
CI grep guard. Step 2 is destructive and force-push — **operator-approved only**, not run
autonomously.

### H8 — Mobile session token: plaintext `shared_preferences`, never expires, cannot be revoked · **CR125**

Token + user id persisted via SharedPreferences (`ami.bearer_token`,
`mobile/lib/services/device_user.dart:59-121`, verified); `flutter_secure_storage` is declared
in `pubspec.yaml:29` but **never imported anywhere in `mobile/lib/`** — dead dependency. The
token is a stateless `scaffold:<hex>:<HMAC(secret,user_id)>` with no `exp` and no server-side
invalidation. `android:allowBackup` is unset in the manifest → defaults `true`, so the token
rides Auto Backup; iOS NSUserDefaults rides iCloud/iTunes backups.

**Exploit:** anyone with a device backup reads the token cleartext and gains **permanent**
impersonation; "Sign out" only wipes the local copy.

**Fix (CR125, breaking — needs a mobile release + forces re-auth):** move the token to
`flutter_secure_storage` (Keychain this-device-only / Keystore); set
`android:allowBackup="false"`; backend adds `exp` + a per-user token-version checked at parse
time so `DELETE /v1/auth/session` actually revokes.

### H9 — Unauthenticated bug-report uploads with no aggregate cap (disk-fill DoS) · **DEF186 / CR124**

`POST /v1/feedback/bug` accepts multipart uploads unauthenticated by design
(`feedback.py:42-50`, verified) with no rate limit. Per-file controls are genuinely good
(5 MB streaming cap, MIME allowlist, `O_EXCL`, no download route). **But v1 missed N3:** the
per-file cap is defeated *before the handler runs* — see N3. Even setting N3 aside, no
aggregate quota and nothing prunes the `bug_attachments` volume, so looping 5 MB uploads fills
the melehost disk → Postgres and the API degrade.

**Fix:** tight IP-keyed limiter (e.g. 5/hour), total-size ceiling, janitor job (folded into
DEF186 metering + CR124 volume hygiene).

### N2 — Blocking I/O on the event loop = unauthenticated remote DoS (new) · **DEF183**

`oidc_verifier.py:156` uses a **synchronous** `httpx.Client` for the JWKS fetch, inside the
`async` `/v1/auth/apple` + `/v1/auth/google` handlers, **while holding `threading.Lock`**
(`:142`). An unknown-`kid` token forces **two** fetches (`:146,:150`) at 5 s each → ~10 s of
**whole-process** stall (single uvicorn worker), freezing every request and every SSE stream.
Systemic: 93 `async def` handlers across `api/*.py` do synchronous DB work via `get_session()`
on the loop; any slow upstream (Apple, yfinance, Adanos, Reddit) has the same blast radius.

**Fix (DEF183):** `run_in_threadpool` / async client for sync I/O in `async` handlers (OIDC
first), or make the routes `def` so Starlette threadpools them.

### N3 — The 5 MB upload cap is defeated by the audit middleware; no body/memory ceiling (new) · **DEF184 / CR124**

`http_audit.py:65` calls `await request.body()` — buffering the **entire** request body into
RAM for every non-skipped route **before** any handler-level streaming cap applies. There is
no global request-size limit anywhere, and **no container has a memory limit** (`docker stats`
→ 14.86 GiB available, unbounded). So a single multi-GB POST to **any** route OOM-kills the
box, taking Postgres + API with it. This is why v1's "per-file controls are good → verified
sound" is wrong.

**Fix:** reject oversized `Content-Length` before buffering; skip body capture for
multipart/large bodies (DEF184); set compose `mem_limit` on every service (CR124).

---

## Medium

| # | Finding | Evidence | Fix | Filed |
|---|---|---|---|---|
| N4 | Rate limiter is a memory-exhaustion primitive + trivially bypassed: unbounded `defaultdict` keyed on attacker-controlled `cf-connecting-ip`, never evicted; spoof a unique value per request → bypass every per-IP limit **and** grow the dict without bound | `rate_limit.py:58,69` | cap/evict key space; derive client IP from a trusted hop only | **DEF184** |
| N6 | `n8n` container shares the Docker network (`ami-trade-local_default`) with Postgres/Redis/api-alpha — broad RCE/SSRF surface with a direct path to the superuser DB + no-auth Redis + internal API | `docker inspect` (live) | isolate the AMI stack on its own network; evict `n8n` | **CR124** |
| N7 | Both app containers run as **root** (`docker exec … whoami` → root) — v1 flagged only the website container | live | non-root `USER` in both Dockerfiles | **CR124** |
| M1 | RevenueCat webhook: no event-ordering guard — a retried stale EXPIRATION revokes a newer paid grant (`event_timestamp_ms` unused) | `webhooks.py:330-345` | per-user high-water mark, or confirm via RC API before revoke | CR123 backlog |
| M2 | CANCELLATION revokes immediately, forfeiting the remaining paid period | `webhooks.py:66,330-345` | revoke only on EXPIRATION / refund-reason CANCELLATION | CR123 backlog |
| M3 | `credit_service.spend()` read-modify-write without row lock — double-spend latent (masked today by a single worker + await-free caller) | `credit_service.py:242-313` | `with_for_update()` or atomic conditional UPDATE | CR123 backlog |
| M4 | Website API: Turnstile fails open silently when secret unset | `website_api/app/services/turnstile.py:24-25` | refuse/loud-log in prod when unset | CR123 backlog |
| M5 | Website API: unauthenticated email relay — AMI-branded mail (incl. LLM auto-answer) to arbitrary addresses | `contact.py:44-78`, `email_service.py:82-99` | double-opt-in before content-bearing mail; strip URLs from LLM answers | CR123 backlog |
| M6 | Website API: HTML injection into operator notification emails (raw user subject/body unescaped) | `email_service.py:130-141` | `html.escape()` all user lines | CR123 backlog |
| M7 | Website API: `/waitlist` — no rate limit, no Turnstile, no length caps | `waitlist.py:32-43` | limiter + `max_length` + Turnstile | CR123 backlog |
| M10 | Indirect prompt injection: Reddit snippets injected verbatim into Social Analyst prompt → Room PM. Blast radius bounded by the deterministic safety floor + no auto-execution | `social_context.py:207-209,336-337` | strip newlines/`─` glyphs like `news_context.py:324` | CR123 backlog |
| M11 | Streak→credit milestones farmable: any free-form `POST /v1/journal` counts as a streak day; ladder pays 660 real credits | `reputation_service.py:82,386-389` | only system-generated entry types qualify | CR123 backlog |
| M12 | Alpaca OAuth link has no `state` nonce; mobile WebView intercepts any `amitrade://alpaca/callback?code=`, no host allowlist, unrestricted JS | `alpaca.py:86-105`, `alpaca_connect_screen.dart:306-337` | per-user `state`; navigation host allowlist | CR123 backlog |
| M13 | DB backups unencrypted; perms depend on a manual step; script defaults `PGPASSWORD=postgres` | `infra/backups/pg-backup.sh:33,40,56` | require password, `chmod 600`, encrypt before offsite | **CR124** |
| M14 | Runtime images ignore `uv.lock` (`uv pip install -e ".[dev]"` re-resolves + ships dev tools); floating tags (`cloudflared:latest`, `postgres:15-alpine`) | `backend/Dockerfile:13`, `docker-compose.yml:22,43,242` | `uv sync --locked --no-dev`; pin by digest | **CR124** |
| M15 | Empty `SECRET_KEY` passes the boot check → forgeable tokens + plaintext Alpaca (one-line slip) | `main.py:50`, `alpha.env.example:67` | refuse empty/short keys in non-local | **DEF185** |

---

## Low / Info

- **Edge security headers absent (Q6)** — no HSTS/CSP/X-Frame-Options/X-Content-Type-Options/
  Referrer-Policy. Add at the CF edge (Transform Rule) or in a backend middleware. *Raised to
  High-adjacent at a launch bar; tracked in CR123.*
- **OIDC `alg` taken from the token header** (`oidc_verifier.py:80,96`) — *not exploitable* on
  python-jose 3.5.0 (v1 PoC: jose rejects an asymmetric key as HMAC secret). Still pin
  `algorithms=["RS256"]` — the safety currently rests on a library-internal guard.
- **`/docs` + `/openapi.json` publicly served (confirmed 200, Q2)** — full API schema incl.
  admin surface as recon aid. Gate behind admin or disable in staging.
- **`/admin` HTML** stores `ADMIN_SECRET` in `localStorage`, renders server data via
  `innerHTML`, no CSP (`static/admin.html:302-303,536+`).
- **PII in audit:** `/v1/auth/me` bodies (email, apple_id, google_id) buffered into
  `http_audit.response_body`; first 64 KB of bug-report photos persisted; account deletion
  doesn't touch the three audit tables (90-day trim vs 30-day policy).
- **Bearer tokens never expire** (mobile half = H8) — no `exp`/`jti`/version. → **CR125**.
- **Magic-link codes hashed with unsalted SHA-256** (`auth_service.py:144-145`) — full 6-digit
  keyspace trivially reversible from a DB read; use HMAC.
- **Unvalidated free-form `ticker`** flows into DB, journal titles, agent prompts, outbound URL
  paths (self-scoped only); no `max_length` on journal title/summary.
- **Safety floor "appended LAST"** but Room PM prompt places ticker/transcript after it
  (`agent_prompts.py:77-95` vs `room_prompts.py:479`) — defense-in-depth erosion; the
  deterministic floor still gates.
- **Mobile:** no cert pinning; legal WebView `JavaScriptMode.unrestricted` with no navigation
  limits; Android manifest relies on a library merge for `INTERNET`.
- **Legacy systemd unit:** `--forwarded-allow-ips=*` trusts spoofed XFF if revived.
- **Website:** container runs as root, unpinned base; `WEBSITE_TEST_DATABASE_URL` overrides
  `DATABASE_URL` in any env; GDPR data-request has no identity verification.
- **Per-IP (not per-user) limiter keying** — carrier-NAT + botnet multiplication; limiter is
  in-memory per process (see N4). → **DEF184/DEF186**.
- **`python-jose>=3.3` floor** permits CVE-2024-33663/33664 — raise to `>=3.5` (locked is
  3.5.0).

---

## Verified-sound controls (v2 — two v1 entries removed)

Confirmed by code/live inspection, NOT trusted from docs:

- **RevenueCat webhook fail-closed:** 503 + log on unset secret, `hmac.compare_digest`, 401 on
  mismatch, `event_id` UNIQUE insert-first replay protection (`webhooks.py:77-92,262-279`).
- **Admin bearer:** timing-safe compare, 503 when unset (`admin.py:53-64`).
- **SECRET_KEY boot refusal** fires for the default key in non-local (`main.py:50-55`) — modulo
  the empty-key gap (H2/M15).
- **OIDC does real verification:** JWKS fetch + signature + `iss`/`aud`/`exp` membership checks
  (`oidc_verifier.py:64-132`), verified. (The blocking-fetch DoS is N2, separate.)
- **`get_current_user` is clean:** token parsed + HMAC-verified, live row required, suspended
  gate (`dependencies.py:29-62`), verified.
- **Magic-link 5-attempt cap** exists and locks the challenge (`auth_service.py:55,386-394`).
- **SQL injection: clean** (ORM, bound params; only static `text()` index predicates). *v2
  did not re-audit exhaustively — carried from v1.*
- **SSRF / path-traversal: clean** — outbound base URLs are constants/env; upload names
  server-generated, extension+MIME allowlist, streaming cap, no download route. *Carried from
  v1.*
- **LLM-output → action gate is structural:** unparseable PM reply fails safe to PASS; every
  APPROVE wrapped by deterministic `enforce_safety_floor`; `/v1/sim/submit` re-runs compliance
  server-side. *Carried from v1; not re-verified in v2.*
- **IDOR guards uniform:** per-user routes scoped by bearer-derived user; merge routes gated by
  a recorded `account_adoption` event (`auth.py:218-234`), verified.
- **Header scrubbing:** no request/response **headers** persisted — structurally cannot leak
  `Authorization`/`Cookie` (the leaks are query/body, H4).
- **No `.env` ever committed** (`git log --diff-filter=A` clean); `.gitignore` covers
  `infra/*.env`; keystore/`.p8` live outside the repo.

**Removed from v1's "verified-sound" list** (were false): the 5 MB upload cap (defeated by
`http_audit` pre-buffering — N3) and the audit trail (cannot attribute actions to a user —
N5).

---

## Filing map (umbrella CR123)

| Item | ID | Type | Domain | Wave |
|---|---|---|---|---|
| Security-hardening program (owns this doc; tracks the M/Low backlog) | **CR123** | CR | governance | — |
| C1 social-login takeover | **DEF176** | DEF | api | same-day |
| C2 unauth LLM proxy | **DEF177** | DEF | api | same-day |
| H7 leaked Adanos key: rotate + history purge + guard | **DEF178** | DEF | process/secrets | same-day |
| H1 mandate entitlement bypass | **DEF179** | DEF | api | this week |
| H5 magic-link oracle + relay | **DEF180** | DEF | api | this week |
| H4 + N5 audit leakage + attribution | **DEF181** | DEF | api/middleware | this week |
| N1 SECRET_KEY reuse + fail-open crypto (degrade-loudly / CR040) | **DEF182** | DEF | core | this week |
| N2 blocking-I/O DoS | **DEF183** | DEF | api | this week |
| N3 body buffering + N4 rate-limiter memory/keying | **DEF184** | DEF | api/infra | this week |
| C3 + N6 + N7 + M8/M13/M14 melehost/compose hardening | **CR124** | CR | infra | before next promotion |
| H2 + M15 env/boot hardening | **DEF185** | DEF | core/infra | before next promotion |
| H6 LLM spend metering + caps + delete `/coach` | **DEF186** | DEF | api | before next promotion |
| H8 mobile secure storage + token exp/revocation (breaking) | **CR125** | CR | mobile+api | before next promotion |

M1–M4, M6–M7, M10–M12 + the Low/Info items are tracked as the CR123 backlog and minted as
DEFs when scheduled.

---

## N1 — `SECRET_KEY` reuse + fail-open crypto (the v1-remediation trap) · **DEF182**

Called out separately because it changes how every other fix must be sequenced.

`secret_crypto.py:42` derives the Fernet key from `settings.secret_key` when
`alpaca_encryption_key` is empty — and it is empty by default (`config.py:279`). So the single
app secret protects **both** bearer-token integrity **and** Alpaca broker-secret
confidentiality, with no separation and no rotation path. Worse, the crypto layer **fails
open**: `decrypt_secret` returns the **raw stored value** on `InvalidToken` (`:72-75`) and on
missing key (`:68-69`) rather than raising.

Consequence the v1 review did not connect: **every "rotate `SECRET_KEY`" remediation it
recommends (H2, H7, M15) would silently destroy all Alpaca ciphertext** — post-rotation,
`decrypt_secret` can't decrypt the old rows, returns the ciphertext, and the Alpaca client
sends `gAAAAA…` as an API key. Silent, app-breaking, and a direct violation of the project's
own **degrade-loudly** rule (CLAUDE.md / CR040 — "if this fires constantly and silently, what
does the user end up believing?").

**Fix (DEF182):** (1) set a dedicated `ALPACA_ENCRYPTION_KEY` distinct from `SECRET_KEY`; (2)
make `decrypt_secret` **raise/loud-log** in non-local env instead of passing ciphertext
through; (3) add a key-version marker (`enc::v2::`) + a documented, tested rotation procedure
(dual-key read during rollover). This must land **before** any `SECRET_KEY` rotation in H2/H7.

---

*Reviewers: TRACK K · Kimi (v1, AT:K1) · TRACK SEC (v2, AT:SEC1). No changes made to
application code in the review sessions; all fixes filed as DEF176–DEF186 / CR123–CR125.*
