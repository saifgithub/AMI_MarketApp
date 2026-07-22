<!-- dispatch assign lane — Architect-owned. CR052. -->
# DEF084-CONTENT — assign

KIND: content
INSTANCE: noncoder.edu
ACCEPTANCE: docs/defect/DEF084_halal_flag_is_an_allowlist_not_a_screen/DEF084_halal_flag_is_an_allowlist_not_a_screen.md — Option 2 (Saiful decided 2026-07-22)
DEPENDS-ON: DEF084-BE (**hard** — the lesson must document the behaviour that ships, not the one that is about to change; the spec says do not correct `355` first)
HOT-FILES: none (content only)

**Scope is narrow and the boundary is the point. Two lessons, product-behaviour claims only:**

- **`355_how_amis_halal_flag_maps_to_real_screening`** — currently false in prose *and* in two
  graded quizzes. It says the flag *"runs that exact discipline against the two-stage screen"* and
  that ratios are *"each computed the same way `sharia_screen` computes them"*; quiz 2's marked
  -correct answer asserts *"the flag checks the full two-stage screen, not a sector-keyword
  shortcut"*. None of that is true — enforcement is a 7-ticker literal set. Rewrite to describe
  what DEF084-BE actually ships: a curated demonstration universe, explicitly not a Sharia screen.
  The title itself is a claim — change it too. Rework both quizzes so nothing graded depends on the
  removed claim.
- **`351_purification_tazkiyah`** — its worked example says *"run this through AMI's
  `purification_amount` function"*, which is reachable from no user-facing path. Remove the
  product-reachability claim; the *concept* of purification stays.

**HARD BOUNDARY — do not touch the religious substance.** The other SHARIA citation findings
(AAOIFI SS 21 being 30/30/5 rather than the 33% in `349`/`356`; `350`'s 12-month window; `351`'s
formula being DJIM/S&P method taught as AAOIFI's; `352` inverting AAOIFI's Feb-2008 sukuk
statement; `348`'s non-existent "Bursa Malaysia SAC"; and the two ESCALATE items `353` and `347`)
are **religious rulings and standards interpretation — Saiful / a qualified SME only, per CR060's
standing rule.** They are NOT in this lane. If you find yourself editing a ratio threshold or a
standard's name, stop and raise `STATUS: NEEDS-INFO`.

You are fixing exactly one class here: **claims about what AMI's software does.**

**Live exposure context:** DEF082 shipped `+50` to both stores, so all 10 SHARIA lessons are now
reachable in-app — the accidental mitigation that kept this false teaching off-screen is gone.

**Corpus invariants:** CR042 answer-position uniformity, CR044 frozen lesson codes, no
answer/explanation index leaks, CR060 §18 **provenance is INTERNAL-ONLY** (never render a "Where
this comes from" line), CR058 §7 "methodology not a Sharia ruling", AMI by name.
Do not touch `content/lessons/357–364` (EVAL, in flight elsewhere).

**Gate:** `READY_FOR_REVIEW` → Architect/Saiful content review. No Auditor.

ASSIGNED: noncoder.edu round 1
DISPATCH: OPEN
