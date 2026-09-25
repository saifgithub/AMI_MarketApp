# DEF423 (lane C) — PM/CIO mixing swept from `content/` outside lessons and agents

**Filed:** 2026-09-25 (AT:R85), source: Saiful — "We have been mixing the term PM
and CIO in the app, and in the lesson. This is because we had renamed the PM to
CIO but not all were updated."
**Category:** content
**Scope:** lane C of 3 — `content/**` EXCLUDING `content/lessons/**` (lane B) and
`content/agents/**` (lane A).

---

## What was found

CR160 (shipped 2026-08-20, AT:R73) renamed `Portfolio Manager` →
`Chief Investment Officer` (abbreviation `CIO`) across the client registry,
backend mirror, and a corpus sweep. The corpus-wide regex guard
(`backend/tests/unit/test_cr160_agent_rename.py::test_retired_labels_absent_from_en_content_corpus`)
checks for the full retired phrase `"Portfolio Manager"` (and the other five
retired labels) and was, and still is, green — **that phrase is genuinely gone
from lane C's EN content.**

What the guard does not check is the **abbreviation**: pre-CR160 copy in
`content/ai_coach/*.json`, `content/daily_challenges/*.json`, and
`content/glossary/terms.en.json` referred to the agent throughout as
**"the PM"** — a shorthand the rename left behind because the full-phrase
guard can't see it (bare `PM` legitimately also means the pricing tier, `AM`/`PM`
clock time, and the `JPM` ticker elsewhere in this same corpus, so a blind
`\bPM\b` ban would have false-failed on those). The result: the same content
family — sometimes the same quiz item — used `"Chief Investment Officer"` in
one field and `"the PM"` two sentences later, or listed `'PM'` as a literal
quiz option next to `'Chief Investment Officer'` as if they were different
roles. `docs/defect/_registry/DEF410.row.md` (2026-09-17, one week before this
filing) hit the same residue class in `content/lessons/` and noted explicitly:
*"the house shorthand across the lesson corpus is 'the PM' (~139 occurrences)
… those sit in compliance/mandate prose"* — left unswept at the time. This
DEF sweeps lane C's share of that same backlog.

Worst single instance: the glossary entry `ami_pm_safety_floor` had
`"term": "PM safety floor"` sitting directly above
`"definition": "...in the Chief Investment Officer prompt..."` — literally
mixing both names inside one entry.

## Fix

110 word-level substitutions across 70 content items in 12 EN files, applied
as a format-preserving raw-text regex sweep (not a JSON re-parse/re-dump, so
no incidental array/whitespace reformatting):

| pattern | replacement |
|---|---|
| `the PM's` | `the CIO's` |
| `the PM` | `the CIO` |
| `PM's` | `CIO's` |
| `PM-written` | `CIO-written` |
| `PM-owned` | `CIO-owned` |
| `PM safety floor` | `CIO safety floor` |
| bare `PM` (word-boundary) | `CIO` |

**Never touched:** JSON `id` values, `agent_id`/`related_agent`/`related_agents`
values (`portfolio_manager` stays `portfolio_manager` — it's the frozen DB key,
byte-identical before/after, confirmed by diff), `tags`, `category`, and every
tooling/log file the existing `_EXEMPT` regex in `test_cr160_agent_rename.py`
already carves out. Two ids contain "jpm" as a ticker substring in their id
(`dc_2026_09_12_whats_missing_jpm_de`, `dc_2026_09_21_jpm_payout_call`) —
checked individually, neither contains the bare-word agent abbreviation, so
neither needed editing; word-boundary matching correctly left the ticker
alone throughout (all AM/PM clock times in this corpus are lower-case
`4:00pm`-style and never collided with the upper-case `PM` agent shorthand).

## Before/after counts, per file

