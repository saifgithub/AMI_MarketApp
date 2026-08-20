# CR197 — PM-replay debate ablation: results

Does removing the three Risk Debators' turns from the Portfolio Manager's prompt change its verdict more often than the model changes its own mind on a byte-identical prompt? Every number below is paired per convene.

**Model that produced the corpora:** not recorded — the transcript's `model` field is null on every turn. The port-8000 registry names Qwen3.6-35B-A3B-NVFP4 as the `ami-llm` designee over the corpus dates, but that is inference from a registry, not a datum from the run. It bears only on the replay-vs-recording side-check; the V1a/V1b/V2 contrast is measured fresh on one model and does not depend on it.

## Recorded baseline (from `response_text`, not the floor-vetoed verdict)

| action | n |
|---|---|
| PASS | 111 |
| APPROVE | 23 |
| PARSE_FAIL | 2 |

## Verdict flip rates

| contrast | flips / n | rate | 95% CI (Wilson) | reads as |
|---|---|---|---|---|
| V1a vs V1b — **noise floor** | 16/133 | 12.0% | 7.5% – 18.6% | same prompt, twice |
| V1a vs V2 — debate removed | 16/134 | 11.9% | 7.5% – 18.5% | all three debators stripped |
| V1a vs V3 — extremes removed | 17/133 | 12.8% | 8.1% – 19.5% | Neutral kept |

## Approval rate by arm

| arm | removed | last voice before PM | Neutral present | APPROVE | rate |
|---|---|---|---|---|---|
| v7 | nothing, + LADDER | Neutral | yes (ladder) | 28 | 21.1% |
| v8 | all three → 1 structured officer | Risk Officer | replaced | 22 | 16.7% |
| v1a | nothing (baseline) | Neutral | yes | 22 | 16.3% |
| v1b | nothing (resampled) | Neutral | yes | 21 | 15.7% |
| v3 | both extremes | Neutral | yes | 23 | 17.2% |
| v5 | Conservative + Neutral | Aggressive | no | 14 | 10.3% |
| v4 | Neutral only | Conservative | no | 16 | 11.9% |
| v6 | all three, + LADDER | Trader | no (ladder) | 16 | 11.8% |
| v2 | all three | Trader | no | 10 | 7.4% |

Read down the 'Neutral present' column. Every arm that keeps the Neutral sits at the baseline rate; every arm without it falls, and falls further as more of the rest is also removed. The count of surviving debators does NOT order the table — v3 keeps one and scores highest, v4 keeps two and scores low.

**The recency explanation is refuted by v5.** Approval rate first appeared to track whoever spoke last, ordered by how negative that voice is (Neutral 15.7-17.2%, Conservative 11.9%, Trader 7.4%) — anchoring would explain that without the debate carrying any information at all. v5 leaves the Aggressive speaking last, a voice that argued 'for' in 117 of 118 convenes, and anchoring therefore predicts approvals at or above baseline. Observed: **10.3%, the second-lowest arm.** The PM is not echoing its final input.

## Decision rule — directional (marginal homogeneity)

The question is not whether the verdict *changes* but whether it changes *in a direction*. Resampling moves verdicts symmetrically; an input that carries signal moves them one way.

| contrast | APPROVE→PASS | PASS→APPROVE | net | exact McNemar p |
|---|---|---|---|---|
| same prompt twice — **noise floor** | 8 | 8 | +0 | 1.00000 |
| all three debators removed | 14 | 2 | +12 | 0.00418 |
| extremes removed, Neutral kept | 8 | 9 | -1 | 1.00000 |
| Neutral removed, extremes kept | 13 | 7 | +6 | 0.26318 |
| Conservative + Neutral removed | 12 | 4 | +8 | 0.07681 |
| all three removed, ladder injected | 12 | 6 | +6 | 0.23788 |
| **ladder added to the full prompt** | 8 | 15 | -7 | 0.21004 |
| **3 officers → 1 structured Risk Officer** | 9 | 9 | +0 | 1.00000 |

Rule: p<0.05 with a net in one direction. Result: **The debate causally moves the PM's verdict.** Removing it makes the PM refuse trades it otherwise approves — 14 approvals lost against 2 gained, against a floor that is balanced by construction.

## Position size, where both arms approved

