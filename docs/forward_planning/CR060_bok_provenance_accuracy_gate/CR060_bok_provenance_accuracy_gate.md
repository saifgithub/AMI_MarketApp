# CR060 — BOK provenance & accuracy gate: every claim sourced *and* verified

**Status:** planned — **quality gate / governance CR** (architect + Saiful) · **Session:** AT:R63 · **Filed:** 2026-07-21

> Requirement (Saiful): *"A high-quality body of knowledge also means 100% certainty the lessons
> are accurate. We need to know the sources of each lesson, and they must come from reputable
> sources. Have we confirmed the questions we have have provenance?"*

**Direct answer: No — not yet.** This CR makes source-provenance **and** independent verification a
hard, enforced requirement across the entire BOK, and elevates CR054's P1 (the sourcing spine) from
a Wave-3 nicety to a **shipping gate**.

---

## 1. Measured state (2026-07-21 snapshot — the corpus is growing live)

| Fact | Count |
|---|---|
| Lessons total | ~312 (actively growing as BOK waves land — 334+ by end of day) |
| Lessons with **no `sources:` field** | **288** — the entire original curriculum |
| Lessons with a **populated, reputable** `sources` | ~24–46 (the newest 293–334 ethics/asset/macro batches) |
| **Quiz explanations that cite a source** | **0** |

**The good news:** the newest batches are sourced *well* — CFA Institute, SEC Rule 10b-5, Bogle,
CBOE, CME, BEA, BLS, NBER, Federal Reserve, CBO, Treasury, Bank Negara, SAMA. Primary/authoritative.
The education lane has already adopted the practice; this CR makes it **mandatory, complete, and
verified** rather than voluntary and partial.

**The two gaps that block "100%":**

