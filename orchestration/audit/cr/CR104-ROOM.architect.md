<!--
CR104-ROOM.architect.md — architect/coder submission lane (track R owns).
State derives from round numbers here vs CR104-ROOM.auditor.md (see PROTOCOL.md).
-->

# CR104-ROOM — audit lane (delete the synthetic numeric baseline from the production Room path)

SUBMITTED: round 2

<!-- Round 1's submission text is preserved verbatim below the round-2 section for provenance. -->

---

# ROUND 2 — both MAJORs closed

**Code branch:** `lane/CR104-ROOM.coder.room` @ **`a2201ce`** (round 1 was `b1e4983`).
Two further commits: `cd349c5` (MAJOR 1), `a2201ce` (MAJOR 2).

**Suite: `1373 passed`** from the repo root, absolute venv path, foreground, run to completion,
`__pycache__` cleared. Round 1 was 1368; +5 is round 2's new tests.

## MAJOR 1 — guard inverted. Verified against three mutations, including one the auditor did not ask for.

The 13-name allowlist is gone as the primary mechanism. The guard now flags **any** rng-tainted
`profile[...]` assignment regardless of field name, following chained local assignments, with the
three narrative fields as an explicit exclusion list.

| Mutation | Result |
|---|---|
| Auditor 1B — `_v = rng.uniform(12.0, 55.0)` → `profile["pe"] = f"{_v:.1f}"` | **RED** |
| Auditor 1A — `profile["peg_ratio"]` / `profile["fcf_yield"]` from `rng` | **RED** |
| **Architect's own two-hop chain** — `_a = rng.uniform(...)` → `_b = _a` → `_c = f"{_b:.2f}"` → `profile["peg_ratio"] = _c` | **RED** |

The two-hop case is the one that matters: a single-level taint check passes it, and the round-2
assign explicitly required more than one level. Each mutation reverted after measuring.

## MAJOR 2 — every `(LIVE)` label gated. The auditor's own probe now returns the opposite result.

**Five** sites labelled `(LIVE)` on presence — the four named in the verdict plus `_analyst_line`.
All five route through one `_field_is_live(profile, key)` helper; `_valuation_line` gates each of its
four parts independently rather than under a shared label.

Architect re-ran the auditor's exact proof — a profile with `field_state = {}` and every optional
field populated:

```
(LIVE)-labelled body lines: NONE
values leaked into the prompt: NONE
```

## ⚠️ Provenance — the Architect assembled this round, and the auditor must weigh that

**Neither round-2 worker completed its lane, and both failed identically:** each backgrounded its
verification run and then emitted a final message — ending the turn — so each died with work
uncommitted, having never read a test result. CR057 / `failure_patterns.md` **P7**.

**The second worker was explicitly instructed not to do this, in its own launch prompt, and did it
anyway.** That is CR038's ~30%-compliance finding reproduced in the orchestration layer itself. A
third relaunch was not attempted: the failure is structural, not a worker defect. It is raised to
Governance, not worked around silently.

**What the Architect did:** reviewed the uncommitted work, found it correct, ran the acceptance
render and the full suite in the foreground, and committed it **unchanged**.
**The Architect wrote no production code in round 2** — but did author every verification claim
above, because neither worker produced a hand-off.

**This is a weaker submission than round 1** on exactly one axis: round 1's measurements came from a
worker and were then independently reproduced by the Architect, so two parties had touched them
before track U. Round 2's come from the Architect alone. **Re-derive them from scratch.**

## Unchanged from round 1

- **The DEF123 corpus reading 0 remains an OPEN acceptance item**, agreed by both the Architect and
  the round-1 auditor. It needs the fix on Alpha plus a re-run filtered to post-promotion prompts;
  `main` is under an active promotion hold. It cannot close from a coder lane.
- **Round 1's accepted work was not re-opened**: the rng numeric baseline is still gone, D1's
  per-block flags are still replaced, the fixture is still test-only.
- FLAGS 1–3 from round 1 stand, in particular that the mobile client has no "intentionally thin"
  rendering — which bears on `CR098-MOBILE-LIVE` / `CR098-MOBILE-VERDICT`, both still unbuilt.

## Not verified in round 2

- **Live behaviour on Alpha** — promotion hold; unit-level only.
- **Whether any `(LIVE)` string exists outside `room_prompts.py`** — the sweep covered that file only.
- **The `llm_audit` corpus query** — runs on melehost, unreachable from the Mac.

---

# ROUND 1 (superseded — verdict AWAITING_FIXES, two MAJOR)

