# CR197 — Risk-debate effectiveness: do the three debators earn their 25%?

**Status:** in_progress · **Filed:** 2026-08-19 · **Track:** AT:R71

---

## Why

Saiful asked, verbatim:

> "i want you to look at the prompts for our aggressive, conservative and nuetral debator. are the promps
> really doing anythinh effective or are they simply taking the two extremes and letting it fall in
> between? is it worth the time and effor debating or should be just used an index to determine the size?"

Two questions, and they need separating because the second one contains a false premise.

---

## What the review found

### 1. The "two extremes, fall in between" suspicion — confirmed for *stances*, refuted for *content*

Across the 118 post-fix convenes committed under `CR143_agent_prompt_audit/corpus/`:

| Agent | for | against | neutral |
|---|---|---|---|
| aggressive_debator | **117** | 1 | 0 |
| conservative_debator | 1 | **117** | 0 |
| neutral_debator | 36 | 55 | 27 |

The two extremes' stance is a **role constant** — it carries ~0 bits of information about the ticker.
Only four distinct `(agg, con, neu)` stance triples occur across 118 convenes, and three of the four
differ only in the Neutral. The room-wide stance-entropy figure of 1.45 bits (CR143 M6) masks this,
because it pools all eleven voices.

The *content*, though, is not formulaic: role identifiability is 97.5% (CR143 M1 re-measurement), the
turns cite real per-ticker numbers, and the Neutral names both other debators in ~98% of its turns.
So the prompts are eliciting differentiated *prose* on top of predetermined *positions*.

### 2. The Aggressive Debator structurally cannot debate

`PHASES` (`backend/app/services/room_runner.py:151-173`) runs RISK as a **single sequential pass** —
aggressive → conservative → neutral, one round, no loop. The Aggressive therefore always speaks into a
transcript that ends at `[trader]`. CR153 F3 measured 0/18 compliance with its own engagement
instruction, and noted the instruction's only available failure mode is the one it forbids. Our own
count over 118 convenes: the Aggressive names the Conservative in 22 turns (19%) — all anticipatory,
since it cannot have read it.

Upstream TradingAgents runs this as a *cycle* (`conditional_logic.py:57-67`, `count >= 3 *
max_risk_discuss_rounds`); we flattened it to a line. That is a defensible latency decision, but the
prompts were never rewritten to match the geometry.

### 3. "Should we just use an index for size?" — the index already decides the size

This is the false premise, and it matters:

- The Trader's "proposal" **is** the mandate risk-tier cap — `ctx.trader_size_pct =
  _risk_tier_size_ceiling(mandate)` (`room_runner.py:3944-3952`), i.e.
  `resolved_single_name_cap_pct(risk_score, override)`.
- The three debator sizes are computed **before any of them speaks**, deterministically:
  `risk_debator_sizes()` (`backend/app/trading_math/sizing.py:111-127`) = `trader+2` / `trader−1.5` /
  `trader`. Each agent is then *handed* the number its role must defend.
- Nothing ever reads a size back out of debate prose. The code says so outright
  (`room_prompts.py:918-921`): *"never parsed back out of prose"*.
- The final size is `min(PM's LLM number, risk_tier_cap)` (`room_runner.py:1511-1521`).

So an index already determines position size, and has all along. The debate contributes to **neither
operand**. Removing the RISK phase entirely would change **zero numeric outputs** on any run.

### 4. The debate is also invisible in a way nobody intended

`parse_stance_envelope` strips the `[STANCE: … | CONVICTION: … | HEADLINE: …]` line *before* the turn is
committed to the transcript (`room_runner.py:4496`). Stance/conviction live on `AgentMessage` as fields
for the UI — but `_format_transcript` (`room_prompts.py:2188-2195`) renders only `[agent_id] content`.
**The PM never sees any debator's stance or conviction.** It reads prose only.

### 5. What the debate *does* buy

It is real, shipped, user-facing product, not internal scaffolding:

- streamed live over SSE (`app/api/room.py:293-311`), replayed from cache, and frozen into the Decision
  Journal (`build_journal_entry_for_run`, `room_runner.py:3089-3111`)
- 3 of the 11 comb voices on the Verdict Board (`mobile/lib/models/agent.dart:195-199`)
- 3 separately unlockable 1-on-1 chat personas (`app/services/agent_gateways.py:108-130`)
- D-012 locks the 12-agent roster ("Don't add or remove without reason"); D-050 records that shipping
  the 12 agents was the single most important item.

Cost: **3 of 12 LLM calls (25%)**, 3,200 of 13,300 output tokens (24%), and 3 serial round-trips on the
latency critical path (the phase is guarded against parallelisation by
`test_cr077_phase_parallelism.py`).

### 6. The measurement nobody has ever run

No experiment in this repo has ablated a *stage*. CR035's three arms varied **inputs** (Street
consensus, social feed), never stages. The strongest existing evidence that the debate reaches the
verdict is CR143's M5 — a cosine similarity between `verdict.reason` and each transcript turn — which is
textual echo, not causation. `docs/Research/benchmark/kimi/03_investment_clubs_retail.md:282` recommended
exactly this test and it was never run:

> "the benchmark should verify the debate actually changes outcomes (e.g., ablation runs), not just that
> it exists."

---

## Decision

**Do not replace the debate with an index** — the index is already in charge of sizing, so the swap
would save 25% of run cost while deleting shipped product and changing no number. But do not leave it
as-is either: three of the four channels the debate could speak through (stance, conviction, declared
size) are currently either constant or invisible to the only agent that decides.

Three workstreams, measurement first.

