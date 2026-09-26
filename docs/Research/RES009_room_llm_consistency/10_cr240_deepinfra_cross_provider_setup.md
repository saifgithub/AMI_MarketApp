# 10 — CR240 DeepInfra/GLM-5.3-Flash cross-provider setup (in progress)

**Status: infrastructure built and smoke-tested; the real 9-ticker comparison
batch has NOT been run yet — Saiful said "do not run the 10 rooms yet, I will
tell you when."** This doc records what's ready and one real defect the
smoke test surfaced, so the eventual real batch isn't run on the same broken
footing.

## Context

CR240 (hosted LLM provider evaluation for production) needs a real,
full-Room, same-ticker comparison of DeepInfra's GLM-5.3-Flash against the
existing Kimi/vLLM data already in hand from CR228's risk_score=3 batch
(`docs/forward_planning/CR228_risk_appetite_differentiation/results/
runs_cr228-r3-kimi-nothink-20260926.jsonl`). Saiful, 2026-09-26: run the 9
tickers that scored `action=APPROVE, approve_votes=5/5` in that Kimi batch —
BAC, JPM, MA, MO, SLB, SO, T, V, WFC — plus AAPL (which PASSed 0/5 in the
same batch, included anyway per explicit instruction). AAPL was later pulled
out to run last/separately, since it had already been used as this setup's
own smoke test (see below) and wouldn't be a clean incremental data point
run twice.

## Toolkit built this session

`docs/tools/room_investigation/room_kimi_gateway.py` (the shared
force-a-provider-and-run-a-Room core already used by
`room_risk_score_sweep.py`) gained `force_deepinfra_gateway()` — the
full-Room counterpart to `room_agent_replay.py --provider deepinfra`'s
single-agent replay. `docs/tools/room_investigation/room_ticker_batch.py` is
new: a multi-ticker, fixed-mandate, any-provider batch driver, generalizing
the CR228-specific `run_local_kimi.py` the same way `room_risk_score_sweep.py`
generalized the risk_score-sweep-on-one-ticker shape. Both take
`--provider {kimi,vllm,deepinfra}`.

## Two real defects the smoke test surfaced (both fixed, both verified live)

**1. DeepInfra base URL double-prefixed the request path.** The gateway's
`OpenAICompatibleProvider` always POSTs to `"{base_url}/v1/chat/completions"`.
The first `DEEPINFRA_BASE_URL` value (`"https://api.deepinfra.com/v1/openai"`,
copied from `room_agent_replay.py`'s standalone `_call_deepinfra`, which
builds its OWN path differently) produced
`.../v1/openai/v1/chat/completions` — a route that doesn't exist. Every
agent call 404'd, and the Room's scripted-fallback path silently absorbed it
(`room_agent_scripted_fallback reason=stream_error`) rather than crashing —
worth naming explicitly, since a silent scripted-fallback masking a total
provider failure is exactly the DEF059/CR040 "confident fake output" shape
CLAUDE.md warns about, just caught here before it produced a false
comparison result. Fixed: `DEEPINFRA_BASE_URL = "https://api.deepinfra.com"`
(bare host). Verified live: re-run produced real `provider=deepinfra` calls,
a real self-consistency verdict, no fallback warnings.

**2. `backend/.env` does not exist — `Settings()` silently missed the real
one.** `Settings.model_config` has `env_file=".env"`, resolved relative to
CWD. Every driver script in this toolkit says "run from `backend/`", but the
repo's actual `.env` lives at the repo root, one level up — `backend/.env`
has never existed. Pydantic-settings loads no file in that case and falls
back to class defaults **without erroring** — so `DATABASE_URL` silently
fell back to `postgresql+psycopg2://postgres:postgres@localhost:5432/...`
(triggering `db/session.py`'s solo-dev **sqlite** fallback, since that
exact string matches its "no real DB configured" check) and
`USE_REAL_MARKET_DATA` silently fell back to `False` (mock-walk data),
despite both being set correctly in the real root `.env`. This is CLAUDE.md's
own "degrade loudly" rule (CR040) being violated by `Settings`' own env-file
resolution — noted here, not fixed at the `Settings` level (out of scope for
this tool) — the fix applied is operational: every setting this toolkit
needs must be **exported explicitly in the shell**, documented in
`room_ticker_batch.py`'s own docstring now, plus a new fail-loud startup
guard (`--allow-mock-market-data` required to override) so a future run
can't silently repeat this.

