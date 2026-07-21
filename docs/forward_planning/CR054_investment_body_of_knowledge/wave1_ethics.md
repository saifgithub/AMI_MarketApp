# CR054 · Wave 1 · Lane W1-ETHIC — Ethics & Market Integrity (Level 13)

**Parent:** [CR054_investment_body_of_knowledge.md](CR054_investment_body_of_knowledge.md) §4.1 (M22–M23), §5 Wave 1, §5.1 guards · §6 constraints.
**Owner:** `noncoder.edu` (maintainer) · **Gate:** content review (Architect/Saiful), NOT the Auditor.
**Depends on:** W0a (track `ethics_integrity`/`ETHIC` wired ✓) + W0c (author-prompt v2 ✓). No math dependency — this is why Ethics leads Wave 1.

Author **10 lessons** = the whole of **Level 13** (M22 *Playing it straight* + M23 *Duty & conflicts*),
following `content/_authoring/lesson_authoring_prompt.md` (v2). CFA puts Ethics first and we have **zero**
files today — every lesson is pure gain. This is one lane (not two) so the whole `ETHIC` code sequence
lands contiguous in a single commit and the corpus-integrity guard stays green.

## Reserved blocks (use EXACTLY these — do not auto-derive; prevents id/code collision with parallel lanes)

| # | Lesson id | code | Module | Working title (refine per v2) |
|---|---|---|---|---|
| 1 | `293_market_integrity_why` | ETHIC 1 | M22 | Why market integrity matters — the level-set |
| 2 | `294_insider_trading` | ETHIC 2 | M22 | Insider trading: material non-public information |
| 3 | `295_market_manipulation` | ETHIC 3 | M22 | Manipulation: pump-and-dump, spoofing, wash trades (bridges M11) |
| 4 | `296_front_running_fair_dealing` | ETHIC 4 | M22 | Front-running & fair dealing |
| 5 | `297_playing_it_straight_capstone` | ETHIC 5 | M22 | **Capstone** — Playing it straight (synthesis quiz) |
| 6 | `298_fiduciary_duty` | ETHIC 6 | M23 | Fiduciary duty: the client's interest first |
| 7 | `299_conflicts_of_interest` | ETHIC 7 | M23 | Conflicts of interest |
| 8 | `300_suitability_kyc` | ETHIC 8 | M23 | Suitability & know-your-client |
| 9 | `301_disclosure_transparency` | ETHIC 9 | M23 | Disclosure & transparency |
| 10 | `302_advice_vs_education_capstone` | ETHIC 10 | M23 | **Capstone** — Advice vs education (ties to AMI's simulation-only frame) |

## Frontmatter (every lesson) — match the corpus schema exactly

```
id: "<from table>"
title: "<refined>"
duration_min: 5
level: 13
track: "ethics_integrity"
code: "ETHIC <n>"
topic: "<short>"
prerequisites: [<within THIS lane or existing corpus ids only — never another in-flight track>]
tags: [...]
agent_callouts: ["portfolio_manager"]  # and/or "concierge" (§4.1 mapping)
locale_versions: ["en"]
created_at: "2026-07-22"
updated_at: "2026-07-22"
```

## Constraints (CR054 §6 — non-negotiable)

- **Simulation-only, forever.** Ethics is literacy + our own advice-vs-education frame; never "act on this."
- **AMI by name** in copy; **LLM** only in code (none here).
- **Quiz invariants (DEF064/DEF065 + CR042):** multiple-choice, options required, no numeric option
  references, correct-answer position varied across the 4 slots (not all index 1). Each capstone's
  final quiz tests **synthesis** across its module.
- **CR044 codes frozen + contiguous:** ETHIC 1..10 exactly, no gaps, no existing code touched.
- **7-part template** (thesis → real example → the trap → ChatWith → synthesis quiz → action → takeaway)
  + optional v2 steelman beat + optional `sources` line where a claim rests on the canon.

## Definition of Done (self-check before READY_FOR_REVIEW)

- [ ] 10 `.en.mdx` files created at the reserved ids, ETHIC 1..10 contiguous.
- [ ] **Run `cd backend && uv run pytest tests/unit/test_lesson_corpus_integrity.py -q` → green.** (You are a
      maintainer, but new lesson DATA must satisfy the guard — fix until it passes; degrade loudly.)
- [ ] No existing lesson/code/track modified. Prereqs all resolve. Capstones are last-in-module + synthesis.
- [ ] `STATUS: READY_FOR_REVIEW (round 1)` for Architect/Saiful content review.
