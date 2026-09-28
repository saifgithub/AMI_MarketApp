# CR246 — Backend concurrency: verify the Room (and the API generally) handles multiple simultaneous users correctly

**Status: proposed, not started.** Filed by investigator session (AT:R85),
2026-09-28. Saiful, 2026-09-28, after a live incident (below) surfaced this
gap: *"This brings me to a very important point. Mint a new CR. we need to
test the back end system for concurrency. We need to be sure that we can
handle multiple users at the same time."* To be assigned to another agent
for build/verification.

## Why this CR exists — the incident that surfaced it

While running the CR228 risk-appetite dial-run investigation, a research
toolkit (`docs/tools/room_investigation/room_ticker_batch.py`) was just
extended to run several Room convenes concurrently instead of strictly
sequentially, and a real backend defect surfaced the first time it ran ≥2
convenes truly in parallel:

```
room_sim_holdings_failed        error='Multiple rows were found when one or none was required' user_id=<uuid>
room_sector_context_holdings_failed error='Multiple rows were found when one or none was required' user_id=<uuid>
```

**What happened, precisely:** the toolkit runs several tickers concurrently
under the SAME synthetic `user_id` (one mandate, one mock user, N tickers).
The first batch of concurrent convenes for that brand-new user all called
whatever `sim.ensure_portfolio(user_id)`-style get-or-create path backs
`_build_sim_holdings_block`/`_build_room_sector_context`
(`backend/app/services/room_runner.py` — the callers around lines
1930-1958, 2020-2037) at the same instant. Multiple coroutines raced the
same get-or-create query, each found no existing row, and multiple rows got
created for the one user — a classic TOCTOU (time-of-check-to-time-of-use)
race on a get-or-create that assumes "there is at most one" without a
unique constraint, upsert, or lock enforcing it.

**Why this did NOT corrupt anything — and why that's not the same as
"safe":** the code's own `except Exception` handler
(`room_runner.py:1948-1958`, and the twin at ~2037) caught the
`MultipleResultsFound`-style error, logged it loudly (CR040's degrade-loudly
rule working exactly as designed), and fell back to an honest "Portfolio
unavailable this run" line rather than silently serving wrong holdings data.
**That is the fallback working, not the underlying race being safe.** The
race itself — two or more requests for the same user creating duplicate
portfolio rows — is a real defect independent of whether the caller happens
to have a good fallback for read failures. A duplicate `SimPortfolioRow` (or
whatever table backs this) left behind after the race is exactly the kind
of state corruption that can bite a LATER read that doesn't have this
particular try/except around it.

## Why this is NOT already answered by other work

- **CR228's own toolkit runs (including the one that hit this) always used
  ONE synthetic user per batch, sequentially, until 2026-09-28.** The
  concurrency-safety check done before adding parallel execution to the
  toolkit (2026-09-28, same day) explicitly verified `RoomRunner.run()`'s
  OWN state (local variables, no `self` mutation on the hot path) and
  `LLMGateway`/`OpenAICompatibleProvider`'s httpx client sharing — it did
  **not** check DB-side get-or-create races for concurrent calls sharing one
  `user_id`, because until this same day nothing in the toolkit exercised
  that path. This CR is exactly the gap that check didn't cover.
- **CR245** (Beta infra 1000-user sizing, proposed) discusses Supabase's
  ~490-500 direct-connection ceiling as a capacity/cost planning number —
  it's about HOW MANY connections the infra can open, not whether the
  APPLICATION CODE behaves correctly when N of those connections are
  in flight for the same or different users at once. Different question.
- **No existing CR/DEF (grepped `docs/forward_planning/`, `docs/defect/`
  for "concurrent", "race condition", "load test", "simultaneous users")
  addresses backend correctness under concurrent real-user load.** This is
  genuinely new ground.