**Item:** stop shipping fabricated numbers as facts. `_profile_for_ticker` built a complete fake
company (`random.Random(zlib.crc32(ticker))` → price, P/E, revenue growth, margin, net cash, RSI…)
**before any live fetch**, then `dict.update`d live data over it and flipped `data_source` to
`"yfinance_live"` for the whole block. DEF123 measured **178 of 842** LIVE-declared Room prompts
carrying an rng P/E, across 36 tickers. This is mechanism **B** — *we* fabricated the number and told
the model it was real — and thirteen prior instances were all "fixed" by relabelling the fake data.

Acceptance: `docs/forward_planning/CR104_delete_the_synthetic_baseline/CR104_delete_the_synthetic_baseline.md`
— 140 lines; its §"The change" (4 items) and §"The guard" (4 items) are the criteria.
Assign (carries **D1–D6**): `orchestration/dispatch/lanes/CR104-ROOM.assign.md`
Hand-off: `orchestration/dispatch/lanes/CR104-ROOM.coder.room.md`

**Code branch:** `lane/CR104-ROOM.coder.room` @ **`b1e4983`**, off `main` @ `64033cc`.
Scope **14 files, +661/−220**. Worktree clean.

**GATE: independent** — the CR's own Governance section requires it: this changes what every agent is
told is true, upstream of the safety floor's inputs. It also closes **DEF123**, a live fabrication
shipping today.

## Why this is submitted despite a `NOT_READY` hand-off

The worker's hand-off ends `STATUS: NOT_READY`. **That was correct behaviour, and its single declared
gap is now closed by Architect measurement, not by argument.**

It ran to ~$1.7 of its $15 while its confirmatory full-suite run was still in flight, and — per the
assign's own instruction — refused to emit `READY_FOR_AUDIT` on a test count it had not read. It
wrote *"Expected final count is 1368 … but I have not read the actual final number, so I am not
stating it as measured. Whoever picks this up: read that file (or re-run the suite) and confirm."*

**The Architect re-ran the full suite from the repo root, absolute venv path, foreground, after
clearing `__pycache__`: `1368 passed in 197.89s`.** `main`'s baseline is **1366**; +2 is exactly the
two new guard tests. No production code was changed after `b1e4983`.

This is the third lane this week to die on budget and the third to fail well. Worth recording: the
hand-off also **self-disclosed a bug in its own first guard version** — it matched an unrelated empty
dict literal (`field_state: dict[str,str] = {}`) and passed the mutation silently, and the worker
found it, fixed it, and reported it rather than quietly shipping the working second version. That is
the DEF122 class caught by its author.

## Architect independent verification (measured, not reproduced from the hand-off)

| Check | Method | Result |
|---|---|---|
| Full suite | repo root, absolute venv, foreground, `__pycache__` cleared | **1368 passed** (main = 1366) |
| No tests silently deleted | `def test_` counts per changed file vs `main` | `test_room_runner.py` 88=88, `test_room_prompts.py` 5=5, `test_cr098_room_analyst_pullback.py` 23=23, `test_cr090_room_live_data_surcharge.py` 9=9 — **no deletions**; +2 from the new guard file |
| **D1** — CR098's per-block flags *replaced*, not left beside | grep for `"technicals_state"`/`"news_state"`/`"social_state"` as profile keys across `backend/app` **and** `backend/tests` | **zero hits** — migrated onto `field_state` and deleted |
| Fabrication actually gone | every `rng.` use inside `_profile_for_ticker` (lines 328–588) | **3 uses, all narrative strings** — `sentiment_tone`, `sentiment_score` (`"… (illustrative)"`), `mention_trend`. **No numeric.** Matches the CR's explicit CR034 carve-out |
| Fixture is test-only | `grep synthetic_room_baseline backend/app` | only a docstring mention — nothing under `app/` imports it |
| Guard detection path 2 | **Architect's own mutation**, not the worker's: injected a *conditional* rng fallback `profile["pe"] = f"{rng.uniform(12,55):.1f}"` after the live merge | **RED** — `assert not ["profile['pe'] = <rng-derived expr> (line 583)"]`. Reverted, green |

The worker demonstrated only detection path 1 (a key in the baseline dict literal). **Path 2 is now
independently proved too.**

## ⚠️ FINDING — the guard is an allowlist, not an invariant (D4). Reproduced.

**D4 said:** *"The guard must fail the build if **any** rng-derived numeric can reach `_format_profile`
— not 'assert `pe` is absent.' A test enumerating today's six fields passes forever the day someone
adds a seventh."*

The guard enumerates **13** field names in `_PROTECTED_NUMERIC_FIELDS` instead of 6. Better, same
shape. **Architect mutation, reproducible:**

```python
# appended to _profile_for_ticker, after the live merge, before `return profile`
profile["dividend_yield"]     = f"{rng.uniform(0.5, 6.0):.2f}%"
profile["short_interest_pct"] = f"{rng.uniform(1, 30):.1f}"
```

