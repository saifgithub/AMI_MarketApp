# Room investigation toolkit

Reusable scripts for investigating a specific Room (12-agent TradingAgents
convene) run or class of runs — consistency checks, cross-provider
comparisons, and tracing a verdict back through the agent pipeline. Built
during the CR228 risk-appetite benchmark cross-check and the RES009 Room LLM
consistency research (2026-09); generalized here from that investigation's
one-off, hardcoded scripts so the same capabilities are one command away next
time, not a re-write.

**Nothing here touches production code or ships a behavior change.** Same
rule as `docs/Research/` — these scripts run `RoomRunner.run()` directly, in
a throwaway process on the Mac, never through melehost's shared
`ami_api_alpha` container (see `room_kimi_gateway.py`'s docstring for exactly
why that distinction matters — forcing a provider on the shared container
would redirect ALL live users' traffic, not just a benchmark's calls).

## What's here

| Script | Question it answers |
|---|---|
| `room_kimi_gateway.py` | (shared core, not run directly) — forces a `RoomRunner`'s `LLMGateway` to Kimi or vLLM, in-process only |
| `room_risk_score_sweep.py` | "Does risk_score actually change this Room's verdict for this ticker, right now?" — one ticker, N risk_score values, either provider |
| `room_repeat_consistency.py` | "Is this ticker/risk_score/provider's verdict stable, or did I see one draw of an unstable distribution?" — full Room, N repeats |
| `room_agent_replay.py` | "Is THIS agent itself unstable on a fixed input, or did it just receive different upstream input?" — one agent, exact captured prompt, N repeats, either provider, optional pinned temperature (vLLM only) |
| `room_llm_audit_trace.py` | "What did agent X actually see/say in run Y?" — pull or diff captured `system_prompt`/`messages`/`response_text` from melehost's `llm_audit` table by `user_id` |

## The investigation pattern these support

This is the actual sequence the CR228 BAC risk_score=2 investigation used,
worth repeating as a pattern for any future "the Room did something odd"
question:

1. **See something surprising** (a single draw's verdict looks off, or two
   runs disagree). Don't conclude anything from one draw.
2. **`room_repeat_consistency.py`** the same ticker/risk_score/provider N
   times (5 is usually enough). If it's stable, the surprising draw was
   real; if it splits, you have an instability worth tracing, not a fact
   about the ticker.
3. If it splits: **`room_llm_audit_trace.py list`** each draw's `user_id` to
   see the full agent-call sequence, then **`diff`** each stage
   (fundamentals_analyst → ... → trader → portfolio_manager) between a
   "PASS-side" and an "APPROVE-side" draw to find where the two runs'
   `response_text` first genuinely differs — not just where the FINAL
   action differs.
4. Once you've found a candidate fork point, **`room_agent_replay.py`** that
   one agent's exact captured prompt N times. If it's stable on a fixed
   input, the fork is upstream of that agent (repeat step 3 one stage
   earlier); if it's unstable even on a fixed input, you've found genuine
   single-agent sampling noise (the RES009 01-06 finding).
5. **Cross-check the same question against the other provider**
   (`--provider vllm`/`--provider kimi` on any of the above) before treating
   a finding as general — this investigation found real cases where the two
   providers agreed a setup was unanimous-and-stable but landed on opposite
   actions (vLLM unanimous PASS vs. Kimi unanimous APPROVE on BAC at
   risk_score=3), which a single-provider investigation would never surface.

See `docs/Research/RES009_room_llm_consistency/07_cr228_bac_risk_score_instability.md`
for a full worked example of this pattern, including a correction where step
2-4 overturned an initial conclusion from step 1 (checking 2 of 6 draws
looked like a clean single-agent fork; checking all 6 plus the agent's
upstream input showed the real cause was a live news feed refreshing between
draws, not model instability).

## Setup, once per session