1. **Coverage** — 288 lessons carry no source at all; the questions carry none.
2. **Verification** — even the sourced lessons are *asserted*, not *confirmed*. A `sources` line
   says "this rests on X"; nobody has checked that every claim and every quiz answer actually
   matches X. The content is **AI-authored**, and per our own house rules — **CR038** ("prompt
   instructions are not controls"), **DEF059** (the LLM confidently faked an APPROVE) — *AI writing
   it and AI citing it is not confirmation.* An AI can cite a real source and misstate it.

## 2. Two distinct requirements — don't conflate them

| | **Provenance** | **Verification** |
|---|---|---|
| What | Every lesson + every quiz question names the reputable source(s) it rests on | An independent check confirms each claim/answer is accurate *per that source* |
| Artifact | `sources: [...]` from an allowlisted registry | `verified: {by, date}` stamp after review |
| Enforceable by | a corpus-test guard (structural) | a review pass (process) + guard that the stamp exists |
| Status today | ~24–46/312 lessons, 0 questions | **0** |

Both are required. Provenance without verification is a footnote that may be wrong; verification
without provenance isn't reproducible.

## 3. The honest truth about "100% certainty"

Provenance is fully achievable and enforceable. **"100% accuracy" is asymptotic** — the gate
*maximises* it and makes every claim *defensible*, but the guarantee we can actually make is:

> *Every factual claim and every quiz question is traceable to a reputable source and has been
> independently reviewed against it; every computed number comes from CR046, not an author.*

That is the real-world standard for a defensible BOK (it is how the CFA curriculum, a textbook, or
a regulator's investor-education material is held to account). **An automated-only pipeline cannot
promise 100%** — the last mile is human/expert judgement. This CR builds the structural backbone
(registry + guards + CR046 numbers) *and* defines the review pass; §7 is the decision on how much
expert review to resource, because that is the true cost of "100%."

## 4. The reputable-source registry (allowlist)

A maintained registry `content/_authoring/source_registry.md`; every `sources` entry must resolve
to a tier below, or the corpus test fails (degrade loudly):

- **Tier 1 — Primary/official:** company filings (10-K/10-Q/8-K), exchange & regulator publications
  (SEC, SC Malaysia, Bursa, Tadawul/CMA), central-bank & statistical data (Federal Reserve, BEA,
  BLS, NBER, Bank Negara, SAMA, IMF, World Bank).
- **Tier 2 — Standard-setters & bodies:** CFA Institute, CMT Association, GARP/FRM, AAOIFI, CBOE,
  CME, index rulebooks (S&P, MSCI, FTSE, Dow Jones Islamic).
- **Tier 3 — Canonical texts (CR054 canon):** Graham, Damodaran, Bodie–Kane–Marcus, Hull, Bogle,
  Kahneman, Taleb, Marks, Ellis, Shiller.
- **Excluded:** blogs, forums, social posts, unattributed web pages, and **AI-generated text as a
  source of fact.**

## 5. Scope — the whole BOK, not just lessons

The same standard applies to every corpus that makes a factual claim: **lessons** (bodies +
frontmatter `sources`), **quiz questions/explanations** (question-level provenance tied to the
lesson's verified sources), **glossary** definitions, **daily challenges**, **AI-coach Q&A**. A
wrong "fact" in a daily challenge is as damaging as one in a lesson.

## 6. Enforcement + process

**Structural guards (land with the content — house rule; this is the *control*, not a prompt):**
extend `backend/tests/unit/test_lesson_corpus_integrity.py` —
- every lesson `sources` non-empty and every entry resolves to `source_registry.md`;
- a `verified: {by, date}` stamp present once a lesson passes review; unverified lessons are
  **quarantined** (not served to users / flagged in the UI as "under review"), never silently
  shipped;
- numeric claims routed through CR046 (`trading_math`) — the numeric half of provenance already has
  its mechanism.

**Process (waves):**
1. **Freeze the standard** — registry + `sources`/`verified` schema + authoring-prompt v2 so every
   *new* lesson is born sourced (the newest batch already does the first half — make it mandatory
   and guarded).
2. **Verify the sourced BOK waves first** (293–334) — they have sources; confirm the claims match.
3. **Backfill + verify the 288 legacy lessons** — the big lift; source then verify.
4. **Question-level provenance** — every quiz explanation ties to its lesson's verified sources.
5. **Glossary / daily / coach** — same pass.

## 7. Decision for Saiful — the verification standard (the cost of 100%)

Structural provenance is not the hard part; **who confirms accuracy** is. Options:

- **A. Expert/human sign-off** on the factual core (Saiful or a hired SME per domain). Highest
  confidence, real cost/time. The only path to a genuine "we reviewed this."
- **B. Structured multi-model cross-check** — an independent verifier model (different from the
  author) checks each claim against the cited source and flags mismatches. Cheap, scalable, but
  **not** a 100% guarantee (CR038/DEF059) — best as a *first filter* that narrows what a human
  reviews.
- **C. Hybrid (recommended):** B as an automated first pass over all content, then A on everything
  B flags + a sampled audit of what it passes + all Tier-1 regulatory/Islamic claims. Numbers via
  CR046 throughout.

This choice sets the resourcing; it does not change the schema or guards, which are built regardless.

## 8. Constraints & registers

- **Structural, not prompt-based** (CR038): the guard — not an instruction to the author — is what
  keeps unsourced/unverified content off users' screens.
- **Degrade loudly** (CR040): unsourced/unverified ⇒ build fails or content quarantined, never a
  silent confident-but-unchecked claim (that is the DEF059 failure mode, applied to content).
- Honours frozen CR044 codes, fixed-5 gateways, DEF064/065, AMI naming.
- **Elevates CR054 §4.3/P1** from Wave 3 to a gate; **consumes CR046** (numeric provenance);
  **CR058** Islamic content sources to AAOIFI/SAC/index rulebooks under this registry; applies
  across the CR059 groups.
- Row added to `docs/forward_planning/cr_list.md` (CR060, `planned`). Commit tag `(AT:R63 CR060)`.

---

### One-paragraph brief

We have **partial provenance and zero verification**: ~288/312 lessons are unsourced, the newest
BOK batches (293–334) cite reputable primary sources but nobody has checked the claims against them,
and **no quiz question carries any provenance**. This CR makes sourcing + independent verification a
**hard shipping gate** — a reputable-source registry, `sources` + `verified` schema, corpus-test
guards that quarantine unsourced/unverified content, CR046 for every number, and a verification pass
(recommended: automated cross-check → human/SME sign-off on flags + Tier-1 claims). It is the only
route to the "100% accurate, fully sourced" bar; the open decision is how much expert review to
resource (§7).
