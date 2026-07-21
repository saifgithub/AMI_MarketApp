<!-- dispatch worker lane — noncoder.edu-owned. CR052. -->
# CR054-W1-ETHIC — noncoder.edu

STATUS: NEEDS-INFO (round 1)

Lane: all 10 Level-13 Ethics & Market Integrity lessons (M22 + M23) — ids 293-302, ETHIC 1-10,
track ethics_integrity, per wave1_ethics.md + authoring prompt v2. Gate: Architect/Saiful content
review (no Auditor).

## Work state: AUTHORED, self-checked, deliberately NOT committed

All 10 files written and passing every data-level guard. They sit **untracked** at
`content/lessons/{293..302}_*.en.mdx` on the Mac checkout (backup:
`<session scratchpad>/CR054-W1-ETHIC_backup/`). Not committed because pushing them now would turn
the corpus guard red on origin for every lane — see Q1.

Self-check evidence (2026-07-21):
- `uv run pytest tests/unit/test_lesson_corpus_integrity.py -q` → **19 passed, 2 failed**. All 280
  files parse; every quiz/code/gateway/track data assertion green on the new files (answerable
  options, in-range answers, distinct options, explanations present, zero option-index citations,
  zero tolerance=, ETHIC prefix matches track, ETHIC 1..10 contiguous, codes unique).
- Full `pytest tests/unit/ -q` → **924 passed, 2 failed** — the same 2; nothing else in the suite
  pins the count (`test_concierge_context_router` uses `>= 270`, passes at 280).
- Both failures are Wave-0 structural pins in `backend/tests/unit/test_lesson_corpus_integrity.py`
  that no lesson DATA can satisfy:
  (a) `EXPECTED_LESSON_COUNT = 270` (L42) — corpus is now 280;
  (b) `test_cr054_new_tracks_are_empty_at_wave_0` (L405-417) — its own docstring calls it "the
      enforcement floor until Wave 1 fills the tracks", i.e. designed to be lifted by exactly this
      lane's content.

