# CR265 — frozen AAPL isolated ablations across three models, 2026-10-28

Sixty valid paired rooms testing the production control, CIO policy only,
four-analyst lane cleanup only and Execution Desk policy only on one frozen AAPL
profile. Production prompts and backend decision code remain unchanged.

## Decision

**No isolated prompt change is a universal stability improvement. Do not promote
any of the three as a global production change.**

1. **CIO policy only:** NO-GO. Agreement fell from 80% to 20% on Ling and from
   100% to 60% on Sonnet; it also reduced `ami-llm` agreement from 100% to 80%.
2. **Lane cleanup only:** model-specific. It improved Ling from 80% to 100%,
   reduced `ami-llm` from 100% to 60%, and left Sonnet below its 100% control at
   80%. Only the Ling result justifies a wider per-model research arm.
3. **Execution Desk only:** promising on `ami-llm` and Sonnet, NO-GO on Ling.
   Sonnet returned unanimous APPROVE with unanimous PM votes, but all five rooms
   needed deterministic geometry repair. That is not promotion-grade evidence.
4. **Architectural conclusion:** prompt effects are model-local. Any future
   fold-in needs per-model acceptance and potentially per-model prompt routing,
   not another global suite.

## Common measurement contract

1. Ticker/mandate: AAPL, risk 4, long horizon.
2. Repetitions: five per arm; four arms per model.
3. Control: current production personas. Candidates change only the named
   persona(s); every other persona stays production.
4. Frozen profile: `benchmarks/snapshots/aapl-r4-frozen.json`, captured once and
   SHA-256 `489b52b9b547fc30899e5ec0fd5af5b59e3c1d8e895a3f7d69c0a7d7afa77bbe`.
5. Rendered input verification: all 60 valid rooms produced the same Fundamentals
   fact-sheet block SHA-256
   `bba3f7f5f8f7e169b6fd0526c299a946f8b2c58020291b1c321bd646cb525843`.
6. Reviews: veto and resurrection OFF. Cards OFF. Five PM samples; R4 threshold
   2/5 APPROVE votes. Temperature remains each provider's native default.
7. Models: `qwen3.8-flash-next-abliterated-nvfp4` (ami-llm),
   `Ling-3.0-flash-Fin-fp4` (thinking OFF), and `claude-sonnet-5-5`.
8. All 60 rooms completed and passed Mac-side `scoring.gate_report`: no failed
   arms, NO_VERDICT, scripted fallbacks, truncation, missing/displaced STANCE or
   PM JSON findings.
9. This is one ticker. It can reject a candidate and identify the next research
   arm; it cannot authorise production adoption or establish decision accuracy.

## Verdict stability

| Model | Control | CIO only | Lane only | Trader only |
|---|---:|---:|---:|---:|
| `ami-llm` | **100% (5A/0P)** | 80% (4A/1P) | **60% (2A/3P)** | 80% (4A/1P) |
| Ling | 80% (4A/1P) | **20% (1A/4P)** | **100% (5A/0P)** | **40% (2A/3P)** |
| Sonnet | **100% (5A/0P)** | **60% (3A/2P)** | 80% (4A/1P) | **100% (5A/0P)** |

A = APPROVE, P = PASS. The V2 stability threshold is 80%.

### Verdict and PM-vote sequences

| Model/arm | Rep 1 | Rep 2 | Rep 3 | Rep 4 | Rep 5 |
|---|---|---|---|---|---|
| ami control | A 2/5 | A 4/5 | A 2/5 | A 5/5 | A 2/5 |
| ami CIO | A 2/5 | P 0/5 | A 5/5 | A 2/5 | A 2/5 |
| ami lane | P 0/5 | A 3/5 | A 2/5 | P 1/5 | P 0/5 |
| ami Trader | P 1/5 | A 3/5 | A 4/5 | A 2/5 | A 2/5 |
| Ling control | A 5/5 | A 5/5 | A 5/5 | P 0/5 | A 3/5 |
| Ling CIO | A 5/5 | P 0/5 | P 1/5 | P 1/5 | P 0/5 |
| Ling lane | A 5/5 | A 5/5 | A 5/5 | A 2/5 | A 3/5 |
| Ling Trader | P 0/5 | P 0/5 | A 2/5 | P 0/5 | A 5/5 |
| Sonnet control | A 5/5 | A 3/5 | A 3/5 | A 2/5 | A 5/5 |
| Sonnet CIO | A 5/5 | A 5/5 | A 5/5 | P 1/5 | P 0/5 |
| Sonnet lane | A 5/5 | A 5/5 | P 1/5 | A 3/5 | A 5/5 |
| Sonnet Trader | A 5/5 | A 5/5 | A 5/5 | A 5/5 | A 5/5 |