| File | EN items touched | "PM" substitutions | AR sibling | MS sibling |
|---|---|---|---|---|
| `content/ai_coach/ai_meta.json` | 20 | 35 | exists — now stale | exists — now stale |
| `content/ai_coach/platform.json` | 11 | 15 | exists — now stale | exists — now stale |
| `content/ai_coach/islamic_finance.json` | 1 | 2 | **none** | **none** |
| `content/ai_coach/beginner.json` | 1 | 1 | exists — now stale | exists — now stale |
| `content/daily_challenges/2026_06.json` | 10 | 19 | exists — now stale | exists — now stale |
| `content/daily_challenges/2026_07.json` | 3 | 5 | exists — now stale | exists — now stale |
| `content/daily_challenges/2026_08.json` | 2 | 2 | exists — now stale | exists — now stale |
| `content/daily_challenges/2026_09.json` | 8 | 11 | exists — now stale | exists — now stale |
| `content/daily_challenges/2026_10.json` | 10 | 12 | exists — now stale | exists — now stale |
| `content/daily_challenges/2026_11.json` | 2 | 4 | exists — now stale | exists — now stale |
| `content/daily_challenges/2026_12.json` | 1 | 3 | exists — now stale | exists — now stale |
| `content/glossary/terms.en.json` | 1 (`ami_pm_safety_floor`) | 1 | exists — now stale | exists — now stale |
| **Total** | **70** | **110** | | |

`content/ai_coach/islamic_finance.json` has no `.ar`/`.ms` sibling file yet
(only `ai_meta`, `beginner`, `intermediate`, `platform`, `psychology`, `scam`
exist under `content/ai_coach/ar/` and `content/ai_coach/ms/` — confirmed by
directory listing) — **no retranslation owed for that file**, recorded
explicitly rather than left to inference, per the DEF410 precedent.

**A second, load-bearing find:** `mobile/assets/glossary/terms.en.json` is a
bundled device copy of the glossary corpus, guarded by
`test_def325_glossary_asset_parity.py` (compares parsed JSON, corpus vs.
bundle, per id). Editing `content/glossary/terms.en.json`'s
`ami_pm_safety_floor.term` broke that parity test immediately. Fixed by
mirroring the identical one-line text change into the bundled copy (no other
change to that file) — this is the same "second derivation of one fact"
class DEF325 itself documents, not new scope. Confirmed green after the
mirror.

## Retranslation flag