---

## Scope

### A. Offline PM-replay ablation — the causal test

Replay only the PM call for each committed convene against the LAN vLLM, in four variants:

| Variant | Prompt |
|---|---|
| V1a | exact recorded PM prompt |
| V1b | exact recorded PM prompt again → **paired same-prompt noise floor** |
| V2 | all three debator turns removed from the transcript block |
| V3 | extremes removed, Neutral kept |

Verified groundwork (all pre-validated offline, zero network):

- `llm_audit_*-epoch.json` carries the **full verbatim** PM `system_prompt` under `flow == "room_pm"`
  (18/40/39/39 records = 136, matching convene counts). `room_pm_reformat` records are excluded.
- The user message is not stored but is deterministic: `f"Convene on {ticker}."` (`room_prompts.py:1057`).
- Joining audit rows to `room_runs` convenes by **trader-turn content substring** resolves **136/136
  uniquely**; timestamp joins fail (parallel batches + ISO-format drift in the 08-07 epoch).
- Debator turns are removable as **verbatim blocks** — `f"\n[{agent_id}] {content}"` appears exactly once
  in the joined prompt for **408/408** debator turns. No line-parser needed; assert removal by length and
  by absence of the `[agent_id]` marker.
- Production sends **no `temperature` and no `top_p`** to vLLM (`llm_gateway.py:481-490`) — server
  defaults apply. PM `max_tokens` = 1700. The replay must match exactly and must use `VLLMProvider`
  directly so it cannot silently fall back to Anthropic and corrupt the measurement.
- Baselines are parsed from the recorded `response_text`, **never** from the stored `verdict` (which
  carries the safety floor's post-hoc `REJECT`s). Raw recorded actions: PASS 113 / APPROVE 19 / MODIFY 1
  / MODIFY-AND-APPROVE 3.

Decision rule: exact McNemar on the paired per-convene flip indicators, plus Wilson CIs. Claim the debate
causally moves verdicts only at p<0.05 **and** an excess ≥5pp over the noise floor. At n=136 effects
below ~8–10pp are not resolvable — stated up front, not discovered afterwards.

Honesty caveats printed into the summary: four prompt epochs (per-epoch tables primary), only 13 unique
tickers (clustered), server sampling temperature unknown, and the served model recorded per run.

**The contrast is internally valid on whatever model serves `ami-llm`**, because both arms are measured
fresh on the same model in the same session. Only the replay-vs-recording side-check needs Qwen3.6
specifically.

### B. Structured SIZE channel in the stance envelope

Give the debate a machine-readable numeric channel, additively:

`[STANCE: … | CONVICTION: … | SIZE: <n.n>% | HEADLINE: …]` for the three debators only, parsed into
`AgentMessage.argued_size_pct` (optional field ⇒ old transcripts deserialize unchanged), carried through
`agent_done` and the journal freeze.

This closes DEF235 / CR143 M4, which has never produced a valid reading — the sweep's own autopsy
(`prompt_quality_sweep.py:390-414`) names this exact fix: *"Restoring it requires the agents to declare
size in the envelope — a prompt change, not a parser change."* M4's headline claim is the one directly
relevant to Saiful's question: **"Zero spread means that phase is costume."** Until now it has been
unmeasurable.

Deliberately **not** re-rendered into the transcript in this CR: doing so would change what the PM reads
and invalidate the Stage A baseline. Flagged as a follow-up decision.

### C. Prompt rebuild

Surgical edits to `content/agents/{aggressive,conservative,neutral}_debator.md`:

- **Declare the size.** Each debator carries its argued size in the envelope's SIZE field.
- **Make CONVICTION the honest channel.** The stance is a brief, not a belief — so conviction becomes
  where the evidence actually speaks, with defined permission to concede. An advocate who never concedes
  is noise the PM learns to skip.
- **Fix what the evidence contradicts.** The Conservative's "Ignore the Aggressive Debator's points —
  engage them" is a double-negative in a DO-NOT list measured at ~33% compliance; replaced with a
  positive instruction to quote the Aggressive's strongest number and answer it.
- **Preserve every pinned string** in `test_def241_def243_debator_arithmetic_and_stance.py` (the
  `"Write anything above the stance line"` marker, the banned `"- Open with:"` forms, the banned
  `size% × stop-distance%` formula) and never restate the envelope's bracket shape in a `.md` — that is
  the DEF243/DEF251 lesson.

Overlay blocks (`backend/app/agents/overlay_generator.py:636-687`) get the conviction-calibration bullet
only — **no SIZE reference**, because overlays also render on the 1-on-1 path where no envelope exists,
and a dangling field reference would be a fresh DEF243-class conflict.

---

## Acceptance

1. `pm_debate_ablation.py --dry-run` validates 136/136 joins and 408/408 strips with zero network calls.
2. The live ablation runs to completion and `ABLATION_SUMMARY.md` reports the noise floor, the ablation
   flip rate, the McNemar result, and the served-model identity.
3. `argued_size_pct` appears on debator turns of a real convene, and `m4_risk_spread` produces a number
   for the first time.
4. `pytest backend/tests/unit/ -q` green, including the updated envelope and pinned-string guards.
5. `REPORT.md` answers Saiful's two questions with the measured numbers and leaves the structural
   options (parallel advocates, envelope-in-transcript, cut/keep) as his decisions.

## Out of scope

- Changing the phase geometry (parallel advocates, multi-round debate) — flagged in the report, not built.
- Rendering envelope fields into `_format_transcript` — see Stage B note.
- Any change to the safety floor, which remains the sole vetoer (DEF059).
