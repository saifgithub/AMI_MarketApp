<!--
CR104-ROOM.auditor.md — auditor lane file (track U owns). State derives from
round numbers here vs CR104-ROOM.architect.md (see PROTOCOL.md).
-->

# CR104-ROOM — audit lane (auditor)

**Item:** delete the synthetic numeric baseline from the production Room path. `_profile_for_ticker`
built a complete fake company from `random.Random(zlib.crc32(ticker))` before any live fetch, then
overlaid live data and declared the whole block `"yfinance_live"`. DEF123 measured **178 of 842**
LIVE-declared Room prompts carrying an rng P/E across 36 tickers.

**Gate:** independent — changes what every agent is told is true, upstream of the safety floor's
inputs, and closes a live fabrication.

**Audited SHA:** `b1e4983`, off `main` @ `64033cc`. Isolated worktree
`.claude/worktrees/audit-CR104/`, own venv. **Provenance:** the worker's hand-off ends
`STATUS: NOT_READY` — correctly, it died at ~$1.7 of $15 with its confirmatory suite run still in
flight and refused to state a test count it had not read. The Architect closed that gap by
measurement and submitted, deliberately leaving a reproduced D4 finding **unfixed** for track U to
grade.

## Round 1

### Reproduced independently

| Check | Result |
|---|---|
| Scope | `git diff 64033cc b1e4983 --stat` — 14 files, **+661/−220**, exact match. |
| Full suite | **1368 passed** in 215s, clean tree, `__pycache__` cleared, run to completion before any mutation. `main` = 1366; `+2` = exactly the two new guard tests. |
| Fabrication actually gone | Walked `_profile_for_ticker`'s AST myself: `rng` appears at **4** nodes — line 366 is the constructor, 379/385/386 are `sentiment_tone`, `sentiment_score`, `mention_trend`. **No numeric derives from rng.** Matches the CR034 carve-out. |
| **D1** — per-block flags replaced, not left beside | `technicals_state`/`news_state`/`social_state` → **zero hits** across `backend/app` and `backend/tests`. Confirmed. |
| Guard detection path 1 | reintroduced `"pe": f"{rng.uniform(12,55):.1f}"` into the real baseline dict → **RED** |
| Guard detection path 2 | appended `profile["net_cash"] = int(rng.uniform(1, 900))` after the live merge → **RED** |

Both detection paths genuinely work **for the shapes they were built for**. The worker's
self-disclosed bug in its own first guard version (positional dict-literal matching fooled by
`field_state: dict[str,str] = {}`) is genuinely fixed — the guard now matches by assignment-target
name.

*Small correction to the D1 claim, not a finding:* the renderer's docstring also names `data_source`
as an eliminated block-level flag, and the Architect's grep list omitted it. I checked: it is gone
from `backend/app/` logic (only a historical mention survives in that docstring) but remains a dead
key in 5 test fixtures, which the renderer now ignores. Harmless — but the claim was verified
narrower than it was stated.

### MAJOR 1 — the guard is an allowlist, and one local variable defeats it *inside* the allowlist

The Architect's D4 finding reproduces. It is also worse than they found.

**A — new fields are unprotected.** Using my own field names rather than theirs, appended after the
live merge:

```python
profile["peg_ratio"] = f"{rng.uniform(0.4, 4.0):.2f}"
profile["fcf_yield"] = round(rng.uniform(1.0, 9.0), 2)
```

→ guard **2 passed**. `_PROTECTED_NUMERIC_FIELDS` enumerates 13 names; anything else is invisible.
D4 said the guard must fail if **any** rng-derived numeric can reach `_format_profile`, and named
this exact failure mode: *"A test enumerating today's six fields passes forever the day someone adds
a seventh."* Thirteen instead of six is a bigger allowlist, not an invariant.

**B — the 13 protected fields are only protected against a *direct* rng reference.** This the
Architect did not test. `_references_rng` walks the assigned expression for a `Name` node `rng`, so
one intermediate variable launders it:

```python
_v = rng.uniform(12.0, 55.0)
profile["pe"] = f"{_v:.1f}"
```

→ guard **2 passed**. That is **DEF123's literal original shape** — a fabricated `pe` on the
production path — sailing through the guard built to prevent DEF123, defeated by a local variable.
And it is not inert: it lands *after* the live merge, so on any convene where yfinance did supply a
P/E, `field_state["pe"] == "live"` and the renderer prints the **fabricated** value under the LIVE
header. That is 178-of-842 recreated exactly.

**Recommended shape** (the Architect proposed the same polarity inversion, and I agree): flag *any*
`profile[...]` assignment whose value is rng-tainted — following local assignments, not just direct
references — with the three narrative fields as an explicit, justified **exclusion** list.
Deny-by-default means a new field argues its way in rather than being silently unprotected.

### MAJOR 2 — the renderer's documented invariant is false, and I rendered the proof

`_format_profile`'s docstring is unambiguous:

> *"A numeric field renders ONLY when its state says 'live' … The disclosure header below is true by
> construction now, not by assertion: it can only describe what `field_state` actually recorded."*
> *"Fields absent from `field_state` entirely … render as not-available — refusal is the default,
> not a special case."*

