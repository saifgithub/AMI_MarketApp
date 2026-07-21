<!-- dispatch return lane — noncoder.edu track, CR058-CONTENT round 2 -->

# CR058-CONTENT — return (noncoder.edu round 2, frame-pass)

KIND: content  
INSTANCE: noncoder.edu  
ROUND: 2 (frame-only pass)

## Summary

Round 2 frame audit complete. All 10 Sharia lessons (347–356) now carry BOTH load-bearing frames:
- **(a) Simulation disclaimer** — "AMI's training output" / "practice artifact" / "methodology teaching" language
- **(b) Sharia-specific frame** — "methodology, not a Sharia ruling" / "consult a qualified scholar" language

No changes to P2 numbers, codes, ids, quizzes, or frontmatter. All nine edited lessons now pass both frame requirements; three lessons (347, 350, 356) already had frame (b) and received frame (a) only.

**Corpus test:** passed (334 lessons, exit 0, ~2.3s).

## Lessons edited (9 of 10)

| Lesson | id | Code | Frame (a) | Frame (b) | Action |
|---|---|---|---|---|---|
| 347 | 347_the_four_prohibitions | SHARIA 1 | ✓ added | ✓ existing | Added frame (a) to Takeaway |
| 348 | 348_the_business_activity_screen | SHARIA 2 | ✓ added | ✓ added | Added both frames to Try it & Takeaway |
| 349 | 349_the_three_financial_ratio_screens | SHARIA 3 | ✓ added | ✓ added | Added both frames to Try it & Takeaway |
| 350 | 350_standards_differ_why_the_same_stock_flips | SHARIA 4 | ✓ added | ✓ existing | Added frame (a) to Try it |
| 351 | 351_purification_tazkiyah | SHARIA 5 | ✓ existing | ✓ added | Added frame (b) to Takeaway |
| 352 | 352_sukuk_vs_conventional_bonds | SHARIA 6 | ✓ added | ✓ added | Added both frames to Try it & Takeaway |
| 353 | 353_islamic_contracts_and_instruments | SHARIA 7 | ✓ added | ✓ added | Added both frames to Try it & Takeaway |
| 354 | 354_islamic_indices_etfs_and_funds | SHARIA 8 | ✓ added | ✓ added | Added both frames to Try it & Takeaway |
| 355 | 355_how_amis_halal_flag_maps_to_real_screening | SHARIA 9 | ✓ added | ✓ added | Added both frames to Try it & Takeaway |
| 356 | 356_capstone_screen_a_company_end_to_end | SHARIA 10 | ✓ added | ✓ existing | Added frame (a) to Try it & Takeaway |

## Frame placement strategy

Frames added naturally to each lesson's voice:
- Frame (a) — simulation/training artifact language — woven into "Try it" sections (setting context for practice) or Takeaway (positioning result as methodology training)
- Frame (b) — Sharia-ruling disclaimer — positioned alongside frame (a) or separately in Try it, emphasizing "consult a qualified scholar"
- Wording varied by lesson topic to avoid boilerplate repetition while keeping both meanings unmistakable

## Verification

- **P2 audit:** no changes to computed numbers, thresholds, or quiz answers
- **Code/ID audit:** no changes to lesson codes (SHARIA 1-10) or lesson ids (347-356)
- **Quiz audit:** no changes to quiz questions, options, or answer indices
- **Frontmatter audit:** no changes to prerequisites, sources, tags, or metadata
- **Corpus test:** `cd backend && uv run pytest tests/unit/test_lesson_corpus_integrity.py -q` → **22 passed** (334 lessons intact, exit 0)

---

STATUS: READY_FOR_REVIEW (round 2)

Edited lessons: 347, 348, 349, 350, 351, 352, 353, 354, 355, 356
