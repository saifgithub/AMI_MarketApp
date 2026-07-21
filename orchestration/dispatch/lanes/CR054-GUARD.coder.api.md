STATUS: READY_FOR_AUDIT (round 1)

<!-- coder-owned lane file for CR054-GUARD. State machine driven by the STATUS line above (byte-exact). See orchestration/dispatch/loop_prompts/CODER.md. -->

# CR054-GUARD — coder.api lane

**Item:** make the corpus guards content-addition-safe so Wave 1–3 content lanes land without touching `backend/`: lesson-count exact pin → floor (>= 270), retire the Wave-0 empty-track pin, add the capstone guard (tag `capstone` ⇒ last-in-module + synthesis final quiz). All in `backend/tests/unit/test_lesson_corpus_integrity.py`.

**Spec:** [`CR054-GUARD.assign.md`](CR054-GUARD.assign.md) + CR054 §5.1 + [`wave1_ethics.md`](../../../docs/forward_planning/CR054_investment_body_of_knowledge/wave1_ethics.md) capstone rule + A1 in [`CR054-W1-ETHIC.noncoder.edu.md`](CR054-W1-ETHIC.noncoder.edu.md).

**Auditor:** auditor.core.
