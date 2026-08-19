# CR032 — GB10 shared-hardware conflict + LoRA fine-tuning go/no-go decision

**Status:** proposed (decision CR — mirrors CR006/CR007's genre, not a build CR) ·
**Session:** AT:R55 · **Date:** 2026-07-12
**Source:** migrated from `Silent_Scout/00_environment/`, `01_research/`, `02_data/`,
`03_training/`, `04_eval/` as part of closing and deprecating Silent_Scout.

## What

The 13-agent LoRA fine-tuning research track (Concierge-first, on-prem GB10) needs a
go/no-go decision before any further work — and one hard blocker was never actually
addressed in ~9 weeks of "active research."

## The blocker: GB10 IS the production LLM server

`Silent_Scout/00_environment/gb10_bringup.md:3` pins the GB10/DGX-Spark research box
at `192.168.20.74`. That is the **exact same IP** `CLAUDE.md`, `HANDOVER_R.md:81`, and
`docs/initial_specs/08_tech/hosting.md` all name as the **live production vLLM host**
serving `ami-llm` (Gemma 4 31B) to every one of the 13 agents in the running Alpha app,
24/7, for real users. The bring-up doc's own capacity math ("never run training and
vLLM serving at the same time, 90GB + 85GB > 128GB") only reasons about Silent_Scout's
*own* two workloads — it never accounts for the fact this box is already carrying
production inference. A Concierge LoRA training run or a 13-adapter serve test risks
starving or crashing live agent-serving for real Alpha users. Nothing in the LoRA
track ever flagged this.

**This is very likely why the track has zero execution artifacts after ~9 weeks:** no
`frozen_<date>.txt` pip snapshot, empty `03_training/runs/`, no adapters, no eval
results, despite the README's own phase table sizing Phase 0+1 at ~1 week.

## The decision, framed plainly

Given GTM mode's near-term direction is real-data wiring into the *existing*
Claude/vLLM-served agents (CR023 news, CR024 social — not a swap to locally fine-tuned
models), this CR asks Saiful to pick one:

1. **Continue the LoRA initiative** — requires either dedicated hardware for
   training/eval (separate from the production GB10) or an explicit maintenance-window
   protocol (e.g., train only during defined low-traffic windows, with a hard kill-switch
   if production latency degrades).
2. **Shelve the LoRA initiative for now** — GTM mode's priority is real-data wiring
   (CR023/CR024) and shipped features, not model infrastructure work with no
   committed rollout date. Revisit post-launch if unit economics or persona-stability
   pressure make it worth resuming.

No code or infra work should happen on this track until one of these is chosen.

## What's salvaged either way (verified against production, still accurate)

- **`02_data/recipes/`** — the per-role SFT-JSONL builders (`concierge.py`,
  `fundamentals_analyst.py`, `_seed_mandates.py`) — every production cross-reference
  checked out exactly against current schemas (`overlay_generator.py:21`,
  `agents.py`, `mandate.py:85-126`). This is the one part of the track that would run
  correctly today, unmodified — worth keeping regardless of the decision above.
- **`01_research/`** (base model pick, dataset map, framework survey, reference
  papers) — no false claims found, but flagged `updated: verified 2026-05-12/13` and
  the doc's own "re-verify weekly" instruction — 9 weeks stale. Re-check before
  spending any GPU time if the initiative continues.
- **`03_training/llamafactory_configs/`** — two well-formed, unexecuted YAML configs.

## A real bug, orthogonal to the decision above

`04_eval/mandate_compliance_eval.py`'s `_trade()` helper constructs `ProposedTrade`
with `is_buy=`/`is_sell=` kwargs. Current schema
(`backend/app/schemas/trade.py:55-72`) requires `side: Side` and exposes
`is_buy`/`is_sell` only as **read-only properties**, not constructor args — every one
of the 500 generated adversarial test cases would raise a `ValidationError` before any
check runs. This is the script meant to gate the README's own hard safety-floor claim
("100% block on 500 adversarial mandate-violation cases") — that claim is currently
unverifiable. Trivial fix (`side=Side.BUY if is_buy else Side.SELL`) **if and when this
track resumes** — not worth fixing in isolation if the initiative is shelved.

## Scope

**In:** the decision itself; preserving the salvageable research/recipes/configs.
**Out:** any training run, any GB10 config change, any code — all blocked on
Saiful's choice above.

## Acceptance

- Saiful has chosen continue-with-dedicated-hardware-or-protocol vs. shelve.
- If continuing: a concrete hardware/scheduling answer exists before Phase 1 restarts,
  and the eval-script bug above is fixed before any safety-floor claim is trusted.
- If shelving: this CR + its ported research stands as the record of where the
  initiative left off, so a future resume doesn't start from zero.

---

## Revived and resolved 2026-08-19 (AT:R70) — decision: GO

The shelve condition ("revisit only if paired with dedicated hardware or a maintenance-window
protocol") is met: Saiful — *the GB10 can be made available for training* (possibly an **offsite**
unit, in which case ami-host is never occupied at all). This CR closes **done** as the decision
record; execution lives in [CR196](../CR196_finance_tuned_model_pilot/CR196.md).

What changed since 2026-07-12, measured on ami-host 2026-08-19:

- **Serving co-residency is now routine** on the box (Qwen3.6 `:8000` + BGE-M3 `:8012` today;
  Falcon-H1 GPTQ ran co-resident earlier per the Manager's `PORT_ALLOCATION.md`). The body's
  "90GB + 85GB > 128GB" math was about *training* vs serving and still holds for training —
  it was never a bar on serving a second model. Free memory with production up: 45Gi of 121Gi.
- **Corrections to the body:** line 19's "`ami-llm` (Gemma 4 31B)" is stale — the slot has served
  `RedHatAI/Qwen3.6-35B-A3B-NVFP4` since 2026-06-11. The 13-per-agent-LoRA framing is superseded:
  the revived target is **one finance-tuned model** — LoRA on the Fastino-Nemotron-3.5-Lightning
  merged BF16 checkpoint (Saiful's base decision, 2026-08-19) — not thirteen adapters.
- **Still true and carried forward:** the `04_eval/mandate_compliance_eval.py` bug this CR recorded
  (`ProposedTrade(is_buy=…)` vs the read-only-property schema) remains unfixed; the track is now
  resuming, so the one-line repair (`side=Side.BUY if is_buy else Side.SELL`) is CR196 Phase 4
  work, and no safety-floor claim is trusted until it lands. The salvaged `02_data/recipes/` are
  load-bearing again — CR196 §2 recipe 7 regenerates them against current schemas.
