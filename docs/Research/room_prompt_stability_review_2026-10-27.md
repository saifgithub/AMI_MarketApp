# Room prompt and decision-stability review — 2026-10-27

A critical review of the production Room prompts, the measured harness variants,
`tm-all` and its converted form, the CR256 card variants, and the earlier RES009
consistency/localisation experiments. Recommendations are proposals for new
measurement arms, not unverified production fixes.

## 1. What I understand the application to be

AMI Trade is a mobile-first, simulation-only trading-education product. The user
is the CEO of a 12-agent analyst team. The differentiator is not merely a final
BUY/PASS answer: it is the visible deliberation, the user's mandate, the ability
to brief agents, and the Decision Journal that lets the user inspect and learn
from the decision.

Convene the Room currently has this decision pipeline:

1. A code-built, lane-filtered fact sheet supplies market, fundamental, news,
   positioning, portfolio and mandate data. Derived values and the safety floor
   are computed in code.
2. Four analysts work in parallel; Bull and Bear Researchers, the Research
   Manager, Execution Desk, three Risk Officers and CIO/Portfolio Manager then
   consume a growing natural-language transcript.
3. Eleven agents emit prose plus a machine-readable stance envelope. The CIO
   emits structured JSON. Five CIO samples are aggregated mechanically, with an
   APPROVE vote threshold of 4/4/3/2/2 across risk scores 1–5.
4. A deterministic safety floor remains the binding compliance control. Alpha
   also runs veto and resurrection reviews after the CIO vote.
5. The user receives a simulated APPROVE/PASS verdict, trade parameters where
   applicable, narration and a journal record.

The product therefore has two related but distinct systems: an educational
multi-agent narrative and a binary decision engine. Most of the instability comes
from allowing the first system to remain the lossy, mutable input to the second.

The current policy target is an approval curve of 5/15/30/45/46 per 60 rooms over
risk levels R1–R5, with deterministic exclusions. This is a policy calibration
target, not evidence that the resulting answers are correct.

## 2. Production state verified for this review

The local `content/agents/*.md` hashes match the deployed Alpha copies exactly.
Alpha currently serves `qwen3.8-flash-next-abliterated-nvfp4`, thinking OFF,
five CIO samples, cards OFF, veto review ON and resurrection review ON.

That last point matters: the principal 30×5 matrix methodology explicitly runs
with both reviews OFF. The matrices are valuable model/prompt experiments, but
they are not measurements of the complete production decision path.

## 3. Evidence reviewed and what each variant actually established

| Variant or lever | Measured result | Correct conclusion |
|---|---|---|
| Production prompts, ami-llm | Conservative curve; 27–47% R4/R5 flips on later disposition/cap arms | The user-facing problem is real and model-independent |
| Production, dsv4 | 5/11/22/27/17; 17% flips | Risk curve can invert; PM does not reliably track evidence |
| CR253 disposition ladder | ami 0/0/3/22/36; dsv4 1/7/13/15/19; ami R4/R5 flips 37%/27% | Improved willingness and direction-signed evidence correlation; did not solve stability |
| Sub-cap prose | No measurable incremental effect; sub-cap sizing occurred spontaneously | Sizing policy cannot be controlled reliably by narration |
| 1% cap | Removed one dsv4 inversion but worsened instability; opposite willingness effect on ami | Size/decision coupling is model- and ticker-specific; do not port this mechanism |
| Wholesale `tm-all` | Mandate horizon and TIER sizing overrode user values; bad stop geometry; cross-model NO-GO | Its global constitution is incompatible with AMI's mandate architecture |
| Converted `tm-all` | dsv4 4/6/15/16/17, 27% flips; ami 0/1/4/7/16 | Some analysis ideas are salvageable; wholesale adoption remains dead |
| CR252 institutional heuristics + CR253 data | Made important evaluation concepts executable, but bundled prompt and data changes | Necessary grounding work, not a demonstrated stability mechanism |
| CR256 voluntary/post-hoc cards | ICC 0.62/0.67 | Asking for evidence, or repairing it in a fresh generation, is insufficient |
| CR256 in-turn enforced cards | 98.3% filing; ICC 0.868 on dsv4 | Best validated stability instrument so far; still OFF and not yet a production verdict gate |
| CR256 proxy threshold simulation | 6–10% rep flips | Promising mechanics, not proof that the real card gate will hold on fresh rooms |
| Kolibri thinking ON | 10% flips, 53.7 min/room; thinking OFF too conservative | Stability improved at unacceptable latency; model-specific |
| ami thinking ON | 30–50% flips, NO_VERDICT contamination, 90.4 min/room | Dead end on the incumbent |
| Ling finance model | 4/11/19/29/27, 9.1 min/room; R4/R5 flips 40%/23% | Best calibration/speed candidate, not stable enough |
| Ling at exact T=0 | R4/R5 flips 33%/20% | Temperature helps second-order; it is not the root fix |
| Jev as decider/panel | High same-transcript replay stability, but curve and holdout failures | Useful auditor/feature source, not a replacement decision policy |
| RES009 temperature/replay work | Analyst stances vary; identical runs can have unanimous but opposite PM votes | Variance starts upstream and compounds before the PM ensemble |
| RES009 AR/MS variants | Translated prompt + short final language instruction: 0% English reversion in 20 draws | Best localisation candidate; broader and native-speaker validation still required |

