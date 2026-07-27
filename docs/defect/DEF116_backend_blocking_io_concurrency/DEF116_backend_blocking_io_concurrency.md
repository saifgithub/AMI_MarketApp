# DEF116 — Blocking I/O in `async def` handlers stalls the whole backend

**Filed:** 2026-07-27 (AT:R65) · **Source:** prompt (ad-hoc investigation 2026-07-26, Saiful: *"check if the Back end is multi-threaded. We are going to be serving multiple customers at the same time"*) · **Area:** infra/room · **Status:** open
**Severity:** **MVP show-stopper** (Saiful, 2026-07-26). Cross-referenced in `CR036_go_to_market_plan.md` as an MVP-gate blocker.

Original triage preserved verbatim at [`original_intake.md`](original_intake.md).

## The bug

One uvicorn process, one event loop. Several `async def` request handlers call **synchronous**,
network-bound functions inline (yfinance, `httpx.Client`) with no thread offload. Each such call —
routinely 1–3s+ — freezes the entire backend: every other user's SSE stream, LLM token relay, and
unrelated API call queues behind it.

Fires on **every Room convene** and **every 1-on-1 turn that mentions a ticker**.

Impact is low today (Stealth Alpha, 10–20 invite testers, low odds of simultaneous use) and total at
the public-launch gate, where concurrent usage is the whole point.

## Second occurrence — so it earns a guard

The **CR049 audit independently found this exact class** in `website_api` on 2026-07-27 (blocking
`httpx` in `turnstile.py`/`email_service.py` reachable from `async def` routes). That lane fixed it
with async `httpx` **and** an AST static-call-graph guard
(`website_api/tests/test_no_blocking_io_in_async_routes.py`) that the Architect verified by mutation:
reintroducing the blocking call turned it red and named all three reachable routes.

Per CLAUDE.md — *second occurrence of anything ⇒ add an entry **with a guard*** — the backend fix must
land with the equivalent guard, adapted for the `asyncio.to_thread` pattern rather than async httpx.

## Call sites — re-derived against `main` @ AT:R65, not copied from the intake

The intake's line numbers were written 2026-07-26 and **CR090-ROOM rewrote `room_runner.py` on
2026-07-27** (+658/−34). Its `sim.py` list was also incomplete. Current, verified:

| # | File | Site | Note |
|---|---|---|---|
| 1 | `backend/app/services/room_runner.py` | **`:1833`** — `profile=_profile_for_ticker(…)` inside the `_RoomContext(...)` kwargs | intake said ~`:1569-1580`; **moved by CR090**. `asyncio` already imported |
| 2 | `backend/app/services/agent_runner.py` | `:187`, `:198`, `:206`, `:214` — the four ticker blocks in `stream_one_on_one_message` (`:89`) | **needs `import asyncio` added**. `tickers` capped at 3 |
| 3 | `backend/app/api/sim.py` | **`:456`** — `sim.current_quote` in **`get_holding_lots`** (`@router.get("/lots/{user_id}/{ticker}")`, `:441-442`) | **MISSED BY THE INTAKE.** Live traffic — CR100 wired this route to mobile today |
| 4 | `backend/app/api/sim.py` | `:481` `quote` · `:541` `history` · `:565` `news` · `:592` `earnings` | `asyncio` already imported |
| 5 | `backend/Dockerfile` | `:34` — drop dev-only `--reload` from the production CMD | one-line finding, bundled |

`sim.py:509` (`quotes_batch`'s `loop.run_in_executor` fan-out) is **already correct** — leave it alone.

## Fix

`asyncio.to_thread` **at the call site** — the established pattern here (`sharia_universe.py:512-521`,
`classification_universe.py:508-513`, `main.py:100,117`, each justified with "the one uvicorn process
serves every concurrent request"). **Not** a new `ThreadPoolExecutor`.

Every leaf function (`_profile_for_ticker`, `build_live_data_block`, `build_news_context_block`,
`build_social_context_block`, `build_technicals_context_block`, `SimEngine.current_*`) stays **plain
synchronous and untouched**, so existing `monkeypatch.setattr` unit tests keep working from inside a
`to_thread` worker (same process memory).

## Ruled out — do not re-investigate

- **Multi-worker uvicorn / DB pool sizing.** Single process is deliberate: `BriefEngine._sessions`
  (`brief_engine.py:182`) and `AgentRunner._sessions` (`agent_runner.py:66`) are process-local
  in-memory stores that would break under multiple workers. Separate, larger decision.
- **DB layer** — Postgres via SQLAlchemy `QueuePool`, session-per-call (`db/session.py:71-83`).
- **LLM streaming** — `llm_gateway.py` already uses `httpx.AsyncClient` correctly.
- **Cross-user isolation** — separately verified clean; every fetch-by-ID route has an explicit
  ownership check with 403 on mismatch (Room `room.py:95-96,271-272,283-284`; 1-on-1
  `one_on_one.py:36-42,100,156`; Brief `brief.py:68-72,104,132,143,178`).

## Excluded pending a separate decision

The Alpaca account-snapshot fetch (`room_runner.py:1557`, `agent_runner.py:145` via
`alpaca_snapshot_text` → plain `httpx.get`/`httpx.post` in `alpaca_service.py:77,113`) has the
**identical** pattern. Found incidentally, outside the original scope. **Do not fold it in** without
its own decision — flag it in the hand-off.

## Acceptance

1. `./backend/.venv/bin/python -m pytest backend/tests/unit/ -q` green from the repo root (**1332
   passed** on `main` at AT:R65). No test is call-order- or thread-sensitive — the intake checked
   `test_room_runner.py`, the four `test_one_on_one_*.py`, `test_fundamentals.py`,
   `test_technicals.py`, `test_news_context.py`, `test_social_context.py`, `test_sim_history.py`,
   `test_sim_news_earnings.py`, `test_sim_engine.py`.
2. **A guard exists and is demonstrated failing** when a blocking call is reintroduced into an
   `async def` handler — mutate it, show it red, revert. Not asserted; shown.
3. All sites in the table above converted, including `get_holding_lots`.
4. `Dockerfile` production CMD has no `--reload`.
5. **Concurrency smoke on melehost post-promote** (the actual regression test — a single-process unit
   test cannot assert it): fire `GET /v1/health` while a Room convene or 1-on-1 SSE stream is
   mid-flight for a different user/ticker; the second request must return promptly instead of
   queueing behind it.
