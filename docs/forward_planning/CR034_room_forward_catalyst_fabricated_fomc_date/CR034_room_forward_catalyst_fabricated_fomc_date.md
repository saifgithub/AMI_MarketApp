# CR034 — Room's "forward_catalyst" FOMC date was a frozen literal, never real

**Status:** done · **Session:** AT:R58 · **Date:** 2026-07-13
**Source:** Saiful, verifying a live HPQ Room convene right after DEF051–055 shipped —
noticed the News Analyst's transcript said "FOMC decisions in 11 days" and asked for it
to be fixed, filed as a CR.

## Problem

`room_runner.py::_profile_for_ticker()` set:

```python
"forward_catalyst": "FOMC decision in 11 days, sector earnings in 3 weeks",
```

as a hardcoded literal, unconditionally, for every ticker, every run, forever. Unlike
the disclosed-synthetic fields it sits next to (`macro_tone`, `fed_tone`, `fed_impact`
— genuinely unmeasurable qualitative flavor text), "in 11 days" is a **specific,
falsifiable factual claim** that was only ever true on the one calendar day it was
written. Verified against the Fed's real 2026 meeting calendar
(federalreserve.gov/monetarypolicy/fomccalendars.htm): the next meeting after
2026-07-13 is **July 28-29** — 16 days out, not 11.

A second, smaller issue: `room_prompts.py::_catalyst_line()` tells the *LLM* this field
is `"forward (synthetic, illustrative — no real macro/earnings-calendar feed)"`, but
that qualifier lives in a separate part of the system prompt, not inside the
`forward_catalyst` value itself. Sibling synthetic fields (`sentiment_score`,
`mention_trend`) bake `"(illustrative)"` directly into their string value, so it
survives into the agent's final prose no matter what the LLM does with the rest of the
prompt. `forward_catalyst` didn't follow that convention, so the live HPQ transcript
stated the fabricated day-count as flat fact with no visible caveat to the end user.

## Fix

`backend/app/services/room_runner.py`:

- Added `_FOMC_DECISION_DATES` — the Fed's published 2026 meeting decision dates
  (2nd day of each 2-day meeting), sourced from the official calendar. Needs a manual
  refresh once the Fed publishes next year's schedule (same maintenance shape as any
  hardcoded reference-data table in this codebase).
- Added `_forward_catalyst_text(today: date | None = None)` — computes the real
  days-to-next-FOMC-decision from the real calendar (`today` param exists purely for
  test injection; production calls use `datetime.now(timezone.utc).date()`).
  Degrades to `"next FOMC decision date not yet published"` past the last hardcoded
  date rather than silently going stale or crashing.
- `sector earnings season` timing has no real feed (same gap CR023 already
  disclosed for News) — kept, but now baked in as `"(illustrative, not
  date-verified)"` directly in the value string, matching the sentiment-field
  convention, so the disclosure can't get dropped by the LLM.
- `profile["forward_catalyst"]` now calls `_forward_catalyst_text()` instead of the
  frozen literal.

`macro_tone`/`fed_tone`/`fed_impact` are unchanged — genuinely unmeasurable qualitative
framing, already disclosed via `room_prompts.py`'s separate "(synthetic, illustrative)"
header line, out of scope here.

## Testing

`backend/tests/unit/test_room_runner.py`:
- Updated `test_profile_overlays_live_news_when_enabled` — was asserting the exact
  frozen string; now asserts the real-computed shape.
- 4 new tests on `_forward_catalyst_text` directly (mid-year countdown, decision-day-
  itself, singular "1 day" grammar, past-last-published-date degradation).
- 1 new test confirming `_profile_for_ticker`'s real-clock call path (no `today`
  override) produces the same shape.

Full suite: 738 passed (was 733).

## Not in scope

- A genuine per-sector earnings-season calendar (would need a new data source/feed,
  same shape of research CR023/CR024 already did for News/Social — not attempted here).
- Annual refresh automation for `_FOMC_DECISION_DATES` — manual for now, same as other
  reference-data tables in this codebase.
