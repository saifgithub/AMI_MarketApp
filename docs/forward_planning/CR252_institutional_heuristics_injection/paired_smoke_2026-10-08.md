# CR252 paired smoke — post vs pre252 (2026-10-08)

The adoption test for the parallel agents' production changes (heuristics
fold-in `0f41f14e`, data lanes `41dc9f3e`, D29 peers `b34bfd2a`). Arms:
`cr252-post-gate` (backend-default = new production) vs
`cr252-pre252-gate` (frozen heuristics-OFF personas `baseline-pre252`).
Both arms: AAPL+V, R3, 2 reps, vLLM ami-llm, identical data lanes (data is
code; the pairing isolates the prompt effect).

## Verdicts

| Arm | pre252 (heuristics OFF) | post (heuristics ON) |
|---|---|---|
| AAPL-rep1 | PASS 0/5 | PASS 2/5 |
| AAPL-rep2 | APPROVE 3.0%, h90 | APPROVE 2.5%, h60 |
| V-rep1 | PASS | PASS |
| V-rep2 | PASS | **APPROVE 2.0%, h90, CIO 5/5 unanimous** |

## Reads

1. **V's quality-floor flip replicated.** Third independent observation of
   the same mechanism (cr252-heur A/B, adapted-AAPL room, now this): with
   the evaluation-parameters section, Visa's network-effects moat +
   ROIC≫WACC argument becomes tradable — one of two V rooms went unanimous
   APPROVE. AAPL stable on verdicts, trimmed on size (3.0→2.5%) — the
   checklist's caution signature.
2. **Data lanes live in both arms** (data is global): MACD/Bollinger cited
   by market desks, WACC comparisons in fundamentals turns — even the
   frozen-prompt agents pick the new fields up.
3. **Repair-era infrastructure held**: one veto-review 401 (kimi key
   defect) failed SAFE — verdict stood, room completed (no NO_VERDICT
   casualty). Flow-aware gate counting clean under CR249 repair flows.
4. Gate: zero MISSING_STANCE in 8 rooms except one envelope drop
   (post V-rep1 market desk) — the new re-ask guard didn't rescue it;
   one look owed with the guard author.

## Caveats

n=2 per cell. V's flip is one room. Directionally consistent across three
experiments, but the adoption-grade evidence remains the full 30×5 re-run
(analysis_r3 vs BASELINE.md) — this smoke certifies the harness and the
fold-in mechanics, not the statistics.

## Infra note

The pg tunnel (Mac→melehost 5434) keeps dying on app exit/sleep — it
killed one pre252 V room mid-run (script_error, re-done cleanly). Consider
running future benchmark legs on melehost directly (the parallel agent's
`2f5b2281` launcher does this) or a launchd keepalive for the tunnel.
