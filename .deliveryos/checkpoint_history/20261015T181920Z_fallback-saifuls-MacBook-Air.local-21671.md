TRACK: K · ROLE: Kimi · INSTANCE: - · session b17abc40-215e-4787-bd04-e9c0fa149047 · AT:K3

## Where we are

Repo `/Volumes/Extreme Pro/AMI_MarketApp` (quote the path). Program: CR251→CR259
decision-consistency + CR256 evidence-gated verdicts. **CR256 card pilot just COMPLETED
its 90 rooms, and the layer-2 gate FAILED informatively — the next action is the
backend in-turn enforcement build (envelope integration), which Saiful approved, then
re-pilot to layer 2.**

## Explicit next step (user-directed)

"yes. then we can move to layer 2." — i.e. BUILD the backend envelope enforcement
(`ROOM_CARDS_ENVELOPE_ENABLED`, below), then re-run the card pilot (30 rooms is enough)
with in-turn enforcement and re-score the layer-2 ICC gate. Proceed without pausing.

## The measured pilot result (the whole point of the last 2 days)

Layer-2 test-retest ICC(A,1), gate ≥0.85, all at risk 4, DeepInfra `deepseek-ai/DeepSeek-V4-Flash`:

| census | n subjects | ICC |
|---|---|---|
| v3 pilot rooms, raw (~64% self-filed) | 4 | 0.80 |
| v3 pilot rooms, repaired (36% repaired) | 4 | **0.93** |
| v6 90-room pilot, raw (~34% self-filed) | 30 | 0.62 |
| v6 90-room pilot, repaired (66% repaired) | 30 | **0.67** |