Q1: The DoD requires the corpus guard green before READY_FOR_REVIEW, and CR054 §5.1 requires guards to land in the same commit as their content — but the two blocking assertions above live in backend/**, which is outside my ownership (NONCODER discipline: never touch code, disjoint write-paths). How do you want the Wave-1 guard extension landed? (i) coder.api hot-lane lands it first — suggested shape: EXPECTED_LESSON_COUNT 270→280, and rewrite test_cr054_new_tracks_are_empty_at_wave_0 to assert empty only for the still-unfilled tracks {asset_classes, economics_macro, quant_methods} so the floor survives for the other Wave-1 lanes (plus the per-wave capstone guard from wave1_ethics.md if you want it now: tags contains "capstone" ⇒ last-in-module + synthesis quiz) — then I commit/push the content and go READY_FOR_REVIEW; or (ii) you grant an explicit one-time carve-out authorizing me to include that minimal test edit in my content commit. I proceed the moment A1 lands (resume live_handle 31ea853e-11d1-4594-9f60-d0c22a3895cb, or bump ASSIGNED).

## Content summary (for the eventual review)

| id | code | Module | Title | Quizzes (answer slot) |
|---|---|---|---|---|
| 293_market_integrity_why | ETHIC 1 | M22 | Why market integrity matters | 2 (2,0) |
| 294_insider_trading | ETHIC 2 | M22 | Insider trading: material non-public information | 3 (1,3,0) |
| 295_market_manipulation | ETHIC 3 | M22 | Market manipulation: pumps, spoofs, and wash trades | 3 (0,2,1) |
| 296_front_running_fair_dealing | ETHIC 4 | M22 | Front-running and fair dealing | 2 (3,2) |
| 297_playing_it_straight_capstone | ETHIC 5 | M22 | Capstone: playing it straight | 3 (1,0,3) |
| 298_fiduciary_duty | ETHIC 6 | M23 | Fiduciary duty: the client's interest first | 2 (2,1) |
| 299_conflicts_of_interest | ETHIC 7 | M23 | Conflicts of interest: follow the money | 2 (0,3) |
| 300_suitability_kyc | ETHIC 8 | M23 | Suitability and know-your-client | 2 (3,1) |
| 301_disclosure_transparency | ETHIC 9 | M23 | Disclosure and transparency | 2 (1,2) |
| 302_advice_vs_education_capstone | ETHIC 10 | M23 | Capstone: advice vs education | 3 (2,0,3) |

- Answer positions: 24 questions, exactly 6 per slot (CR042). No option-index citations (DEF065),
  multiple-choice only (DEF064). 7-part template throughout; both capstones tagged "capstone",
  last-in-module, all-synthesis quizzes + steelman.
- Real cases with pinned numbers: Enron ($90.75→<$1), 1MDB ($4.5B DOJ), Stewart/ImClone (3,928 sh,
  $45,673, 5 months), Rajaratnam (11 yrs, $92.8M), Sarao/Flash Crash (Dow −998.5 intraday, ~$40M
  2010-14), Robinhood PFOF ($65M fine, $34.1M inferior execution), Global Research Analyst
  Settlement ($1.4B), TSLA 2022 (−65%: $352.26→$123.18), Wirecard (€1.9B, €104→<€3), MAYBANK
  front-run worked example (RM0.15 × 50,000 = RM7,500), fee-drag 20y example ($27,573 vs $38,051,
  gap $10,478 — arithmetic verified). Multi-market: US + Bursa (MAYBANK, TOPGLOV) + DE (Wirecard).
- Editorial choices flagged for review (bounce if unwanted):
  - `module: 22/23` + `difficulty:` included in frontmatter (authoring-prompt v2 schema; the
    wave1_ethics.md frontmatter block omits them; parse-safe either way, and capstone
    last-in-module enforcement needs `module`).
  - `created_at/updated_at: "2026-07-22"` exactly per the wave1_ethics.md block (authored 07-21).
  - `sources` + "Where this comes from" on 4 lessons (CFA Code/III(A)/III(C), SEC Rule 10b-5);
    omitted elsewhere.
  - Steelman beat on 293, 296, 300 (analytical) + both capstones (required); skipped on the
    mechanics-leaning 294/295/298/299/301.
  - Prereq bridges into existing corpus: 066_telegram_whatsapp_pump_groups (ETHIC 3, M11 bridge),
    291_the_pm_and_your_mandate (ETHIC 8), 073_what_ami_cannot_do (ETHIC 10). All other prereqs
    intra-lane; both capstones list 4+ module lessons.
  - agent_callouts: portfolio_manager throughout; concierge added on 300 + 302 (§4.1 and/or rule);
    ChatWith = PM except 300/302 = concierge. No gateway edits (DEF068 respected).

A1 (architect, 2026-07-22): Correct call to stop — a maintainer must not edit backend/ (disjoint write-paths). Decision = your option (i), generalized: **coder.api** lands guard-v2 as lane **CR054-GUARD** (backend/tests is its file): (a) lesson-count assertion → FLOOR (>= current count), not an exact pin; (b) RETIRE test_cr054_new_tracks_are_empty_at_wave_0 (Wave-0 scaffolding — tracks now fill deliberately per wave); (c) add the capstone guard (tags~"capstone" ⇒ last-in-module + synthesis quiz). That is green STANDALONE at 270 lessons. Once it is audited + integrated I bump your ASSIGNED to round 2 → you then commit your 10 already-authored lessons + go READY_FOR_REVIEW (now green). HOLD until the round bump. Your 10 lessons are safe uncommitted in the working tree — do NOT push them while the guard is red. Good escalation.

CONTENT PRE-REVIEW (architect, 2026-07-21): reviewed all 10 on disk while CR054-GUARD audits — **PASS, zero required changes.** 293 read in full (exemplary: 7-part template, Enron $90.75→<$1 / 1MDB $4.5B, real steelman with a falsifier, safety-floor tie-in, CFA-Code source). Compliance sweep across all 10: codes ETHIC 1–10 contiguous, all L13, M22 (1–5)/M23 (6–10), capstones 297/302 tagged capstone+synthesis and last-in-module; quizzes DEF064/065-clean (options required, no numeric option refs); answer positions well-varied per CR042; zero "the AI" (AMI named throughout); simulation-only respected; `sources` correctly optional-where-canon-anchored (4 cite CFA/SEC, capstones synthesize so omit). Editorial flags all accepted. Only nit: `created_at/updated_at: 2026-07-22` vs authored 07-21 — cosmetic, matches the spec block verbatim, NOT a bounce. **⇒ When you go READY_FOR_REVIEW in round 2, I accept on sight — no quality bounce coming. The pipeline is validated; I will fan out ASST/MACRO/QUANT on the same standard.**
