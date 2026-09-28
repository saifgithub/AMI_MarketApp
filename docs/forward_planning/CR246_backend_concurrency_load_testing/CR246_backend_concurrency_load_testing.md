# CR246 — Backend concurrency: simulate real-world multi-user load

**Status: proposed, not started.** Filed by investigator session (AT:R85),
2026-09-28, from Saiful: *"we need to test the back end system for
concurrency. We need to be sure that we can handle multiple users at the
same time."* And, correcting an earlier draft of this CR that over-focused
on one bug: *"the CR is not about the race condition. It is about the
application's ability, as a whole, to handle multiple users. We need to
simulate a real world condition."* To be assigned to another agent for
build/verification.

## What this CR is

**Simulate realistic concurrent usage of the whole application — many
different real users, doing the things real users do, at overlapping
times — and verify the system holds up.** Not a single race condition, not
one code path: the app's ability AS A WHOLE to serve multiple simultaneous
users correctly. Today this has never been tested. Every load the backend
has seen to date (production Alpha's real but small user base, every
research/benchmark toolkit run, every manual test) has been effectively
single-user-at-a-time or close to it.

"Real-world condition" means simulating what actual concurrent usage looks
like, not a synthetic worst case: a realistic MIX of different users doing
different things at once — some browsing/reading, some in the middle of an
onboarding interview, some convening the Room, some checking a portfolio,
some executing a trade — overlapping in time the way a real cohort of
simultaneous users would, at a scale that matters for where the product is
headed (CR245's 1,000-user Beta sizing is the relevant target scale to
anchor against).

## Why now

Filed the same day a research toolkit was extended to run several backend
operations concurrently (unrelated to production — a client-side research
tool) and, for the first time, exercised something close to real concurrent
load against this codebase. That run surfaced at least one real defect (a
get-or-create race creating duplicate rows for one user under concurrent
writes) that had simply never been hit before, because nothing had ever hit
the backend with genuine concurrency. **That incident is the trigger for
filing this CR, not its subject** — it's one data point suggesting
concurrency is genuinely untested territory, not a symptom to chase down in
isolation. The assigned agent may well re-find that same bug (and should
fix it if so), but the deliverable here is the general capability — a
realistic multi-user simulation and a verdict on how the app holds up — not
a patch for one code path.

