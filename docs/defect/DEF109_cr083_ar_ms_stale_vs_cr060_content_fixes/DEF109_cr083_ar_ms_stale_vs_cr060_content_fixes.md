# DEF109 — AR/MS translations stale against the CR060 apply-pass content fixes

## What

Commit `672466e` ("CR060 apply pass — 165 lessons, DEF078 + DEF101 + DEF102-A", 2026-07-25
20:42) corrected EN lesson content across 165 lessons: DEF101's 142 exact fact/math/quiz-key
corrections (each dual-pass verified against a primary source), DEF102-A's 22 phantom-Mandate-
field realignments (`max_position_pct`/`pause_at_drawdown_pct`/`region_allowlist` → the real
`risk_score`-derived cap / `max_drawdown_pct` / `ticker_allowlist` schema), and DEF078's 19
sourced-batch fixes (GDP-revision, tracking-difference, naked-call, drawdown-recovery math).

All 165 lessons' AR/MS translations were produced **before** this commit (git-history-checked,
not mtime-checked — see [[project_ami_trade]] staleness-detection note) and were never
refreshed against it. That means 330 translation files (165 lessons × 2 locales) may currently
teach the pre-correction fact, math, quiz key, or Mandate-field name while the EN source now
teaches the corrected one.

## How found

Spotted as a byproduct of evaluating the Falcon-H1-34B-GPTQ verifier model
(`192.168.20.74:8044`) against lesson `071_how_to_verify_before_you_wire_money`. Falcon flagged
a sentence in the AR body attributing an unsourced claim to "the SEC's Office of Investor
Education" that does not exist anywhere in the current EN source. `git log --follow -p` on the
EN file showed the sentence *was* present until `672466e` removed it (as part of the DEF101
sourced-content cleanup) — the AR translation simply never caught up. That triggered a full
sweep: every EN file touched by `672466e`, cross-referenced against its AR/MS sibling's last-
touched commit date. Result: **all 165/165 lessons' AR+MS files predate the fix, 0 already
refreshed** (see `docs/forward_planning/CR083_language_manager_ar_ms_translation_delivery/`
for the check script pattern — same git-log-based method used for the DEF102/DEF097 staleness
sweep earlier in CR083, mtime diffing was ruled out there as too noisy).

Spot-checked a second lesson (`012_why_most_traders_fail`) to confirm this isn't an isolated
case: its EN body changed "Brazilian regulator-led work" (unsourced) → "a Brazilian academic
study of index-futures day traders (Chague et al. 2020)" (sourced), and its "Try it" section's
`max_position_pct` → `risk_score` Mandate-field rename — both material, both still present in
the stale AR/MS files at time of writing.

## Scope

165 lessons, 330 translation files (AR + MS). 5 of the 165 are in the Sharia `strict_review`
cluster (`348`, `349`, `350`, `354`, `356`) — held to the ≥3-model/zero-issue bar, elevated
care per existing project precedent. Lesson `355` itself is **not** in this list (unaffected —
its own DEF097 rewrite was handled separately) and its MS quarantine is untouched by this fix.

## Fix

Retranslate all 165 lesson ids, both locales, via the existing
`scripts/translate_lessons_lan.py --ids <165 ids> --locales ar ms --overwrite` (same tool used
for DEF103/DEF102/DEF097, sequential-only against `ami-llm` at `192.168.20.74:8000`). Then:
- Re-run the real backend serving gate (`parse_mdx` + `_locale_quiz_servable`) across all 342
  lessons to confirm nothing regressed.
- Re-run `scripts/i18n_coverage_report.py` to resync `locale_versions`.
- Queue the 5 strict-review lessons for elevated verification once retranslated.
- Log a fresh confidence-verification pass in `content/i18n/lesson_confidence_log.json` for the
  165 (their old entries, if any, now describe pre-fix content and should not be treated as
  still valid for the corrected text).

## Process note (not this DEF's fix, flagged for awareness)

This is the third concurrent-track staleness wave found this CR (after DEF102's 4 orphaned
lessons and DEF097's lesson 355), each caught only because someone happened to look. A
lesson's translation has no structural link back to the EN commit it was translated from, so
any future EN content-fix pass will silently re-open this gap unless something re-checks. Not
fixing that here (out of DEF109's scope) — worth a future CR if this keeps recurring.