The vote count is APPROVE votes out of five. Sonnet's Trader arm is the only arm
with both unanimous final verdicts and unanimous PM support in every room. Its
geometry-repair caveat below is therefore especially important.

## Runtime and repair burden

| Model | Control mean | CIO mean | Lane mean | Trader mean | Trader geometry repairs (control/CIO/lane/Trader) |
|---|---:|---:|---:|---:|---|
| `ami-llm` | 10.49 min | 11.08 min | 10.49 min | 10.12 min | 1 / 0 / 0 / 1 |
| Ling | 7.19 min | 7.59 min | 7.14 min | 7.28 min | 1 / 0 / 2 / 0 |
| Sonnet | 5.25 min | 5.42 min | 5.10 min | 5.27 min | 4 / 4 / 3 / 5 |

Additional warnings do not change the contract-gate result but limit quality
claims:

1. Incoherent Trader R:R warnings: `ami-llm` control 2 and lane 1; Ling control
   2, CIO 1, lane 3 and Trader 1; Sonnet control 1.
2. Stance-envelope conflicts: `ami-llm` CIO 1 and Trader 1.
3. Sonnet's Trader-only arm needed geometry repair in **5/5 rooms**. The PM's
   unanimous APPROVEs therefore depend on the deterministic repair machinery,
   not simply on a better initial proposal.

## Desk-level findings

1. **`ami-llm` lane cleanup stabilised the first desk but not the decision.**
   Fundamentals became FOR in all five rooms, versus four FOR and one AGAINST in
   the control. Research Manager nevertheless used three stances and final
   agreement fell to 60%. This is direct evidence that first-stage stability
   does not guarantee downstream stability.
2. **Ling lane cleanup improved the final margin, not evidence identity.**
   Fundamentals still used two stances and Trader three, yet all five PM runs
   approved. Verdict stability and evidence stability remain different metrics.
3. **Sonnet's candidates remain variable inside the PM.** Even where final
   actions agree, vote counts and sizes vary. Unanimous action must not be read
   as a unique or deterministic thesis.
4. **Execution Desk policy does not transfer across models.** The same text
   produces 80% agreement on `ami-llm`, 40% on Ling and 100% on Sonnet.
5. **CIO policy is the clearest general negative.** No model improved on it;
   Ling and Sonnet degraded sharply. It should not be carried forward in its
   current form.

## Configuration exclusions and checks

1. The first 20-room Sonnet pass is excluded. Mac defaults omitted recent
   filings and differed on Risk Officer/Trader flags, producing a different
   rendered fact sheet. All 20 rooms were rerun with melehost-equivalent flags;
   only the rerun is reported above.
2. Ling initially failed to launch because log redirection targeted a nonexistent
   host path. It was corrected before any Ling rooms ran.
3. melehost has no Anthropic key, so Sonnet runs used the Mac V2 in-process
   harness with an SSH Postgres tunnel. No backend service was started on the
   Mac. The frozen profile path itself proved to be configuration-sensitive;
   the final hash check is what makes the rerun valid.
4. `test_cr265_freeze_lab.py`: **4 passed**, including RatioBaseline codec
   round-trip, mutation isolation, hash validation and ticker mismatch.
5. The original live-input AAPL suite result is unchanged: combined prompt suite
   NO-GO. These isolated arms explain which components have model-local effects.

## Recommended next step

1. **Do not promote any isolated change globally and do not re-run the combined
   suite as a candidate.** The components have different effects by model.
2. **Retire the current CIO-only variant** rather than tuning it on AAPL again.
3. **For Ling only:** test lane cleanup on a fresh multi-ticker, frozen-snapshot
   set at R4 before considering it for that model. Include per-desk direction
   agreement, not just final verdict agreement.
4. **For `ami-llm` and Sonnet:** keep Trader-only as a research candidate, but
   first separate its thesis/timing text from geometry quality. A valid next arm
   must reduce or explicitly account for repair burden; Sonnet's 5/5 repairs
   cannot be hidden behind a unanimous verdict.
5. **For any wider arm:** retain the production control, freeze the same input
   across repetitions, keep feature flags identical, and report vote margin,
   per-desk stability, repairs, durations and independent quality labels.

## Artifacts

1. Valid runs: `docs/tools/room_investigation_V2/out/cr265-frozen/{ami,ling,sonnet_parity}/`.
2. Excluded Sonnet pilot: `docs/tools/room_investigation_V2/out/cr265-frozen/sonnet/`.
3. melehost runs: `~/cr265_frozen/` and `~/cr265_frozen_ling/`.
4. Logs are stored beside each local arm's JSONL output.
