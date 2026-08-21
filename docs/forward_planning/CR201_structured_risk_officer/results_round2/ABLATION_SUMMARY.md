# CR197 — PM-replay debate ablation: results

Does removing the three Risk Debators' turns from the Portfolio Manager's prompt change its verdict more often than the model changes its own mind on a byte-identical prompt? Every number below is paired per convene.

**Served model at replay time:** `ami-llm, qwen3.6-35b-a3b-nvfp4`

**Model that produced the corpora:** not recorded — the transcript's `model` field is null on every turn. The port-8000 registry names Qwen3.6-35B-A3B-NVFP4 as the `ami-llm` designee over the corpus dates, but that is inference from a registry, not a datum from the run. It bears only on the replay-vs-recording side-check; the V1a/V1b/V2 contrast is measured fresh on one model and does not depend on it.

## Recorded baseline (from `response_text`, not the floor-vetoed verdict)

| action | n |
|---|---|
| PASS | 113 |
| APPROVE | 23 |

## Verdict flip rates

| contrast | flips / n | rate | 95% CI (Wilson) | reads as |
|---|---|---|---|---|
| V1a vs V1b — **noise floor** | 20/136 | 14.7% | 9.7% – 21.6% | same prompt, twice |

## Approval rate by arm

| arm | removed | last voice before PM | Neutral present | APPROVE | rate |
|---|---|---|---|---|---|
| v9 | all three → 1 officer, PRODUCTION render | Risk Officer ×3 | replaced | 21 | 15.8% |
| v8 | all three → 1 structured officer | Risk Officer | replaced | 18 | 13.3% |
| v1a | nothing (baseline) | Neutral | yes | 22 | 16.2% |
| v1b | nothing (resampled) | Neutral | yes | 22 | 16.2% |

**v8 vs v9 (CR201).** Both make the same single officer call on the same shipped prompt; they differ only in what reaches the CIO. v8 injects one `render_risk_assessment` block ahead of the transcript (CR197's shape); v9 renders the payload into the three risk AgentIds via `render_officer_turns` and appends them where the debate was removed, which is what `_run_risk_officer` actually does. v9 is the shipped assembly; v8 is kept beside it so a move can be attributed to the prompt or to the rendering.

## Risk Officer replies the shipped parser accepted

| arm | convenes | trailing prose after the JSON | otherwise unparseable | discarded |
|---|---|---|---|---|
| v8 | 136 | 0 (0.0%) | 1 (0.7%) | 0.7% |
| v9 | 136 | 0 (0.0%) | 1 (0.7%) | 0.7% |

`trailing prose after the JSON` is a reply that IS a complete JSON object followed by a sentence. `extract_json_object` trims surrounding prose only when the reply does not START with '{' — one that opens with the object and closes with a sentence is handed whole to `json.loads` and rejected as extra data. Production parses with that function, so these are replies production discards, and the arms discard them too.

## Decision rule — directional (marginal homogeneity)

The question is not whether the verdict *changes* but whether it changes *in a direction*. Resampling moves verdicts symmetrically; an input that carries signal moves them one way.

| contrast | APPROVE→PASS | PASS→APPROVE | net | exact McNemar p |
|---|---|---|---|---|
| same prompt twice — **noise floor** | 10 | 10 | +0 | 1.00000 |
| **3 officers → 1 structured Risk Officer** (officer block) | 10 | 6 | +4 | 0.45450 |
| **3 officers → 1 structured Risk Officer** (PRODUCTION assembly) | 9 | 9 | +0 | 1.00000 |

## Position size, where both arms approved (v1a vs v2)

v2 was not replayed in this pass — nothing to compare.

## Narration divergence — does the debate change what the user reads?

| contrast | n | mean Jaccard distance | median |
|---|---|---|---|
| V1a vs V1b — same prompt (floor) | 98 | 0.785 | 0.784 |

## Per-epoch (primary — pooling across prompt epochs is not defensible)

| epoch | convenes | noise flips | v9 flips | v1a APPROVE | v9 APPROVE |
|---|---|---|---|---|---|
| 2026-08-07 | 18 | 0/18 | 0/18 | 3/18 | 3/18 |
| 2026-08-13 | 40 | 7/40 | 6/39 | 6/40 | 6/39 |
| 2026-08-14 | 39 | 5/39 | 4/37 | 8/39 | 7/37 |
| 2026-08-14b | 39 | 8/39 | 8/39 | 5/39 | 5/39 |

## Samples for hand-reading

**Noise flips (same prompt, different answer)** — 20 total
- ANET/740e451e: APPROVE→PASS
- SNDK/49426fa3: PASS→APPROVE
- SNOA/0b1e3043: PASS→APPROVE
- AMD/fb825f23: PASS→APPROVE
- GRAB/05c9df6d: PASS→APPROVE
- NBIS/edd5c822: APPROVE→PASS
- NVDA/a7acdb30: APPROVE→PASS
- GRAB/d182a53f: PASS→APPROVE
- SNDK/0a19af2b: PASS→APPROVE
- AVGO/a129374d: APPROVE→PASS
- NBIS/8585ed67: APPROVE→PASS
- NVDA/9d87b4be: PASS→APPROVE

## Caveats that bound every number above

- Four prompt epochs; per-epoch tables are primary, pooled figures are indicative.
- 13 unique tickers underlie the convenes — observations are clustered, not independent.
- Server-side sampling temperature is unknown, which is exactly why the noise floor is measured rather than assumed.
- At n≈136 a difference below roughly 8–10pp is not resolvable; a null here bounds the effect, it does not prove absence.
- **The limit that bounds the obvious action.** Every arm holds the surviving turns FIXED at what was recorded, and those turns were written in a room where all three debators spoke. So v3 shows the PM does not need the extremes' text *given a Neutral turn that was produced with the extremes present* — it does NOT show the extremes can be deleted. The Neutral's stated job is to synthesise those two; remove them from a live run and it has nothing to synthesise and writes something different. Testing that needs a live two-arm room benchmark, not this replay.
- Only the PM turn is replayed. This measures whether the debate changes the PM's decision, not whether the debate has value as user-facing product — which it demonstrably does (SSE stream, Journal replay, comb voices, 1-on-1 personas).
