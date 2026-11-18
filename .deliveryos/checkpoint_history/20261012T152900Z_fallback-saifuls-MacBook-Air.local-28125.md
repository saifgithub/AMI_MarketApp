TRACK: K · ROLE: Kimi · INSTANCE: -
SESSION: fallback-saifuls-MacBook-Air.local-28125 (no CLAUDE_CODE_SESSION_ID in this env; PID-based fallback — if /sm-readpoint computes a different PID, open this exact filename directly)

# Savepoint — 2026-10-12 (Kimi track K, AT:K4 session)

## Where we are
Repo: /Volumes/Extreme Pro/AMI_MarketApp (branch main). Session work: CR251/255
decision-consistency program — independent review of the Jev evidence scores and
the room llm_audit trail, then design Q&A with Saiful on replacing the PM verdict
with a Jev typed-decision call.

State: review DONE and committed; CR257 (Jev-as-decider) specced, minted,
committed, register verified. Nothing in flight, no background tasks.

## What was decided this session
1. **Jev judge quality is sufficient to anchor CR255 C7** — 20-turn deep-read:
   0 clear errors, ~3 adjacent-grade borderlines (≤10%, estimate ~5%), no desk
   bias (if anything skeptical of bull re-rating theses); judge catches subtle
   agent errors (CAG price/level confusion; BAC 24.9% cost-of-debt artifact).
   Mild leniency only on technical-desk interpretive verbs. figures_consistent
   noul sub-score is noisy — choice labels reliable.
2. **Compression is structural** — room means quantized at 1/16 (8 turns/room);
   net support at ±1/3 because only bear_researcher exists on the bear side
   (debator turns absent from Jev logs). Root mechanical cause of the dead
   single-metric bar (net=+0.33 tie problem: 82 rooms at −0.167 in dsv4).
3. **r values reproduced**: dsv4 production +0.186 (reported +0.19) CONFIRMED;
   disposition lift +0 CONFIRMED; ami r reported +0.03 CHALLENGED — clean joins
   give +0.043..+0.085 (R3 partial coverage 83%); conclusion (no discrimination)
   stands. Caveat found: pooled lift hides +10pts per-level lift at dsv4 R3/R4
   (r real mid-levels: R2 +0.327, R3 +0.324, R4 +0.232; ~0 at R1/R5 tails).
4. **6-room llm_audit read** (disposition R5: APPROVE APD-rep2/PYPL-rep1/
   XPEV-rep2; PASS APD-rep1/DE-rep1/RIOT-rep1): verdicts follow debate 5/6;
   PM engages losing side. Two flags: (a) APD-rep2 APPROVE violates the
   target-curve APD holdout rule (approved at R5 with −$350M SBC-adj FCF on an
   unstated "one-time distortion" inference); (b) APD-rep1/rep2 flip is
   desk-phase variance on identical data (flip rate visible intra-ticker).
   RIOT-rep1 confirms over-refusal shape is verdict-layer, not judge noise.
   Incidental: one APD-rep2 PM candidate had degenerate text ("squirrel trap"),
   filtered by multi-sample selection; XPEV-rep2 approve leaned on the Street
   target the bear had shown was a lagging artifact.
5. **Saiful proposed Jev-as-decider** (agents opine, Jev emits approve/pass
   probability). My answer: legitimate, test as an arm before adopting; Jev
   decides WHETHER, code decides HOW MUCH, safety floor decides WHAT'S FORBIDDEN.
   Buy/hold/sell framing noted but action space stays APPROVE/PASS (long-only,
   no position review yet).
6. **CR257 minted** as the offline measurement arm (spec below). Positioned as
   competitor to CR256's code-computed composite bar for the evidence→verdict
   step; CR256's deterministic gate stays enforcement layer either way.

## Plan
n/a (no PLAN_LEDGER in this repo)

## What to do next
Await Saiful's GO on CR257. If GO: build `tools/jev_decision_arm.py` (clone of
`jev_score_runs.py` over transcripts instead of turns), run over the three scored
arms (cr251-v2-dsv4 300, cr253-disp-matrix 300, ami clean 287), 2 replays/room,
then evaluate the four GO criteria in the spec.

## Active constraints
1. Read-only on all run data; frozen r1/r2 baselines + BASELINE.md never edited.
2. Backend venv python for all tool runs:
   "/Volumes/Extreme Pro/AMI_MarketApp/backend/.venv/bin/python".
3. pg tunnel: `ssh -f -N -L 5434:127.0.0.1:5434 melehost-ts` (was already up this
   session); password via `ssh melehost-ts "docker exec ami_postgres printenv
   POSTGRES_PASSWORD"`; asyncpg is the available driver (psycopg NOT installed).
4. Join key for Jev↔verdict is (arm_key, risk_score) — arm_key alone collides.
5. Commit with explicit pathspec, never bare; format `type(scope): ... (AT:K4 CR###)`.
6. Registers are generated — row files under docs/forward_planning/_registry/,
   regenerate via `"$PY" scripts/registers/gen_registers.py gen cr`, then
   `verify all` must pass (row file must be committed WITH the table, DEF159).
7. PROSE_AGENTS excludes PM and risk_officer — PM/risk-officer turns are NOT
   Jev-scored; PM produces 5 candidates per room, recorded verdict = majority.

## Open items
1. CR257 (Jev-as-decider) — proposed, awaiting Saiful GO. Spec:
   docs/forward_planning/CR257_jev_decision_arm/spec.md.
2. CR256 (evidence-gated verdicts, code-computed bar) — proposed by AT:K3,
   parallel/competing design for the same step.
3. Recommendation from my review not yet actioned: r6 table should carry ami
   r as "+0.04…+0.09 (join-dependent)" instead of the point value +0.03.
4. Recommendation: add aggressive/conservative debator turns to Jev logs to fix
   the ±1/3 net-support quantization at source.
5. Carryover program items (unchanged this session): DGX memory cap top infra
   risk; ami-llm disposition twin arm pending; CR254 tm-all lane handoff gates
   in EXPERIMENT_LOG.md §4.

## Commits this session
- a2745752 docs(cr255): jev evidence review memo (AT:K4 CR255) —
  docs/forward_planning/CR255_decision_consistency/jev_review_2026-10-12.md
- 2847c137 docs(cr257): jev-as-decider measurement arm (AT:K4 CR257) —
  spec + row + regenerated cr_list.md

## Key paths
- Program map: docs/tools/room_investigation_V2/EXPERIMENT_LOG.md
- Analysis: docs/forward_planning/CR251_risk_monotonicity_matrix/analysis_r6.md
- Target curve: docs/forward_planning/CR255_decision_consistency/target_curve.md
- Review memo: docs/forward_planning/CR255_decision_consistency/jev_review_2026-10-12.md
- CR257 spec: docs/forward_planning/CR257_jev_decision_arm/spec.md
- Tools: docs/tools/room_investigation_V2/tools/{jev_score_runs,jev_verdict_relation,net_support}.py
- Jev data: docs/tools/room_investigation_V2/out/<arm>/jev/r{1..5}.jsonl
