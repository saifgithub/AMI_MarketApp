# CR062 — Author the `decision_evaluation` (EVAL) track: 8 lessons completing CR054 M24

**Status:** in progress
**Round:** AT:R64
**Owner:** Claude (CR060 content-quality lane)
**Trigger:** Saiful, 2026-07-22 — *"we need the eval urgently."*

---

## 1. Context — why this exists

`decision_evaluation` (EVAL, "Evaluating Analysis") is the **only registered track in the corpus
with zero lessons**. It is fully wired — enum `backend/app/schemas/lessons.py:63`, display name and
`EVAL` prefix in `lessons_service.py:84,115`, present in the corpus-test 13-facet taxonomy — but no
content was ever authored. The code comment records why: both net-new tracks were wired at 0
lessons each; `islamic_finance` content landed via **CR058**, `decision_evaluation` was deferred to
"a later content lane" that never ran. CR054 **Wave 2** was supposed to carry M24 alongside M25;
only M25 shipped.

Surfaced when Saiful asked whether the EVAL group has any lessons during the CR060 sweep. It is
also already noted in **DEF082** as `decision_evaluation (0 lessons, unauthored)`.

**Source spec (already written, not invented here):**

- **CR054 §Level 14 — M24 "Evaluating analyst & AI output"**, *the Discerning CEO*, **8 lessons**:
  calibration & confidence · red-team/steelman a thesis · decision journaling & post-mortems ·
  process vs outcome · when to override the Room · automation bias & cognitive offloading ·
  aggregating disagreeing analysts.
- **CR059 §2** locks the wiring: prefix **`EVAL`** (frozen), display name "Evaluating Analysis"
  (adjustable), default `agent_callouts` **`research_manager` / `concierge`**, and the instruction
  to **downplay the "Discerning CEO" framing** — it is a normal facet, not positioned as the moat.

## 2. The overlap problem, and why EVAL gets net-new lessons

CR054 originally folded this material into `edge_process`, and **most of M24 is therefore already
written**:

| existing lesson | code | M24 topic it already covers |
|---|---|---|
| `075_the_risk_of_overreliance` | EDGE 25 | automation bias / cognitive offloading |
| `076_human_oversight_is_the_product` | EDGE 26 | human-in-the-loop framing |
| `077_decision_support_vs_prediction` | EDGE 27 | what a confidence number is not |
| `274_the_safety_floors_audit_trail` | EDGE 91 | auditing the Room's reasoning |
| `275_when_agents_disagree` | EDGE 92 | aggregating disagreeing analysts |
| `276_spotting_hallucinated_numbers` | EDGE 93 | verifying agent output |
| `277_pass_is_not_buy` | EDGE 94 | reading a verdict correctly |
| `279_you_are_the_ceo` | EDGE 96 | when to override the Room |

**Re-homing these into EVAL is rejected.** CR044 froze group-scoped codes and
`test_lesson_corpus_integrity.py` asserts each track's numeric parts form a **contiguous 1..N**.
Moving 8 lessons out of `edge_process` would either hole EDGE's numbering (guard fails) or force
reissuing codes across all 98 EDGE lessons — violating CR044's "codes are never reissued". The
constraint decides this, not preference.

So EVAL is authored as **net-new lessons that cross-link** the EDGE ones via `<Lesson id="…"/>`,
covering the genuinely-unwritten half of M24:

**process vs outcome · calibration · red-team/steelman · decision journaling · pre-mortem ·
post-mortem · self-scoring over time · an end-to-end capstone.**

Nothing above duplicates an existing lesson; each instead names its EDGE sibling as prerequisite or
cross-reference.

## 3. The 8 lessons

Lesson ids continue the corpus (`356` is the current maximum) → **357–364**; codes **EVAL 1–8**,
assigned once, never reissued.

