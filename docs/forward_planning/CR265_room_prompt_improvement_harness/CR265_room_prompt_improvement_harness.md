# CR265 — Room prompt-improvement harness

**Status:** in_progress · **Owner:** AT:K4 · **Opened:** 2026-10-27

## Purpose

Implement the prompt-only recommendations from
`docs/Research/room_prompt_stability_review_2026-10-27.md` as a V2 harness
variant and compare them with current production prompts before any production
change.

## Scope

1. New `cr265-prompt-improvements` whole-persona variant: shorter lane-specific
   briefs, contradiction removal, bounded advocacy, clearer Research Manager,
   Execution Desk, Risk Officer and CIO policies.
2. AAPL, risk 4, `ami-llm`, five repetitions per arm, real market data.
3. Current production prompts as the paired control; identical benchmark shape,
   provider and review configuration.
4. Veto/resurrection reviews OFF for comparability with the existing V2 matrix.
   This is not a production-parity acceptance run.
5. Production `content/agents/` and backend decision code remain unchanged.
   Thesis/execution schema separation, lane-specific CLAIMS registries and the
   CR256 verdict gate are structural follow-ups, not disguised prompt edits.

## Acceptance

1. Prompt override probe passes for all 12 agents.
2. Baseline and candidate each complete five AAPL rooms with no failed arms.
3. V2 gate reports no truncation, missing/displaced STANCE or PM JSON findings.
4. Report verdict distributions, flips, vote counts, trade parameters, durations,
   scripted fallbacks and review configuration. One ticker cannot establish a
   general stability improvement; say so explicitly.
5. Any production fold-in requires isolated ablations and a fresh multi-ticker
   production-parity matrix. This AAPL gate can reject a candidate, not authorise
   adoption by itself.

## Result — 2026-10-27

All acceptance measurements completed: 10/10 rooms and 10/10 contract gates.
Combined candidate **NO-GO for stability**; production remains unchanged. Full
analysis and next ablation decision:
`results_aapl_ami_llm_2026-10-27.md`.

## Frozen-input isolated ablations — 2026-10-28

Saiful approved the recommended next step. V2 gains a hash-validated frozen
profile path (`freeze_lab.py` + `room_freeze_profile.py`), leaving backend
production code unchanged. One captured AAPL profile feeds four five-repetition
arms: production control, CIO policy only, four-analyst lane cleanup only, and
Execution Desk thesis/timing only. The combined suite is excluded so each effect
is attributable. Contract, verdict, vote-margin and per-desk stability are
required before any wider matrix. Saiful then expanded the identical frozen design
to Ling-3.0-flash-Fin-fp4 (thinking OFF) and Anthropic Sonnet 5.5, giving 60 rooms
across three models.