**Decomposition (the pilot's deliverable):**
1. Self-filed cards ARE stable (0.93) — card format/registry/grading validated.
2. Voluntary filing is salience noise: per-desk rates wobble 0–92% across six prompt
   variants (v1–v6), same LLM. Prompt iteration is measured-dead.
3. Post-hoc repair (cards_repair.py) works ONLY as top-up: a repaired card is a fresh
   generation with its own variance; at low filing rates repair noise dominates
   (0.67), at high filing it rescues (0.93). NOT a substitute for in-turn enforcement.

## The build: in-turn enforcement (the spec's Layer 1, now measured-necessary)

Flag-gated backend change, CR201 pattern, default OFF:
- `backend/app/core/config.py`: `room_cards_envelope_enabled: bool = False`
  (+ env `ROOM_CARDS_ENVELOPE_ENABLED`, CR040 compose parity in `docker-compose.yml`
  api-alpha block — `test_config_compose_parity.py` auto-enforces).
- `backend/app/services/room_prompts.py` (~line 1006 `_build_stance_format`,
  ~1018): extend the stance-envelope grammar with the CLAIMS contract (5-item
  registry eq/vc/vh/bs/moat; `item=<id> dir=support|oppose|neutral
  grade=well|partial|unsupported data=yes|no claim=<one sentence> nums=<figures>`);
  bear/research_manager additionally OBJECTIONS (`target=<id> severity=high|medium|low
  objection=<sentence>`). Envelope position: after the stance line, before analysis
  (the measured slot-2 anchor — fundamentals 100%); GAPS keeps terminal position.
- `backend/app/services/room_runner.py` (~4436 `parse_stance_envelope`, CR143
  family): parse cards/objections into the envelope result; missing/malformed cards
  → treated as envelope failure → existing CR143 repair call re-asks (mechanical
  enforcement, in-turn, self-generated).
- Unit tests + `python scripts/registers/gen_registers.py verify all` green.
Commit `feat(room): ... (AT:K3 CR256)`; rsync changed files to melehost `~/ami_trade`
(targeted, NO promote — the api-alpha container keeps running old code until a real
promote; compose run jobs load code at start).

## What was decided this session (chronological, all committed)

- **Parity v2**: v1 chain killed (prompt-variant arms serialize on runner override_lock
  → --max-concurrent silently degrades to 1); per-level-parallel v2 launcher
  `/tmp/ami_parity_v2.sh` (4 job slots, wave-requeue, resume-safe). **Results
  committed `ae552477` in `docs/forward_planning/CR251_risk_monotonicity_matrix/
  analysis_r7_parity.md` (INTERIM 2): ami disposition 0/0/3/22/36 (r=+0.37/+0.62/+0.62
  at R3–R5 — disposition prompts CURE ami discrimination); ami cap1 1/5/9/11 with
  discrimination collapse (r +0.62→+0.04) — size-pin is poison on ami; dsv4 refs
  1/7/13/15/19 disp, 11/13/16/15/23 cap1. Flips rise with level on ami (R4 37%, cap1 R5 47%).**
- **M7 closed**: `jev_score_runs.py` now fetches flow `room_risk_officer`
  (agent_id `risk_officer`, the CR201 consolidated risk stage — melehost .env has
  `ROOM_RISK_OFFICER_ENABLED=true`); `--agents` flag added. Officer re-scores done
  for all 4 arms (1,200 turns, 0 errors). Memo `m7_debator_turns_memo.md`.
- **CR259 thinking pilot**: `VLLM_ENABLE_THINKING`/`VLLM_THINKING_MAX_TOKENS` knobs
  (`da9d01d5`, 138 tests green, synced to melehost, defaults OFF — not promoted).
  Probe: server default thinking OFF, `chat_template_kwargs {enable_thinking:true}`
  works per-call, reasoning text NOT surfaced. Smoke FAILED (105.9 min, 8/12
  scripted, NO_VERDICT under parity contention). **Reframed per Saiful: thinking =
  async PAID upgrade, never default; quality-delta is the only GO gate (`5cf3dca0`).**
  Pilot queued after parity chain, uncontended.
- **Card pilot arc**: v1 (appended, GAPS-terminal conflict found) → v2 emphatic →
  v3 evidence-desks-only → v4 slot-2 → v5 skeleton → v6 desk-class positions →
  ALL superseded by the enforcement finding. v6 prompts are the frozen harness state
  (`b0d74a70`). Root cause of filing variance: persona NATIVE terminal structures
  (GAPS for analysts, Raises/Lowers for bull) outrank appended sections — position
  by file order.
- **Mechanical enforcement (harness)**: `tools/cards_repair.py` (post-hoc re-ask
  over llm_audit via provider_gateway.direct_call, 429-retry, inline template —
  MUST paste the exact card template into the ask; "the shape your instructions
  specify" gets a condensed `eq: ...` format that fails parse) + `cards_run.py
  --turns-file` mode (`9748b79e`, closing-tag fix `e39668c1`).

## Active constraints / gotchas

- Harness runs on melehost: mount MUST be repo root `-v ~/ami_trade:/harness:ro`,
  `chmod -R a+rwx` out-dirs BEFORE launch (a chmod chain-abort cost 3h — the v5
  smoke died on a PermissionError writing users_<batch>.json and sat dead; always
  verify boot: benchmark banner + room_started in the launch command itself).
- DeepInfra: chronic 429 engine_overloaded bursts; the `_RetryTransient` wrapper in
  `library/provider_gateway.py` (`81db3fda`) buffers chunks until an attempt is
  known-good (the provider yields a sentinel + meta["stream_error"], never raises).
  6 concurrent rooms is approved by Saiful but throttles hard; repair calls need
  their own 429-retry (in cards_repair.py). DEEPINFR_API_KEY: only in Mac `.env`
  (melehost .env lacks it — inject via `-e DEEPINFR_API_KEY=$KEY` on compose run).
- Launch envs for deepinfra card jobs: `-e USE_REAL_MARKET_DATA=true
  -e ROOM_VETO_REVIEW_ENABLED=false -e ROOM_RESURRECTION_REVIEW_ENABLED=false`,
  `--provider deepinfra --model deepseek-ai/DeepSeek-V4-Flash` (--model is CLI-only,
  the yaml `model:` field is ignored). Benchmark benchmark yaml prompt_variant arms
  serialize per process (override_lock) — shard jobs for parallelism.
- 90-room pilot data: `out/cr256-p6/` (runs_all.jsonl, repaired.jsonl,
  analysis-{raw,final}/); v3 partial: `out/cr256-cards-pilot/`. Runs live on
  melehost `~/ami_cards/pilot6/{a..f}`.
- **Never mix prompt-version rooms in one ICC**: v3-partial and v6-90 are separate
  instruments. Re-pilot after the envelope build = fresh rooms only.
- CR228 vote bar frozen during measurement; target curve 5/15/30/45/46; R5=46
  investable universe; 7 holdouts APD BA FCEL RIOT RIVN SNAP SPCE.
- Jev: funded; join Jev rows on (arm_key, risk_score). CR257 draft
  (`cr257_coordination_draft.md`) still unsent — gates AC4 only.

## Open items

- **NEXT: envelope build → re-pilot 30 rooms → layer-2 ICC.** Reuse the
  pilot6 launcher shape (6 shards or fewer for 30) with fresh out-dirs.
- Parity chain finishing (tm-all r1/r2 + probes on DGX, ~hours) → then CR259
  thinking pilot uncontended → final analysis_r7_parity.
- Production: alpha-2026-10-09-1 (bf0fa99f) live; everything since is unpromoted
  (CR259 knobs default OFF, behavior-neutral). The envelope build will also be
  unpromoted until measured GO (D32).
- GLM-5.3-Flash = $0.15/$0.50 per 1M on DeepInfra; dsv4-0731 = $0.06/$0.18
  (workhorse); card pilot total spend ≈ $2.
