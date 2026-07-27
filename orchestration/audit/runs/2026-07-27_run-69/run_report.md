<!--
Auditor run report — run-69 (2026-07-27, session auditor.core/track U). Round-1
audit of CR104-ROOM. Audited SHA b1e4983. Verdict AWAITING_FIXES — two MAJOR,
both reproduced. Owner: AUDITOR.
-->

# run-69 (round 1) — CR104-ROOM delete the synthetic baseline → AWAITING_FIXES

- **Auditor session:** auditor.core (track U), 2026-07-27.
- **Audited SHA:** `b1e4983`, off `main` @ `64033cc`. Isolated worktree
  `.claude/worktrees/audit-CR104/`, own venv.
- **The item:** `_profile_for_ticker` built a complete fake company from
  `random.Random(zlib.crc32(ticker))` **before any live fetch**, then overlaid live data and flipped
  `data_source` to `"yfinance_live"` for the whole block. DEF123 measured **178 of 842**
  LIVE-declared Room prompts carrying an rng P/E across 36 tickers. Thirteen prior instances of this
  class were all "fixed" by relabelling the fake data rather than removing it.
- **Gate:** independent — changes what every agent is told is true, upstream of the safety floor's
  inputs, and closes a live fabrication.
- **Provenance:** the worker's hand-off ends `STATUS: NOT_READY`, correctly — it died at ~$1.7 of a
  $15 cap with its confirmatory suite run still in flight and refused to state a test count it had
  not read. The Architect closed that gap by measurement and submitted, **deliberately leaving a
  reproduced D4 finding unfixed** for track U to grade, on the explicit reasoning that patching it
  themselves would blend their work into the audit — which is how CR098's round-2 MAJOR happened.

## Reproduced independently

Scope: 14 files, **+661/−220**, exact match. Full suite: **1368 passed** in 215s on a clean tree
with `__pycache__` cleared, run to completion before any mutation touched the tree. `main` = 1366;
`+2` = exactly the two new guard tests.

**Fabrication actually gone.** Rather than grep, walked `_profile_for_ticker`'s AST: `rng` appears
at 4 nodes — line 366 is the `random.Random(...)` constructor, and 379/385/386 are `sentiment_tone`,
`sentiment_score`, `mention_trend`. **No numeric fact derives from rng.** Matches the CR034
illustrative-scaffolding carve-out the CR explicitly preserves.

**D1 — per-block flags replaced, not left beside.** `technicals_state` / `news_state` /
`social_state` as profile keys → **zero hits** across `backend/app` and `backend/tests`. Confirmed.

*Correction to the D1 claim, recorded but not scored:* the renderer docstring also names
`data_source` among the eliminated block-level flags, and the Architect's grep list omitted it. I
checked — it is gone from `backend/app/` logic (only a historical mention survives inside that
docstring) but remains a dead key in 5 test fixtures, which the renderer ignores. Harmless; the
claim was simply verified narrower than it was stated.

**Both guard detection paths work for their intended shapes**, re-proved with my own mutations:

| Path | Mutation | Result |
|---|---|---|
| 1 — protected key in the unconditional baseline dict | reintroduced `"pe": f"{rng.uniform(12,55):.1f}"` into the real `profile = {...}` literal | **RED** |
| 2 — direct rng expression on a protected field | appended `profile["net_cash"] = int(rng.uniform(1, 900))` after the live merge | **RED** |

The worker's self-disclosed bug in its own first guard version — positional dict-literal matching
fooled by `field_state: dict[str,str] = {}` appearing earlier in source — is genuinely fixed; the
guard now matches by assignment-target name. Worth recording that the worker found, fixed and
**reported** that rather than quietly shipping the working second version.

## MAJOR 1 — the guard is an allowlist, and one local variable defeats it *inside* the allowlist

The Architect's D4 finding reproduces. It is also worse than they found.

**A — new fields are unprotected.** Used my own field names rather than theirs (they used
`dividend_yield`/`short_interest_pct`), appended after the live merge:

```python
profile["peg_ratio"] = f"{rng.uniform(0.4, 4.0):.2f}"
profile["fcf_yield"] = round(rng.uniform(1.0, 9.0), 2)
```

→ guard **2 passed**. `_PROTECTED_NUMERIC_FIELDS` enumerates 13 names and both tests intersect
against that set, so anything outside it is structurally invisible. D4 named this exact failure
mode: *"A test enumerating today's six fields passes forever the day someone adds a seventh."*
Thirteen instead of six is a longer allowlist, not the invariant D4 required.

**B — the 13 protected fields are only protected against a *direct* rng reference.** The Architect
did not test this. `_references_rng` walks the assigned expression looking for a `Name` node `rng`,
so a single intermediate variable launders it:

```python
_v = rng.uniform(12.0, 55.0)
profile["pe"] = f"{_v:.1f}"
```

→ guard **2 passed**.

That is **DEF123's literal original shape** — a fabricated `pe` on the production path — passing the
guard built to prevent DEF123, defeated by one local variable. It is not inert either: the injection
lands *after* the live merge, so on any convene where yfinance did supply a P/E,
`field_state["pe"] == "live"` and the renderer prints the **fabricated** value under the LIVE header.
That is the 178-of-842 condition recreated exactly.

**Recommended shape.** The Architect proposed inverting the polarity and I agree, with one
addition: flag *any* `profile[...]` assignment whose value is rng-tainted, **following local
assignments** rather than only direct references, with the three narrative fields as an explicit,
justified exclusion list. Deny-by-default means a new field must argue its way in.