**Root cause of that one incident, confirmed** (kept here only as evidence
the gap is real, not as this CR's task list): `SimEngine.ensure_portfolio`
(`backend/app/services/sim_engine.py:961-984`) does an unlocked
SELECT-then-INSERT, and `SimPortfolioRow`'s `UniqueConstraint(user_id,
kind, run_id)` (`backend/app/db/models.py`) is silently ineffective for
every training portfolio because `run_id IS NULL` for all of them and NULL
never equals NULL in a SQL unique constraint — CR109 slice 2 widened this
constraint and, in doing so, removed the real protection a plain
`UNIQUE(user_id)` used to provide. This is reachable by REAL users, not
just the research toolkit: `ensure_portfolio(user_id)` is called
independently from at least four separate API surfaces (Room convenes,
`GET /v1/portfolio/health/{user_id}`, `GET /v1/sector-watch/{user_id}`,
the options-chain endpoints), and the mobile app's own Riverpod providers
for sector-watch and portfolio-health fire independently/concurrently on
first widget mount — so an ordinary brand-new user's first Floor-screen
load can plausibly trigger this exact race with no double-tapping or
multi-device session required. The toolkit itself was fixed separately
(mints a distinct `user_id` per concurrent ticker instead of sharing one —
see `room_ticker_batch.py`'s own docstring) — that fix only stops the
TOOLKIT from triggering this, it does nothing for real users, who remain
exposed until this CR's work (or a dedicated DEF, if the assigned agent
prefers to split it out) actually fixes the constraint/locking gap.

## Why this is NOT already answered by other work

- **CR245** (Beta infra 1000-user sizing, proposed) is capacity/cost
  planning — how many DB connections Supabase allows, what Cloud Run
  scaling costs. It answers "how much infra do we need," not "does the
  application behave correctly when that many users actually show up at
  once." Different question, and CR245 says so itself (flags the
  connection ceiling as a number, not something load-tested).
- **No existing CR/DEF simulates real concurrent multi-user traffic against
  this backend at all** (grepped `docs/forward_planning/`, `docs/defect/`
  for "concurrent", "load test", "simultaneous users" — nothing addresses
  this). Genuinely new ground.
- Production already proves ONE narrow kind of concurrency works (a single
  convene fans out 12 concurrent LLM calls internally, documented in
  `llm_gateway.py`'s own comments) — that says nothing about many
  DIFFERENT users' independent sessions overlapping, which is the actual
  question here.

## Scope — build a realistic multi-user simulation, then verify against it

1. **Define the realistic scenario first.** What does "N simultaneous
   users" actually look like for this app, at the scale that matters
   (anchor to CR245's 1,000-user Beta target, and to whatever near-term
   milestone Saiful cares about — ask if unclear)? A mix of concurrent
   actions across the user journey — onboarding, Room convenes, portfolio
   views, trades, Brief Your Agent, Coach — not just N copies of the same
   single action. Decide the mix and the scale before building anything.
2. **Build (or adapt) a load-simulation harness** that drives that mix
   against a real backend instance (a disposable/staging environment, not
   production Alpha — melehost's `ami_api_alpha` serves real users) through
   the actual public API surface, not by calling internal functions
   directly — this needs to look like real traffic hitting real endpoints,
   the way real concurrent users would generate it.
3. **Verify correctness under that load**, not just "did it crash":
   no cross-user data leakage (User A never sees/affects User B's
   portfolio, mandate, balance, or convene), no lost updates or duplicate
   rows from any concurrent write path, credit balances end up
   mathematically correct after concurrent deductions, DB connections stay
   within safe bounds relative to Supabase's ceiling (CR245), and LLM
   provider traffic degrades gracefully (queues/backs off) rather than
   failing silently or spiking scripted-fallback rates under load.
4. **Establish a numeric pass/fail bar up front** — e.g., "N concurrent
   distinct users running a realistic action mix, zero data corruption,
   zero cross-user leakage, p99 latency within X" — and report against it,
   rather than an open-ended exploration with no verdict.
5. **Make it repeatable.** Whatever harness gets built should be reusable
   after future changes, not a one-off — this is exactly the kind of thing
   that should be re-run before major releases, not verified once and
   forgotten.

## Non-goals

- Does not re-litigate CR245's capacity/cost sizing (connections, Cloud Run
  scaling, GCP project topology) — that's planning, this is behavioral
  verification under real load.
- Does not require chasing every individual race condition to exhaustion —
  if the simulation surfaces specific bugs (like the one that prompted this
  CR), file them as their own DEFs; the deliverable here is the overall
  verdict and a reusable way to keep re-checking it, not a guarantee every
  possible race is hunted down in one pass.
- Does not test the research toolkit itself
  (`docs/tools/room_investigation/room_ticker_batch.py`) — that's a
  separate, already-shipped, client-side research tool with its own narrow
  concurrency (one synthetic user, controlled use), unrelated to this CR's
  question about real production traffic.

## Acceptance (draft — refine at build time)

- A realistic concurrent-multi-user scenario is defined (action mix, scale)
  and agreed before building.
- A repeatable load-simulation harness exists, driving that scenario
  through the real API against a disposable/staging backend.
- The app's behavior under that load is verified against a stated numeric
  bar (data correctness, no cross-user leakage, connection/latency bounds)
  and the result — pass, fail, or partial — is reported plainly.
- Any concrete defects the simulation surfaces are filed as their own DEFs,
  not silently absorbed into this CR's scope.
