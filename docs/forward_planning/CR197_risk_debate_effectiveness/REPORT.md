# Are the Risk Debators doing anything? — CR197 report

**Asked:** are the aggressive/conservative/neutral prompts really doing anything effective, or
simply taking the two extremes and letting it fall in between? Is it worth the time and effort
debating, or should we just use an index to determine the size?

**Answered:** 2026-08-19, from 118 committed convenes + a full read of the Room's code path.
Every number below is reproducible: `.venv/bin/python -m scripts.debate_signal_report`.

---

## The short answer

You are right about the extremes, wrong about the remedy — and the remedy you proposed is
already in place.

1. **The two extreme debators' positions are constants.** Aggressive argues "for" in 117 of 118
   convenes; Conservative argues "against" in 117 of 118. Their stance carries essentially no
   information about the ticker (mutual information with the verdict: **0.0024** and **0.0321**
   bits). The debate's entire stance output reduces to the Neutral's single call.
2. **But their prose is not formulaic.** The three turns overlap on only 23–35% of the numbers
   they cite, and role identifiability across the twelve agents is 97.5%. The prompts are
   eliciting genuinely different *arguments* on top of predetermined *positions*.
3. **"Just use an index for size" is already what happens.** Position size never depended on the
   debate. It is `min(PM's number, risk-tier cap)`, the Trader's "proposal" *is* the cap, and the
   three debator sizes are computed in code before anyone speaks. Deleting the RISK phase
   entirely would change **zero numeric outputs**.

So the choice was never "debate vs index". It is: keep paying 25% of each run for three turns
whose stance is fixed and whose numbers nothing reads, or make those turns carry signal. This CR
does the second, and sets up the measurement that decides whether even that is enough.

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

### A. The causal test, ready to run (`scripts/pm_debate_ablation.py`)

Replays only the PM call for each committed convene against the LAN vLLM:

- **V1a / V1b** — the exact recorded prompt, twice → the paired same-prompt **noise floor**
- **V2** — the three debator turns stripped from the transcript
- **V3** — extremes stripped, Neutral kept

Validated offline, zero network: **136/136 convenes joined** to their PM audit rows,
**408/408 debator turns** removable as verbatim blocks. Fidelity rules enforced in code:
`VLLMProvider` used directly (the gateway would double the grounding directive and could fall
back to Anthropic mid-measurement), no temperature/top_p sent (production sends none),
`max_tokens=1700`, and baselines parsed from `response_text` rather than the safety-floor-vetoed
`verdict`.

Decision rule fixed in advance: exact McNemar plus Wilson CIs, claim causality only at p<0.05
**and** ≥5pp excess over the noise floor. At n=136, effects below ~8–10pp are not resolvable —
stated up front rather than discovered afterwards.

**Blocked on one thing:** `ami-llm` on port 8000 is down (CR196's finance-model pilot has the
box). The contrast is internally valid on *whatever* model serves that slot, since both arms are
measured fresh in the same session — so this can run whenever the box is free.

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

**Recommended:** keep the debate, run the ablation when the box frees up, and let the result
decide the structural question. Cutting it now would save 25% of run cost while changing no
number the user sees in a verdict — but it would delete three of eleven comb voices, three
unlockable 1-on-1 personas, the RISK stage of the Journal replay, and the 12-agent roster D-012
locks. That is a product decision, not an efficiency one, and it should be made against a
measured effect rather than an assumed one.

**Yours to decide, once the ablation reports:**

1. **If the debate does not move the verdict above noise** — the honest options are to keep it
   explicitly as *narrative product* (and stop implying it informs the decision), or to cut the
   two extremes and keep the Neutral, which is the only voice whose position varies. V3 measures
   exactly that.
2. **Render the envelope into the transcript?** The PM currently cannot see any debator's
   stance, conviction or declared size. Making those visible is the cheapest way to give the
   debate a real channel — but it changes what the PM reads, so it must come after the baseline.
3. **Fix the geometry?** The Aggressive cannot rebut anyone. Running the two extremes in
   parallel and the Neutral after them would cost one fewer serial round-trip and give the
   Conservative something to answer — but it needs the CR077 phase-parallelism guard extended,
   since that guard exists precisely to stop a debate being silently deleted.

---

## Appendix — what this report does not claim

- **Not claimed:** that the debate is worthless. Its prose is differentiated and it is shipped
  user-facing product; what is measured here is that its *stance* channel is near-constant and
  its *numeric* channel was never read.
- **Not claimed:** that the Neutral persuades the PM. 55/55 is an association between two agents
  reading the same eleven turns.
- **Not measured:** whether any of this improves user learning outcomes, which is the actual
  product goal and which no metric here touches.
- **Sample bounds:** 118 convenes over 13 tickers across three prompt epochs. Clustered, not
  independent.