This content family (`ai_coach`, `daily_challenges`, `glossary`) has **no
per-id `source_sha`/`retranslate` JSON field** — that mechanism
(`content/_authoring/locale_staleness_check.py`) only instruments
`content/lessons/*.mdx` frontmatter (lane B's territory). The standing
convention CR160 itself used for this same file family is a **commit-message
flag** (`64f0739e feat(CR160): rename six agent roles across EN content —
Debator era ends. retranslate:[ar,ms]`), not a per-item field. This commit
follows that same convention: `retranslate:[ar,ms]` in the trailer, covering
all 70 touched ids above except the six under `islamic_finance.json` (no
sibling exists) and the `ami_pm_safety_floor` glossary items which get their
own explicit line since the AR/MS glossary siblings already carry the old
`"مدير المحفظة"` / `"Portfolio Manager"` phrasing in that entry and were left
untouched (transcreation rule: CR160's Bull/Bear transcreation note doesn't
cover PM/CIO, so no invented AR/MS substitution was applied — only EN got the
fix, AR/MS wait for the i18n lane).

**Full list of ids needing `retranslate:[ar,ms]`** (AR/MS content
retranslation, once each family's translation pipeline runs): the 20 ids in
`ai_meta.json`, 11 in `platform.json`, 1 in `beginner.json`, 10 in
`2026_06.json`, 3 in `2026_07.json`, 2 in `2026_08.json`, 8 in `2026_09.json`,
10 in `2026_10.json`, 2 in `2026_11.json`, 1 in `2026_12.json`, and
`ami_pm_safety_floor` in the glossary — 66 ids total (the `islamic_finance.json`
item excluded per above). Exact id lists are reproducible from
`git diff content/ai_coach/*.json content/daily_challenges/*.json
content/glossary/terms.en.json` against this commit's parent.

## Ambiguous occurrences left alone (and why)

- **`content/i18n/lesson_confidence_log.json`** (50 "PM" mentions) and
  **`content/i18n/style_guide_ar_ms.md`** (1 "Portfolio Manager" mention,
  explicitly framed as *"the pre-CR160 labels"*) — both are translation-QA
  tooling logs, already carved out by `test_cr160_agent_rename.py`'s
  `_EXEMPT` regex. They quote historical strings verbatim as evidence of past
  translation errors; rewriting them would falsify the historical record they
  exist to preserve. Left untouched, matching how the existing guard already
  treats them.
- **`portfolio_manager` as an `agent_id`/`related_agent(s)` value**, wherever
  it appears (glossary `related_agents`, ai_coach/daily_challenges
  `related_agents`, daily-challenge quiz `options` arrays that literally list
  raw ids like `["portfolio_manager", "trader", "bear_researcher",
  "conservative_debator"]` in `dc_2026_07_15_drawdown_gate_owner`) — these are
  frozen identifiers per CR160's explicit "Out of scope" clause, not labels.
  Noted but **not fixed**: those quiz items render raw snake_case ids as
  user-facing answer text, which is a pre-existing display bug independent of
  PM/CIO naming — out of DEF423's scope, flagged here only so it isn't
  mistaken for something this sweep should have caught.
- **`content/_authoring/**`** — translation manifests and sweep logs
  (`cr060_*`, `cr172_*`, `cr223_*`, etc.) are tooling metadata, not rendered
  content; inspected, none render to users, left untouched per the task
  brief.
- **`content/support_kb/**`** — checked, zero occurrences of either
  `Portfolio Manager` or agent-role `PM` found. Nothing to fix.

## Guard gap (not fixed here — outside lane C's paths)

`backend/tests/unit/test_cr160_agent_rename.py`'s
`RETIRED_LABELS`/`test_retired_labels_absent_from_en_content_corpus` guards
the full phrase `"Portfolio Manager"` but has no check for the bare `PM`
abbreviation mixing with `CIO` — this is precisely the class DEF423 reports
and the class DEF410 flagged a week earlier in the lesson corpus. That test
file sits outside `content/**` (lane C's assigned paths) and is closely tied
to `content/agents/**`/`mobile/lib/models/agent.dart` (lane A's territory);
recommending lane A add a scoped guard (e.g. flag bare `PM` outside a
lowercase-time-of-day/`JPM`-ticker/pricing-tier context) rather than adding
one here, to avoid a second lane editing a shared test file this session.

## Tests

```
cd backend && .venv/bin/python -m pytest \
  tests/unit/test_ai_coach_service.py \
  tests/unit/test_daily_challenge_attempt.py \
  tests/unit/test_daily_challenge_service.py \
  tests/unit/test_def144_no_foreign_script_in_shipped_translations.py \
  tests/unit/test_def144_sensitive_content_is_gated_structurally.py \
  tests/unit/test_def325_glossary_asset_parity.py \
  tests/unit/test_def350_content_agent_ids_are_real.py \
  tests/unit/test_glossary_service.py \
  tests/unit/test_cr160_agent_rename.py \
  tests/unit/test_registers_no_drift.py \
  tests/unit/test_p30_registers_name_things_that_exist.py \
  -q -p no:cacheprovider
```

74 passed (0 failed). `test_def325_glossary_asset_parity.py` failed on first
run after the glossary edit (bundled `mobile/assets/glossary/terms.en.json`
drifted from the corpus) — fixed by mirroring the one-line change, re-ran
green. Full `pytest backend/tests/unit/ -q` also launched; see report body
for its result at hand-back time.