- Production's live traffic pattern already fans out 12 concurrent LLM
  calls PER SINGLE convene (documented in `llm_gateway.py`'s own comments —
  `OutputConstraint` is `frozen` "because providers are shared singletons
  serving concurrent runs") — so SOME concurrency is already proven safe in
  production every day. What's untested is concurrency ACROSS different
  in-flight convenes/users hitting shared resources: the DB, the safety
  floor / risk-budget bookkeeping, sim portfolio writes, credit-balance
  deduction, journal writes, rate limiting.

## Scope — what this CR should verify

**Primary question: does the backend produce CORRECT results (not just
"doesn't crash") when multiple real users hit it at the same time?**
Specifically:

1. **Get-or-create / first-write races for a single user.** The exact bug
   above: does any code path assume "there is at most one X for this user"
   without a DB-level unique constraint or an atomic upsert enforcing it?
   Audit candidates: `sim.ensure_portfolio` (or wherever the portfolio
   get-or-create actually lives — confirm the real function name/file),
   any similar pattern for mandates (`MandateRow`), journal entries, credit
   balances. A single new user's FIRST convene (or first anything) is the
   highest-risk moment — that's exactly when "no row yet" races are
   possible, and it's also exactly onboarding, the highest-traffic single
   moment in a real user's lifecycle.
2. **Two genuinely DIFFERENT users convening at the same time.** Does
   User A's convene ever read/write anything that leaks into User B's
   convene — portfolio data, mandate fields, risk-budget consumption,
   credit balance, rate-limit counters, the DB session itself? (The
   concurrency-safety check done 2026-09-28 found `RoomRunner.run()`'s own
   state is per-call-local and DB access goes through a fresh pooled
   session per call — that's a good sign, but it was reasoned from reading
   code, not from an actual concurrent-different-users load test.)
3. **Shared mutable resources under concurrent write.** Credit-balance
   deduction (a classic double-spend race if not atomic), risk-budget /
   drawdown bookkeeping if two convenes for the same user overlap, the
   safety-floor's compliance checks, `RoomRunner`'s own
   `_active_queues`/`_active_by_key` dedup dicts (`room_runner.py`, per the
   2026-09-28 audit — these ARE touched by `start_run()`, the REAL
   production entry point, unlike the toolkit's direct `run()` calls; the
   2026-09-28 audit explicitly did not need to check this because the
   toolkit bypasses `start_run()`, but real production traffic does not
   bypass it).
4. **DB connection pool behavior under real concurrent load** — not just
   "does SQLAlchemy's QueuePool exist" but what actually happens when
   concurrent requests exceed pool size: do they queue and wait
   (acceptable, if bounded) or error out? What's the configured pool size
   vs. Supabase's ~490-500 connection ceiling (CR245) — is there a
   realistic simultaneous-user count where the app's own connections could
   approach that ceiling, and what happens at/near it?
5. **Rate limiting / provider-side concurrency** — separate from the DB
   question: does concurrent LLM traffic across multiple users' convenes
   hit any provider-side rate limit (vLLM's real GPU capacity, Kimi/DeepInfra
   API limits) in a way that degrades gracefully (queued, backed off) vs.
   ungracefully (silent failures, wrong provider fallback, scripted-fallback
   rate spiking under load in a way a single low-traffic convene never
   reveals)?

## Suggested method (for the assigned agent to refine)

- **Start from the reproduced bug.** Reproduce the exact race with a
  minimal repro (N concurrent requests for ONE brand-new user's first
  action) against a real or realistic-enough backend, confirm root cause
  (the specific get-or-create call site), fix it properly (DB unique
  constraint + `ON CONFLICT`/upsert, or a per-user advisory lock, or
  whatever's idiomatic for this codebase's ORM/DB layer) — not just widen
  the try/except.
- **Then widen to a real concurrent-load test**: N simulated DIFFERENT
  users, each triggering a real Room convene (or other write-heavy
  endpoints — onboarding, trade execution, credit deduction) at
  overlapping times, against a staging-like environment (not production
  Alpha — melehost's `ami_api_alpha` serves real users; use a disposable
  container or a load-test-specific DB). Assert: no cross-user data leakage,
  no lost updates, no duplicate rows, credit balances end up mathematically
  correct after N concurrent deductions, DB connections stay within
  configured pool bounds.
- **Decide what "handles concurrency" means as a pass/fail bar** before
  building — e.g., "N=10 concurrent distinct users, each completing a full
  Room convene, zero data corruption, zero cross-user leakage, p99 latency
  within X" — rather than an open-ended exploration.

## Non-goals

- Does not re-litigate CR245's capacity/cost sizing (connections, Cloud Run
  scaling, GCP project topology) — that's planning, this is correctness.
- Does not require fixing every finding immediately — surfacing real races
  with reproductions and severity is the deliverable; fixes can be their
  own DEFs if the assigned agent prefers to triage that way.
- Does not test the research toolkit itself (`room_ticker_batch.py`) beyond
  what's needed to explain how this was discovered — the toolkit's own
  concurrency (client-side, single synthetic user, controlled research use)
  is a different, already-shipped, narrower concern from "can production
  handle N real users."

## Acceptance (draft — refine at build time)

- The exact `room_sim_holdings_failed`/`room_sector_context_holdings_failed`
  race is root-caused (the real get-or-create call site named) and fixed at
  the DB/ORM level, not just tolerated by the existing try/except.
- At least one other shared-mutable-resource path (credit balance, or
  risk-budget bookkeeping, or the `start_run()` dedup dicts) is checked for
  the same class of race under real concurrent load, not just reasoned
  about from reading code.
- A repeatable concurrent-load test exists (script or documented procedure)
  that the team can re-run after future changes to check this doesn't
  regress.
- A clear, numeric pass/fail bar for "handles concurrent users" is stated
  and met, or the gap it doesn't meet is documented with severity.
