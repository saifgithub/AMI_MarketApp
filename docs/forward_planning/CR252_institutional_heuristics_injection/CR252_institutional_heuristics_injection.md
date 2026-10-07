# CR252 — Institutional-heuristics injection (evaluation parameter set)

**Status:** proposed · **Owner:** AT:K3 · **Opened:** 2026-10-07

## Origin

Saiful recalled the teammate had specified a CFA-style parameter set for
every evaluation. Found: `teammate_suite/01_institutional_heuristics.md`
(SBC-as-cash penalty, accrual trap, ROIC>WACC law, EV/EBITDA hygiene,
debt-wall/leverage limits, Dorsey moat typology) — and verified it **never
reached any agent**: not in tm-all (constitution-only assembly), only
fragments in production (ROIC in the fundamentals lane; nothing else).

## The A/B

- Variant `cr252-heur`: production persona + heuristics appended verbatim,
  all 12 agents (`benchmarks/cr252-heur/prompts/`).
- Gate: AAPL+V, R3, 2 reps, vLLM (`benchmarks/cr252-heur-gate.yaml`).
- BEFORE: cr251 matrix R3 AAPL+V arms (production prompts, n=4).

## Reads

1. Stance census diff (both tickers, all 12 agents).
2. Heuristics uptake: agents citing ROIC-vs-WACC, classifying the moat,
   SBC-adjusted FCF, EV/EBITDA framing, debt-wall checks.
3. Trade geometry + verdict drift; Jev re-score of both arms.
4. If measured GO: production prompt section + full 30×5 matrix re-run as
   the new regression baseline.
