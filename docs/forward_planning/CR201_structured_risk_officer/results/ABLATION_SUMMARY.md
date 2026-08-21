# CR197 — PM-replay debate ablation: results

Does removing the three Risk Debators' turns from the Portfolio Manager's prompt change its verdict more often than the model changes its own mind on a byte-identical prompt? Every number below is paired per convene.

**Served model at replay time:** `ami-llm, qwen3.6-35b-a3b-nvfp4`

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
| V1a vs V1b — **noise floor** | 15/130 | 11.5% | 7.1% – 18.2% | same prompt, twice |

## Approval rate by arm

| arm | removed | last voice before PM | Neutral present | APPROVE | rate |
|---|---|---|---|---|---|
| v9t | v9, trailing prose dropped on read | Risk Officer ×3 | replaced | 16 | 12.0% |
| v9 | all three → 1 officer, PRODUCTION render | Risk Officer ×3 | replaced | 9 | 12.5% |
| v8 | all three → 1 structured officer | Risk Officer | replaced | 14 | 18.2% |
| v1a | nothing (baseline) | Neutral | yes | 25 | 18.5% |
| v1b | nothing (resampled) | Neutral | yes | 25 | 19.1% |

**v8 vs v9 (CR201).** Both make the same single officer call on the same shipped prompt; they differ only in what reaches the CIO. v8 injects one `render_risk_assessment` block ahead of the transcript (CR197's shape); v9 renders the payload into the three risk AgentIds via `render_officer_turns` and appends them where the debate was removed, which is what `_run_risk_officer` actually does. v9 is the shipped assembly; v8 is kept beside it so a move can be attributed to the prompt or to the rendering.

## Risk Officer replies the shipped parser accepted

| arm | convenes | trailing prose after the JSON | otherwise unparseable | discarded |
|---|---|---|---|---|
| v8 | 136 | 56 (41.2%) | 2 (1.5%) | 42.6% |
| v9 | 136 | 59 (43.4%) | 1 (0.7%) | 44.1% |
| v9t | 136 | 0 (0.0%) | 1 (0.7%) | 0.7% |

`trailing prose after the JSON` is a reply that IS a complete JSON object followed by a sentence. `extract_json_object` trims surrounding prose only when the reply does not START with '{' — one that opens with the object and closes with a sentence is handed whole to `json.loads` and rejected as extra data. Production parses with that function, so these are replies production discards, and the arms discard them too.

## Decision rule — directional (marginal homogeneity)

The question is not whether the verdict *changes* but whether it changes *in a direction*. Resampling moves verdicts symmetrically; an input that carries signal moves them one way.

| contrast | APPROVE→PASS | PASS→APPROVE | net | exact McNemar p |
|---|---|---|---|---|
| same prompt twice — **noise floor** | 7 | 8 | -1 | 1.00000 |
| **3 officers → 1 structured Risk Officer** (officer block) | 7 | 7 | +0 | 1.00000 |
| **3 officers → 1 structured Risk Officer** (PRODUCTION assembly) | 4 | 0 | +4 | 0.12500 |
| **PRODUCTION assembly, trailing prose dropped on read** | 12 | 4 | +8 | 0.07681 |

## Position size, where both arms approved (v1a vs v2)

v2 was not replayed in this pass — nothing to compare.

## Narration divergence — does the debate change what the user reads?

| contrast | n | mean Jaccard distance | median |
|---|---|---|---|
| V1a vs V1b — same prompt (floor) | 97 | 0.771 | 0.758 |
| V1a vs V9t — production officer assembly | 104 | 0.784 | 0.784 |

## Per-epoch (primary — pooling across prompt epochs is not defensible)

| epoch | convenes | noise flips | v9t flips | v1a APPROVE | v9t APPROVE |
|---|---|---|---|---|---|
| 2026-08-07 | 18 | 0/17 | 1/18 | 3/18 | 2/18 |
| 2026-08-13 | 40 | 5/37 | 3/37 | 8/39 | 4/38 |
| 2026-08-14 | 39 | 4/39 | 7/39 | 9/39 | 6/39 |
| 2026-08-14b | 39 | 6/37 | 5/38 | 5/39 | 4/38 |

## Samples for hand-reading

**Noise flips (same prompt, different answer)** — 15 total
- ANET/740e451e: APPROVE→PASS
- BAC/2edfe094: APPROVE→PASS
- MU/1c6b5fed: PASS→APPROVE
- SNDK/49426fa3: APPROVE→PASS
- NBIS/edd5c822: PASS→APPROVE
- LITE/bded89f3: PASS→APPROVE
- AMD/5efe8134: APPROVE→PASS
- GRAB/d182a53f: PASS→APPROVE
- NBIS/bbf92ccb: APPROVE→PASS
- GRAB/42cfea51: APPROVE→PASS
- KTOS/d4b840cd: PASS→APPROVE
- MU/e5e05aae: APPROVE→PASS

**Production-officer flips (v1a vs v9t)** — 16 total
- BAC/9a940443: APPROVE→PASS
- BAC/2edfe094: APPROVE→PASS
- SNDK/49426fa3: APPROVE→PASS
- SNOA/0b1e3043: APPROVE→PASS
- AMD/0bb2186b: APPROVE→PASS
- LITE/bded89f3: PASS→APPROVE
- AMD/5efe8134: APPROVE→PASS
- GRAB/d182a53f: PASS→APPROVE
- MU/4e67044b: APPROVE→PASS
- NBIS/bbf92ccb: APPROVE→PASS
- NVDA/3b0f4c1e: APPROVE→PASS
- MU/d6be4ff4: APPROVE→PASS

## Caveats that bound every number above

- Four prompt epochs; per-epoch tables are primary, pooled figures are indicative.
- 13 unique tickers underlie the convenes — observations are clustered, not independent.
- Server-side sampling temperature is unknown, which is exactly why the noise floor is measured rather than assumed.
- At n≈136 a difference below roughly 8–10pp is not resolvable; a null here bounds the effect, it does not prove absence.
- **The limit that bounds the obvious action.** Every arm holds the surviving turns FIXED at what was recorded, and those turns were written in a room where all three debators spoke. So v3 shows the PM does not need the extremes' text *given a Neutral turn that was produced with the extremes present* — it does NOT show the extremes can be deleted. The Neutral's stated job is to synthesise those two; remove them from a live run and it has nothing to synthesise and writes something different. Testing that needs a live two-arm room benchmark, not this replay.
- Only the PM turn is replayed. This measures whether the debate changes the PM's decision, not whether the debate has value as user-facing product — which it demonstrably does (SSE stream, Journal replay, comb voices, 1-on-1 personas).
