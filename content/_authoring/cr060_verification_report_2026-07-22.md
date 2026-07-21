# CR060 verification pass — sourced-lesson batch (2026-07-22)

**Owner:** Claude (BOK content-quality lane, CR060). **Scope of this pass:** the **30 lessons that
carry a non-empty `sources:` field** (the CR054/CR058 BOK batch, lessons 293–345). **Internal-only**
— users never see this; it exists so *we* are certain the content is correct.

> This is the first end-to-end accuracy audit of the curriculum. It answers Saiful's question —
> *"have we confirmed the questions have the provenance, and that they're correct?"* — for the
> sourced batch. **Answer: no, not until now. 20 of 30 sourced lessons carry at least one genuine
> factual, numerical, or legal error.** Ten are clean and are now stamped `verified`.

---

## 1. Headline

| Outcome | Count | Lessons (CR044 code) |
|---|---|---|
| ✅ **VERIFIED** (stamped) | **10** | ETHIC 6, ETHIC 8, ASST 19, MACRO 3, MACRO 7, MACRO 11, MACRO 12, QUANT 1, QUANT 3, QUANT 8 |
| ⚠️ **FINDING** (real defect, not yet fixed) | **20** | see §4 |
| ⚖️ **legal escalation** (subset of findings) | **1** | ETHIC 2 (294) — see §5 |

**67% of the "sourced" batch had a defect.** The `sources:` field told us where a lesson *claimed*
to be grounded; it never told us the lesson was *right*. This pass is the difference.

## 2. Method — and its honest limits

Two independent LLM agents per lesson, both with **live web retrieval** (WebSearch/WebFetch against
primary sources — BEA/BLS/Fed/SEC/CBOE/CME, filings, the cited papers):

1. **Fact-check** — extract every checkable claim (dates, statutes, statistics, arithmetic, and every
   graded quiz answer + explanation), verify each against the real source, compute all math.
2. **Adversarial refute** — a second agent told to *assume the first was too lenient* and break the
   lesson. A lesson is **VERIFIED only if the fact-check passes AND the refuter cannot break it.**

Why two passes and not one: per the house rule (CR038 "prompt instructions are not controls";
DEF059 the LLM confidently faked an APPROVE), **one agent saying "looks right" is not verification.**
The refute layer earned its keep — it caught real errors the fact-check pass had waved through
(294 Chiarella, 328/327 GDP revisions, 311 tracking-error/difference, 332 QT-mechanism).

**Limit (stated plainly):** dual-AI-pass with source retrieval is **tier-1 assurance, not a human
SME certificate.** The `verified` stamp records exactly that method and date — it is auditable, not
a claim of divine truth. Legal and Sharia claims are escalated to a human regardless (§5). Two
agents died on connection errors and were re-run (327/334/336) — those results are as complete as
the rest.

The `verified` stamp written into the 10 clean lessons:

```yaml
verified: {by: "cr060-ai-dual-pass", date: "2026-07-22", method: "web-corroborated fact-check + adversarial refute"}
```

## 3. Verified (10) — clean, stamped

Every checkable claim SUPPORTED, arithmetic re-computed, quiz answers independently confirmed, and
the adversarial pass could not break them. Several correctly navigated traps the audit itself nearly
fell into (MACRO 3 used the report-day selloff not the post-Fed rally; QUANT 3 used the S&P −20.5%
not the DJIA −22.6%).

`298 ETHIC 6` fiduciary duty · `300 ETHIC 8` suitability/KYC · `321 ASST 19` futures & forwards ·
`325 MACRO 3` labor market · `329 MACRO 7` Fed dual mandate · `333 MACRO 11` FX transmission ·
`334 MACRO 12` capstone policy→portfolio · `335 QUANT 1` expected value · `337 QUANT 3` fat tails ·
`342 QUANT 8` overfitting.

## 4. Findings (20) — genuine defects, **handed to the education lane, not fixed here**

Per the lane rule (verify-on-commit; don't edit another lane's content; protect-the-Room), I log
precise fixes; the education/architect lane applies them. **None of these is refuter over-reach — I
reviewed each as owner.**

### Tier A — poisons a graded quiz answer/explanation (7) — worst class, the app actively teaches the error

