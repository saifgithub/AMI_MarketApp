# DEF124 — No Room prompt states today's date, so agents invent the time until the next earnings

**Filed:** 2026-07-27 · **Track:** AT:R59 (room-quality) · **Kind:** Defect · **Area:** prompt / backend
**Found by:** the BBAI convene review (Saiful: *"i suspect we had hallucinations"*) — **this one is a
true hallucination**, unlike DEF123.

---

## What happened

BBAI run `1906ccf2-bae9-49c8-a83e-9e82e18ec144`, convened **2026-07-27**. The fact sheet's last
line read:

```
Next earnings (LIVE): 2026-07-30 (Q3)
```

Earnings were **3 days away**. Two agents told the Room otherwise:

- **News Analyst:** *"Earnings for Q3 are not scheduled until **2026-07-30**, leaving a **13-month
  void of reported data**"*
- **Research Manager:** *"no earnings data for **13 months**"* … *"the **3.0%** sizing cap is wasted
  on a position with **no clear catalyst until mid-2026**"*

The Research Manager's synthesis is the input the Trader, all three Risk debators and the PM
reason from, so the invented 13-month gap became the Room's premise. It survived into the
**Trader** (*"the next earnings catalyst not until 2026-07-30"* — correct, but framed as remote),
and into the **PM's recorded verdict reason**:

> *"the absence of earnings data until 2026-07-30 leaves the trade reliant on speculative sentiment
> rather than fundamental value"*

The verdict was `PASS`, which is defensible on the fundamentals alone — but part of the stated
rationale is a fabricated 13-month data void, and a user reading the transcript learns that a
company reporting in 72 hours has no catalyst for over a year.

## Root cause — the model is asked to do date arithmetic without one of the operands

**No Room prompt contains the current date.** Measured on melehost:

- BBAI run: **0 of 12** prompts contain the string `2026-07-27` (checked across `system_prompt`
  and `messages`).
- 30-day window, `flow='room'`: **2 of 9,789** prompts contain any date string outside the
  earnings line. Effectively zero.

`_format_profile` (`backend/app/services/room_prompts.py:459-465`) renders the earnings date as a
bare ISO date with no relative anchor:

```python
if profile.get("next_earnings_date"):
    lines.append(f"Next earnings (LIVE): {profile['next_earnings_date']}" + …)
```

The model has no "today" to subtract from, and the grounding directive forbids it from recalling
one — so it guesses, and the guess is unconstrained. LLM training cutoffs make a 2026 date read as
distant future by default, which is exactly the error observed.

**The correct pattern already exists three lines up, in the same file.**
`_forward_catalyst_text()` renders the FOMC date *relatively*, and the agents got it right every
time — the BBAI fact sheet said `FOMC decision in 2 days` and four agents quoted "2 days"
accurately. The machinery is there; the earnings line just doesn't use it.

## Why it matters

- It is a **true hallucination reaching the user-visible verdict reason**, not merely transcript
  colour.
- It is **cheap to eliminate structurally** (CR038: don't instruct the model to compute; hand it
  the computed value). A prompt line saying "today is X" would help, but the stronger fix — the one
  the FOMC line already demonstrates — is to render the interval directly.
- The Room's whole credibility rests on the fact sheet being the single source of truth. Half its
  dates are anchored and half are not.

## Proposed fix

1. Render the earnings line with the interval alongside the date, mirroring
   `_forward_catalyst_text()`:
   `Next earnings (LIVE): 2026-07-30 (Q3) — in 3 days`.
   Compute it in `_format_profile`/the profile builder, not in the prompt text.
2. Add the run date once to the shared fact-sheet header (`… as of 2026-07-27`) so any *other*
   absolute date in the block — present or future — is anchored. The disclosure header already
   says "as of this call"; make it say which call.
3. Sweep for other absolute dates the Room renders without an interval (the earnings line is the
   one found; check the news-recency strings, which already use relative form `3d ago`, and any
   1-on-1 / Brief Your Agent renderer that shares the profile).

## Verification

1. `cd backend && .venv/bin/python -m pytest tests/unit/ -q` green.
2. Unit test: profile with `next_earnings_date` = today + 3 days ⇒ rendered line contains
   `in 3 days`; today + 0 ⇒ `today`; a past date ⇒ handled explicitly, not negative-days.
3. Live smoke: convene a ticker reporting within the week; grep `llm_audit.response_text` for any
   agent stating a month/year gap.

## Related

**DEF123** (same convene, same fact sheet — provenance rather than anchoring), **DEF125** (same
convene — truncation), **CR038** (compute it, don't ask the model to), **CR098 Amendment 1** (same
renderer, `_format_profile`; sequence against it).
