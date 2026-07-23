<!-- dispatch assign lane — Architect-owned. CR052. -->
# CR054-GUARD — assign

KIND: code
INSTANCE: coder.api
GATE: independent    <!-- backfilled CR070 — audited by the track-U auditor, verdict on file -->
ACCEPTANCE: this file (small, self-contained) + CR054 §5.1 + wave1_ethics.md capstone rule
DEPENDS-ON: none (must be green STANDALONE at the current 270-lesson corpus, before any Wave-1 content lands)
HOT-FILES: backend/tests/unit/test_lesson_corpus_integrity.py (coder.api owns tests)

**Why:** the W0a guards are Wave-0-rigid and will block EVERY Wave-1+ content lane. Generalize them once
so content additions are green without any content lane touching `backend/`. Root unblock for all of Wave 1–3.

**What (all in test_lesson_corpus_integrity.py):**
1. **Lesson-count → FLOOR.** Replace the exact `EXPECTED_LESSON_COUNT == 270` assertion (in
   `test_every_lesson_parses` / wherever it lives) with a floor `>= 270` (keep the "don't silently lose
   lessons" intent; drop the brittle exact upper pin). Every lesson must still parse + validate.
2. **Retire `test_cr054_new_tracks_are_empty_at_wave_0`.** Its Wave-0 job (no track populated before its
   wave) is done; tracks now fill deliberately. Delete it (or convert to a comment noting why).
   The per-track CR044 contiguity guard stays and covers correctness going forward.
3. **Add a capstone guard (new):** any lesson whose `tags` contains "capstone" must be the LAST lesson
   in its module and its final quiz must be a synthesis question. (wave1_ethics.md; CR054 §5.1.)

**Constraint:** MUST be green standalone at HEAD (270 lessons) — do not assume any Wave-1 content exists.
`cd backend && uv run pytest tests/unit/test_lesson_corpus_integrity.py -q` green; full suite green.

ASSIGNED: coder.api round 1
DISPATCH: ACCEPTED (round 1)

<!-- Integrated 2026-07-22 by architect: auditor.core VERDICT COMPLETE (da3c3f8) on src fd64a29 —
927 reproduced at both corpus states, 5 blind probes bit, 071 exemption load-bearing, floor-vs-pin
judged acceptable, new permanent pin test_cr054_guard_capstone_floor_pin.py added. Unblocks ALL
Wave 1-3 content lanes. 2 MINOR advisories: (1) floor-bump-per-wave is a backend edit → wave-
integration checklist item (I bump LESSON_COUNT_FLOOR via a coder.api micro-step at each wave wrap;
CR044 contiguity covers the lag meanwhile); (2) synthesis-tag contract → add to authoring capstone
template (folded into W1-ETHIC round 2). -->

