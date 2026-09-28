# Room investigation toolkit V2 — benchmark + proof harness

V2 turns the v1 investigation scripts (`docs/tools/room_investigation/`) into
a **benchmark and proof harness for LLM and prompt quality**, driven by
CR247. V1 answered one-off questions ("why did BAC flip at risk_score=2?");
v2 answers repeatable measurement questions: did this prompt change improve
reasoning quality, does provider/model X reach better verdicts than Y on the
same fixed matrix, is this verdict stable. The design spec is
[`DESIGN.md`](DESIGN.md); v1 stays frozen and usable alongside.

**Nothing here touches production code or ships a behaviour change.** Same
execution model as v1: tools run `RoomRunner.run()` in-process on the Mac,
never through melehost's shared `ami_api_alpha` container; melehost is
reached only via SSH for Postgres reads (`llm_audit`, `http_audit`,
`room_runs`, `verdict_outcomes`).

## Layout

```
library/     # shared modules — the graduation candidates
tools/       # thin CLI wrappers over library/
benchmarks/  # named, versioned benchmark definitions (YAML)
out/         # run outputs (gitignored except curated baselines)
```

## library/

| Module | What it owns |
|---|---|
| `env_bootstrap.py` | Repo-root `.env` load (from `__file__`, never CWD), named-refusal requirement checks (CR040 for tooling), the one allowed `sys.path` insert |
| `provider_gateway.py` | One provider registry (kimi / vllm / deepinfra); `force_provider` for in-process LLMGateway surgery with post-force verification; `direct_call` for single-call replay |
| `runner.py` | `run_arms` over explicit `Arm` cells; deterministic per-arm uuid5 user ids; locked JSONL appends; resume on completed; one-prompt-variant-per-batch enforcement |
| `audit_db.py` | The one parameterized ssh→psql helper; `list_calls` / `get_field` / `diff_fields` / `lookup_request_id`; hard refusal (`AmbiguousQueryError`/`NoRowsError`) instead of v1's warn-and-return |
| `replay.py` | Single-agent prompt replay loop over `direct_call` + `scoring.extract_decision`; null-content tolerance; token rollup |
| `scoring.py` | Deterministic metrics — verdict distribution/stability, batch diffs, outcome quality, conviction consistency. LLMs never compute scores |
| `prompt_lab.py` | Whole-persona prompt variants installed in-process at `agent_prompts.load_base_prompt`, with probe-render verification (fail-loud, never a silent no-op) |

## tools/

| Tool | Question it answers |
|---|---|
| `room_repeat.py` | "Is this ticker/risk_score's verdict stable, or did I see one draw of an unstable distribution?" — N full-Room repeats, distribution + stability report |
| `room_sweep.py` | "Does risk_score actually change this Room's verdict for this ticker, right now?" — one ticker across N risk scores, risk_score/action/votes table |
| `room_batch.py` | "Do these N tickers reach the same verdict on provider X as on provider Y?" — ticker axis, one fixed mandate, resumable, concurrent |
| `room_trace.py` | "What did agent X actually see/say in run Y?" / "paste the request id, get the whole story" — `list`/`get`/`diff` on `llm_audit` by user_id, `lookup` on an X-Request-Id prefix |
| `room_replay.py` | "Is THIS agent itself unstable on a fixed input, or did it receive different upstream input?" — one captured prompt, N draws, distribution + token totals |
| `room_benchmark.py` | "Did this prompt/provider change move the needle on the fixed matrix?" — runs a versioned benchmark file, prints the stability report, diffs against the baseline |

Every Room-running tool takes `--provider {kimi,vllm,deepinfra}` and
`--model` — v1's inconsistency (some tools lacking deepinfra or a model flag)
is fixed by construction, since all flags resolve through the one registry in
`provider_gateway`. Every tool prints a human summary to stdout AND writes
machine-readable JSONL/JSON under `--out-dir`. Room-running tools exit 1 if
any arm failed.

## Setup

v2's guarantee over v1: you no longer hand-export anything —
`env_bootstrap.load_repo_env()` loads the repo-root `.env` explicitly (the
path is derived from `__file__`, never CWD, so v1's silent `backend/.env`
miss cannot recur), and each tool **refuses to run** with a named error when
a required key is absent or the market-data guard fails. What must exist:

- **Repo-root `.env`** with the keys for the provider you pick:
  `KIMI_API_KEY` (the Mac's Moonshot **Open Platform** `sk-…` key —
  melehost's Coding Plan `sk-kimi-…` key is a different product and is
  rejected on sight), `DEEPINFR_API_KEY` (the codebase's own spelling, no
  trailing A), and/or `VLLM_BASE_URL` (e.g. `http://192.168.20.74:8000`,
  LAN-direct).