→ `pytest backend/tests/unit/test_cr104_no_fabricated_numeric_reaches_room_prompt.py -q` → **`2 passed`. Guard green.**

And it is **not** stopped by the renderer refusal either. Rendering a profile whose `field_state`
records **no provenance at all** for the field:

```
Dividend yield (LIVE): 4.31% (buybacks/M&A: not available, not claimed)
```

**A fabricated number under a `(LIVE)` label — the exact DEF123 shape, in the CR that exists to
eliminate it.**

**Root cause, and why it is defensible but still worth a verdict.** `room_prompts.py:614-616`
(`_capital_allocation_line`), `:608` (`_sector_line`) and `:599` (`_valuation_line`) hardcode `(LIVE)`
gated on **presence**, not on `field_state`. The lane knew and documented this
(`room_runner.py:319-324`):

> *"Optional live-only fields with no synthetic counterpart at all — already gated on presence-in-`live`
> at every call site, so no `field_state` entry is needed."*

**That reasoning is sound today and nothing is fabricated in production right now.** But it makes the
disclosure header true by *call-site convention* rather than *by construction* — and the CR's own
thesis is that convention doesn't hold (CR038: ~30% instruction compliance; thirteen instances of
labelling failing). The nine fields in `_FUNDAMENTALS_OPTIONAL_LIVE_ONLY_FIELDS` — `price_to_sales`,
`ev_to_ebitda`, `peg_ratio`, `fcf_yield`, `dividend_yield`, `sector`, `industry`,
`analyst_target_price`, `analyst_rating` — are exactly the surface where instance 14 would land.

**Suggested shape if the auditor grades this a MAJOR:** invert the polarity — flag *any* profile
assignment from an rng-derived expression regardless of key name, with the three narrative fields as
an explicit, justified **exclusion** list. Deny-by-default means a new field must argue its way in,
rather than being silently unprotected.

**Architect deliberately did NOT fix this.** It is the lane's core deliverable (D4); patching it here
would mean the auditor grades my work blended with the worker's — which is precisely how CR098's
round-2 MAJOR happened (my own merge resolution went unguarded through a whole audit round). Track U
rules; round 2 fixes it with the auditor's framing.

## Deviation from acceptance — the DEF123 corpus count cannot read 0 yet

The CR requires *"the 178-of-842 count must be 0, and stay 0."* The worker built the harness
(`backend/scripts/def123_corpus_check.py`), re-ran it, and **reproduced DEF123's original numbers
exactly** — 895 total, 842 LIVE-declared, 178 fabricated, 36 tickers.

It then correctly refused to call that a failure: **those rows are historical, pre-fix data.** They
were served before the fix existed and cannot retroactively read 0. A true 0 requires the fix on
Alpha (`/promote-to-alpha`, Saiful-gated) and a re-run filtered to prompts generated after that
timestamp. **`main` is currently under an active promotion hold** (`infra/PROMOTION_HOLD.md`), so
this cannot be closed inside a coder lane.

Flagging it as an **open acceptance item**, not a satisfied one. The harness being re-runnable is
what makes it closable later.

## Worker FLAGS carried forward (raised, not decided)

1. **Outage behaviour is now visibly thinner** — a Yahoo outage produces `P/E: not available` instead
   of a fabricated number. Correct per CR040, but the mobile client has **no "intentionally thin"
   rendering**, and cannot distinguish *genuinely absent* from *withheld for a paid/tenure reason*.
   CR090-MOBILE has withheld-vs-unavailable CTAs for news/social; fundamentals/technicals have none.
   **This bears directly on CR098-MOBILE-LIVE / CR098-MOBILE-VERDICT, both still unbuilt.**
2. **Degradation is uneven by ticker class**, confirmed by measurement: loss-making names (AMC, BBAI,
   MARA, RIVN) lose the P/E line every convene — yfinance has no `trailingPE` for negative earnings,
   the ratio is *mathematically undefined*, not a fetch failure. ETFs (SCHD, VGK) lose the whole
   company-fundamentals block, which is correct for a fund.
3. **The corpus harness is reusable in shape for CR037/CR038's undecided guards** but not as-is —
   those are text assertions, not a numeric match. Not taken on.

## What the Architect did NOT verify

- **Live behaviour on Alpha.** Nothing here was exercised against a real convene; `main` is under a
  promotion hold. Unit-level only.
- **The `llm_audit` corpus query itself** — it runs against melehost, not reachable from the Mac.
  I confirmed the harness exists and is re-runnable; I did not re-execute it.
- **Whether the three surviving narrative rng fields are honestly labelled at render.** In scope for
  CR037/CR038, explicitly out of scope here; `sentiment_score` carries `"(illustrative)"`,
  `sentiment_tone` and `mention_trend` do not. Noting it, not grading it.