## MAJOR 2 — the renderer's documented invariant is false, and I rendered the proof

`_format_profile`'s docstring is unambiguous about what the whole fix rests on:

> *"A numeric field renders ONLY when its state says 'live' … The disclosure header below is true by
> construction now, not by assertion: it can only describe what `field_state` actually recorded."*
> *"Fields absent from `field_state` entirely … render as not-available — refusal is the default,
> not a special case."*

Four call sites label `(LIVE)` on **presence alone**, never consulting `field_state`:
`room_prompts.py:545` (next earnings), `:599` (valuation), `:608` (sector/industry), `:616`
(dividend yield). The Architect enumerated nine optional fields as the exposed surface; the
`next_earnings_*` pair is a fifth line they did not list.

Rendered a profile with `field_state = {}` — no provenance recorded for anything:

```
Data source disclosure — every fact below is tagged with where it came from. A field with no live
source is marked not available below, never silently filled in — do NOT estimate, recall from
training memory, or invent a number for it:
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

The **same prompt** instructs the model that any field without a live source is marked not available
and must never be invented — and then hands it four LIVE-labelled facts with no recorded source.
This is structurally worse than DEF123: there, one block-level flag was wrong; here the header
explicitly promises per-field refusal and four lines in the same render break that promise.

## Why these are two findings, not one

They are **independent and individually sufficient** routes to a fabricated number under a LIVE
label, and they need different fixes:

- MAJOR 1 is guard polarity — it lets fabrication into a **protected** field, which the renderer
  *does* gate, but which renders as LIVE whenever the live fetch also succeeded.
- MAJOR 2 is renderer gating — it needs no guard evasion at all, because those four lines never
  consult provenance.

Fixing either one alone leaves the other open. They also compound: the guard cannot see it and the
renderer labels it live.

**On the "sound today" defence.** The Architect is right that nothing is fabricated in production
right now — those optional fields are only populated from live yfinance data. But that is exactly
the argument this CR's own thesis rejects: the disclosure is true by *call-site convention* rather
than by construction, and the project has thirteen prior instances of convention failing (CR038
measured ~30% instruction compliance). D4 is this lane's core deliverable and it is measurably unmet.

## Acceptance deviation — agreed, and correctly framed

The CR requires *"the 178-of-842 count must be 0, and stay 0."* The harness
(`backend/scripts/def123_corpus_check.py`) reproduces DEF123's original numbers exactly — 895 total,
842 LIVE-declared, 178 fabricated, 36 tickers. Those rows are **historical**, served before the fix
existed, and cannot retroactively read 0. A true 0 requires the fix on Alpha plus a re-run filtered
to prompts generated after that timestamp, and `main` is under an active promotion hold.

I agree with the Architect's framing: an **open acceptance item, not a satisfied one**. It does not
change the verdict either way, but the CR is not fully closed until it reads 0 post-promote, and the
re-runnable harness is what makes that closable.

**Not verified by me:** the harness itself queries `llm_audit` on melehost, unreachable from the Mac
(pure editor). I confirmed only that the script exists and is re-runnable in shape — same limitation
the Architect disclosed.

## FLAGS carried forward — Saiful's calls, recorded not decided

1. **Outage behaviour is visibly thinner** — a Yahoo outage now yields `P/E: not available` instead
   of a fabricated number. Correct per CR040, but the mobile client has no "intentionally thin"
   rendering and cannot distinguish genuinely-absent from withheld-for-tenure. This bears directly
   on `CR098-MOBILE-LIVE` / `CR098-MOBILE-VERDICT`, both still unbuilt — the same
   promotion-sequencing coupling I recorded on CR090-ROOM and again on CR098-ROOM.
2. **Degradation is uneven by ticker class**, confirmed by the lane's own measurement: loss-making
   names lose the P/E line every convene (yfinance has no `trailingPE` for negative earnings — the
   ratio is mathematically undefined, not a fetch failure), and ETFs lose the whole
   company-fundamentals block, which is correct for a fund.
3. **The corpus harness is reusable in shape** for CR037/CR038's undecided guards, but not as-is —
   those are text assertions, not a numeric match.

## Findings

1. **MAJOR** — the guard is an allowlist over 13 field names (new fields invisible — reproduced with
   `peg_ratio`/`fcf_yield`), **and** within that allowlist it detects only a *direct* rng reference:
   `_v = rng.uniform(...)` then `profile["pe"] = f"{_v:.1f}"` passes green, recreating DEF123's exact
   original shape on the production path.
2. **MAJOR** — `_format_profile`'s documented "refusal is the default" invariant is false. Four call
   sites (`:545`, `:599`, `:608`, `:616`) label `(LIVE)` on presence without consulting
   `field_state`; rendering a `field_state={}` profile produces four LIVE-labelled lines directly
   under a header promising the opposite.

## Verdict

**VERDICT: AWAITING_FIXES (round 1)** — two MAJOR.

What this lane deletes, it deletes properly. The rng numeric baseline is genuinely gone from the
production path, D1's per-block flags are genuinely replaced by per-field `field_state`, and both
guard detection paths work for the shapes they target. The submission is also unusually honest: the
worker refused to claim a test count it had not read, self-disclosed a bug in its own first guard
version, and the Architect reproduced a finding against the lane's core deliverable and left it
standing rather than shipping past it.

But D4 *is* the deliverable, and it is unmet on two independent counts, both reproduced here — one
of which recreates DEF123 itself inside the CR written to eliminate DEF123.
