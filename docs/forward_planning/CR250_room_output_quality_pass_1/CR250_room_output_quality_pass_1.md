# CR250 — Room output quality pass 1

**Status:** proposed · **Owner:** AT:K3 · **Opened:** 2026-10-06

Parent evidence: CR247 tm-all gate measurement + Jev V1 pilot
(`docs/tools/room_investigation_V2/out/jev_v1_pilot/` — two batches of 12
analyst turns scored with full request/response logging).

## Finding 1 — Debators argue from figures not in their payload

Cross-provider: figures_consistent 0.08–0.21 (GLM tm-all), 0.18 (vLLM
production) for the debator desks; envelope↔prose agreement lowest for
neutral_debator on both (0.55 / 0.59). The debator brief hands them computed
role sizes (`agent_size_pct`, CR241) but they write as if they derived the
numbers — the transcript and the PM consume phantom figures as analysis.

**Fix (prompt-only, room_prompts.py debator brief):** attribute handed
figures to "the desk's computed reference"; require payload-citation for any
other number.

## Finding 2 — "High" conviction is claimed, not earned

Cross-provider: turns claiming HIGH conviction show the lowest evidence
support (GLM bull-high support-confidence 0.22; vLLM fundamentals-against-high
0.39). RM and PM weight stances by conviction, so inflated highs skew the
synthesis toward overconfidence.

**Fix (prompt-only, envelope instructions):** "high" requires at least two
named evidence items from the current payload; otherwise the envelope must
cap at medium.

## Boundaries

- Prompt-only. No orchestration, no verifier, no veto path (DEF059 stands).
- One repair/regeneration path is CR249's; this CR adds none.

## Acceptance

D26 gate (AAPL+V, R3, vLLM, production prompts) before/after: verdicts
unchanged when geometry sane; no truncation; stance census shows debator
size attributions; high-conviction rate drops only where unsupported.

## Deferred (separate CRs)

- Bull/bear simultaneous generation + rebuttal swap (anti-anchoring;
  CR247-measured sequential order today).
- V1 live Jev verifier (flag high-claim ∧ low-support turns; needs domain
  threshold validation before it may touch Room output).