n=8 paired approvals · median Δ = **+0.50 pt** · 4/8 differ at all.

## Narration divergence — does the debate change what the user reads?

| contrast | n | mean Jaccard distance | median |
|---|---|---|---|
| V1a vs V1b — same prompt (floor) | 100 | 0.780 | 0.783 |
| V1a vs V2 — debate removed | 99 | 0.790 | 0.799 |
| V1a vs V3 — extremes removed | 100 | 0.775 | 0.781 |

Excess divergence attributable to removing the debate: **+0.011** Jaccard distance over the resampling floor. A positive value means the PM reasoned from visibly different material, whether or not its verdict moved.

## Per-epoch (primary — pooling across prompt epochs is not defensible)

| epoch | convenes | noise flips | ablation flips |
|---|---|---|---|
| 2026-08-07 | 18 | 1/18 | 1/18 |
| 2026-08-13 | 40 | 7/37 | 2/38 |
| 2026-08-14 | 39 | 5/39 | 8/39 |
| 2026-08-14b | 39 | 3/39 | 5/39 |

## Samples for hand-reading

**Noise flips (same prompt, different answer)** — 16 total
- NVDA/cfd7c48f: PASS→APPROVE
- ANET/740e451e: APPROVE→PASS
- BAC/2edfe094: PASS→APPROVE
- SNDK/49426fa3: APPROVE→PASS
- ANET/24ea86c1: PASS→APPROVE
- AMD/fb825f23: PASS→APPROVE
- GRAB/05c9df6d: PASS→APPROVE
- MU/131bfba9: APPROVE→PASS
- LITE/bded89f3: PASS→APPROVE
- SNDK/92e9636d: APPROVE→PASS
- AMD/5efe8134: APPROVE→PASS
- NBIS/bbf92ccb: APPROVE→PASS

**Ablation flips (debate removed)** — 16 total
- NVDA/cfd7c48f: PASS→APPROVE
- SNDK/49426fa3: APPROVE→PASS
- NBIS/edd5c822: APPROVE→PASS
- SNDK/92e9636d: APPROVE→PASS
- AMD/5efe8134: APPROVE→PASS
- MU/4e67044b: APPROVE→PASS
- NBIS/bbf92ccb: APPROVE→PASS
- SNDK/0a19af2b: APPROVE→PASS
- AVGO/a129374d: APPROVE→PASS
- MU/79e0ee6f: APPROVE→PASS
- NVDA/9d87b4be: APPROVE→PASS
- BAC/1632ce98: APPROVE→PASS

**Extremes-removed flips** — 17 total
- NVDA/cfd7c48f: PASS→APPROVE
- SNOA/0b1e3043: PASS→APPROVE
- ANET/24ea86c1: PASS→APPROVE
- AMD/fb825f23: PASS→APPROVE
- GRAB/05c9df6d: PASS→APPROVE
- MU/131bfba9: APPROVE→PASS
- SNDK/92e9636d: APPROVE→PASS
- AMD/5efe8134: APPROVE→PASS
- NBIS/bbf92ccb: APPROVE→PASS
- NVDA/3b0f4c1e: PASS→APPROVE
- AVGO/a129374d: APPROVE→PASS
- BAC/1632ce98: APPROVE→PASS

## Caveats that bound every number above

- Four prompt epochs; per-epoch tables are primary, pooled figures are indicative.
- 13 unique tickers underlie the convenes — observations are clustered, not independent.
- Server-side sampling temperature is unknown, which is exactly why the noise floor is measured rather than assumed.
- At n≈136 a difference below roughly 8–10pp is not resolvable; a null here bounds the effect, it does not prove absence.
- **The limit that bounds the obvious action.** Every arm holds the surviving turns FIXED at what was recorded, and those turns were written in a room where all three debators spoke. So v3 shows the PM does not need the extremes' text *given a Neutral turn that was produced with the extremes present* — it does NOT show the extremes can be deleted. The Neutral's stated job is to synthesise those two; remove them from a live run and it has nothing to synthesise and writes something different. Testing that needs a live two-arm room benchmark, not this replay.
- Only the PM turn is replayed. This measures whether the debate changes the PM's decision, not whether the debate has value as user-facing product — which it demonstrably does (SSE stream, Journal replay, comb voices, 1-on-1 personas).
