# CR252 — Heuristics A/B diff report (first measurement, 2026-10-07)

Gate: AAPL+V, R3, 2 reps, vLLM ami-llm. BEFORE = cr251 matrix R3 arms
(production prompts, n=4). AFTER = variant cr252-heur (production persona +
`01_institutional_heuristics.md` appended, all 12 agents, n=4).

## Verdict diff

| Arm | BEFORE | AFTER |
|---|---|---|
| AAPL-rep1 | APPROVE 3.0% | APPROVE 2.5% (h26d) |
| AAPL-rep2 | PASS | PASS |
| V-rep1 | PASS | **APPROVE 2.5%, PM 5/5 unanimous** |
| V-rep2 | PASS | PASS |

V flipped PASS → unanimous APPROVE in rep1. AAPL held APPROVE (size trimmed
3.0→2.5%). n=2 per cell — direction, not proof.

## The V-rep1 mechanism (stance census)

| Agent | BEFORE V-rep1 | AFTER V-rep1 |
|---|---|---|
| fundamentals | for/high | neutral/medium |
| market | neutral/low | **for/medium** |
| news | for/medium | neutral/low |
| trader | neutral/low | **for/medium** |
| research_manager | neutral/low | neutral/medium |
| conservative | neutral/low | for/low |

With the parameter set, the desk stopped hand-wringing over "premium
multiple, no catalyst" and found the institutional floor: network-effects
moat classification + ROIC≫WACC turns Visa's quality into a *tradable*
thesis. The Trader flipping neutral→for is the hinge; the PM then went 5/5.
This is exactly what "feeding the right information" was supposed to do —
the agents didn't get smarter, they got the checklist.

## Uptake (concepts cited per arm, prose turns)

SBC-adjustment 17 turns, EV/EBITDA 13, ROIC 13, WACC 6, moat
classification 6, accrual check 3, Net-Debt 4 — across all 4 rooms.
Production baseline (V walkthrough sample): zero WACC/moat framing.
The module is being applied, not ignored.

## The guard finding (shared with production)

V-rep2 AFTER dropped envelopes on bear_researcher + research_manager
(gate FAIL, MISSING_STANCE ×2). BUT the BEFORE set also shows one
NO-ENVELOPE (neutral_debator, AAPL-rep2). Envelope loss is the ambient
long-output failure class (CR219-era), not heuristics-specific — n=8 total
rooms, 3 events. Still: heuristics add ~3.5k chars to already-long prompts,
so a format guard (envelope presence checked before commit, re-ask once)
belongs in the same CR that ships this, or CR250's scope.

## Recommendation

**Measured GO, with guard.** Fold the module into production briefs as a
distinct "evaluation parameters" section (adapted: AMI voice, grounded to
the fact sheet — not the raw teammate text), plus the envelope-presence
re-ask. Acceptance: D26 gate before/after (already partially evidenced),
then the full 30×5 matrix re-run as the new regression baseline — the
monotonicity science then measures the *heuristics-on* system, which is
the version that should ship. Jev re-score of both arms lands with the
matrix-wide scoring pass.
