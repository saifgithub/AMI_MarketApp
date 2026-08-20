# Are the Bull and Bear Researchers doing anything? — CR199 report

**Asked:** *"evaluate the impact of the bull and bear agent. Are they really effective? Do they
impact the trade decision?"*

**Answered:** 2026-08-20, from 136 committed convenes plus **952 live calls** against
`ami-llm` — the first stage-ablation this Room has ever completed. Every number below is
reproducible: `.venv/bin/python -m scripts.researcher_signal_report` and
`.venv/bin/python -m scripts.researcher_ablation --report-only`.

---

## The short answer

**Yes to "effective", no to "impact the trade decision" — and the two are not in tension.**

1. **Their positions are constants.** The Bull argues *for* in 135 of 136 convenes; the Bear
   argues *against* in **136 of 136**. The Bear's stance channel measures **0.000 bits** — a
   perfect constant, more rigid than any Risk Debator CR197 measured. The tie the Research
   Manager breaks is a tie by construction, every single time.
2. **Their prose is not a constant, and it moves the adjudicator.** Delete both from the
   Research Manager's window and its stance shifts **significantly bullish**: "for" share goes
   21.7% → 34.9%, statistic +0.233 on a −1..+1 scale, permutation **p = 0.0029** against the
   model's own resampling noise. This is the first causally-demonstrated effect of any Room
   stage on any downstream agent.
3. **That effect dies before the verdict.** The PM's APPROVE rate is 16.0% with them and 15.3%
   without — permutation **p = 0.71**. Verdict flip rate 19.1% against a same-prompt noise
   floor of 14.9%, McNemar **p = 0.38**. The pre-registered rule (p<0.05 **and** ≥5pp over the
   floor) is not met, on either the cascade arm or the PM-only arm.

So they are not decoration — they demonstrably tilt the synthesis bearish, and removing them
would make the Room's adjudicator visibly more bullish. But nothing that tilt does survives
to the number a user acts on.

---

## 1. What channel they have at all

One, and it is prose.

| Channel | Status |
|---|---|
| Stance / conviction / headline | Parsed to `AgentMessage` for the UI — then `parse_stance_envelope` strips the envelope **before** the transcript commit. Verified against real recorded prompts: the PM's window contains `STANCE:` **0 times**. No downstream agent has ever seen a researcher's stance |
| A declared position size | The prompt forbids one (*"Sizing is the Trader's proposal… at this phase no trade has been proposed to size"*), and `_SIZE_DECLARING_AGENTS` is the three Risk Debators only |
| Any structured field | None. Nothing under `app/` reads `BULL_RESEARCHER` / `BEAR_RESEARCHER` outside the phase list, the mock templates and the 1-on-1 overlay |
| **Prose in the transcript** | **The only one.** `_format_transcript` renders `[agent_id] content` into every later prompt |

This is the same finding CR197 made about the Debators, generalised: the envelope strip is
global, not RISK-specific.

## 2. What they cost

They are the **two most expensive decoders in the Room**.

| phase | calls | decode tokens | prefill tokens |
|---|---|---|---|
| RESEARCHERS (Bull, Bear) | 2 of 12 (16.7%) | **27.5%** | 15.8% |
| RISK (3 Debators) | 3 of 12 (25.0%) | 28.3% | 33.1% |

Two agents cost as much decode as the entire three-agent RISK phase.

## 3. The observational read (136 convenes, no LLM)

**Stance is a costume; conviction is not, but carries nothing.**

| agent | for | against | H(stance) | I(stance; verdict) |
|---|---|---|---|---|
| bull_researcher | 135 | 1 | 0.063 bits | 0.0020 |
| bear_researcher | 0 | **136** | **0.000 bits** | **0.0000** |
| research_manager | 28 | 90 | 1.210 bits | 0.3217 |
| trader | 31 | 95 | 1.125 bits | 0.3599 |

Conviction does vary (Bull 62 medium / 73 high; Bear 39 / 97) but its mutual information with
the decision is ≈0.01 bits — indistinguishable from the plug-in estimator's own upward bias.

**Their content decays sharply with distance.** Of the numbers each reader cites, the share
reaching it *only* through a researcher — present in a researcher's turn and nowhere else in
that reader's own prompt, fact sheet and analyst turns included:

| reader | numbers | content words |
|---|---|---|
| research_manager | 4.4% | 12.5% |
| trader | 0.9% | 3.7% |
| portfolio_manager | 0.2% | 2.4% |

**And the Bear does 6.6× the Bull's work.** Numbers reaching the RM uniquely via one side:
Bear **0.46** per convene, Bull **0.07**. The direction of the ablation result was visible here
before a single call was made.