Four call sites label `(LIVE)` on **presence alone**, never consulting `field_state`:
`room_prompts.py:545` (next earnings), `:599` (valuation), `:608` (sector/industry), `:616`
(dividend yield). The Architect enumerated nine optional fields; the `next_earnings_*` pair is a
fifth surface they did not list.

Rendered a profile with `field_state = {}` — **no provenance recorded for anything**:

```
- Numeric fundamentals (price, P/E, growth, margin, net cash): none available live this call —
  every such field below is marked not available.
...
Reference price: not available
P/E: not available
Market technicals: not available this call.
Valuation (LIVE): PEG 2.71, FCF yield 6.42%
Sector/industry (LIVE): Technology / Consumer Electronics
Dividend yield (LIVE): 4.31% (buybacks/M&A: not available, not claimed)
Next earnings (LIVE): 2026-08-14
```

The **same prompt** tells the model *"a field with no live source is marked not available below,
never silently filled in — do NOT estimate, recall from training memory, or invent a number for
it"* and then hands it four LIVE-labelled facts with no recorded source. That is a self-contradicting
disclosure header — structurally worse than DEF123, where a single block-level flag was wrong;
here the header explicitly promises per-field refusal and four lines break it in the same render.

These are **two independent, individually-sufficient** routes to a fabricated number under a LIVE
label, needing two different fixes: MAJOR 1 is guard polarity, MAJOR 2 is renderer gating. They also
compound — the guard cannot see it and the renderer labels it live.

**On the "sound today" defence.** The Architect is right that nothing is fabricated in production
right now: those fields are only populated from live yfinance data today. But that is precisely the
argument the CR's own thesis rejects — the disclosure is true by *call-site convention*, not by
construction, and this project has thirteen prior instances of convention failing (CR038: ~30%
compliance). D4 is this lane's core deliverable and it is measurably unmet.

### Acceptance deviation — agreed, and correctly framed

The CR requires *"the 178-of-842 count must be 0, and stay 0."* The harness
(`backend/scripts/def123_corpus_check.py`) reproduces DEF123's original numbers exactly — those rows
are historical, served before the fix existed, and cannot retroactively read 0. A true 0 needs the
fix on Alpha plus a re-run filtered to prompts generated after that timestamp, and `main` is under a
promotion hold. I agree this is an **open acceptance item, not a satisfied one** — it does not
change my verdict either way, but the CR is not fully closed until it reads 0 post-promote.

I did **not** re-execute the harness: it queries `llm_audit` on melehost, unreachable from the Mac
(pure editor). Confirmed only that the script exists and is re-runnable in shape.

### FLAGS carried forward — Saiful's calls, not mine

1. **Outage behaviour is visibly thinner** — `P/E: not available` instead of a fabricated number.
   Correct per CR040, but the mobile client has no "intentionally thin" rendering and cannot
   distinguish genuinely-absent from withheld-for-tenure. Bears directly on `CR098-MOBILE-LIVE` /
   `CR098-MOBILE-VERDICT`, both still unbuilt — the same promotion-sequencing coupling I recorded
   on CR090-ROOM and CR098-ROOM.
2. **Degradation is uneven by ticker class** — loss-making names lose the P/E line every convene
   (yfinance has no `trailingPE` for negative earnings; the ratio is mathematically undefined, not a
   fetch failure). ETFs lose the whole company-fundamentals block, which is correct for a fund.
3. **The corpus harness is reusable in shape** for CR037/CR038's undecided guards but not as-is.

### Findings

1. **MAJOR** — the guard is an allowlist over 13 field names (new fields invisible: reproduced with
   `peg_ratio`/`fcf_yield`), **and** within that allowlist it only detects a *direct* rng reference —
   `_v = rng.uniform(...)` then `profile["pe"] = f"{_v:.1f}"` passes green, recreating DEF123's exact
   original shape on the production path.
2. **MAJOR** — `_format_profile`'s documented "refusal is the default" invariant is false: four call
   sites (`:545`, `:599`, `:608`, `:616`) label `(LIVE)` on presence without consulting
   `field_state`. Rendered a `field_state={}` profile producing four LIVE-labelled lines directly
   under a header promising the opposite.

### Verdict

**VERDICT: AWAITING_FIXES (round 1)** — two MAJOR. (Round 1 is the round *audited*.)

What the lane actually deletes, it deletes properly: the rng numeric baseline is genuinely gone,
D1's per-block flags are genuinely replaced, and both guard detection paths work for the shapes they
target. The submission is also unusually honest — the worker refused to claim an unread test count,
self-disclosed a bug in its own first guard, and the Architect reproduced a finding against the
lane's core deliverable rather than shipping past it.

But D4 is the deliverable, and it is unmet on two independent counts, both of which I reproduced —
one of them recreating DEF123 itself in the CR written to eliminate DEF123.

Run report: [`../runs/2026-07-27_run-69/run_report.md`](../runs/2026-07-27_run-69/run_report.md)
