<!-- dispatch assign lane — Architect-owned. CR052. -->
# CR058-SUPPORT — assign (Islamic-finance glossary + coach Q&A + daily challenges)

KIND: content
INSTANCE: noncoder.edu
ACCEPTANCE: docs/forward_planning/CR058_sharia_compliant_investing/CR058_sharia_compliant_investing.md (§3.2 mirror-across-corpora, §7 frame, §8 guards)
DEPENDS-ON: CR058-CONTENT (lessons 347-356 exist ✓), CR059 (islamic_finance track wired ✓)
GATE: content review (Architect) — no auditor, no pytest gate beyond the 3 targeted corpus tests
HOT-FILES: content/glossary/terms.en.json (append-only — flat list of 188; do NOT reorder/edit existing)

**What:** Mirror the shipped Sharia lessons (347-356) across the OTHER THREE content corpora so the
Concierge/coach/glossary/daily surfaces aren't blind to Islamic finance (CR058 §3.2 — "or the
Concierge stays blind"). THREE deliverables, ONE commit:

### 1. Glossary — ~20 terms, category `islamic_finance`
Append to `content/glossary/terms.en.json` (flat JSON list; APPEND only — never touch the existing 188).
Per-term schema (match existing exactly): `id` (snake_case), `term`, `definition`, `category:"islamic_finance"`,
`see_also` (ids of related terms — cross-link within this new set + to existing where apt), `related_lessons`
(string ids — draw from **347-356** and the tie-ins 271/273/303/307/310), `related_agents`
(fundamentals_analyst / portfolio_manager where apt), `tags`.
Terms (§3.2): riba, gharar, maysir, halal, haram, sukuk, ijarah, murabahah, musharakah, mudarabah,
takaful, tazkiyah (purification), aaoifi, shariah_advisory_council, dow_jones_islamic_market_index,
sharia_screening, business_activity_screen, financial_ratio_screen, sharia_compliant, islamic_etf.
(No backend enum change — `category` is a free string; CATEGORY_ORDER omission is degrade-safe, unlisted
categories fall to the end alphabetically. Do NOT edit glossary_service.py.)

### 2. Coach Q&A — ~15, NEW file `content/ai_coach/islamic_finance.json`
Flat JSON list. Per-entry schema (match content/ai_coach/beginner.json exactly): `id` (e.g.
`qa_islamic_is_ticker_halal`), `category:"islamic_finance"`, `question`, `short_answer`, `long_answer`,
`related_lessons` (347-356 + tie-ins), `related_agents`, `tags`. Service auto-discovers via `*.json` glob +
the `category` field — no backend change. Questions (§3.2): "Is [ticker] halal?", "What does AMI's halal
filter actually check?", "Why did a stock stop being halal?", "Is a sukuk the same as a bond?", "Which
Sharia standard does AMI use?", "Do I need to purify my dividends?", "Is crypto halal?", + ~8 more.
**Frame is load-bearing here (§7):** the "Is X halal?" answer must teach the *methodology* + the two-stage
screen and **defer to a qualified scholar — never issue a ruling.**

### 3. Daily challenges — 10, NEW file `content/daily_challenges/2026_12.json`
Flat JSON list, days **01–10** (ids `dc_2026_12_0N_<slug>`). Per-entry schema (match 2026_08.json exactly):
`id`, `type`, `difficulty`, `locale:"en"`, `scenario`, `question`, `options` (≥3, required), `answer`
(index — **VARY across the 10**, CR042), `explanation`. **REUSE existing types only** — `spot_the_violation`
+ `whats_missing` (do NOT add a `screen_the_stock` type — that needs a backend guard; out of scope here).
Themes (§3.2): spot-the-non-compliant-stock, screen-this-balance-sheet, sukuk-vs-bond, which-standard-applies.

**P2 (non-negotiable):** any ratio/purification number in a Q&A or daily challenge is COMPUTED via CR046
`screening.py` (`sharia_debt_ratio`/`sharia_liquidity_ratio`/`sharia_impermissible_income_ratio`/`sharia_screen`/
`purification_amount`), correct to the stated dp — or REUSE the already-verified worked numbers from the
lessons (349: debt 138000/128000=107.8%, liq 4200/128000=3.3%, income 900/122000=0.7%, overall FAILS on debt;
356 capstone: a lightly-levered tech balance sheet that clears all three). Never hand-author a halal number.

**Frame (CR058 §7 — as firm as "not investment advice"):** "methodology, NOT a Sharia ruling." Wherever a
term/Q&A/challenge touches a compliance verdict, carry (a) simulation/training-artifact framing and (b)
"AMI teaches the published screening methodology (AAOIFI / Bursa SAC / index rulebooks); it does not issue
religious rulings — consult a qualified scholar." Where standards disagree, present the disagreement.

**Constraints:** AMI by name (never "the AI"); DEF064 (options required) + DEF065 (no "option N") + **no
POSITIONAL option refs** ("the first/second option") in any explanation — name the distractor by content;
CR042 answer-position variety on the 10 daily challenges. **Sources (CR060):** Tier-1/2 only — AAOIFI,
Bursa SAC, the named index rulebooks (Dow Jones Islamic / S&P Shariah / MSCI Islamic / FTSE Shariah),
Usmani, El-Gamal.

**Self-test (headless one-shot — targeted, NOT the full suite / P7):**
`cd backend && uv run pytest tests/unit/test_glossary_service.py tests/unit/test_ai_coach_service.py tests/unit/test_daily_challenge_service.py -q` green (~fast). ONE commit, tag `(AT:noncoder.edu CR058)`.

ASSIGNED: noncoder.edu round 1
DISPATCH: OPEN
