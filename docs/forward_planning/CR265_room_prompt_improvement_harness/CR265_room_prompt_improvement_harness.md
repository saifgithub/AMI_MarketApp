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
