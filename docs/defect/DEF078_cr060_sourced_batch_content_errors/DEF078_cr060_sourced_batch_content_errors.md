# DEF078 — CR060 sourced-batch content errors (20 lessons)

**Source:** prompt (Claude, CR060 verification pass). **Area:** content. **Status:** open.
**Filed:** 2026-07-22 (AT:R64). **Owner of the finding:** Claude (CR060 BOK-quality lane).
**Owner of the fix:** education / build lane — CR060 verifies, it does **not** edit another
lane's content.

## What

The first end-to-end CR060 accuracy audit ran a **dual-AI-pass** (web-corroborated fact-check +
adversarial refute, both with live retrieval against primary sources) over the **30 lessons that
carry a non-empty `sources:` field** (293–345). Result: **10 verified & stamped, 20 with a genuine
factual / numerical / legal error, 1 of those escalated for legal sign-off.**

**Full detail — per-lesson defect + exact fix + method + limits:**
[`content/_authoring/cr060_verification_report_2026-07-22.md`](../../../content/_authoring/cr060_verification_report_2026-07-22.md).

## The 20 findings (fix targets)

**Tier A — poisons a graded quiz answer/explanation (7), fix first (app actively teaches the error):**

- `311 ASST 9` — conflates tracking *error* (volatility of the gap) with tracking *difference*
  (fee-driven avg gap); the graded **Q2 explanation** repeats it.
- `322 ASST 20` — theta + vega + break-even framed as three stacking hurdles (double-counts one
  premium) in **Quiz 2/3**; "~half of volume is 0DTE" (an index stat) misapplied to single names in
  the **Quiz 3 stem**; worked example is 2DTE but branded "0DTE".
- `323 MACRO 1` — "double-digit declines across major US indices" 2022 (Dow was −8.8%), in the
  **Quiz 1 stem**.
- `324 MACRO 2` — **Q1 explanation** has the subtraction-vs-Fisher gap direction backwards.
- `327 MACRO 5` — H1-2022 presented as two negative GDP quarters; BEA's Sept-2024 revision flipped
  Q2 to +0.3%; **Quiz 1 explanation** "GDP figures were not revised to positive" is false.
- `328 MACRO 6` — same GDP-revision staleness; **Quiz 1 explanation** "GDP was not revised away" is
  false.
- `345 QUANT 11` — **Quiz 2 marked-correct answer** "cut by more than half" (8%→4.1% is 48.75%).

**Tier B — factual/conceptual prose error (10):** `293 ETHIC 1` Enron "top-ten by market value"
(was #7 by *revenue*) · `312 ASST 10` CMH mis-dated to 1999 (2005 FAJ) + "SPIVA decades" (2002) ·
`317 ASST 15` S=K call called OTM not ATM · `319 ASST 17` put payoff $15 vs $20 (profit/payoff
mislabel) · `320 ASST 18` short-vol "coin flip" · `326 MACRO 4` Nov-2023 unemployment 3.4% vs 3.7%
· `330 MACRO 8` "more than doubling" the mortgage payment (actually +53–66%) · `332 MACRO 10` QT =
"selling" vs runoff · `336 QUANT 2` "mostly false alarms" (precision is exactly 50%) · `340 QUANT 6`
"fails to clear" subject/object reversed.

**Tier C — overstatement / bare source (2):** `304 ASST 2` YTM-primary quoting overgeneralized +
bare source (QF-001) · `331 MACRO 9` $1T balance-sheet-drain timing overstated ~30–40%.

## ⚖️ Legal escalation — `294 ETHIC 2` (needs human/SME sign-off, NOT in this batch's auto-fix)

The insider-trading lesson teaches "MNPI — trading is off, no matter how you learned it." Settled
US law (*Chiarella* 1980, *Dirks* 1983, *O'Hagan* 1997) requires a **breach of a fiduciary duty** —
the "equal-access" theory the lesson states was expressly rejected. Reframe to the duty-based rule
after SME approval. See report §5.

**CLOSED 2026-07-22 (`4dfd6c9`).** Saiful edited the lesson himself, adding *who* holds the
information to the non-public prong (CEO/directors/employees; lawyers/bankers/auditors) — which is
the duty test in all but name — then approved the reframe of the closing rule. The equal-access
claim appeared in **four** places, all now moved together: the intro, "the trap", quiz 1's answer
text + explanation, and the takeaway. Quiz 1's correct index is unchanged; it was already right, for
the wrong stated reason. The three cases are now in `sources`, and the provenance line records that
this is US law specifically — several jurisdictions do run a possession-based rule, so the old text
was not wrong everywhere, only where it claimed to be. The operating heuristic ("holding MNPI with
no innocent path you can name ⇒ don't trade") survives as a heuristic rather than as a claim about
the law.

## Acceptance

1. Each Tier-A/B/C fix applied to its lesson by the education lane, matching the report's fix column.
2. `294` reframed after human/SME sign-off.
3. Re-run the CR060 dual-pass on the fixed lessons; a lesson earns its `verified` stamp only on a
   clean re-pass.
4. (Separately, CR060 open item) architect wires the corpus guard so unverified ≠ served, and
   author-prompt v2 mandates `sources` + `verified` so new lessons are born sourced.

## Notes

- **Live exposure:** all 20 serve Alpha users today; there is no quarantine gate yet.
- Cross-cutting failure classes driving these (feed author-prompt v2 + the guard): stale-but-was-true
  data, category conflation, overstated generalizations, legal oversimplification, bare/mis-dated
  sources. Report §6.
