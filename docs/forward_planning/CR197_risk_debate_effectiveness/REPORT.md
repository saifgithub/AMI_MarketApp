# Are the Risk Debators doing anything? — CR197 report

**Asked:** are the aggressive/conservative/neutral prompts really doing anything effective, or
simply taking the two extremes and letting it fall in between? Is it worth the time and effort
debating, or should we just use an index to determine the size?

**Answered:** 2026-08-19, from 118 committed convenes + a full read of the Room's code path.
Every number below is reproducible: `.venv/bin/python -m scripts.debate_signal_report`.

---

## The short answer

You were right about the two extremes and wrong about the Neutral — and the remedy you proposed
was already in place.

1. **The two extreme debators' positions are constants.** Aggressive argues "for" in 117 of 118
   convenes; Conservative argues "against" in 117 of 118. Their stance carries essentially no
   information about the ticker (mutual information with the verdict: **0.0024** and **0.0321**
   bits).
2. **And the ablation confirms the extremes are inert for the decision.** Delete both from the
   PM's prompt and the approval rate does not move — 17.2% against a 16.3% baseline, net −1
   verdict, p=1.0. That is the tightest null in the whole experiment.
3. **But the debate as a stage IS load-bearing, and the Neutral is what carries it.** Delete all
   three and approvals halve: 22 → 10, **p = 0.004**. Every arm that keeps the Neutral sits at
   the baseline rate; every arm without it falls.
4. **"Just use an index for size" is already what happens.** Position size never depended on the
   debate. It is `min(PM's number, risk-tier cap)`, the Trader's "proposal" *is* the cap, and the
   three debator sizes are computed in code before anyone speaks.

So the answer to "is it worth the time and effort debating" is: **two thirds of it is not, and
one third of it is doing real work.** The Neutral is not a tie-breaker between two theatrical
extremes — it is the only voice whose position responds to the ticker, and it is the one the
Portfolio Manager actually uses.

---

## 1. What the debate actually decides today: nothing numeric

The chain, traced end to end:

| Step | Code | Consequence |
|---|---|---|
| Trader's "proposal" | `room_runner.py:3944-3952` → `_risk_tier_size_ceiling` | It *is* the mandate risk-tier cap, not a judgement |
| Debator sizes | `trading_math/sizing.py:111-127` | `trader+2` / `trader−1.5` / `trader`, computed **before** the phase runs and handed to each agent to defend |
| Reading a size back out | — | Never happens. `room_prompts.py:918-921`: *"never parsed back out of prose"* |
| Final size | `room_runner.py:1511-1521` | `min(PM's LLM number, risk_tier_cap)` |
| Compliance / veto | `safety_floor.py:173-192` | `check_mandate_compliance` takes **zero** debate-derived arguments |

The debate reaches the decision through exactly one channel: flat text in the PM's prompt
window, rendered `[agent_id] content` by `_format_transcript`.

**A finding nobody had noticed:** `parse_stance_envelope` strips the stance line *before* the
turn is committed to the transcript (`room_runner.py:4496`). Stance, conviction and headline
exist as fields for the UI — but the PM never sees any of them. It reads prose only. Three of
the four channels the debate could speak through were either constant or invisible to the only
agent that decides.

---

## 2. The measurements

### Stance is a costume (§1 of `DEBATE_SIGNAL.md`)

| agent | for | against | neutral | H(stance) bits |
|---|---|---|---|---|
| aggressive_debator | 117 | 1 | 0 | **0.071** |
| conservative_debator | 1 | 117 | 0 | **0.071** |
| neutral_debator | 36 | 55 | 27 | **1.523** |
| *trader (reference)* | 28 | 81 | 9 | 1.148 |

Only **5 distinct stance triples** occur across 118 convenes, and 3 of the 5 differ solely in
the Neutral. A channel at 0.07 bits decided its answer before the ticker was known.

### Conviction was heading the same way

| agent | low | medium | high |
|---|---|---|---|
| aggressive_debator | **0** | 21 | 97 |
| conservative_debator | 3 | 29 | 85 |
| neutral_debator | 5 | 90 | 23 |

The Aggressive never once expressed low conviction in 118 turns. An advocate that is maximally
confident every time is one a reader learns to discount — which is what makes conviction the
right channel to fix, since unlike stance it is free to vary without breaking the role.

### The prose is genuinely differentiated

Mean Jaccard overlap on cited numbers: aggressive↔conservative **0.233**, aggressive↔neutral
**0.315**, conservative↔neutral **0.346**. These are three different arguments, not three
restatements. This is the half of your question where the prompts come out well.

### Engagement is exactly as lopsided as the geometry predicts

| speaker | names Aggressive | names Conservative |
|---|---|---|
| aggressive_debator | — | 22 (19%) |
| conservative_debator | 39 (33%) | — |
| neutral_debator | **116 (98%)** | **115 (97%)** |

