# Room investigation toolkit V2 — design spec

Status: DRAFT for review (Saiful). Nothing here is built yet.
Date: 2026-09-28 · Author: Kimi (AT:K3) · Driver CR: CR247

## 1. Purpose

V2 turns the v1 investigation scripts (`docs/tools/room_investigation/`) into a
**benchmark and proof harness for LLM and prompt quality**. V1 answered
one-off investigation questions ("why did BAC flip at risk_score=2?"). V2
answers repeatable measurement questions:

- "Did this prompt change improve reasoning quality?" (CR247 phase gates)
- "Does provider/model X reach better verdicts than Y on the same fixed
  matrix?" (CR240, CR217)
- "Is this verdict stable, and do its intermediate scores survive the
  producer→consumer hand-offs?" (CR247 D-items)

Same execution model as v1: scripts run `RoomRunner.run()` **in-process on
the Mac**, never through melehost's `ami_api_alpha` container. melehost is
reached only via SSH for Postgres reads (`llm_audit`, `http_audit`,
`room_runs`, `verdict_outcomes`). Nothing here touches production code or
ships a behaviour change.

## 2. Directory layout

```
docs/tools/room_investigation_V2/
├── DESIGN.md                # this file
├── README.md                # written when v2 exists; user-facing usage
├── library/                 # shared modules — the graduation candidates
│   ├── __init__.py
│   ├── env_bootstrap.py     # §4.1
│   ├── provider_gateway.py  # §4.2
│   ├── runner.py            # §4.3
│   ├── audit_db.py          # §4.4
│   ├── replay.py            # §4.5
│   ├── scoring.py           # §4.6 (NEW — CR247's core)
│   └── prompt_lab.py        # §4.7 (NEW — prompt-variant A/B)
├── tools/                   # thin CLI wrappers over library/
│   ├── room_repeat.py
│   ├── room_sweep.py        # risk_score axis
│   ├── room_batch.py        # ticker axis
│   ├── room_trace.py        # list/get/diff + request-id lookup
│   ├── room_replay.py       # single-agent prompt replay
│   └── room_benchmark.py    # benchmark-set runner (§5)
├── benchmarks/              # named, versioned benchmark definitions (YAML/JSON)
└── out/                     # run outputs (gitignored except curated baselines)
```

`library/` is written to be liftable into `backend/app/` unchanged when the
CR development completes: no script-only shortcuts, no `sys.path` hacks
inside library modules (the one bootstrap `sys.path` insert lives in
`tools/` entry points), parameterized SQL only, typed returns.

## 3. What v2 fixes from v1 (absorbed landmines)

Every item below is a live hit documented in v1's README or docstrings:

1. **Silent env fallback.** `backend/.env` does not exist; `Settings` resolves
   `env_file=".env"` relative to CWD and silently loads nothing → fell back
   to mock-walk market data live 2026-09-26. V2: `env_bootstrap` loads the
   repo-root `.env` explicitly and **refuses to run** if required keys are
   absent or `use_real_market_data` is false without an explicit override.
2. **Concurrency race workaround.** v1 found `SimEngine.ensure_portfolio`'s
   unlocked SELECT-then-INSERT corrupts concurrent convenes sharing one
   `user_id` (phantom REJECTs; production defect still open). V2: per-ticker
   deterministic `uuid5(base_user_id, ticker)` everywhere, enforced inside
   `library/runner.py` so no caller can forget it.
3. **Inconsistent provider flags.** `room_repeat_consistency.py` lacks
   `deepinfra`; `room_risk_score_sweep.py` lacks `--deepinfra-model`; replay
   duplicates provider HTTP code instead of using the gateway. V2: one
   provider registry in `provider_gateway.py`; every tool gets every
   provider + model flag for free.
4. **DeepInfra URL split.** Bare host for the `OpenAICompatibleProvider`
   path vs `/v1/openai` for replay's standalone path — mixing them 404'd
   live. V2: one call path; the suffix rule lives in exactly one place.
5. **Unguarded JSONL appends.** Only the batch script had the
   `asyncio.Lock`. V2: append lives in `library/runner.py`, always locked.
