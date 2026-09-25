# DEF423 — CR160 acceptance not met: residual old agent labels

**Reporter:** founder (Saiful) · **Filed:** 2026-09-25 · **Area:** content · **Status:** open (this lane closed; lanes B/C tracked elsewhere)

Saiful, 2026-09-25: *"We have been mixing the term PM and CIO in the app, and in the
lesson. This is because we had renamed the PM to CIO but not all were updated."*

This doc covers **lane A only** — `mobile/lib/**`, `backend/app/**` user-facing strings,
`content/agents/*.md` prompt text, and `website/` + `website_api/` copy. Content lessons,
`ai_coach`, `daily_challenges` and `glossary` are other lanes' files and are not touched
here.

## Why CR160's own guard missed this

CR160 shipped 2026-08-20 (AT:R73) with `test_cr160_agent_rename.py`, which asserts:

1. `agent_id` values are frozen and match filenames — still true, untouched by this DEF.
2. Display names are lockstep across `backend/app/schemas/agents.py`,
   `content/agents/*.md` frontmatter, and `mobile/lib/models/agent.dart` — still true,
   confirmed correct before any fix in this DEF (see "Already correct" below).
3. `test_retired_labels_absent_from_en_content_corpus` — **only walks `content/`**. It
   never looked at `mobile/lib` at all, so a whole surface (every ARB string in the app)
   had no structural guard. That is the gap this DEF closes.

CR160's own row (`docs/forward_planning/_registry/CR160.row.md`) already recorded two
pieces of known residue at ship time — AR/MS retranslation riding the i18n lane, and the
live Terms page's two "Portfolio Manager" mentions deferred to "Saiful's call" — but the
EN `mobile/lib` gap was not on that list. This DEF is what surfaced it.

## Already correct (verified, zero residue)

- `mobile/lib/models/agent.dart` — all 12 `displayName` values use the new labels.
  `AgentId` enum members (`aggressive_debator`, etc.) are frozen identifiers, correctly
  unchanged per CR160's OUT list.
- `backend/app/schemas/agents.py` — `AGENT_DISPLAY_NAMES` already correct for all 12 ids.
- `content/agents/*.md` — no retired label in any of the 13 prompt files' body text or
  `display_name` frontmatter. `research_manager.md:48` says "a senior portfolio manager
  listening to two analysts argue" — lowercase, a generic real-world persona simile
  teaching what the role sounds like, not naming AMI's own agent. Allowlisted (see
  classification rules below); left as-is.

## Residue found and fixed, by surface

### `mobile/lib/l10n/app_en.arb` — 14 keys (before → after)

The 12 keys named in the DEF423 task brief, all "PM" → "CIO":

| Key | Before | After |
|---|---|---|
| `insightsVerdictTitle` | `WHAT YOUR PM DECIDED` | `WHAT YOUR CIO DECIDED` |
| `insightsVerdictNoVerdictNote` | "...The PM declined to rule..." | "...The CIO declined to rule..." |
| `portfolioStartSimTradingBody` | "...Your PM's safety floor..." | "...Your CIO's safety floor..." |
| `lessonPlayBreachDrawdownCeiling` | "...the PM stopped you..." | "...the CIO stopped you..." |
| `settingsMaxDrawdownExplain` | "Your PM refuses trades..." | "Your CIO refuses trades..." |
| `roomTradeTicketCaption` | "...PM safety floor reruns." | "...CIO safety floor reruns." |
| `tradeTicketFooterNote` | "PM safety floor runs..." | "CIO safety floor runs..." |
| `tourYou3Body` | "...what your PM decided..." | "...what your CIO decided..." |
| `roomOverrideHeading` | "...CHANGED THE PM'S CALL" | "...CHANGED THE CIO'S CALL" |
| `roomRibbonDerived` | "...NOT THE PM" | "...NOT THE CIO" |
| `roomStagePmVerdict` | `PM VERDICT` | `CIO VERDICT` |
| `roomConsensusNoCall` | "The PM made no call..." | "The CIO made no call..." |