The RISK phase is a single sequential pass, so the Aggressive always speaks into a transcript
ending at `[trader]` — it *cannot* rebut anyone, and its 19% are anticipatory. Upstream
TradingAgents runs this as a cycle; we flattened it to a line for latency and never rewrote the
prompts to match. The Conservative's instruction to engage was a double negative in its DO-NOT
list and measured 33%.

### The one result that cuts the other way

| neutral stance | PM action |
|---|---|
| against | **PASS 55 / 55** |
| for | PASS 19, REJECT 10, APPROVE 7 |
| neutral | PASS 23, APPROVE 2, REJECT 2 |

When the Neutral says "against", the PM passes every single time. Its stance carries 0.233 bits
about the verdict — third highest of any voice measured.

**But this is association, not influence, and the direction is genuinely ambiguous.** The
Neutral speaks immediately before the PM and reads the same eleven turns the PM reads, so a
shared upstream cause fits the data exactly as well as persuasion does. The Trader scores
*higher* (0.361) while merely preceding the decision. Nothing observational can separate these.

---

## 3. What was built

### A. The causal test — RUN, 816 calls (`scripts/pm_debate_ablation.py`)

Replayed the PM call for all 136 committed convenes against `ami-llm` (Qwen3.6-35B-A3B-NVFP4 —
the same model that produced the corpora), six arms, zero errors:

| arm | removed | last voice before PM | Neutral present | APPROVE | rate |
|---|---|---|---|---|---|
| v1a | nothing (baseline) | Neutral | yes | 22 | 16.3% |
| v1b | nothing (resampled) | Neutral | yes | 21 | 15.7% |
| **v3** | **both extremes** | Neutral | yes | **23** | **17.2%** |
| v5 | Conservative + Neutral | Aggressive | no | 14 | 10.3% |
| v4 | Neutral only | Conservative | no | 16 | 11.9% |
| **v2** | **all three** | Trader | no | **10** | **7.4%** |

Directional test (marginal homogeneity — see the correction below):

| contrast | APPROVE→PASS | PASS→APPROVE | net | exact McNemar p |
|---|---|---|---|---|
| same prompt twice — noise floor | 8 | 8 | **0** | 1.000 |
| all three debators removed | 14 | 2 | **+12** | **0.004** |
| extremes removed, Neutral kept | 8 | 9 | −1 | 1.000 |
| Neutral removed, extremes kept | 13 | 7 | +6 | 0.263 |
| Conservative + Neutral removed | 12 | 4 | +8 | 0.077 |

The 14 lost approvals spread across **9 distinct tickers and 3 epochs**, so this is not one
clustered name.

**A correction worth recording, because it changed the answer.** The pre-registered statistic
compared *symmetric* flip rates — "does the ablation flip the verdict more often than resampling
does" — and returned p=1.0, "not demonstrated". That was the wrong instrument. The flip rates are
near-identical (≈12% either way) because noise flips balance out (8 up, 8 down) while ablation
flips do not (14 down, 2 up). The APPROVE count halves with the flip rate unmoved. Marginal
homogeneity was the hypothesis all along.

**And the deflationary explanation was tested, not assumed.** The first four arms showed approval
rate tracking *whoever spoke last*, ordered by how negative that voice is — Neutral 15.7–17.2%,
Conservative 11.9%, Trader 7.4%. Simple recency anchoring explains that without the debate
carrying any information at all. So v5 was added to separate them: it leaves the Aggressive — a
voice that argued "for" in 117 of 118 convenes — speaking last while deleting two thirds of the
debate. Anchoring predicts approvals at or above baseline. **Observed: 10.3%, the second-lowest
arm.** The PM is not echoing its final input.

### The mechanism, visible in one convene

AVGO, same eleven upstream turns, debate present vs absent:

- **With the debate** → APPROVE at 1.5%: *"I am down-sizing the Trader's 3.0% proposal to 1.5%…
  rejecting the Trader's 20-day SMA stop and the Conservative's 50-day SMA stop in favour of…"*
- **Without it** → PASS: *"Risk/Reward asymmetry… 1:1 is insufficient for a 3/5 risk score."*

The debate's function is **option generation**, not persuasion. It hands the PM a middle-sized
alternative it does not construct on its own; without it the PM sees only the Trader's raw
take-it-or-leave-it proposal, and leaves it. That shows up in the sizes too: without the debate,
8 of 10 approvals sit at exactly the Trader's 3.0%, against roughly half when it is present.

This is also why the Neutral specifically matters. Its literal job is *"propose a middle-path
position"*, and it is the only debator whose stance responds to the ticker at all.

### B. A structured SIZE channel

The RISK phase's stance envelope now carries a fourth field, parsed to
`AgentMessage.argued_size_pct` and frozen into the Journal.

This closes CR143's M4 — *"the sizes aggressive/conservative/neutral propose; zero spread means
that phase is costume"* — which has **never produced a valid reading** (its prose extractor was
27% precise; the contracted surface carried a size in 1 of 54 turns).