| Code | Lesson | Defect | Fix |
|---|---|---|---|
| ASST 9 | 311 expense ratio & tracking error | Conflates **tracking *error*** (volatility of the return gap) with **tracking *difference*** (the fee-driven average gap); the graded **Q2 explanation** repeats it — the expense ratio drives tracking *difference*, not tracking *error* | Relabel to tracking *difference* in body + Q2 explanation |
| ASST 20 | 322 capstone: why retail options lose | (a) Frames theta + vega + break-even as **three stacking hurdles** → double-counts one premium (at expiry theta=vega=0; break-even already embeds it) — in **Quiz 2 & Quiz 3**; (b) "~half of volume is 0DTE" is an **index/ETF** stat, misapplied to single names in the **Quiz 3 stem**; (c) worked example is **2-days-to-expiry but branded "0DTE"** | Reframe the single cost; scope the 0DTE stat to indices; relabel the example |
| MACRO 1 | 323 GDP | "**double-digit declines across major US indices**" in 2022 — Dow was **−8.8%** (single digit); repeated in the **Quiz 1 stem** | Scope to S&P −19% / Nasdaq −33% |
| MACRO 2 | 324 inflation CPI/PCE | **Q1 explanation** claims the subtraction-vs-Fisher gap is *"far larger at 9% than 5%"* — **backwards** (holding nominal fixed, the gap is maximized ≈4.9% and *shrinks* higher); "converge only as inflation→0" is incomplete (also when n=i) | Correct the direction in the Q1 explanation |
| MACRO 5 | 327 business cycle | States as current BEA fact that H1-2022 had **two negative quarters (Q2 −0.6%)**; BEA's **Sept-2024 revision flipped Q2 to +0.3%**. **Quiz 1 explanation** asserts *"GDP figures were not revised to positive"* — false | Reframe as "two negative quarters *as first reported*, later revised"; fix Q1 explanation |
| MACRO 6 | 328 capstone: macro machine | Same GDP-revision staleness (−1.6%/−0.6% presented as current); **Quiz 1 explanation** *"GDP was not revised away"* — false | Same as 327 |
| QUANT 11 | 345 data-mining & survivorship | **Quiz 2's marked-correct answer** says the correction *"can cut the figure by more than half"* — 8%→4.1% is **48.75% (under half)**; contradicts the lesson's own "barely half the 8%" | "cut by nearly half" |

### Tier B — factual / conceptual error in prose (10)