**They are re-citers, not fabricators.** Numbers absent from their own prompt: Bull 6%
(0.8/turn), Bear 12% (2.0/turn) — and sampling them shows almost all are the derived
percentages the prompt explicitly asks for ("a reversion to the 20-day SMA of $62.32 is −3.8%
from the last close"). Not a hallucination finding.

**The RM engages them by name in 90% / 89% of turns.** The Bear names the Bull in 46%.

## 4. The causal test

Four arms per convene, 7 live calls, 136 convenes. A1 control, A2 the **same prompt resampled**
(the noise floor — sampling is server-side and unknown, so the rate at which this model
disagrees with itself had to be measured), B the ablated cascade, C the PM-only strip.

### Stage 1 — the Research Manager: a real effect

| arm | 'for' share (n=129) |
|---|---|
| A1 control | 21.7% |
| A2 noise | 24.0% |
| B ablated | **34.9%** |

`B − mean(A1, A2)` = **+0.233**, permutation **p = 0.0029** (200,000 permutations under
exchangeability — the correct test, since B-vs-A2 alone discards one of the two null draws and
loses the power to see this; it reports p=0.10).

Read plainly: **the pair is net-bearish, and it is the Bear supplying it.** Remove both and the
adjudicator becomes about half again as likely to lean long.

### Stage 2 — the verdict: no resolvable effect

| arm | APPROVE rate (n=131) |
|---|---|
| A1 control | 16.0% |
| A2 noise | 11.5% |
| B ablated | 15.3% |

`B − mean(A1, A2)` = **+0.0153**, permutation **p = 0.71**. Flip rate 19.1% vs a 14.9% floor,
McNemar p = 0.38 (cascade) and p = 0.40 (PM-only). Restricting to the two epochs that replay
today's prompts (n=78) does not change it: 20.0% vs a 16.9% floor.

Note the noise floor itself: **the identical prompt, replayed twice, produces 21 APPROVEs one
time and 15 the next.** Sampling variance is larger than anything the researchers do to the
verdict.

### Where it dies

| arm | RM said 'for' | of those, APPROVE | RM said 'against' | of those, APPROVE |
|---|---|---|---|---|
| A1 control | 29 | 16 (55%) | 94 | 5 (5%) |
| B ablated | 47 | 17 (36%) | 75 | 2 (3%) |

The chain is connected — the RM's stance is strongly predictive of the PM's action (I = 0.20
bits, "for" → 55% APPROVE vs "against" → 5%). But the ablation buys 18 extra "for" syntheses
that each convert at a lower rate, and the product is 16 approvals versus 17. The effect is
real at the adjudicator and arithmetically cancels one step later.

---

## 5. What this does not claim

- **Not claimed: the phase is worthless.** It carries a significant, directional effect on the
  Room's adjudicator, it is shipped user-facing product (SSE, Journal replay, 2 of 11 comb
  voices, 2 unlockable 1-on-1 personas), and D-012 locks the 12-agent roster.
- **Not claimed: exactly zero effect on the verdict.** At n=136 the resolvable effect is
  ~8–10pp. A null here means "no effect large enough to see against this model's own sampling
  noise", not "no effect".
- **Lower bound, not a point estimate.** The Trader and the three Debators keep their *recorded*
  turns in the PM's window in every arm. They wrote those after reading the researchers, so
  whatever they absorbed survives the ablation. Deleting the phase outright would do at least
  this much, possibly more.
- **Not measured:** whether any of this improves user learning, which is the actual product
  goal and which no metric here touches.
- **Sample bounds:** 136 convenes over 13 tickers across four prompt epochs, two of which
  predate the 2026-08-13 persona rewrite. Clustered, not independent.

---

## 6. What I recommend, and what is yours to decide

**Recommended: keep them, and stop paying for a channel nobody reads.**

The stance/conviction envelope is computed, rendered for the UI, and then stripped before any
downstream agent can see it. That is the cheapest available upgrade in the Room: the PM is told
"the Bear argued at high conviction" today only implicitly, through prose it has to infer from.
CR197 flagged the same gap for the Debators and deliberately deferred it so as not to invalidate
its baseline. **That baseline now exists for both phases.** `_format_transcript`
(`room_prompts.py:2228`) already receives the `AgentMessage` objects carrying `stance`,
`conviction` and `headline` and renders only `content` — so this is a small, contained change,
and it is directly re-measurable with these same scripts.

**Yours to decide:**

1. **Cutting the phase to buy back 27.5% of decode.** The evidence says the verdict would not
   measurably move, and the adjudicator would drift bullish by ~13pp of "for" share. That is a
   product decision — you would be deleting the Room's only structured disagreement, two comb
   voices and two 1-on-1 personas — not an efficiency one.
2. **Cutting the Bull alone.** It supplies 0.07 numbers per convene to the RM against the Bear's
   0.46, and its stance is a constant. If one of the two is doing the work, the measurement
   says which. But an unopposed Bear is not a debate, and the bearish drift would deepen.
3. **Fixing the geometry.** The Bear is the only voice with a live chance to rebut, and takes it
   46% of the time. The Bull cannot rebut anyone — it speaks first into a transcript that ends
   at the analysts. Same structural flaw CR197 found in the RISK phase, same fix available
   (a second pass, or reordering), same CR077 phase-parallelism guard to extend first.