6. **`llm_audit` has no run_id/ticker.** V1 mints synthetic user_ids and
   warns on batch-driver reuse. V2 keeps the fresh-user-per-convene
   convention (load-bearing) but makes it structural: `runner.py` mints and
   records the id; `audit_db.py` refuses ambiguous queries loudly instead of
   warning text on stderr.
7. **Duplicated `_run_psql`** in trace_lookup and llm_audit_trace, with
   f-string SQL. V2: one parameterized implementation in `audit_db.py`.

## 4. Library modules

### 4.1 `env_bootstrap.py`

Single entry: `bootstrap(require: list[Requirement]) -> Settings`.

- Loads repo-root `.env` explicitly (path resolved from `__file__`, not CWD).
- Validates each requirement (KIMI key present AND is the Open Platform
  `sk-…` key not the Coding Plan `sk-kimi-…` key; VLLM_BASE_URL reachable
  when provider=vllm; DATABASE_URL points at the tunnel; market data is
  real) and **exits with a named error** on any miss — CR040 degrade-loudly
  applied to tooling.
- Centralizes the constants v1 scattered: hosts, container/db names,
  timeouts, model IDs, spacing defaults, reasoning-token tolerance.

### 4.2 `provider_gateway.py`

Generalizes v1's `force_gateway()`:

- `force_provider(name, *, model=None, temperature=None) -> LLMGateway` —
  provider registry pattern; adding a provider (or a second model on an
  existing one, e.g. GLM-5.3 vs GLM-5.3-Flash) is a registry entry, not a
  new function.
- Post-force verification kept and strengthened: after forcing, resolve the
  active provider AND model, print both, refuse on mismatch. Model identity
  for vLLM read from `/v1/models` `root`, never the alias (D21 lesson).
- Single-agent direct-call path (today duplicated in replay) moves here so
  replay and Room runs share request-shape code.

### 4.3 `runner.py`

The shared run-loop skeleton v1 copy-pasted across three scripts:

```python
async def run_arms(
    arms: Iterable[Arm],          # an Arm = one (ticker, mandate, prompt_variant, label) cell
    *,
    max_concurrent: int = 3,
    post_spacing_s: float = 15.0,
    out_path: Path,               # locked JSONL append, resume on status=="completed"
    batch_id: str,
) -> RunSummary
```

- An **Arm** names the swept axis explicitly (ticker / risk_score /
  mandate-file / prompt-variant / provider-model), replacing v1's
  one-script-per-axis shape. `--risk-score` required "just for the filename"
  goes away.
- Per-arm deterministic `uuid5(batch_user, arm_key)` user ids.
- Emits v1-compatible JSONL fields (`ticker`, `risk_score`, `user_id`,
  `triggered_at`, `status`, `verdict.{action,approve_votes,samples}`,
  `duration_ms`, `spot_price`, `batch_id`) so existing `out/` analysis keeps
  working.

### 4.4 `audit_db.py`

- One parameterized ssh→`docker exec ami_postgres psql` helper (absorbs both
  v1 copies).
- `list_calls(user_id)`, `get_field(user_id, agent_id, field, *, after,
  before, nth)` with hard refusal on ambiguity, `diff(...)`, and
  `lookup_request_id(prefix)` (absorbs trace_lookup).
- New: `verdict_outcomes` access for the Phase 0.1 census (read-only SELECT
  helpers; schema read first, never assumed).

### 4.5 `replay.py`

Single-agent replay rebuilt on `provider_gateway` (no duplicated HTTP code):

- Same interface as v1 (`--system-prompt-file`, `--messages-file`,
  `--repeats`, `--extract-pattern`/`--extract-json-key`, `--temperature`
  where the provider supports pinning).
- Keeps v1's null-content tolerance and reasoning-token tolerance check.
- Output schema unchanged (`draws[].{draw,extracted,full_text,usage,error}`,
  token totals, cost estimate marked as estimate).

### 4.6 `scoring.py` — NEW, CR247's reason for v2