The aggregate lesson is unusually consistent: **persona prose changes priors;
structured evidence and code change reliability.**

## 4. Why stability is still failing

### 4.1 The five-sample PM vote treats the last source of noise, not the largest

The PM samples share one already-diverged transcript. They cannot recover the
alternative facts, objections and emphases lost upstream. RES009's BAC traces
show different analyst emphasis, different Bear theses and different downstream
prompts before the Trader visibly flips BUY/WAIT.

The strongest direct result is in CR256 review M1: among flipped pairs, the PM
was unanimous in opposite directions in 15/26 production-dsv4, 17/31 disposition
and 24/40 `tm-all` cases. More CIO samples would only make the system more
confidently reproduce each run's upstream accident.

### 4.2 Natural language is being used as the decision database

Each run selects a different subset and wording of the available evidence. Later
agents inherit that selection, add their own variation, and the PM sees a
different case. Numeric self-correction blocks can also differ between runs and
become new downstream input.

The transcript is good product narration and a poor deterministic interface.
CR256's card channel is the right correction, but its stable composite is not
yet the production PM's binding decision input.

### 4.3 The task itself creates threshold flips

R4/R5 instructions such as “any defensible thesis” and “pass only broken cases”
do not define a measurable boundary. Many names sit near that boundary. A binary
action then amplifies a small change in evidence direction or wording into a
100% visible verdict change.

Stability, calibration and correctness are different metrics. Forcing a stable
binary label without representing uncertainty would hide, not solve, this issue.

### 4.4 Prompts still contain avoidable contradictions and irrelevant load

These are not the main explanation for 20–40% flips, but they add variance:

1. `fundamentals_analyst.md:162-164` says no WACC is sourced, while CR253 now
   supplies a WACC estimate and every agent's checklist asks for ROIC/WACC.
2. `bear_researcher.md:54-57` tells the agent to derive a percentage, while the
   shared Room format says never compute a new figure.
3. `research_manager.md:12` says “You don't take sides” and then requires a
   recommended stance; line 44 says “Pick a stance.”
4. All 12 personas repeat the same five fundamental evaluation parameters,
   including Technical, News, Social and all three Risk Officers. Several refer
   to a GAPS line those agents do not emit. This is irrelevant instruction load,
   not a lane-specific decision contract.
5. The PM base contains a prose `Verdict:` output format that the Room addition
   must explicitly replace. The base and Room should not describe two contracts.
6. The R1 phrase “strongest case you have seen this quarter” asks for a
   cross-room comparison for which the PM has no calibrated memory or census.
7. `tm-all` repeats a supremacy constitution 12 times, hardcodes horizon and
   size bands, demands unsupported metrics, and mandates rebuttals/catalysts.
   Its converted form made arguments harder but less stable (27% flips).

### 4.5 Sampling remains non-zero and T=0 is not full determinism