- **`DATABASE_URL`** (Room-running tools only): melehost's Postgres via SSH
  tunnel —
  `ssh -f -N -L 5434:127.0.0.1:5434 melehost`, then export
  `DATABASE_URL=postgresql+psycopg2://postgres:<pw>@127.0.0.1:5434/ami_trade`.
- **`USE_REAL_MARKET_DATA=true`** in the environment or root `.env` —
  otherwise every Room-running tool refuses unless `--allow-mock-market-data`
  is passed deliberately.
- **ssh access to `melehost`** for `room_trace.py` (no DATABASE_URL needed —
  read-only `docker exec ami_postgres psql` over ssh).

Real shell exports still win over `.env` values (dotenv's default
`override=False`), so a one-off shadow for a single run keeps working.

## The benchmark workflow

```bash
# Phase 0.2 — baseline, BEFORE any prompt change. Verify the serving model
# first: curl $VLLM_BASE_URL/v1/models and record the `root` field (never
# trust the ami-llm alias). The baseline benchmark does this for you at
# startup via env_bootstrap.require_vllm.
backend/.venv/bin/python3 docs/tools/room_investigation_V2/tools/room_benchmark.py \
    --benchmark cr247-phase0-baseline-v1 \
    --out-dir docs/tools/room_investigation_V2/out

# Phases 1-5 — copy the benchmark file, change only prompt_variant, run the
# candidate, then diff against the baseline:
backend/.venv/bin/python3 docs/tools/room_investigation_V2/tools/room_benchmark.py \
    --benchmark cr247-phaseN-<variant>-v1 \
    --out-dir docs/tools/room_investigation_V2/out \
    --diff-against docs/tools/room_investigation_V2/out/runs_cr247-phase0-baseline-v1.jsonl
```

A benchmark YAML names `name`, `provider`, `tickers`, `mandate`
(`risk_score` or a `file` reference), `repeats`, and `prompt_variant`
(`backend-default`, or a `benchmarks/<variant>/prompts/<agent_id>.md` set —
whole-persona replacement only, DESIGN §7.2). Arms are `tickers × repeats`
with deterministic keys (`{ticker}-rep{i}`), so an interrupted benchmark
resumes cleanly on re-run. The diff report flags FLIPPED / DESTABILIZED /
STABILIZED per ticker, in a paste-ready table for the CR gate review.

## Known constraints (carried forward from v1, still true)

- **`llm_audit` has no `run_id` or `ticker` column.** Correlation works only
  because one fresh synthetic `user_id` is minted per convene. In v2 this is
  structural: `runner.py` mints and records the id (deterministic uuid5 off
  the batch base user + arm key), and `audit_db.get_field` **refuses**
  ambiguous queries (`AmbiguousQueryError`, exit 2) instead of v1's stderr
  warning that still returned the wrong ticker's call.
- **`messages` is a trivial placeholder for every Room agent — `system_prompt`
  carries the actual content** (role/task text, live fact sheet, full upstream
  transcript). Diffing `messages` between two runs always comes back trivial;
  it produced a wrong "prompts are byte-identical" conclusion live
  2026-09-26. `room_trace.py diff` therefore defaults to `--field
  system_prompt`.
- **vLLM is LAN-only** (`192.168.20.74:8000`) — the `vllm` provider does not
  work off the office LAN. Kimi and DeepInfra work from anywhere with the
  right key.
- **A full-Room convene costs real wall-clock time** — roughly 5-6 min/draw
  at the full 12-agent pipeline with Kimi thinking disabled (vLLM is
  typically faster, LAN-direct). The baseline benchmark is 9 tickers × 5
  repeats = 45 convenes; budget accordingly.
- **A backgrounded launch's "completed" notification is NOT the run
  finishing.** If a tool is started as `cmd ... &` inside a backgrounded bash
  call, the notification fires when the outer call returns (the moment the
  `&` detaches), not when the tool finishes — hit live 2026-09-26, twice.
  Verify against the real process (`ps -p <pid>`) or the output JSONL, never
  the notification.
- **The `ensure_portfolio` race is designed out here, not fixed in
  production.** `SimEngine.ensure_portfolio`'s unlocked SELECT-then-INSERT
  corrupts concurrent convenes sharing one `user_id` (phantom REJECTs, hit
  live 2026-09-28; production defect still open). V2 makes the race
  impossible by construction — every arm's user id is `uuid5(batch_base_user,
  arm_key)` inside `runner.py`, so no caller can forget it. This toolkit fix
  does NOT close the underlying production defect.

## Graduation note

`library/` is written to be lifted into `backend/app/` unchanged when the CR
development completes: no script-only shortcuts, no `sys.path` hacks inside
library modules (the one bootstrap insert lives in `tools/` entry points),
parameterized SQL only, typed returns. `library/data_feeds/` is the CR244
example of that pattern: the insider-trade / float-liquidity feeds written
inside `library/` in backend-liftable shape, ready to move into
`backend/app/` unchanged when their CR closes.