## AAPL smoke test — real result, but on the WRONG market-data path

Before defect #2 above was caught, one full AAPL convene ran end-to-end
successfully (defect #1 was already fixed) but on **mock-walk data**, not
real Yahoo data — confirmed both from the log
(`market_data_provider_registered stack=mock_walk`) and from the captured
fact sheet, which reported reference price, P/E, TTM growth, and all
technicals as "not available." This is NOT comparable to the original Kimi
batch's AAPL run, whose captured reasoning cites real figures ($341.07,
RSI 74, 50-day range, Street mean target $328.22) — the two runs are not on
the same evidentiary footing, so no verdict-comparison conclusion is drawn
from this pair. Kept as raw data anyway (nothing here is discarded, per
RES009's own convention) — see `out/10a_aapl_deepinfra_glm53flash_smoketest.jsonl`.

| | Original Kimi AAPL (r3 batch) | DeepInfra AAPL (this smoke test) |
|---|---|---|
| Market data | Real (Yahoo) | **mock_walk** (defect #2 above) |
| Action | PASS, 0/5 approve | PASS, 0/5 approve |
| Duration | not recorded in this doc | 274.4s (4.6 min) |

Both landed PASS 0/5 — but with the DeepInfra run's fact sheet blank, this
is not evidence of cross-provider agreement, just two runs that happened to
both decline for very different, unverifiable reasons. The real comparison
needs a re-run with real market data once the batch is authorized.

## Cost, measured directly from the DeepInfra dashboard (not estimated)

Saiful pulled the DeepInfra usage dashboard immediately before and after the
AAPL smoke test (`zai-org/GLM-5.3-Flash`, 2026-09-01→2026-10-01 window):

| | in tokens | out tokens | cached in tokens |
|---|---|---|---|
| Before | 36,184 | 4,443 | 12,160 |
| After | 109,485 | 9,440 | 14,592 |
| **Delta (this one convene)** | **73,301** | **4,997** | **2,432** |

At GLM-5.3-Flash's fetched rate card ($0.075/$0.25/$0.015 per 1M for
in/out/cached-in): **one full 12-agent Room convene (with PM's 5x
self-consistency sampling) cost $0.00678.** Linear-projected (not measured —
per-ticker cost will vary with prompt length and agent chatter) 9-ticker
batch: **~$0.061**. Trivial against the $25 DeepInfra balance; cost is not
the constraint on running this properly.

## Ready to run, pending Saiful's go-ahead

`docs/tools/room_investigation/out/cr240_tickers_9_kimi_approved.txt` (BAC,
JPM, MA, MO, SLB, SO, T, V, WFC — AAPL excluded, to run last/separately).
Staged command, NOT yet executed:

```bash
cd backend
export DATABASE_URL="postgresql+psycopg2://postgres:<melehost POSTGRES_PASSWORD>@localhost:5434/ami_trade"
export USE_REAL_MARKET_DATA=true
export DEEPINFR_API_KEY=...
.venv/bin/python3 ../docs/tools/room_investigation/room_ticker_batch.py \
    --tickers-file ../docs/tools/room_investigation/out/cr240_tickers_9_kimi_approved.txt \
    --provider deepinfra --risk-score 3 \
    --batch-id cr240-deepinfra-glm53flash-9tickers-20260926 \
    --out-dir ../docs/tools/room_investigation/out \
    --fresh-user
```

Next doc in this series (11, once the batch runs) compares each ticker's
DeepInfra verdict/votes against the same ticker's Kimi r3 verdict, and
records dashboard before/after stats for the real cost of the 9-ticker
batch, per Saiful's request.