Two more found by a case-insensitive sweep (the first pass missed these because they're
ALL-CAPS UI strings, e.g. "MARKET ANALYST" not "Market Analyst"):

| Key | Before | After |
|---|---|---|
| `watchlistEmpty` | "...Ask the Market Analyst, Convene the Room..." | "...Ask the Technical Strategist, Convene the Room..." |
| `watchlistAskMarketAnalyst` | `ASK THE MARKET ANALYST` | `ASK THE TECHNICAL STRATEGIST` |
| `roomPmCardHeading` | `PORTFOLIO MANAGER` | `CHIEF INVESTMENT OFFICER` |
| `roomStageRiskReviewSubtitle` | "The Trader drafts a ticket. Aggressive, Conservative and Neutral stress it from both sides." | "The Execution Desk drafts a ticket. Risk Officers — Aggressive, Conservative and Balanced — stress it from both sides." |

**Before: 16 EN ARB values with a retired agent label. After: 0** (verified by
`test_no_retired_agent_label_in_en_arb_values` + `test_no_bare_pm_agent_abbreviation_in_en_arb_values`
+ `test_no_retired_trader_agent_label_in_en_arb_values`, all green).

All 16 changed/new-metadata keys now carry `retranslate:[ar,ms]` in their `@key`
description (6 already had it; 4 keys had no `@key` block at all and got one added; 6 had
a description but not the flag, now added). **AR/MS values were not hand-edited** — the
repo's ARB translation flow (`scripts/translate_arb.py`) explicitly reserves target-locale
edits for the i18n lane; `--seed-missing` was not run because no new *translatable* keys
were added (only `@key` metadata, which is not translated). AR/MS still read the old
labels for 3 of these keys (`watchlistEmpty`, `watchlistAskMarketAnalyst`,
`roomPmCardHeading` — real hand-translations of the old label, now stale) and 1
(`roomStageRiskReviewSubtitle` — an untranslated DEF295 English seed, whose seed marker
does not auto-detect that its *source* changed, only that the *target* was hand-edited).
Both are legitimate i18n-lane follow-up, flagged via the description tag, not silently
left matching the old meaning.

### `backend/app/services/room_prompts.py` — 1 inconsistency

