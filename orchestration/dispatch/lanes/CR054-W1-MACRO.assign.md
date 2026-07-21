<!-- dispatch assign lane — Architect-owned. CR052. -->
# CR054-W1-MACRO — assign

KIND: content
INSTANCE: noncoder.edu
ACCEPTANCE: docs/forward_planning/CR054_investment_body_of_knowledge/wave1_macro.md
DEPENDS-ON: CR054-W0a (track wired ✓), CR054-W0c (author-prompt v2 ✓), CR054-GUARD (guards content-addition-safe ✓)
HOT-FILES: global lesson-id sequence — reserved block ids 323-334 / MACRO 1-12 (disjoint from every other lane)

**What:** Author all 12 Level-10 Economics & Macro lessons (M16 growth/inflation/cycle · M17 central banks,
policy & currency), codes MACRO 1-12, ids 323-334, per `wave1_macro.md`. Third Wave-1 content track. One
commit (contiguous codes). Content-review gate, not the Auditor. **Self-test = corpus-integrity test ONLY**
(NOT the full suite — the 210s suite gets auto-backgrounded past the 120s Bash timeout and kills a one-shot
worker, P7). Macro figures are **pinned historical values with a date**, never invented current data (P2).

ASSIGNED: noncoder.edu round 1
DISPATCH: ACCEPTED (round 1)

<!-- Accepted 2026-07-22 by architect: content review PASS. 12 lessons committed b4a30e5 (corpus
300→312, verified green by MY corpus-test exit code 22-pass, NOT the worker's word). Scope clean:
commit = exactly 12 MACRO lessons (323-334) + return lane, no backend/uv.lock/settings/Archive.zip.
Compliance sweep: MACRO 1-12 contiguous, all L10, M16 (323-328) / M17 (329-334) exact, 2 capstones
(328/334) last-in-module + capstone/synthesis tagged, CR042 answer variety, zero "the AI".
**P2 verified:** 324 Fisher (1.10/1.05−1 = 4.762%) exact + honestly labelled illustrative; all macro
figures pinned+dated+sourced (CPI 9.1% Jun-2022 BLS; FOMC +25bp 26-Jul-2023 to 5.25-5.50%; balance
sheet $8.9T peak; ~$1.7T FY23 deficit; BNM OPR ~3.00%). 334 read full — genuine synthesis (one dated
Fed decision through all 5 M17 channels), Ethics-grade. One worker: c7a0966c (sonnet/standard/ultra,
$15 cap — deliberate tier, no death). MINOR (non-blocking, folded to authoring prompt): 324/332 use
spelled-out positional option refs ("the first/last option") in explanations — passes DEF065 guard
(catches only "option \d"), stable given fixed option order; prefer content-based refs going forward.
noncoder.edu freed. -->