```bash
cd backend

# Kimi: the Mac's Moonshot OPEN PLATFORM key (sk-ZJutc...), NOT melehost's
# Coding Plan key (sk-kimi-...) — see room_kimi_gateway.py's docstring, this
# mistake was made twice live before being caught.
export KIMI_API_KEY=$(python3 -c "import re; print(re.search(r'^KIMI_API_KEY=(.+)\$', open('../.env').read(), re.M).group(1))")

# vLLM: LAN-direct from the Mac (feedback_lan_route.md) — only works from
# the office LAN, not a remote/cloud sandbox.
export VLLM_BASE_URL=http://192.168.20.74:8000
export VLLM_MODEL=ami-llm

# DB (for room_llm_audit_trace.py and mandate persistence): melehost's
# Postgres via SSH tunnel.
ssh -f -N -L 5434:127.0.0.1:5434 melehost
export DB_PASSWORD=$(ssh melehost "docker exec ami_postgres printenv POSTGRES_PASSWORD")
export DATABASE_URL="postgresql+psycopg2://postgres:${DB_PASSWORD}@127.0.0.1:5434/ami_trade"
export USE_REAL_MARKET_DATA=true
```

`room_llm_audit_trace.py` doesn't need `DATABASE_URL` — it shells out to
`ssh melehost docker exec ami_postgres psql` directly, matching how this
investigation actually pulled data.

## Examples

```bash
# Full-Room repeat check, Kimi, 5x
.venv/bin/python3 ../docs/tools/room_investigation/room_repeat_consistency.py \
    --ticker BAC --risk-score 2 --repeats 5 --provider kimi \
    --out-dir ../docs/tools/room_investigation/out

# Same, vLLM, for cross-provider comparison
.venv/bin/python3 ../docs/tools/room_investigation/room_repeat_consistency.py \
    --ticker BAC --risk-score 2 --repeats 5 --provider vllm \
    --out-dir ../docs/tools/room_investigation/out

# Risk_score sweep, one ticker, one provider
.venv/bin/python3 ../docs/tools/room_investigation/room_risk_score_sweep.py \
    --ticker AAPL --risk-scores 1,2,3,4,5 --provider kimi \
    --out-dir ../docs/tools/room_investigation/out

# Trace a specific run's agent sequence, then diff two runs' trader input
python3 ../docs/tools/room_investigation/room_llm_audit_trace.py list --user-id <uuid>
python3 ../docs/tools/room_investigation/room_llm_audit_trace.py diff \
    --user-id-a <uuid-pass-run> --user-id-b <uuid-approve-run> \
    --agent-id trader --field system_prompt

# If --user-id belongs to a batch driver (one user_id reused across a whole
# 30-ticker sweep, not one-per-draw) — `list` prints a NOTE when it detects
# this (>20 rows). Narrow get/diff to the right convene with --after/--before
# (from the batch's own JSONL triggered_at) or --nth (0-indexed occurrence,
# simpler when you just know "the Nth ticker in this batch"):
python3 ../docs/tools/room_investigation/room_llm_audit_trace.py get \
    --user-id <batch-uuid> --agent-id trader --field response_text \
    --after "2026-09-26T01:22:51+00" --before "2026-09-26T01:28:00+00"
# — or —
python3 ../docs/tools/room_investigation/room_llm_audit_trace.py get \
    --user-id <batch-uuid> --agent-id trader --field response_text --nth 21

# Replay one agent's exact captured prompt, isolate whether IT is unstable
python3 ../docs/tools/room_investigation/room_llm_audit_trace.py get \
    --user-id <uuid> --agent-id trader --field system_prompt > /tmp/sp.txt
python3 ../docs/tools/room_investigation/room_llm_audit_trace.py get \
    --user-id <uuid> --agent-id trader --field messages > /tmp/msgs.txt
python3 ../docs/tools/room_investigation/room_agent_replay.py \
    --system-prompt-file /tmp/sp.txt --messages-file /tmp/msgs.txt \
    --repeats 5 --provider kimi --label "trader replay"
```

## Known constraints, carried over from the original investigation