`_PM_VERDICT_FORMAT` (the CIO's verdict-generation prompt) said "the Execution Desk's
proposal" / "Do not just restate the Execution Desk's numbers" at lines 441/443, but two
sentences later, in the same constant, said "the Trader's size" (line 508) and "the
Trader recommended WAIT" (line 515) — an internal inconsistency within one prompt block
left over from CR160's sweep. Both fixed to "Execution Desk". This reaches the user: it's
prompt text the model reads and can echo back into its `narration` field, per CR160's own
scope rationale for `content/agents/*.md` cross-references.

Everything else the initial grep flagged in `backend/app/` (dozens of hits across
`room_prompts.py`, `room_runner.py`, `sizing.py`, `credit_service.py`, etc.) was verified
individually and is out of scope: Python `#` comments and docstrings explaining
historical/design rationale (CLAUDE.md: internal comments are fine), the `DebatorSizes`
`NamedTuple` type name (an internal identifier, no string literal emitted), the `"pm"` /
`"trader"` wire-value sentinels in `schemas/room.py` (DB/wire keys, frozen per CR160's OUT
list — only labels move, not keys), and three `display_name=o.get("display_name",
"Trader")` fallbacks (`concierge_engine.py`, `brief_engine.py`, `agent_runner.py`) that
default the **user's own** detected persona name from onboarding, not an AMI agent label.

### `website/` + `website_api/`

- `website_api/app/knowledge/faq.md` (2 occurrences) and
  `website_api/app/services/faq_answer.py` (1 occurrence) — "a Trader, and a Portfolio
  Manager" / "The Portfolio Manager runs a compliance + judgment review" / "and a
  Portfolio Manager" — all fixed to "an Execution Desk, and a Chief Investment Officer" /
  "The Chief Investment Officer runs..." / "and a Chief Investment Officer". These are
  the website chatbot's grounding source and its scripted fallback — genuinely
  user-facing, not legal copy.
- `website/index.html`, `website/competition-rules/index.html` — remaining "Trader" hits
  are the $14.99/mo pricing tier and a competition-ladder rank
  ("Apprentice → Analyst → Trader → Senior → Floor Veteran"), neither the CR160 agent
  label. Allowlisted, left as-is.
- `website/terms/index.html` (the live, current v4.0 Terms page) — **left untouched,
  flagged below as ambiguous.** `website/terms/v1/`, `v2/`, `v3/` are frozen historical
  archives (each carries its own `document-version` meta and a "prior version archived
  at" trail) and must never be edited to match; only `index.html` is live.

## Classification rules used

- Replace only where the text names **AMI's own agent**.
- Keep "PM" when it denotes a **time** (e.g. "4 PM ET") — none found in the touched
  surfaces, but the guard test's regex explicitly excludes this pattern
  (`_PM_TIME_CONTEXT`).
- Keep a lowercase, generic real-world "portfolio manager" (a human at a fund) where the
  sentence teaches finance rather than naming our agent — one instance
  (`content/agents/research_manager.md:48`).
- Keep "Trader" as the **pricing tier** name ($14.99/mo, CR084), the **Day Trader risk
  preset** (CR129), and the **competition-ladder rank** (website) — all unrelated product
  nouns that predate and postdate CR160's agent-label rename.
- Never touch `agent_id` values, DB/wire sentinels (`"pm"`, `"trader"` as
  `level_provenance` literals), file names under `content/agents/`, or code
  identifiers/enum members/comments/docstrings (CLAUDE.md: internal names are fine).

## Ambiguous — left alone, flagged for Saiful

**`website/terms/index.html` (live Terms v4.0), lines 218 and 227** — two mentions:
"Trader and Portfolio Manager verdicts" and "including Portfolio Manager verdicts,
mandate-compliance checks". CR160's own row already named this exact residue and deferred
it to "Saiful's call" without resolving it. Not touched here because:

1. It is **versioned legal copy** — the page's own header comment says "when publishing a
   new version, archive the current `/terms/index.html` to `/terms/vN/`" and a
   `<meta name="document-version">` + in-page "Version history" section record every
   change with an effective date. A silent text edit to live Terms without a version bump
   contradicts the page's own convention; a version bump is a legal/process decision, not
   a rename mechanic.
2. It was **already flagged once** (CR160 ship note) and deliberately left for Saiful
   rather than auto-resolved — re-deferring it a second time without a new instruction
   would compound the same unresolved call, not fix it.

Recommend: Saiful decides whether this rides the next Terms revision (bundled with
whatever else prompts a v5.0) or gets its own version bump now.

No other ambiguous cases were found in lane A's paths — everything else was either a
clear fix (real user-facing text naming the agent) or a clear allowlist (pricing tier,
time, generic finance-teaching prose, internal identifier).

## Guard added

`backend/tests/unit/test_def423_agent_rename_residue.py` — 5 tests:

- `test_no_retired_agent_label_in_en_arb_values`
- `test_no_bare_pm_agent_abbreviation_in_en_arb_values`
- `test_no_retired_trader_agent_label_in_en_arb_values`
- `test_no_retired_agent_label_in_flutter_agent_registry_display_names`
- `test_no_retired_agent_label_in_agent_prompt_markdown`

Registered in `docs/initial_specs/08_tech/failure_patterns.md` under the incomplete-rename
class (second occurrence — CR160's own sweep was the first, `test_cr160_agent_rename.py`'s
`content/`-only scope was the gap).

## Verification

- `flutter analyze` — baseline 11 issues, 0 errors (unchanged by this DEF; no new
  analyzer issues from the ARB edits, which are value-only string changes).
- `flutter test` — full suite green (see report for exit code).
- Backend targeted: `test_cr160_agent_rename.py`, `test_def295_seeded_translations_are_marked.py`,
  `test_registers_no_drift.py`, `test_p30_registers_name_things_that_exist.py`,
  `test_def423_agent_rename_residue.py` — all green (see report for exit codes).