Production does not pin temperature. vLLM's default was T=1.0 in the measured
programme. Pinning T=0 on Ling reduced but did not eliminate flips. Continuous
batching and serving implementation can remain non-deterministic at T=0.

Temperature should be explicit calibration hygiene: PM T=0 and low desk
temperatures. It should not be sold or accepted as the stability fix.

### 4.6 The measurement label “same data” is not always strong enough

RES009 found changed headline sets and relative timestamps between nearby runs.
Live market data, journal history and relative-time text can change the actual
prompt even when ticker, mandate and as-of date appear unchanged.

A flip metric must distinguish:

1. **Model flip:** byte-identical frozen inputs and valid complete rooms.
2. **Data revision:** a changed snapshot or changed derived values.
3. **Invalid-room difference:** timeout, scripted fallback, NO_VERDICT or
   missing required machine channels.

At present these are not consistently separated. T=0 results are still strong
evidence of residual structural variance, but earlier aggregate flip totals are
not all pure model-only measurements.

### 4.7 Production and harness configurations differ

Alpha reviews are ON; matrix reviews are OFF. Reviews can uphold, veto or cause
a one-draw CIO reconsideration. Their flip contribution has not been isolated in
the main matrix. Every candidate needs a production-shaped control with the same
review flags, model root, thinking, temperature, cards and safety configuration.

### 4.8 The experiment record itself needs tighter canonicalisation

The deep dive found a duplicate `tm-all` scoring copy, two ami R3 datasets and a
CR257 leg built on the contaminated join. Current documents still carry both
0/0/4/10/20 and 0/0/10/10/20 as the “clean” ami curve. This does not invalidate
the main architectural conclusion, but it prevents precise comparison of small
improvements and must be cleaned before another optimisation round.

### 4.9 No stable independent definition of “right” yet exists

Jev is repeatable, but it largely mimics the PM, does not produce a usable
standalone threshold and can approve holdouts. Fitting thresholds to the target
curve proves that a policy can reproduce counts, not that it selects good trades.
Without held-out tickers, independent case labels and eventual outcome analysis,
the programme can optimise consistency around the wrong answer.

## 5. Prompt improvement plan

These changes are worth testing because they remove ambiguity and variance at
the source. They are **not** expected to achieve the <10% flip target alone.
Implement them as small harness variants, one family at a time.

### 5.1 Replace static data dictionaries with lane-specific reasoning briefs

The generated fact sheet must be the only statement of what arrived. Personas
should describe interpretation and output, not repeatedly enumerate fields that
can later become stale.

Use this common input block for the four analysts:

```text
## Inputs

You receive only this lane's generated fact sheet and the mandate overlay.
The sheet is the sole authority on field availability, provenance, dates and
whether a value is live. Do not recall or estimate a missing value.

Distinguish a reported figure, an AMI-derived figure and your inference.
Use only comparisons supported by the periods and bases stated on the sheet.
Do not derive a new number when AMI supplies the derived value.
Name genuinely decision-relevant missing data in GAPS; do not pad the list.
```

Then retain only each desk's lane-specific interpretation rules. Delete the
five-item CFA block from Market, News, Social, Trader and the three Risk
Officers. Keep a lane-specific checklist for Fundamentals, Bull, Bear, Research
Manager and CIO. In particular:

1. Fundamentals: remove the stale “no WACC” statement; use the sheet's live/NA
   status and label the WACC estimate's limited CAPM basis.
2. Market: evaluate trend/setup/volatility/levels, not earnings quality or moat.
3. News: evaluate catalyst identity, proximity and novelty; require a real dated
   catalyst before discussing catalyst timing.
4. Social: evaluate positioning and sample quality separately from sentiment.
   With no real data, emit `STANCE: none` plus the required machine channels;
   do not “stop” before the contract is satisfied.

### 5.2 Make evidence collection a fixed census before opinion selection

The CR256 registry should be lane-specific, as the independent review already
recommended. A candidate shared contract is:

```text
Process the registry in the stated order. File exactly one card for every item;
do not select only salient items and do not add new items.

For each card:
1. dir is the direction of THIS item's evidence on the proposed long thesis,
   not the direction expected from your role.
2. grade describes support from the supplied payload, not your confidence.
3. Quote only sheet figures and their field identifiers. Missing data is neutral,
   never silently negative and never invented.
4. If an item is outside your lane or has no usable evidence, mark it neutral and
   unsupported rather than constructing an argument.

Complete the evidence census before choosing your stance. Your stance summarises
the filed evidence; it is not a commitment you must defend.
```

