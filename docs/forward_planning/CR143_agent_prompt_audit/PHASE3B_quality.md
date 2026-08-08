# CR143 Phase 3b — Are the prompts any good at their actual job?

Every other measurement in this audit grades honesty or machine-legibility. Four analysts who all
say the same thing parse perfectly. This phase asks the question the prompts exist to answer: **do
they get twelve agents to do twelve jobs?**

Epoch: strictly after the DEF227–233 fixes reached Alpha (2026-08-07 12:00). **n = 18 convenes, 198
prose turns, 18 verdicts.** Tool: `backend/scripts/prompt_quality_sweep.py`. Numbers pooled across a
prompt change would be meaningless, so nothing here crosses that boundary.

---

## Result: the prompts are doing their job. One production parser is not.

| Metric | Result | Read |
|---|---|---|
| **M1** role identifiability | **87.9%** vs 9.1% chance — **9.7× lift** (n=198) | the twelve roles are real, recoverable from text alone |
| **M2** role signal vs ticker signal | same agent/diff tickers **0.302** > same ticker/diff agents **0.199** | turns cluster by **role**, not by ticker |
| **M2b** the four analysts, same convene | **0.128** — the *least* similar pairing measured | the parallel-phase instruction works |
| **M3** number provenance | 92.6% grounded · 3.1% inherited · **4.3% novel** | and the novel ones are derivations, not fabrications (hand-read below) |
| **M4** risk-debator size spread | **unmeasurable** — the production parser is broken | → **DEF235** |
| **M5** PM groundedness | Trader 9/18; the other 9 spread over RM (3), Neutral (2), Aggressive, Market, Conservative | the debate reaches the verdict about half the time |
| **M6** stance entropy | **1.48 of 1.58 bits**; **0 unanimous convenes**; against 80 / for 60 / neutral 48 | the room genuinely disagrees |

### M1/M2 — the roles are not cosmetic

Leave-one-out nearest-centroid over content tokens (ticker symbols removed, so similarity measures
what an agent *says*, not which name it was handed) recovers the author of a turn **87.9%** of the
time against a 9.1% chance baseline. The residual confusions are all semantically adjacent —
`trader → bull_researcher` (3), `neutral_debator → trader` (2), `conservative_debator →
bear_researcher` (2), `research_manager → fundamentals_analyst` (2). Nothing confuses across the
argumentative divide.

M2 is the decisive contrast, and it lands the right way round: a turn resembles **its own role on
other tickers** (0.302) more than **its phase-mates on the same ticker** (0.199). If the ranking were
inverted, the fact sheet would be writing the turns and the role prompts would be decoration.

The strongest single number is **M2b = 0.128**: the four analysts speaking in parallel on the same
convene are the *least* similar pairing in the corpus. That is the CR077 rescoped collaboration line
working — it replaced *"build on the transcript"* (a lie for an agent whose transcript is empty by
design) with an own-domain-lens instruction, after measuring "-7% margin / -1.4% FCF repeated in 3 of
4 analyst turns". **Nobody had re-measured it since. It worked.**

### M3 — "novel" is derivation, not fabrication

4.3% of stated numbers appear in neither the turn's own fact sheet nor its transcript. Per P16 these
were hand-read, not counted. A representative sample:

- Bull: *"$608.23 by 2026-11-03 (88 days), representing a **22.9%** potential gain"* — arithmetic on
  a grounded target
- Conservative: *"a **-14.2%** drawdown from the $494.31 entry, which would consume **1.17%** of our
  total 50% portfolio"* — arithmetic on grounded levels
- Bear: *"if growth decelerates to 10-15%, the multiple compresses to **20-25x**, implying a **-25%
  to -35%** correction"* — an explicitly hypothetical scenario, correctly framed

**The CR037/CR038 fabrication class does not reproduce on this epoch.** That is the guard
`failure_patterns` P2 has recorded as missing since 2026-07; this sweep is the measurement, and it
comes back clean. Caveat: 18 convenes, and the two agents whose feeds are dead (News, Social —
DEF063) state 0.0% novel numbers, which likely means they state almost no numbers at all rather than
that they are especially disciplined.

### M4 — the metric died, and the autopsy is the finding

Only 3 of 18 convenes yielded two extractable sizes, so the spread is unmeasurable. Hand-reading all
11 matches showed **7 of 11 were wrong**: the production `_LEVEL_PATTERNS["size"]` captures stop
distances (`"3.0% size × 6.0% stop"` → 6.0), upside percentages, and raw prices.

One of those reached a user. ANET, Neutral Debator: *"a **MEDIUM** size entry at **$188.62** with a
tight **6.0%** stop at **$177.30**"* — `size` and `entry` both extracted 188.62, and
`_verify_and_annotate_geometry` published

> *"drawdown contribution ≈ **11.32 pt** … These are the figures of record."*

against a true 0.18 pt at the mandate's 3% cap. **63× overstated, under AMI's loudest authority
claim.** Reproduced exactly: `drawdown_contribution(188.62, 188.62, 177.30) = 11.32`. Filed as
**DEF235** — DEF066's overstatement class re-entering through the parser rather than the formula.

### M5/M6 — the debate has friction and it reaches the verdict

Mean stance entropy 1.48 bits against a 1.58 ceiling, **zero unanimous convenes**, and `against`
(80) outnumbering `for` (60) — consistent with the PASS-heavy verdict rate without being uniform.
The PM's reason echoes the Trader in half the convenes and some other voice in the other half.

One outlier is a known defect still present in this epoch: a **GRAB APPROVE whose reason is 19
characters** and matches no agent's turn at all (similarity 0.0). That is DEF232's exact signature.

---

## What this changes

**The model-change hypothesis is now materially weaker.** Phase 1 showed the machine-compliance
scaffolds absorbing ~zero on this epoch. Phase 3b shows the qualitative dimension — role separation,
analyst differentiation, grounded numbers, genuine disagreement — is also healthy. The prompts are
eliciting the behaviour they were written to elicit.

The failures that remain in this epoch are **not** the model failing to follow instructions:

| Remaining failure | Attribution |
|---|---|
| DEF235 — 63× drawdown figure | **our parser**, not the model. The agent's prose was correct English. |
| DEF232 — 19-char APPROVE reason | model-side, 1/18, still open |
| Aggressive citing caps its prompt contradicts (KTOS, SNDK) | model-side, 2 instances — the DEF231 class on the mandate rather than the price |
| News/Social state no numbers | **data supply** (DEF063), not the prompt |

Three of four are ours. A better model fixes at most one of them, and DEF235 — the only one that put
a wrong number in front of a user — would be **unaffected by any model change whatsoever**.

**Recommendation for Phase 4b:** do not run the model arm yet. On this evidence it would be
measuring headroom that is already near the ceiling on every axis we can currently measure. The
higher-value next step is Phase 2 with an attribution bias toward *our* code, plus fixing DEF235.

Caveat that keeps this from being a verdict: **n = 18 convenes.** A 5%-rate failure needs ~60 to
appear once with confidence. Phase 4a's ~30-ticker batch is what would upgrade every number here
from indicative to solid, and it is cheap. That is the measurement I would spend on next, not the
model arm.