- **`llm_audit` has no `run_id` or `ticker` column.** Every script here
  mints a fresh synthetic `user_id` per draw specifically so
  `room_llm_audit_trace.py` can correlate unambiguously — always capture the
  `user_id` a sweep/repeat script prints, you'll need it to trace that draw.
- **Not every user_id is one-convene-only** — a batch driver (a 30-ticker
  sweep run outside this toolkit, e.g. the CR228 r3 Kimi batch) can reuse ONE
  user_id for the whole batch, back-to-back with no gap. Hit this live
  2026-09-26: a bare `get --agent-id trader` against such a user_id silently
  returned an earlier ticker's trader call (AAPL instead of the intended SO),
  no error. `list` now warns when a user_id has >20 rows (one convene is
  ~17); `get`/`diff` now take `--after`/`--before` (timestamp window) or
  `--nth` (0-indexed occurrence) to target the right convene, and warn loudly
  on stderr if the query still matches more than one row.
- **`messages` is a trivial placeholder for every Room agent — `system_prompt`
  carries the actual content.** Every agent's captured `llm_audit.messages`
  is just `[{"role": "user", "content": "Convene on <TICKER>."}]`; the real
  role/task text, the live fact sheet, AND the full upstream transcript (every
  earlier agent's output the current agent can see — e.g. `research_manager`'s
  `system_prompt` inlines the Bull's and Bear's full arguments verbatim) are
  all in `system_prompt`. Diffing `--field messages` between two runs will
  always come back empty/trivial and prove nothing — this produced a wrong
  "prompts are byte-identical" conclusion live 2026-09-26 (caught by a user
  question, not by the tooling) before the same comparison was redone on
  `--field system_prompt` and found genuinely different. **Diff/replay
  `system_prompt`, not `messages`, for anything upstream-of-this-agent.**
- **Temperature/seed are unset everywhere else in this codebase** — an RES009
  finding, not an oversight. `room_agent_replay.py --provider vllm
  --temperature X` is the one place in this toolkit that pins it, for a
  single-agent test only; `room_risk_score_sweep.py`/`room_repeat_consistency.py`
  always run at whatever the server's own default is (matching production).
- **Kimi's reasoning/thinking is disabled** (`{"thinking": {"type":
  "disabled"}}`) everywhere in this toolkit by default — reasoning-enabled
  Kimi calls run ~3-4x slower and can blow the Room's vLLM-tuned
  `room_agent_timeout_s` default. See `room_kimi_gateway.py` if a future
  investigation genuinely needs reasoning-enabled Kimi (RES009 05-06 used it
  deliberately for single-call, non-Room probes).
- **vLLM only reaches from the office LAN** (`192.168.20.74:8000`) — these
  scripts will not work from a remote worktree/cloud sandbox for the vLLM
  provider; Kimi works from anywhere with the Open Platform key.
- **A full-Room repeat costs real wall-clock time** — roughly 5-6 min/draw
  at the full 12-agent pipeline with Kimi thinking disabled (vLLM is
  typically faster, LAN-direct). 5 repeats is ~25-30 min; budget accordingly
  before launching a large sweep × repeat matrix.
- **A backgrounded launch's "completed" notification is NOT the run
  finishing** — if a script is started as `cmd ... &` inside a bash call that
  itself runs in the background (`run_in_background: true`), the harness's
  "completed" notification fires when that OUTER bash call returns (i.e. the
  moment the `&` successfully detaches the inner process), not when the
  detached script itself finishes. Hit this live 2026-09-26, twice, on both
  a 5-min full-Room draw and a ~20s single-agent replay: the notification
  arrived in under a second each time, well before the room convene or
  replay had produced any output. **Always verify against the real process**
  (`ps -p <pid>` — capture the `&`'s `$!` at launch) or the actual output
  file/JSONL, never the notification text alone, before reporting a result.
  A `while ps -p <pid> >/dev/null 2>&1; do sleep 5; done` loop before reading
  results is the reliable pattern.