Test cards-first/stance-second against the current stance-first layout. The
current leading stance protects against truncation but commits the model before
the argument; it may anchor direction. This is an A/B hypothesis, not a presumed
improvement. If cards-first creates truncation, use separate constrained channels
rather than accepting a fragile long combined generation.

Suggested registries:

1. Fundamentals/research: earnings quality, value creation, valuation,
   balance-sheet survival, moat durability.
2. Market: primary/window trend, range/levels, volatility, volume/liquidity.
3. News: issuer catalyst, macro/regulatory event, timing/proximity, novelty.
4. Social: mention sample, sentiment split, options positioning, baseline
   availability.
5. RM/risk: mandate fit, unresolved objections, execution asymmetry, portfolio
   risk consumption.

`data_present`, catalyst dates, numeric validity and objection resolution must
be computed in code. Self-grades remain tie-breakers, not the primary score.

### 5.3 Replace compulsory advocacy with bounded, falsifiable analysis

For both Bull and Bear, replace “absolute strongest” and mandatory rebuttal
language with:

```text
Build the strongest case your assigned side can support from the filed evidence.
Do not manufacture a catalyst, downside scenario, probability or rebuttal to
satisfy the role. If none is supported, state that explicitly.

Identify the one or two decision-relevant claims, their sheet evidence and the
observable condition that would falsify them. Classify opposing evidence as
answered, partially answered or unanswered; never call it irrelevant merely
because it opposes your seat. Your conviction reflects evidence strength, not
the strength of your language.
```

For Bear specifically, delete the instruction to derive a downside percentage.
Quote AMI's computed downside/asymmetry line or state the price level without a
newly derived percentage.

This preserves the useful `tm-all` dissent discipline without its forced
argumentation, which measurably amplified variance.

### 5.4 Make the Research Manager an adjudicator, not another advocate

Replace the contradictory role wording with:

```text
You adjudicate between Bull and Bear; you have no loyalty to either seat, but
you must reach a stated assessment.

For each material disagreement, identify the exact claim and decide whether the
sheet supports Bull, Bear, both partially, or neither. Separate:
1. thesis quality;
2. unresolved material objections;
3. entry timing;
4. mandate fit.

Recommend LEAN LONG, NEUTRAL/WAIT or PASS with the decisive card/objection IDs.
Do not introduce a new thesis or new figures. Do not convert “evidence is mixed”
into “the company is bad,” or “entry is poor” into “the thesis is broken.”
```

### 5.5 Separate thesis direction from execution timing

The current envelope asks for a view on “taking this position now,” while the
Trader separately chooses BUY/WAIT. Those concepts need separate machine fields:
`thesis_stance` and `execution_action`.

Until that schema exists, use this clarifying Trader text only as a harness arm:

```text
Assess the Research Manager's thesis independently of whether immediate entry
is attractive. State the thesis stance first, then choose BUY only when both the
thesis and current geometry are acceptable; otherwise WAIT with Size 0.00%.

Use AMI's supplied ATR, support, target and drawdown calculations. Do not invent
a wide structural stop to satisfy the investment horizon, and do not turn a
timing-only WAIT into a negative fundamental thesis. State the observable entry
condition when waiting.
```

The long-term fix is structured geometry and separate fields, not more stop-loss
prose. `tm-all`'s wide-stop rule must not return.

### 5.6 Reframe Risk Officers as option generators

CR197 showed that the debate's value is option generation, not simple persuasion.
The Aggressive seat's near-constant FOR stance is not independent evidence.

```text
Your seat defines the option you evaluate, not a conclusion you must reach.
Aggressive: present the largest evidence-supported size within the computed cap.
Conservative: reduce size only for a specific, quantified threat or binding
portfolio constraint. Balanced: select the best-supported executable option;
do not average mechanically.

Use the computed cap, stop contribution, open-risk headroom and trade geometry.
If the evidence does not support your usual posture, lower conviction and say so.
Do not invent objections or upside to make the debate appear balanced.
```