Metrics over run records, computed **deterministically in code** — LLMs
never compute scores (house rule):

1. **Verdict stability:** action distribution + entropy per
   (ticker, arm) cell across repeats; flags cells below a configurable
   agreement threshold. This is the baseline-vs-candidate comparison
   instrument for every CR247 phase gate.
2. **Producer→consumer score consistency:** pulls each convene's per-agent
   captured payloads via `audit_db` and checks that quantized stances /
   convictions consumed downstream match what the producer emitted (D-item:
   "mutual understanding of scores"). Phase 0.3 conviction-signal audit is
   this metric over journaled envelopes.
3. **Outcome quality:** joins run verdicts to `verdict_outcomes` (Phase 0.1
   census shape) → false-APPROVE vs false-PASS rates per horizon bucket.
4. **Diff reports:** given two batch JSONLs (baseline vs candidate), per-arm
   verdict deltas + stability deltas, rendered as a plain table suitable for
   pasting into a CR gate review.

### 4.7 `prompt_lab.py` — NEW, prompt-variant A/B

CR247's phases change agent personas. Benchmarking a prompt change needs to
run the Room with a **candidate prompt** without editing backend files:

- `PromptOverride` map: `agent_id → prompt text` (or content-file path),
  applied in-process for the benchmark run only.
- Implementation approach decided at build time after reading how
  `RoomRunner` assembles each agent's `system_prompt` (v1 README: the real
  content is all in `system_prompt`; `messages` is a placeholder). The
  override hook must sit where the persona text is injected, and must fail
  loudly if the backend's prompt-assembly path changed (no silent no-op
  overrides).
- A benchmark definition (§5) can name a prompt variant per agent; the
  baseline variant is "backend default".

## 5. Benchmark definitions and Phase 0 wiring

A **benchmark** is a versioned file in `benchmarks/` naming:

```yaml
name: cr247-phase0-baseline-v1
provider: vllm            # resolved through provider_gateway; model recorded
tickers: [AAPL, ...]      # fixed set, chosen once, documented why
mandate: { risk_score: 3 } # or mandate-file reference
repeats: 5
prompt_variant: backend-default
```

`tools/room_benchmark.py` runs a benchmark file through `library/runner.py`
and feeds results to `library/scoring.py`. CR247 Phase 0 consumes this
directly:

- **0.2 baseline replay:** benchmark pinned to the CURRENT serving model
  (verified via `/v1/models` `root`, never the `ami-llm` alias), run BEFORE
  any prompt change; output committed as the reference baseline.
- **Phase gates 1–5:** same benchmark file, `prompt_variant` swapped;
  `scoring.py` diff report decides pass/fail at the gate.
- **0.1 outcome census:** `audit_db.verdict_outcomes` + `scoring.outcome_quality`
  (runs against melehost via SSH; logistics per the CR247 savepoint — census
  runs there or off a dump).

## 6. Explicit non-goals

- No production code changes; no new backend dependencies from `library/`
  beyond what `backend/.venv` already has (library imports backend modules
  the same way v1 does).
- No WebSocket/SSE driving of melehost's API — in-process `RoomRunner` only
  (Saiful, 2026-09-28: "Same as V1").
- No DSPy/auto-optimization loop in v2 tooling (CR247 D20: prompt evolution
  is a governed, versioned, measurement-gated process; this harness is the
  measurement instrument, not the author).
- V1 stays frozen and usable; v2 does not migrate v1's `out/` data.

## 7. Open questions for Saiful

1. Benchmark ticker set for the Phase 0 baseline — reuse CR228/CR240's
   tickers for continuity, or pick a fresh fixed set with rationale?
2. `prompt_lab` override granularity: whole-persona replacement only, or
   section-level patching (e.g. swap just the sizing ontology block)?
   Whole-persona is simpler and safer; section-level is more surgical but
   couples the harness to prompt internal structure.
3. Should `scoring.py`'s stability threshold defaults (e.g. min agreement
   4/5) come from CR247's SPEC gates verbatim, or be tuned after the first
   baseline run?
