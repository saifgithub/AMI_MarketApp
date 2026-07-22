<!-- dispatch return lane — noncoder.edu track, CR058-SUPPORT round 1 -->

# CR058-SUPPORT — return (noncoder.edu round 1)

KIND: content
INSTANCE: noncoder.edu
ROUND: 1

## Summary

Mirrored the shipped Sharia lessons (347–356) across the other three content corpora
per CR058 §3.2: glossary, AI-coach Q&A, daily challenges. All P2 ratio/purification
numbers reused verbatim from the already-verified lesson figures (349 debt/liquidity/
income ratios, 351 purification amount, 356 capstone ratios) — none hand-authored.
Every ruling-adjacent entry carries both load-bearing frames (simulation/training-
artifact + "methodology, not a Sharia ruling — consult a qualified scholar").

## Manifest

- **Glossary:** 20 terms appended to `content/glossary/terms.en.json` (category
  `islamic_finance`), existing 188 untouched — append-only, verified via diff.
- **AI-coach Q&A:** 15 entries, new file `content/ai_coach/islamic_finance.json`
  (category `islamic_finance`), including "Is [ticker] halal?" (teaches the two-stage
  screen, defers to a scholar), "Is crypto halal?" (presents the live scholarly debate,
  no ruling), and the sukuk/standards/purification/halal-flag questions from the brief.
- **Daily challenges:** 10 entries, new file `content/daily_challenges/2026_12.json`,
  days 01–10, `spot_the_violation` (5) + `whats_missing` (5) only — no new type added.
  Answer index varied across the 10: `[0, 1, 2, 3, 0, 2, 1, 3, 2, 0]` (CR042). No
  positional option references in any explanation (DEF065) — distractors named by
  content.

## Verification

- Targeted pytest: `cd backend && uv run pytest tests/unit/test_glossary_service.py tests/unit/test_ai_coach_service.py tests/unit/test_daily_challenge_service.py -q`
  → **32 passed, exit 0**.
- All 3 JSON files parse (`json.load` clean): glossary 208 total entries, coach 15,
  daily challenges 10.
- `git diff` on `terms.en.json` confirmed append-only (200 insertions, 0 deletions,
  0 modifications to the existing 188).
- Only the 3 content files staged and committed — `backend/uv.lock`,
  `.claude/settings.local.json`, `Archive.zip` left untouched.

## Commit

`5ebfef4c93f58aa599250b5d09130792cd410638` — `content(islamic_finance): CR058-SUPPORT —
mirror Sharia content into glossary/coach/daily (AT:noncoder.edu CR058)`. Pushed to
`origin/main`.

---

STATUS: READY_FOR_REVIEW (round 1)

Manifest: 20 glossary terms / 15 coach Q&A / 10 daily challenges — commit 5ebfef4
