<!-- dispatch assign lane — Architect-owned. CR052. -->
# CR054-W1-QUANT — assign

KIND: content
INSTANCE: noncoder.edu
GATE: none    <!-- backfilled CR070 — maintainer lane: content review, not an audit gate (by design) -->
ACCEPTANCE: docs/forward_planning/CR054_investment_body_of_knowledge/wave1_quant.md
DEPENDS-ON: CR054-W0a (track wired ✓), CR054-W0c (author-prompt v2 ✓), CR054-GUARD (guards content-addition-safe ✓)
HOT-FILES: global lesson-id sequence — reserved block ids 335-346 / QUANT 1-12 (disjoint from every other lane)

**What:** Author all 12 Level-12 Quantitative Methods lessons (M20 probability & evidence · M21 testing a
claim), codes QUANT 1-12, ids 335-346, per `wave1_quant.md`. Fourth Wave-1 content track. One commit
(contiguous codes). Content-review gate, not the Auditor. **Self-test = corpus-integrity test ONLY** (NOT the
full suite — P7 one-shot-death trap). **Every worked number arithmetically exact and hand-checkable** (EV,
Bayes, significance) — a wrong number in a math lesson is the worst failure mode; content review recomputes a
sample (P2).

ASSIGNED: noncoder.edu round 1
DISPATCH: ACCEPTED (round 1)

<!-- Accepted 2026-07-22 by architect: content review PASS. 12 lessons committed 680a8f3 (corpus
312→324, verified green by MY corpus-test exit code 22-pass, NOT the worker's word). Scope clean:
commit = exactly 12 QUANT lessons (335-346) + return lane, no backend/uv.lock/settings/Archive.zip.
Compliance: QUANT 1-12 contiguous, all L12, M20 (335-340) / M21 (341-346) exact, 2 capstones
(340/346) last-in-module + capstone/synthesis tagged, CR042 answer variety, zero "the AI".
**P2 verified by hand (the hard part of this track):** 335 EV (0.7·100 + 0.3·-400 = -$50) exact;
339 SE √(0.7·0.3/20)=√0.0105≈10.2pp exact; 340 Bayes posterior 0.08/0.26 = 30.77%≈30.8% exact, EV
chain -$384.6≈-$385 exact, 2·SE≈20.5 vs 20-pt edge ties to 339 correctly. 340 read full — genuine
base-rate→sample-size→Bayes→EV synthesis, Ethics-grade. One worker: 1e52dde3 (sonnet/standard/ultra,
$15 cap, no death). **FINDING (non-blocking, deferred to Wave-1 wrap):** worker used POSITIONAL option
refs ("the first/second option") in 335/337/338/339 explanations DESPITE an explicit prompt instruction
against it → confirms CLAUDE.md "prompt instructions are not controls." Passes DEF065 guard (catches only
"option \d") and is stable (fixed corpus-wide option order), so accepted. Structural fix queued: extend
the corpus guard to forbid positional refs, then a cheap economy sweep fixes the ~6 flagged explanations
(Macro 324/332 + these) — bundled with the LESSON_COUNT_FLOOR bump micro-lane. noncoder.edu freed.
Wave-1 LESSON tracks COMPLETE (Ethics+Asset+Macro+Quant = 54 lessons, corpus 270→324). -->

