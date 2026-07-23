<!-- dispatch assign lane — Architect-owned. CR052. -->
# CR054-W1-ETHIC — assign

KIND: content
INSTANCE: noncoder.edu
GATE: none    <!-- backfilled CR070 — maintainer lane: content review, not an audit gate (by design) -->
ACCEPTANCE: docs/forward_planning/CR054_investment_body_of_knowledge/wave1_ethics.md
DEPENDS-ON: CR054-W0a (tracks ✓), CR054-W0c (author-prompt v2 ✓)
HOT-FILES: global lesson-id sequence — reserved block ids 293-302 / ETHIC 1-10 (disjoint from other lanes)

**What:** Author all 10 Level-13 Ethics & Market Integrity lessons (M22 Playing it straight + M23 Duty
& conflicts), ETHIC 1-10, ids 293-302. First Wave-1 lane — Ethics leads (CFA-first, zero files today,
no math dependency). Content-review gate, not the Auditor. Self-check with the corpus-integrity test.

**Round 2 (2026-07-22):** CR054-GUARD is integrated (guards now content-addition-safe) → the HOLD
lifts. Commit your 10 already-authored lessons (293-302, untracked in the working tree), run the
corpus-integrity suite green, go READY_FOR_REVIEW. Architect content pre-review is already PASS
(see the lane file) — this is the commit+signal step, not a re-author. ALSO fold in auditor MINOR-2:
add the `synthesis`-tag requirement to the "Module capstone template (v2)" in
`content/_authoring/lesson_authoring_prompt.md` (a capstone's final quiz is a synthesis question,
declared via the `synthesis` tag — the corpus guard now enforces it). Small, same commit is fine.

ASSIGNED: noncoder.edu round 2
DISPATCH: ACCEPTED (round 2)

<!-- Accepted 2026-07-22 by architect: content review PASS (pre-reviewed on disk; commit 32eac8a
verified = exactly the 10 pre-reviewed lessons + the 2-line synthesis-tag template edit, zero
forbidden paths). Corpus 270→280. First Wave-1 content track shipped end-to-end, AND the first
launch through the CR057 helper — ran at economy tier (haiku/low, $2 cap) instead of Fable-5/xhigh:
the cost fix proven live. noncoder.edu slot freed. -->

