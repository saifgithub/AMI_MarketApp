# CR199 — the causal test: removing the Bull and Bear Researchers

**136 convenes** replayed through the full four-arm cascade (952 live calls). Reproduce with `scripts/researcher_ablation.py --report-only`.

| arm | RM prompt | PM prompt |
|---|---|---|
| A1 control | verbatim | verbatim, RM turn := A1's RM |
| A2 noise | verbatim, resampled | verbatim, RM turn := A2's RM |
| B ablated | Bull+Bear removed | Bull+Bear removed, RM turn := B's RM |
| C direct | (reuses A1) | Bull+Bear removed, RM turn := A1's RM |

## 1. Stage 1 — does the Research Manager's synthesis depend on them?

| arm | for | against | neutral | unparsed |
|---|---|---|---|---|
| A1 | 29 | 96 | 9 | 2 |
| A2 | 31 | 86 | 15 | 4 |
| B | 47 | 77 | 11 | 1 |

| comparison | RM stance differs | rate | 95% CI |
|---|---|---|---|
| A1 vs A2 (noise floor) | 43/129 | 33.3% | 25.8%–41.8% |
| A1 vs B (ablated) | 50/129 | 38.8% | 30.8%–47.4% |

Mean prose distance (1 − Jaccard over content words): resample **0.738**, ablated **0.769**. The gap is how much of the adjudicator's wording the two researchers were supplying.

### The directional test — which way does the adjudicator move?

A flip rate counts disagreement in either direction and hides a one-way push. Scoring the stance as for=+1 / neutral=0 / against=-1 and testing arm B against BOTH null draws under exchangeability answers the question the flip rate cannot.

| arm | 'for' share (n=129) |
|---|---|
| A1 control | 21.7% |
| A2 noise | 24.0% |
| B ablated | 34.9% |

Statistic `B - mean(A1, A2)` = **+0.233** on the -1..+1 scale, permutation **p = 0.0029** (200,000 permutations).

## 2. Stage 2 — does the verdict move?

| arm | APPROVE | PASS | REJECT | unparsed |
|---|---|---|---|---|
| A1 | 21 | 113 | 0 | 2 |
| A2 | 15 | 121 | 0 | 0 |
| B | 20 | 113 | 0 | 3 |
| C | 14 | 122 | 0 | 0 |

### Flip rates against the control arm

| comparison | verdict differs | rate | 95% CI |
|---|---|---|---|
| A1 vs A2 (noise floor) | 20/134 | 14.9% | 9.9%–21.9% |
| A1 vs B (ablated, cascade) | 25/131 | 19.1% | 13.3%–26.7% |
| A1 vs C (ablated, PM only) | 25/134 | 18.7% | 13.0%–26.1% |

### McNemar — ablation against its own noise floor

| test | b (abl flipped, noise did not) | c (reverse) | p (exact, two-sided) |
|---|---|---|---|
| B vs noise | 13 | 8 | 0.3833 |
| C vs noise | 14 | 9 | 0.4049 |

### Restricted to the current-prompt epochs

The Bull, Bear and Research Manager persona prompts last changed 2026-08-13 (CR179/CR150/CR151), so the 08-14 and 08-14b epochs replay TODAY's prompts and the 08-07/08-13 epochs replay older ones. Every arm is internally valid either way — each convene is compared against itself — but the current-prompt subset is the one that speaks about the Room as it ships.

n = 78 convenes.

| comparison | verdict differs | rate | 95% CI |
|---|---|---|---|
| A1 vs A2 (noise floor) | 13/77 | 16.9% | 10.1%-26.8% |
| A1 vs B (ablated, cascade) | 15/75 | 20.0% | 12.5%-30.4% |
| A1 vs C (ablated, PM only) | 16/77 | 20.8% | 13.2%-31.1% |

### The same directional test, on the verdict

| arm | APPROVE rate (n=131) |
|---|---|
| A1 control | 16.0% |
| A2 noise | 11.5% |
| B ablated | 15.3% |

Statistic `B - mean(A1, A2)` = **+0.0153**, permutation **p = 0.7122**. The push that is real at the adjudicator is gone by the verdict.

### Where it dies

| arm | RM said 'for' | of those, APPROVE | RM said 'against' | of those, APPROVE |
|---|---|---|---|---|
| A1 control | 29 | 16 (55%) | 94 | 5 (5%) |
| B ablated | 47 | 17 (36%) | 75 | 2 (3%) |

Removing the researchers buys the Bull's side more 'for' verdicts from the adjudicator and each one converts at a lower rate, so the two cancel.

## 3. Position size

| arm | mean size_pct | n stated |
|---|---|---|
| A1 | 2.40 | 21 |
| A2 | 2.43 | 15 |
| B | 2.50 | 20 |
| C | 2.75 | 14 |

## 4. What the user reads

| comparison | mean narration distance |
|---|---|
| A1 vs A2 (noise) | 0.807 |
| A1 vs B (ablated) | 0.809 |
| A1 vs C (PM-only) | 0.798 |

## 5. Per-ticker verdict flips (ablated cascade vs control)

| ticker | n | flips | noise flips |
|---|---|---|---|
| AMD | 11 | 2 | 2 |
| ANET | 11 | 3 | 0 |
| AVGO | 9 | 2 | 4 |
| BAC | 10 | 1 | 1 |
| GRAB | 11 | 5 | 5 |
| KTOS | 10 | 0 | 0 |
| LITE | 10 | 1 | 1 |
| MU | 10 | 4 | 2 |
| NBIS | 9 | 2 | 1 |
| NVDA | 11 | 1 | 1 |
| SNDK | 11 | 1 | 2 |
| SNOA | 8 | 1 | 0 |
| TSLA | 10 | 2 | 1 |

## Appendix — what this does not claim

- The Trader and the three Risk Debators keep their recorded turns in the PM's window in every arm. They wrote those turns after reading the researchers, so the ablation cannot remove what they already absorbed: this is a **lower bound** on deleting the phase.

- Sampling is server-side. The floor is measured on this model, in this session; it is not transferable to another serving slot.

- At n=136 the resolvable effect is roughly 8–10 percentage points. A null here is 'no effect large enough to see', not 'exactly zero'.

