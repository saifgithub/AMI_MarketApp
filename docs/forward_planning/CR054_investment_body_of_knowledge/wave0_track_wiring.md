# CR054 · Wave 0 · Lane W0a — Track wiring (the enum decision)

**Parent:** [CR054_investment_body_of_knowledge.md](CR054_investment_body_of_knowledge.md) §4.2, §5 (Wave 0), §5.1 (guards).
**Owner instance:** `coder.api` · **Auditor:** `auditor.core` · **Filed by:** Architect (dogfood of CR052).

This is the **root enabling lane** of the BOK expansion: it wires the new curriculum tracks so
every downstream Wave-1 content lane can assign lessons a frozen CR044 code in a real track. Pure
backend + guard work. **No lessons are authored here** (that is Wave 1); this lane only makes the
tracks *exist and enforceable*.

---

## Architect decision (resolves CR054 §4.2)

**Option A — add 4 new tracks.** Forcing the new disciplines into the 7 existing tracks (Option B)
is dishonest — "what is a bond" is not `edge_process`, and the track facet stops meaning anything.
Deepenings still land in existing tracks; only the orthogonal new domains get new tracks.

| New track (enum value) | CR044 prefix | Houses (Wave 1+) | Agent-callout mapping |
|---|---|---|---|
| `asset_classes` | **ASST** | M13–M15 (fixed income, funds, options) | fundamentals_analyst / market_analyst |
| `economics_macro` | **MACRO** | M16–M17 (macro machine, policy) | news_analyst |
| `quant_methods` | **QUANT** | M20–M21 (probability, testing a claim) | research_manager |
| `ethics_integrity` | **ETHIC** | M22–M23 (integrity, duty & conflicts) | portfolio_manager / concierge |

Prefixes obey the CR044 rules: spoken aloud, unambiguous, frozen, contiguous 1..N **within a
track**. All four tracks start empty (0 lessons), so contiguity holds trivially until Wave 1 fills
them. Islamic-finance (M25) / ESG (M26) / portfolio-theory (Level 11) tracks are **out of scope
here** — they deepen existing tracks or wait for a Wave-2 decision.

---

## Scope (must-have — the acceptance)

1. **Lesson `track` enum** — add the 4 values in `backend/app/schemas/lessons.py`.
2. **Display-name + prefix maps** — extend the maps in `backend/app/services/lessons_service.py`
   (~L69–90) so each new track has a human display name and its CR044 prefix (ASST/MACRO/QUANT/ETHIC).
3. **Corpus-integrity guard** — extend `backend/tests/unit/test_lesson_corpus_integrity.py`:
   the 4 new prefixes are present in the prefix map, unique across all prefixes, each maps 1:1 to
   its track, and contiguity/prefix-matches-track holds for any lesson that *later* carries the new
   track (today: zero, so the test asserts the maps are wired and no prefix collides). CR044
   invariants (existing codes frozen, no renumbering) stay green.
4. **Green suite** — `pytest backend/tests/unit/ -q` passes (was 866 green).

## In scope if trivial (else defer to a Wave-1 glossary lane, note it)

5. Glossary category **enum** additions (`asset_classes`, `economics`, `ethics`, `quantitative`,
   `islamic_finance`) where the category enum lives — **enum only, no terms** (terms are Wave-1
   corpus data owned by `noncoder.edu`). If the enum is tangled with data validation that would
   fail on empty categories, DEFER and say so in the hand-off.

## Explicitly OUT of scope (other lanes)

- Authoring any lesson / glossary term / Q&A / daily challenge → **Wave 1** (`noncoder.edu`).
- Mobile `_trackShortLabel` (`track_lessons_screen.dart:20-28`) → **lane W0b** (`coder.mobile`,
  DEPENDS-ON this lane for the canonical track names + short labels).
- Author-prompt v2 → **lane W0c** (`noncoder.edu`). CR046 bond/option/portfolio math → **lane W0d**
  (`coder.math`).

## Constraints (non-negotiable — CR054 §6)

- **New tracks are additive.** Do not touch, reorder, or renumber any existing track or CR044 code
  → DEF068/DEF071 safe.
- **Degrade loudly (CR040).** A missing/duplicate prefix must fail the corpus-integrity test, never
  a user's screen. If any new config is env-gated, forward it in compose parity (unlikely here — this
  is static enum/map work).
- **AMI by name** in any user-facing display string; **LLM** only in code.

## Definition of Done (fill the table in the audit lane)

- [ ] 4 track enum values added; 4 prefixes wired in the display/prefix maps.
- [ ] Integrity test extended + green; full unit suite green (state the count).
- [ ] No existing CR044 code or track altered (grep-proof in the hand-off).
- [ ] Glossary category enum handled or explicitly deferred with reason.