Their SIZE remains an LLM-reported option. Final size must be code-bounded and,
under CR256, computed from evidence rather than negotiated in prose.

### 5.7 Reduce the PM prompt to one decision policy and one output contract

Remove the legacy prose output block from the PM base. Room JSON belongs in one
place only. Retain the measured disposition idea, but define its vocabulary:

```text
## Decision policy

Decide from the evidence record, not from speaker seniority, eloquence, role or
the order of arguments. Evaluate in this order:
1. binding AMI compliance and exclusion results;
2. unresolved material objections;
3. affirmative support for the causal thesis;
4. execution geometry and timing;
5. portfolio fit and size.

Risk appetite changes tolerance and size, never the direction or availability of
evidence. A large permitted size is not itself a reason to PASS.

“Defensible” means an affirmative, sheet-grounded causal thesis with no
unanswered material objection. “Broken” means the causal thesis lacks required
support or a material objection remains unanswered. A material objection can
change expected return, survival, mandate fit or portfolio risk within the
thesis horizon; a generic caveat is not material.

Timing is separate from thesis quality. If the thesis is sound but entry is
unattractive, say so and use the available execution action; do not rewrite the
evidence record to justify the preferred verdict.

Risk disposition:
1. R1: exceptional within-room evidence; all applicable thesis pillars supported
   and no unresolved material objection.
2. R2: strong evidence; one unresolved material objection is sufficient to PASS.
3. R3: solid, well-evidenced case; marginal or contested cases PASS.
4. R4: any defensible thesis; PASS requires a specific flaw or contested material
   objection, not general caution.
5. R5: approve every defensible, eligible thesis; PASS only a broken or
   policy-ineligible case.
```

This removes the unavailable “strongest this quarter” comparison and defines the
R4/R5 boundary. It still needs empirical calibration; wording alone cannot make
that boundary stable.

The future PM JSON should carry `supporting_card_ids`,
`unresolved_objection_ids`, `timing_assessment` and `decision_factor`, with code
validating IDs and computed counts. Narration remains illustrative explanation,
not the source of decision metrics.

### 5.8 Keep localisation simple and separate from decision reasoning

For AR/MS, start from the measured recipe: translated prompt plus one short,
standalone final instruction to respond only in the target language. Keep the
JSON grammar structural. Do not adopt hybrid-CoT as the default; it added a
format-abandonment failure and is more complex than the better-tested
instruction-last arm. Expand beyond JPM/PM and obtain native-speaker review.

## 6. What not to do next

1. Do not run another wholesale 12-persona rewrite and call it a stability arm.
2. Do not raise PM samples as the primary fix; they share the same upstream
   transcript and add cost without restoring missing evidence.
3. Do not revive `tm-all`, its constitution, TIER sizing, hardcoded horizon,
   forced rebuttals or wide-stop doctrine.
4. Do not use another LLM judge as an unverified source of truth or policy
   enforcement. Jev already fails this gate.
5. Do not treat T=0, seed setting or more emphatic wording as deterministic
   architecture.
6. Do not fit on the same 30 tickers and accept on them again; use fresh held-out
   names and report confidence intervals.
7. Do not hide contested decisions by forcing agreement or suppressing the
   split-vote disclosure.

## 7. General application recommendations

### Priority 0 — make the decision path measurable and structurally stable

1. **Finish CR256 as a production decision path, per model.** Complete the
   lane-specific card census, computed data/objection fields, evidence score,
   monotone thresholds and allowed-action gate. The current ICC result validates
   the channel, not the final verdict.
2. **Separate the educational transcript from the decision record.** Preserve
   the 12-agent experience, but let the binding decision consume typed evidence
   and computed geometry rather than the full accumulated prose. This is the
   largest architectural simplification available without deleting the product
   differentiator.
3. **Freeze inputs for stability testing.** Store and hash the exact fact sheet,
   portfolio, mandate, journal context, relative-time rendering, all assembled
   prompts and model parameters. Replay those artifacts, not fresh fetches.