| id | code | title | core idea | prereq / cross-link |
|---|---|---|---|---|
| 357 | EVAL 1 | Process vs outcome | a good decision can lose; judge the decision at the moment it was made | EDGE 96 |
| 358 | EVAL 2 | What a confidence number actually means | calibration; a number is a claim you can be scored on | EDGE 27 |
| 359 | EVAL 3 | Keeping a decision journal | write thesis + invalidation **before** the outcome exists | EVAL 1 |
| 360 | EVAL 4 | Steelmanning the other side | red-team your own thesis; strongest opposing case, not the weakest | EDGE 92 |
| 361 | EVAL 5 | The pre-mortem | assume it already failed, explain why — surfaces risk hindsight would hide | EVAL 4 |
| 362 | EVAL 6 | The post-mortem that isn't a blame hunt | separate process error from variance | EVAL 1, EVAL 3 |
| 363 | EVAL 7 | Scoring yourself over time | base rates + your own hit rate; small samples lie | EVAL 2, EVAL 3 |
| 364 | EVAL 8 | Capstone: evaluate one Room verdict end to end | applies all seven to a full verdict | all |

## 4. Authoring constraints — this track is authored under the CR060 rule

CR060 has measured **86% of the existing corpus carrying a genuine defect**, overwhelmingly
**confabulated worked-example data**: real tickers with invented prices, dates on market holidays,
close-vs-intraday inversions. Authoring EVAL the old way would manufacture the exact defect the
lane is cataloguing. So, binding for every lesson here:

1. **No fake-real data.** A worked example is **either** sourced from a real, citable figure **or**
   openly hypothetical ("a position you entered at $50…"). **Never a real ticker with invented
   prices.** That hybrid is what produced ~165 findings. `351_purification_tazkiyah` is the model —
   *"Take a hypothetical balance sheet shaped like a large, screen-passing tech company."*
2. **Quiz answers must be independently correct**, with all arithmetic computed, not asserted.
3. **Distractors are named by content, never by position** — no "the first one", "the last —".
   This is DEF065 / DEF079 / **DEF083** (filed today: 11 explanations still point at the wrong
   option because a shuffle reordered options without rewriting ordinal prose).
4. **Every lesson passes the CR060 dual-pass** (web-corroborated fact-check + adversarial refute)
   **before commit** — the 18-of-19 refute kill rate on Wave 2 is why one pass is not enough.
5. Regulatory frame intact: simulation-only, AMI never gives advice; "AMI" by name in user-facing
   copy, never "the AI".

## 5. Sources

Most of this material is genuine decision-science canon, not market data — which is why it can be
sourced properly rather than made illustrative.

**Already on the Tier-3 allowlist** (`content/_authoring/source_registry.md`): **Kahneman**
(judgement, bias, noise), **Taleb** (*Fooled by Randomness* — outcome vs process), **Marks**
(*The Most Important Thing* — luck, second-level thinking).

**Proposed additions to Tier 3** (CR060 owns the registry; each is standard, citable, and
domain-canonical):

| source | for |
|---|---|
| Tetlock & Gardner — *Superforecasting* | calibration, Brier scoring (EVAL 2, 7) |
| Annie Duke — *Thinking in Bets* | "resulting"; process vs outcome (EVAL 1, 6) |
| Gary Klein — "Performing a Project Premortem", *HBR* (2007) | the pre-mortem method (EVAL 5) |
| Mauboussin — *The Success Equation* | luck vs skill, small-sample inference (EVAL 1, 7) |
| Parasuraman & Riley (1997), "Humans and Automation" | automation bias (cross-link EDGE 25) |

## 6. Guards (same commit as the content — house rule)

- `LESSON_COUNT_FLOOR` **334 → 342** in `backend/tests/unit/test_lesson_corpus_integrity.py`.
- Existing CR044 invariants automatically extend to `EVAL`: prefix present, unique, matches track,
  contiguous `1..N`. Confirm they bite on the new track rather than assuming.
- Prerequisite DAG stays acyclic; every `<Lesson id="…"/>` reference resolves.

## 7. Known dependency — EVAL will be invisible until DEF082 ships

**DEF082** (mobile lane, open): the app builds its group cluster from a hardcoded 7-entry map and
iterates *that*, using the API only as a filter — so any backend-served track without a hardcoded
hex position is silently dropped. **64 lessons across 6 tracks are currently dark.** EVAL will be
the 7th such track the moment it lands.

So authoring EVAL is necessary but **not sufficient** for Saiful to see it — DEF082's fix must ship
too, and its layout decision (7-hex honeycomb vs 12–13 facets) needs Saiful's direction. Flagged
rather than silently assumed. This is also why EVAL landing empty-but-registered was invisible for
so long.