It also corrects what M4 was measuring. The spread was never evidence: it is 3.5 pt by
construction. What carries information is whether an agent endorses the figure it was handed or
moves off it. M4 now reports that, plus the declaration rate, and refuses to compute a mean from
prose guesses.

Deliberately **not** rendered into the transcript: doing so would change what the PM reads and
invalidate the ablation baseline. That is a decision for after the measurement.

### C. The prompts, rebuilt where the evidence said so

- **All three** now declare the size they actually endorse — framed as "what you mean after
  reading the numbers", not "restate your brief".
- **Aggressive** gains a conviction section with explicit permission to concede: name the
  strongest number against the trade, take conviction down, size below the reference. *"An
  advocate who is maximally confident every time is one the Portfolio Manager learns to discount
  entirely."*
- **Conservative**'s dead double-negative is replaced by a positive instruction to quote the
  Aggressive's strongest number and answer it, plus permission to land *at* the reference size
  when nothing specific is wrong — a real finding it currently has no way to report.
- **Neutral**'s conviction is redefined as how clearly the evidence separates the two cases.
- Overlay blocks carry matching conviction guidance; no SIZE reference there, since overlays
  also render on the 1-on-1 path where no envelope exists.

Every string pinned by `test_def241_def243_debator_arithmetic_and_stance.py` is preserved. Full
suite: **4459 passed, 3 skipped**.

**One caveat, stated plainly:** these are prompt-level instructions, and `failure_patterns` P2
says those measure ~30% compliance. DEF251 measured a *worse* outcome the last time this region
was reworded. So the SIZE field is a **measurement channel, not a control** — nothing downstream
assumes it is present, and its declaration rate is itself reported.

---

## 4. What I recommend, and what is yours to decide

**Do not cut the debate.** Removing it drops the approval rate from 16.3% to 7.4%. On a training
simulator that is not a saving, it is a behaviour change: the Room would refuse roughly half the
trades it currently approves, and the user would mostly be taught to do nothing. Whatever the
extremes are worth, the stage as a whole is load-bearing.

**Do not cut the two extremes either — not yet, and not on this evidence.** This is the trap the
result sets, and it is worth being explicit about. v3 shows the PM does not *read* the extremes:
delete their text and its decisions are unchanged. But every arm holds the surviving turns fixed
at what was recorded, and the Neutral's turn was written in a room where the extremes had spoken.
Its entire job is to synthesise those two. Delete them in a live run and it has nothing to
synthesise, and writes something different — which this replay cannot see. **v3 proves the PM
doesn't need the extremes' prose; it does not prove the Neutral doesn't.**

The honest way to settle it is a live two-arm room benchmark — full convenes, extremes on vs off —
using the CR035 harness that already exists. That is one CR, and it is the only remaining question
worth spending money on here.

**Yours to decide:**

1. **Run the live two-arm benchmark?** If the Neutral holds up without the extremes, cutting them
   saves 2 of 12 LLM calls (~17% of run cost) and two serial round-trips, at a product cost of two
   comb voices and two 1-on-1 personas. If it does not, the extremes are earning their keep as the
   Neutral's raw material rather than as the PM's — which is a perfectly good reason to keep them,
   just not the one the prompts currently claim.
2. **Render the envelope into the transcript?** The PM still cannot see any debator's stance,
   conviction or now-declared size. Given the mechanism is option generation, exposing the three
   declared sizes directly is the cheapest possible upgrade — it puts the menu in front of the
   decision-maker as data instead of prose. This baseline is now recorded, so the change is safe
   to make and re-measure.
3. **Fix the geometry?** The Aggressive still cannot rebut anyone. Running the two extremes in
   parallel and the Neutral after them costs one fewer serial round-trip and gives the Conservative
   something to answer — but it needs the CR077 phase-parallelism guard extended, since that guard
   exists precisely to stop a debate being silently deleted.
4. **Reconsider the roster claim, not the roster.** D-012 fixes twelve agents and that is fine. But
   the product currently implies three risk voices deliberate toward the verdict, and what the
   measurement supports is that one of them does while two supply it with material. Worth aligning
   the copy with the mechanism.

---

## Appendix — what this report does not claim

- **Not claimed:** that the debate is worthless. The opposite is measured — removing it costs
  more than half the approvals (p=0.004).
- **Not claimed:** that the two extremes can be deleted. Only that the PM does not read them.
  Their value as the Neutral's raw material is untested and needs a live benchmark.
- **Not claimed:** that the debate *improves* decisions. It changes them, in the direction of
  more approvals, by supplying middle-sized options. Whether those approvals are better trades
  is a different question this cannot answer — the corpora carry no outcomes.
- **Not resolvable here:** narration divergence. Same-prompt resampling already moves the PM's
  narration by 0.78 Jaccard distance, so the ablation's 0.79 sits inside the noise. That channel
  is too variable to measure this way.
- **Not measured:** whether any of this improves user learning outcomes, which is the actual
  product goal and which no metric here touches.
- **Sample bounds:** 118 convenes over 13 tickers across three prompt epochs. Clustered, not
  independent.