4. **Run a true production control.** Match review flags, model root, thinking,
   sampling, cards and fallbacks. Add review ON/OFF as a separately measured
   factor; do not silently compare review-OFF harness results to review-ON Alpha.
5. **Quarantine incomplete rooms.** Any scripted desk, timeout, NO_VERDICT,
   missing card or replaced PM draw must be labelled and excluded from clean
   stability denominators. Production should show an incomplete/contested state,
   not a settled verdict assembled from fallbacks.

### Priority 1 — make uncertainty and change intelligible to users

1. Show a continuous evidence/contestedness readout and vote distribution beside
   the binary verdict. A marginal decision should look marginal.
2. On repeat convenes, show what changed: data revision, evidence-card direction,
   objection status, geometry, mandate, model or review. Do not present an
   unexplained APPROVE/PASS reversal as a fresh independent truth.
3. Consider decision hysteresis for live repeated runs: a previous verdict may
   change without a material snapshot/evidence delta only after an explicit
   review. This is a product policy, not a substitute for fixing the engine.
4. Keep narration clearly labelled as the model's explanation. RES009 showed
   that confidently stated self-thresholds can be empirically wrong.

### Priority 1 — establish quality, not merely repeatability

1. Build a small independently reviewed case set with known thesis-breaking
   facts, missing-data branches, timing-only cases and genuinely borderline
   cases. Keep it disjoint from threshold fitting.
2. Hold out entire tickers, not just repetitions. Report per-ticker monotonicity,
   holdout recall, discrimination, flip CI, fallback rate, latency and cost.
3. Continue Decision Journal outcome evaluation. A stable but bad decision is
   not success; a changed verdict after material new evidence can be correct.

### Priority 2 — simplify operations and model policy

1. Pin PM T=0 and low desk temperatures as hygiene, log them in every run, and
   keep concurrency controlled. Do not expect this to close the residual gap.
2. Do not enable thinking on the incumbent. Ling remains a candidate only after
   licence, production-parity and fresh held-out acceptance; Kolibri's latency is
   not product-viable as measured.
3. Reduce the number of decision-relevant generative stages where typed evidence
   can replace them. Keep additional agent voices for education only when their
   measured informational value justifies their variance and latency.
4. Clean the experiment registry: one canonical run ID per execution, content
   hashes, one declared ami R3 join, contamination flags, and no duplicate arms
   in pooled analysis.

## 8. Recommended measurement sequence

1. **Measurement repair first:** freeze snapshots; declare the canonical historic
   joins; record full configuration; define model flip, data revision and
   invalid-room difference as separate metrics.
2. **Baseline:** current production prompts and review configuration on ami-llm,
   fixed snapshots, R4/R5 pilot with at least five repetitions per ticker. This
   measures the system users actually receive.
3. **Prompt hygiene arm:** lane-specific briefs and contradiction removal only.
   Expect reduced irrelevant output and fewer avoidable conflicts; do not move
   the goalposts to verdict flips if that was not the measured mechanism.
4. **Evidence-order arm:** lane-specific cards-first versus current
   stance-first, with mechanical filing in both. Measure per-card direction and
   grade agreement, not just ICC of the final scalar.
5. **Decision-policy arm:** the clarified PM definitions alone. Measure boundary
   behaviour, approval curve and holdouts; do not bundle it with step 3 or 4.
6. **Structural arm:** CR256 card gate and computed action set, per model, with
   production reviews both ON and OFF. Only this stage is expected to address the
   main flip mechanism directly.
7. **Acceptance:** fresh held-out tickers; flips <10% with 95% CI; zero
   unlabelled fallbacks; positive discrimination; all deterministic exclusions;
   monotone per-ticker risk behaviour; acceptable latency/cost. Then run the full
   30×5 production-parity matrix before promotion.

## 9. Bottom line

The programme has not failed because the perfect wording has not yet been found.
It has shown that wording cannot reliably stabilise a long chain whose database
is regenerated prose. The remaining prompt work is worthwhile hygiene: shorter,
lane-specific, non-contradictory briefs and clearer decision definitions. The
actual stability fix is to freeze and structure evidence, compute the decision
constraints in code, and measure the exact production path against frozen inputs
and independent labels.