## 8. Acceptance

1. 8 lesson files `357–364`, codes EVAL 1–8, track `decision_evaluation`, each following the 7-part
   template in `content/_authoring/lesson_authoring_prompt.md`.
2. `pytest backend/tests/unit/ -q` green, including the raised floor and CR044 invariants on EVAL.
3. Every lesson carries `sources:` and a CR060 `verified:` stamp — **the first track in the corpus
   authored verified-from-birth**, rather than swept years later.
4. Zero positional distractor references (DEF083 pattern) — checked by the deterministic scan.
5. `GET /v1/lessons` returns `decision_evaluation` with 8 lessons after promotion.

---

## 9. Verification outcome — NOT VERIFIED after two passes (2026-07-22)

The 8 lessons are committed (`ed7926b`) but **must not be stamped `verified:`**. Two full gate
passes have run; the content is not clean.

| pass | result |
|---|---|
| **Pass 1** (`wf_2df6fa9b-bfe`) | 1 VERIFIED, 7 rejected. 6 confirmed defects hand-fixed; 1 triaged as a false positive (wrongly — see below). |
| **Pass 2** (`wf_81d07121-d8c`, fresh run) | **1 VERIFIED (`359`), 5 REFUTED, 2 STILL_FINDING.** |

Pass 2 was a **new run, not a resume** — resuming would have replayed the unchanged verify prompts
from cache and returned verdicts on the pre-fix content.

### Outstanding defects

| lesson | defect |
|---|---|
| `357` | Quiz 2 explanation: A "sized so a total loss costs 0.3%" — a total loss is $2,000 = **2.0%**; 0.3% is the *stopped-out* loss. Contradicts its own body, and `364` names this exact conflation as a wrong answer. |
| `358` | Brier fix **holds**, but Quiz 2 keys "the 70% was not earned" off n=10 — P(≤5 \| p=.7) = 15%, 1.38 SD from calibrated. Contradicts `362`/`363`'s own small-sample teaching. |
| `360` | The user-facing *"Where this comes from"* line. **CR060 §18 retires it — provenance is internal-only.** My pass-1 triage called this a false positive by reading the older authoring prompt; that was wrong. **Corpus-wide: 33 lessons carry the line.** |
| `361` | "The pre-mortem grants the thesis" misstates Klein's method and is contradicted by its own Example stories 1 and 3, and by prerequisite `360`. |
| `362` | "Try it" demands an outcome label *before* reading the P&L column — impossible, and it inverts the lesson's own process-then-P&L rule. |
| `363` | Stem fix **holds**, but Quiz 2's first distractor still says the 64% figure "covers decisions you didn't take" — residue of the old rejected-subset framing the fix missed. My fix was incomplete. |
| `364` | Quiz 1 keys AMI's 0.68 as a **scorable calibration claim**, contradicting `358`/`077`/`275`: AMI's confidence is *the Room's weighted lean, not a calibrated probability*. No option states the correct reading, and the body repeats the conflation. **This is the load-bearing decision-support-not-prediction framing** — the most serious of the seven. |

### What this establishes

**LLM-authored lesson content did not reach a verifiable standard in two passes**, under the
strictest prompt available and with a hand-fix round between them — even though the *dominant*
corpus defect was successfully eliminated (zero fake-real data, zero positional refs, verified
attributions).

What survived is a different and harder class: **internal contradiction** — against the lesson's
own body, against its prerequisites, and against the product's regulatory framing. A per-lesson
gate is structurally poor at catching this, because each defect is only visible when two documents
are read together.

Two consequences for the wider plan:

1. The remediation CR should not assume "regenerate and verify" converges in one round. Budget for
   iteration, or accept a lower assurance tier and say so.
2. A **cross-lesson consistency check** is a distinct detector, alongside citation-integrity and
   the repo-truth check that found DEF084. All three found things the others could not.

### Next actions (not yet done)

1. Fix the seven above; strip the "Where this comes from" line from all 8.
2. Re-run pass 3 (fresh run, not a resume).
3. Only then stamp `verified:`.
4. Separately: the 33 legacy lessons carrying the retired provenance line — belongs to the
   remediation CR, not here.