| Code | Lesson | Defect | Fix |
|---|---|---|---|
| ETHIC 1 | 293 market integrity | Enron called *"a top-ten US company **by market value**"* in Aug 2000 — it was **#7 by *revenue*** (Fortune 500 ~$100.8B); by market cap (~$70B) it ranked ~#30–45 | "the seventh-largest US company by revenue" |
| ASST 10 | 312 passive vs active (Bogle) | The named **"cost matters hypothesis"** is attributed to *Common Sense on Mutual Funds (1999)* — Bogle coined CMH in **2003–2005** (FAJ); and *"predicted SPIVA decades before the data"* — SPIVA launched **2002** (~3 yrs later) | Re-date CMH to 2005 FAJ; drop "decades" |
| ASST 15 | 317 payoff diagrams | A $200-strike call with the stock **exactly at $200** is called **"out of the money"** — at S=K it is **at-the-money** (lesson's own put sentence + Quiz 3 get it right) | Call the S=K case at-the-money |
| ASST 17 | 319 covered call & protective put | Put **"payoff"** at $170 (on a $190 put) stated as **$15** — payoff (intrinsic) = MAX(190−170,0) = **$20**; $15 is the *profit* (payoff − $5 premium). Mislabels profit as payoff; inconsistent with the lesson's own covered-call example | State payoff $20, net benefit $15 |
| ASST 18 | 320 implied vs realized vol | Steelman: a single option-selling trade is *"close to a coin flip"* — **wrong**; short-vol is **high-win-rate, negatively-skewed** (~70–90% POP), the very VRP the lesson teaches | Replace "coin flip" with high-win-rate/tail-risk framing |
| MACRO 4 | 326 leading/coincident/lagging | The "trap" pairs **PMI 46.7 (Nov 2023)** with **unemployment 3.4%** "in the same news cycle" — Nov-2023 unemployment was **3.7%**; 3.4% was Jan/Apr 2023 | Change 3.4% → 3.7% |
| MACRO 8 | 330 rate transmission | Rate rise *"**more than doubling** the monthly payment"* — amortized 30-yr P&I rises **~53–66%**, not >100% (only the first payment's *interest component* more than doubles) | "raising the payment by more than 50%" |
| MACRO 10 | 332 fiscal policy | Defines QT as *"**selling down** its own bond holdings"* — 2022–24 QT was **passive runoff** (maturing bonds roll off), **zero outright sales**; wrong mechanism, stated as the definition, in a lesson whose prereq is the QE/QT lesson | "letting maturing bonds roll off without reinvesting" |
| QUANT 2 | 336 base rates | *"most/mostly false alarms"* at 10% base-rate + 90% accuracy — precision is **exactly 50%** (90 of 180), i.e. **half, not most**; self-contradicts ("coin flip" elsewhere) | "about half the alerts are false" |
| QUANT 6 | 340 capstone: Bayesian | *"a two-SE bar (≈20.5) only just **fails to clear** the observed 20-point edge"* — subject/object reversed (20.5 *does* exceed 20 → implies significance, the opposite of intent); contradicts prereq 339. Minor: "$308−$692 ≈ −$385" displays as −$384 | Reverse to "the 20-point edge fails to clear the 20.5 bar" |

### Tier C — overstatement / imprecision / bare source (2)

| Code | Lesson | Defect | Fix |
|---|---|---|---|
| ASST 2 | 304 bond pricing & YTM | *"professional desks quote YTM primary and back into price — they do exactly that"* is **overgeneralized** (US Treasuries — the lesson's own example — are quoted in **price/32nds**, yield derived). Quiz key unaffected. **Also a bare source** ("Standard fixed-income present-value pricing" — QF-001) | Qualify to munis/IG-spread quoting; cite Hull or a CFA fixed-income reading |
| MACRO 9 | 331 QE/QT balance sheet | *"balance sheet shrank ~$1T over the same window"* (rates 0→5.5%, ending Jul 2023) — only **~$0.75T** by then; $1T not reached until **Oct 2023**. Minor: peak "$8.9T" is actually $8.97T (rounds to $9.0T) | Scope the $1T to late-2023, or use ~$0.75T for the rate-hike window |

## 5. ⚖️ Legal escalation — ETHIC 2 (294 insider trading) → needs human/SME sign-off

**This one I do not adjudicate.** The lesson teaches: *"Material and non-public — MNPI — and trading
is off, **no matter how you learned it**… the test is the status of the information, not how
innocently it reached you,"* and treats a tippee as automatically liable.

Under settled US law this is **the rule the Supreme Court struck down**: *Chiarella v. United States*
(1980) rejected the "equal access / parity of information" theory — 10b-5 liability requires a
**breach of a fiduciary duty** (classical or misappropriation theory, *O'Hagan* 1997); *Dirks v. SEC*
(1983) makes tippee liability contingent on the tipper's **breach for personal benefit** and the
tippee's knowledge of it. MNPI acquired with no duty (overheard from a stranger, independently
deduced) can be lawfully traded on.

**Why escalate rather than just fix:** it's a legal-domain claim, and the app is simulation-only
education, not legal advice. The safest teaching frame ("in a duty relationship, treat MNPI as
off-limits — that's the standard your analysts are held to") preserves the *ethics* lesson without
mis-stating the *law*. **Saiful / an SME should approve the reframing before it ships.**

## 6. Cross-cutting patterns → feed author-prompt v2 + the guard

Five recurring failure classes drove the 20 findings. These are the guardrails worth encoding:

1. **Stale-but-was-true data** (327, 328, and 293's rank): figures correct at authoring, invalidated
   by later BEA revisions / the revenue-vs-market-cap conflation. → **numbers need CR046 provenance
   + an "as-of" convention**; capstones must not present a revised figure as current.
2. **Category conflation** (319 payoff vs profit · 311 tracking error vs difference · 293 revenue vs
   market cap · 332 runoff vs sales): confidently swaps two adjacent technical terms.
3. **Overstated generalizations** (323 "across indices" · 320 "coin flip" · 336 "mostly false" · 330
   "more than doubling" · 322 0DTE→single-names · 304 "they do exactly that"): a claim stated more
   strongly than the data supports — often the *load-bearing* clause of the lesson.
4. **Legal oversimplification** (294): a lay rule that settled case law rejects.
5. **Bare / mis-dated sources** (304/317/320 "Standard X"; 311/312 CMH→1999 vs 2005; 328 ISM cited
   inline but absent from frontmatter): passes "has a `sources` field" but not "resolves to a
   specific reputable source."

## 7. Risk + next steps

- **Live exposure:** the 20 defective lessons are **serving to Alpha users today** — there is no
  quarantine gate yet (the CR060 corpus guard isn't wired). Until it is, unverified ≠ withheld.
- **Recommended order:** (1) education lane applies the Tier-A quiz fixes first (the app is actively
  teaching those); (2) Tier B/C; (3) 294 reframed after SME sign-off; (4) architect wires the guard
  (schema `sources`/`verified` + `parse_mdx` + quarantine of unverified) and author-prompt v2 so new
  lessons are born sourced+verified; (5) re-run this pass on the fixed lessons to stamp them; (6)
  extend the pass to the **9 empty-`sources:[]`** asset-class lessons (303/305/306/307/308/309/310/
  313/314) and the **285 unsourced legacy** lessons.
- **What's done here:** 10 verified + stamped; 20 findings logged with fixes; 1 legal escalation;
  the source registry's findings log updated to point here.
