# CR059 — Hexagonal group architecture: lock the 6 new lesson groups

**Status:** planned — **schema / design-decision CR** (architect wires the enum) · **Session:** AT:R63 · **Filed:** 2026-07-21

> Design decision (Saiful): *"Our design is hexagonal. We need to add in total 6 new groups to
> maintain our tessellated hexagonal design."* This CR **locks the count at 6** and defines all
> six, resolving the open track question CR054 §4.2 left to "architect confirms." It supersedes the
> "4 tracks (Option A)" proposal in CR054 §4.2 and makes CR058's **Islamic Finance its own
> first-class group** (group 5); **ESG folds into `ethics_integrity`** so the count stays at six.

A **group** = a lesson `track` (CR044 codes are group-scoped: `TECH 12`, `ASST 1`). The AMI
"Hex-Reinforced Precision" language renders groups as hex facets in the lessons cluster, so the
count is a **design constraint**, not just a taxonomy convenience.

---

## 1. The decision

- **6 new groups**, no more, no fewer. Existing 7 tracks untouched. **Total groups: 7 + 6 = 13.**
- Four are **already wired** in `lessons_service.py::TRACK_TITLES` (architects implemented them
  under "CR054 Wave 0"). Two are **net-new** and must be added to the enum, prefix map, UI labels,
  glossary categories, and corpus test: **`islamic_finance`** and **`decision_evaluation`**.
- **Islamic Finance is its own group** (not bundled). Its sibling values-screen, **ESG /
  sustainable investing**, folds into `ethics_integrity` rather than claiming a 7th facet.

## 2. The 6 new groups

| # | Group (`track`) | Prefix | Display name | Domain / CR054 modules | Default agent_callouts | Status |
|---|---|---|---|---|---|---|
| 1 | `asset_classes` | **ASST** | Asset Classes | fixed income, funds/ETFs, options (M13–M15) | fundamentals_analyst / market_analyst | ✅ **live** — 20 lessons / 50 Q |
| 2 | `economics_macro` | **MACRO** | Economics & Macro | the macro machine (M16–M17) | news_analyst | wired, unwritten |
| 3 | `quant_methods` | **QUANT** | Quantitative Methods | the evaluator's math (M20–M21) | research_manager | wired, unwritten |
| 4 | `ethics_integrity` | **ETHIC** | Ethics & Integrity | market integrity (M22–M23) **+ ESG / sustainable (M26)** | portfolio_manager / concierge | ✅ **live** — 10 lessons / 24 Q |
| 5 | `islamic_finance` | **SHARIA** | Islamic Finance | Sharia-compliant investing (M25 — CR058) | portfolio_manager / fundamentals_analyst | **net-new** (wire enum) |
| 6 | `decision_evaluation` | **EVAL** | The Discerning CEO | evaluating analyst & AI output (M24 — the moat) | research_manager / concierge | **net-new** (wire enum) |

**Why these complete the six:**

- **`islamic_finance` (SHARIA)** — Sharia-compliant investing is a first-class discipline
  (business + ratio screening, sukuk, Islamic contracts, purification) tied directly to the app's
  **`halal` mandate flag** and to the **GCC/Tadawul + Bursa** target markets. It earns its **own
  hex facet** — visible, not folded into fundamentals. This is the group CR058 builds.
  *(Prefix `SHARIA` is the industry-standard term; `HALAL` — matching the mandate flag — or
  `ISLAM` are alternatives if Saiful prefers. Speakable and unambiguous per CR044.)*
- **ESG folds into `ethics_integrity`** — responsible/sustainable-investing screening is the
  natural sibling of market-integrity/governance content, so ESG rides that facet rather than
  spending a scarce group slot. This is the trade that keeps the count at exactly six while giving
  Islamic finance its own.
- **`decision_evaluation` (EVAL)** — the **Discerning-CEO strand** is the product's signature: the
  discipline of evaluating analyst and AI output that no rival curriculum teaches. CR054 folded it
  into `edge_process`; promoting it to its own facet is the strongest identity statement and is
  purely additive.

> **Swap option.** If Saiful would rather the 6th facet be `portfolio_construction`, swap it for
> `decision_evaluation` here (portfolio theory otherwise deepens the existing `risk_portfolio`
> track per CR054 Level 11). Islamic Finance as its own group is fixed either way.

## 3. Assessment sizing — "how many questions per group"

Measured density across the current 300-lesson corpus: **2.15 quiz questions per lesson** (min 2,
max 3); new BOK groups author slightly richer. Per group, questions ≈ *lessons × ~2.2–2.5*:

| Group | Planned lessons | Quiz questions | Basis |
|---|---|---|---|
| `asset_classes` | 20 | **50** | measured (live) |
| `ethics_integrity` (incl. ~4 ESG) | ~14 | **~32** | 10 live (24 Q) + ~4 ESG projected |
| `economics_macro` | ~12 | **~28** | projected @2.3 |
| `quant_methods` | ~12 | **~28** | projected @2.3 |
| `islamic_finance` | ~10 | **~23** | projected @2.3 (CR058 Sharia module) |
| `decision_evaluation` | ~8 | **~18** | projected @2.3 |
| **Total new** | **~76** | **~180** | — |

Each group also seeds **daily challenges** and **AI-coach Q&A** in its domain — separate question
banks (CR054 §4.7 / CR058 §3.2). Lesson quizzes obey DEF064/DEF065 (multiple-choice only, `options`
required, no numeric option references, answer position varied).

## 4. Wiring checklist (architect)

The 4 wired groups need nothing here. For the 2 net-new groups (`islamic_finance`,
`decision_evaluation`):

1. `TRACK_TITLES` + `TRACK_PREFIX` in `backend/app/services/lessons_service.py:66-90` — add both,
   prefixes **SHARIA** / **EVAL** (speakable, unambiguous per CR044).
2. `track` enum in `backend/app/schemas/lessons.py`.
3. Mobile `_trackShortLabel` in `mobile/lib/screens/lessons/track_lessons_screen.dart:20-28`.
4. Glossary category parity: add `islamic_finance` (CR058) + an `esg` category (under
   `ethics_integrity`'s content); an `evaluation` category if EVAL terms warrant.
5. Agent-callout routing per §2 — **gateways stay fixed at 5 per agent**; new-group lessons may be
   callouts but do not change any gateway set.
6. Corpus-integrity test (`test_lesson_corpus_integrity.py`): extend the CR044 invariants (prefix
   present/unique/matches-track/contiguous 1..N) to **SHARIA** and **EVAL**.

## 5. UI / design-system implication

The lessons hex cluster (`mobile/lib/screens/lessons/lessons_screen.dart`) now renders **13 group
facets**. Per the "Hex-Reinforced Precision" system (`/Volumes/Extreme Pro/AMI AI Design System/`),
the 13 facets must tessellate cleanly — the design driver behind fixing the new-group count at 6.
Layout/geometry is Saiful's call; this CR's job is to land the *data model* on exactly six new
groups so the visual system has a stable target. (If a specific *total* is wanted instead of 13 —
e.g. a centered-hex count — that changes the new-group number and Saiful should say so; this CR
delivers the "+6" he specified.)

## 6. Constraints honoured

- **CR044 codes frozen / contiguous.** New groups get new prefixes (SHARIA, EVAL); no existing code
  renumbered → DEF068/DEF071 safe. The 20 live `ASST` + 10 live `ETHIC` codes are untouched.
- **Gateways fixed at 5 per agent** (DEF068); additive callouts only.
- **Degrade loudly (CR040):** a new track/prefix/glossary-category missing from the enum fails the
  corpus test, never a user's screen.
- **AMI by name** in display names + copy; **LLM** only in code.
- **CR058's "methodology, not a Sharia ruling"** frame carries into the `islamic_finance` group
  unchanged.

## 7. Registers & relationships

- Row added to `docs/forward_planning/cr_list.md` (CR059, `planned`).
- **Supersedes** CR054 §4.2's "4 new tracks (Option A)" — count locked at 6; ESG reassigned from
  the mooted `mandate_compliance` track to `ethics_integrity` (annotated in CR054).
- **Finalises** CR058 §4's open track question — Islamic finance is its **own** `islamic_finance`
  group (SHARIA), not a shared `mandate_compliance` track (annotated in CR058).
- **Pairs with** CR053 (deep-linkable references across the 13 facets) and CR046 (group content
  numbers computed, not authored).
- Commit tag for filing: `(AT:R63 CR059)`. Wiring commits: `(AT:R<N> CR059)`.

---

### One-line brief

Lock the lesson-group taxonomy at **13** (7 existing + 6 new: ASST, MACRO, QUANT, ETHIC already
wired, plus net-new **SHARIA** Islamic Finance as its own facet and **EVAL** discerning-CEO; ESG
folds into ETHIC), so the hex facets tessellate; wire the two net-new groups into the
enum/prefix/UI/glossary/test; ~76 new lessons / ~180 new quiz questions across the six, honouring
frozen codes, fixed-5 gateways, and DEF064/065.
