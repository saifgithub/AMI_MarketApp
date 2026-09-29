# CR246 — What we are building: the concurrency test system

**Audience: Saiful.** This document explains, in plain terms, the system we will
build to load-test the AMI Trade backend — what each piece is, what it does, and
what you will see when it runs. Decisions recorded 2026-09-30 (planning session,
AT:K5). Companion to the CR itself:
[`CR246_backend_concurrency_load_testing.md`](CR246_backend_concurrency_load_testing.md).

## The one-paragraph version

We stand up a **throwaway copy of the backend** on minihost (the spare Ubuntu
machine at 192.168.20.14), pointed at a **fake LLM** so tests are free and
deterministic. Then a **load script** on the Mac pretends to be **10 different
users at the same time** — each doing realistic things (reading portfolios,
onboarding, convening the Room, trading) — for 20 minutes. (Scale set at **10**
concurrent users, not 50: minihost is a small box — 4 cores / 15GB — and Saiful
capped it accordingly.) Afterwards we audit
the database for correctness: nobody saw anyone else's data, no duplicate rows,
credit balances add up exactly. The result is a plain **pass / fail / partial
verdict** against numbers we fix before running, plus a reusable script we can
re-run before every release.

## The four pieces

### 1. The throwaway backend (on minihost)

1. A second Docker Compose project named `ami-loadtest` on minihost: its own
   Postgres, its own Redis, its own API container. Completely separate from
   alpha — alpha's real users are never touched.
2. Code gets there by rsync of a tagged repo snapshot — the same transport
   `/promote-to-alpha` already uses, just a different host. No new machinery.
3. Key settings for this copy:
   1. `ENV=staging` — a real deployment mode, not a test hack.
   2. **Mock LLM** (`VLLM_BASE_URL` unset / `LLM_FORCE_PROVIDER=mock`): every
      AI call returns canned text instantly. Costs nothing, behaves
      deterministically, and means any slowness we see is *our* code or the
      database — not the LLM.
   3. `USE_REAL_MARKET_DATA=False` — deterministic simulated prices.
   4. Its own `SECRET_KEY` — tokens minted here are invalid on alpha, so a
      mistake can never leak across.
4. Tearing it down is one command (`docker compose down -v`) — disposable by
   design.

### 2. The load harness (k6, run from the Mac)

1. **k6** is a standard load-testing tool: you write a script describing what
   virtual users do, and it runs N of them in parallel, measuring every request.
   We already have a small k6 script (`backend/scripts/load_test_1on1.js`,
   CR126); this extends it.
2. Before the run, the harness **mints ~15 fresh users** through the real
   signup endpoint (`POST /v1/auth/anon`) — exactly how a real new user appears.
   It paces itself under the real 10-per-minute signup limit, so we test the
   system as it actually behaves, with no test-only backdoors.
3. Each virtual user then loops through a **realistic activity mix**:

   | Activity | Share | What it does |
   |---|---|---|
   | Browsing | 50% | Reads portfolio, sector-watch, health, trade history |
   | Onboarding | 15% | Starts the interview, answers questions, confirms |
   | Room convene | 15% | Convenes the 12-agent Room on a ticker (the heaviest operation) |
   | Trading | 15% | Previews a trade, submits it, later closes it |
   | Brief / 1-on-1 | 5% | Talks to an agent, adjusts the mandate |

   The mix matters: real load is *different users doing different things at
   once*, and that's where races and leaks hide. 50 copies of one action would
   miss most of them.
4. The harness obeys the app's real per-user rate limits (Room: 5/min etc.) —
   they are part of the product being tested, not obstacles.

### 3. The correctness audits (after the run)

"Didn't crash" is not the bar. After each run we check the database directly:

1. **No duplicate portfolio rows** per user — this re-checks the exact race
   condition (`ensure_portfolio`) whose discovery triggered CR246.
2. **Credit math is exact**: every user's ledger entries sum to their balance.
   Concurrent deductions must never lose or invent credits.
3. **No cross-user leakage**: during the run the harness asserts every response
   belongs to the user who asked; zero violations allowed.
4. **Database connections stayed within bounds**: sampled live during the run
   against the pool ceiling (a known weak spot — the backend currently runs one
   worker with a ~15-connection default pool).

### 4. The verdict — fixed pass/fail bar

Set before the first run, reported against after:

1. 10 distinct concurrent users, sustained 20 minutes.
2. **Zero** data corruption (audits 1–2), **zero** cross-user leakage (audit 3).
3. Server-error (5xx) rate under 1%.
4. p99 latency under 2 seconds on all endpoints (possible because the mock LLM
   removes the LLM from the timing — a slow endpoint = an app or DB problem).

Output is a short report: pass / fail / partial, the numbers, and any defects
found — each filed as its own DEF, not silently patched inside this CR.

## What this deliberately does NOT do (yet)

1. **Real vLLM under load** — deferred to a later phase. Testing whether the LLM
   gateway queues/backs off gracefully when the on-prem vLLM is saturated is a
   real question, but mixing it in now would muddy the app-level correctness
   results. Recorded as deferred in the CR.
2. **Beta-scale topology** — Cloud Run, Supabase connection ceilings, CR245
   sizing. This test runs on minihost; it answers "is the app correct under
   concurrency," not "is GCP big enough."
3. **Alpha** — never touched.

## Deliverables when built

1. `ami-loadtest` compose + env definition under `infra/`, deployable to
   minihost in one command.
2. The k6 multi-scenario harness under `backend/scripts/`, runnable from the
   Mac in one command.
3. The audit script (SQL + report generator).
4. A runbook (how to deploy, run, read results) so any future session can
   re-run the whole thing before a release.
5. The first verdict report against the bar above.
