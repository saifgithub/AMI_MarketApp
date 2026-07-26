<!-- intake draft — ad-hoc investigation, not a register write. Architect owns IDs/registers. -->
# backend-concurrency-blocking-io — proposed DEF: blocking I/O stalls the whole backend for every concurrent user

PROPOSED-KIND: DEF
SOURCE: ad-hoc investigation, 2026-07-26 (Saiful: "check if the Back end is multi-threaded. We are going to be serving multiple customers as the same time")
TRIAGE: OPEN

**Symptom:** the backend is a single uvicorn process, single event loop, no workers/gunicorn
(`backend/Dockerfile:34` — deliberate, see "Not proposed" below). Several `async def` request
handlers call *synchronous*, network-bound functions (yfinance, `httpx.Client`) directly inline,
with no thread offload. Each such call (often 1-3s+) freezes the entire backend — every other
user's SSE stream, LLM token relay, or unrelated API call — for its duration. Fires on every Room
convene and every 1-on-1 chat turn that mentions a ticker.

**Category:** infra / room

**Blast radius / severity (proposed):** **MVP show-stopper (Saiful, 2026-07-26).** Low risk today
(Stealth Alpha, 10-20 personal-invite testers, low odds of two people hitting Room/1-on-1 at the
same instant) but a hard blocker at the MVP/public-launch gate, where concurrent usage is the
whole point.

**Suspected owner:** `coder.api` (owns `backend/app`, per `board.md` roster table)

**What's already fine, ruled out during investigation (don't re-check):**
- Deployment model: single process is deliberate — `BriefEngine._sessions`
  (`brief_engine.py:182`) and `AgentRunner._sessions` (`agent_runner.py:66`) are in-memory,
  process-local, and would break under multiple workers/replicas. Not proposing multi-worker.
- DB layer: Postgres via SQLAlchemy `QueuePool`, session-per-call via `get_session()`
  (`backend/app/db/session.py:71-83`), no shared connections. Not the bottleneck.
- LLM streaming (vLLM/Anthropic via `llm_gateway.py`) already correctly uses `httpx.AsyncClient` —
  not part of this bug.
- Cross-user isolation (session/Room leaking to the wrong customer) — separately verified clean,
  not related to this bug. Every fetch-by-ID route has an explicit ownership check: Room
  (`room.py:95-96,271-272,283-284`, `user_id` vs `current_user.id`, 403 on mismatch — hardened by
  a prior adversarial-audit finding A6 about run_id harvesting; dedup keyed `(user_id, ticker)`);
  1-on-1 (`one_on_one.py:36-42`, checked at `:100,156`); Brief/Coach (`brief.py:68-72`, checked at
  `:104,132,143,178`). No finding here — recorded so the Architect doesn't have to re-check it.

**Recommended fix — `asyncio.to_thread` at the call site** (stdlib, already the established
pattern in this codebase: `sharia_universe.py:512-521`, `classification_universe.py:508-513`,
`main.py:100,117`, all justified with "the one uvicorn process serves every concurrent request").
Not a new `ThreadPoolExecutor` — that pattern (`sim.py:404-433`, `quotes_batch`) solves a
different problem (parallel fan-out over N tickers). Wrap at the call site; every leaf function
(`_profile_for_ticker`, `build_live_data_block`, `build_news_context_block`,
`build_social_context_block`, `build_technicals_context_block`,
`SimEngine.current_quote/history/news/earnings`) stays untouched — plain synchronous, unit-tested
exactly as today (`monkeypatch.setattr` still works from inside a `to_thread` worker, same
process memory).

Call sites:

1. `backend/app/services/room_runner.py`, inside `RoomRunner.run()` (~`:1478`). Around
   `:1569-1580`, pull `profile=_profile_for_ticker(ticker)` out of the `_RoomContext(...)` kwargs
   into a preceding awaited line: `profile = await asyncio.to_thread(_profile_for_ticker,
   ticker)`, then pass `profile=profile`. (`asyncio` already imported `:34`.)
2. `backend/app/services/agent_runner.py`, inside `stream_one_on_one_message()` (`:89`). Add
   `import asyncio`. Wrap each of the four ticker-block loops (`:186-216`):
   `build_live_data_block`, `build_news_context_block`, `build_social_context_block`,
   `build_technicals_context_block` → `await asyncio.to_thread(fn, t)`. `tickers` capped at 3, so
   ≤3 sequential thread hops per loop.
3. `backend/app/api/sim.py`, four single-ticker endpoints (`asyncio` already imported `:18`;
   `quotes_batch` at `:404-433` stays untouched — already correct):
   - `quote` (~`:389-399`): `q = await asyncio.to_thread(sim.current_quote, ticker)`
   - `history` (~`:437-453`): `bars, source = await asyncio.to_thread(sim.current_history, ticker, period)`
   - `news` (~`:466-477`): `items, source = await asyncio.to_thread(sim.current_news, ticker, limit)`
   - `earnings` (~`:494-504`): `info, source = await asyncio.to_thread(sim.current_earnings, ticker)`
4. `backend/Dockerfile:34` — drop dev-only `--reload` from the production CMD (separate one-line
   finding, bundle into the same lane): `CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0",
   "--port", "8000"]`.

**Deliberately not proposed:**
- DB pool sizing / multi-worker uvicorn — separate, larger decision (blocked on solving the
  in-memory session-store problem first).
- Parallelizing the 5 sequential calls inside `_profile_for_ticker`
  (fundamentals/technicals/news/earnings/sentiment) — would cut single-user latency
  (~5-10s → ~1-2s) but requires `_profile_for_ticker` to become `async def`, breaking ~15 existing
  synchronous unit tests in `test_room_runner.py`. It's a latency optimization for one user, not
  the cross-user concurrency-correctness fix this item is about. Possible fast-follow if
  Room-convene latency itself becomes a complaint — separate from this item.

**Also found, explicitly excluded from this item:** the Alpaca account-snapshot fetch
(`room_runner.py:1557`, `agent_runner.py:145`, via `alpaca_snapshot_text` → plain `httpx.get`/
`httpx.post` in `alpaca_service.py:77,113`) has the identical bug pattern — same two files, same
shape of fix. Found incidentally, outside original scope. Flagged as a candidate for its own
follow-up Defect — do not fold into this item without a separate decision.

**Verification (for whoever picks up the lane):**
1. `pytest backend/tests/unit/ -q` — full suite; no test is call-order- or thread-sensitive
   (checked `test_room_runner.py`, `test_one_on_one_{live_data,news_injection,market_injection,
   social_injection}.py`, `test_fundamentals.py`, `test_technicals.py`, `test_news_context.py`,
   `test_social_context.py`, `test_sim_history.py`, `test_sim_news_earnings.py`,
   `test_sim_engine.py`).
2. Manual concurrency smoke test on melehost post-promote: fire `GET /v1/health` (or an unrelated
   `/v1/sim/quote/{ticker}`) while a Room convene or 1-on-1 SSE stream is mid-flight for a
   different ticker/user — confirm the second request returns promptly instead of queueing. This
   is the actual regression test; a single-process unit test can't assert it directly.
3. Confirm via `docker compose ps`/`docker inspect` on melehost that the container starts without
   `--reload`.

**Cross-reference:** highlighted to the GTM Manager in
`docs/forward_planning/CR036_go_to_market_plan/CR036_go_to_market_plan.md` (build-stands MVP row +
open-defects paragraph) as an MVP-gate blocker, 2026-07-26.
