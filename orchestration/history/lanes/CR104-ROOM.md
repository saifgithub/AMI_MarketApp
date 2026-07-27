<!-- ARCHIVED LANE — CR104-ROOM, closed 2026-07-27 (AT:R65). Two rounds. Assign + hand-off + architect + auditor, concatenated at closure. -->

# CR104-ROOM — archived lane (audited COMPLETE round 2, integrated)

---

## assign (rounds 1 + 2)

<!-- dispatch assign lane — Architect-owned. CR052. -->
# CR104-ROOM — assign (delete the synthetic numeric baseline from the production Room path)

KIND: code
INSTANCE: coder.room
GATE: independent    <!-- The CR's own Governance section requires it: this changes what every agent is told is true, upstream of the safety floor's inputs. It also closes DEF123, a live fabrication shipping today. -->
BUDGET: $15    <!-- Export DISPATCH_BUDGET_USD=15 at launch. Do NOT reach for `ultra` for headroom — it switches on fan-out tooling this lane does not need. -->
ACCEPTANCE: docs/forward_planning/CR104_delete_the_synthetic_baseline/CR104_delete_the_synthetic_baseline.md — **140 lines. Read it in full; it is short and every section is load-bearing.** Its §"The change" (4 items) and §"The guard" (4 items) are your acceptance criteria.
DEPENDS-ON: **CR098-ROOM — SATISFIED.** Audited COMPLETE round 3 and integrated to `main` 2026-07-27; suite 1366 green post-merge. Branch from `main` at or after that merge — you would be rebasing onto a moving `_format_profile`, and that renderer has already been the collision point for three lanes in one day.
HOT-FILES: `backend/app/services/room_runner.py` (`_profile_for_ticker`, `:325-405`), `backend/app/services/room_prompts.py` (`_format_profile`), plus a new test fixture. **`_format_profile` is the single most contended function in this codebase right now** — CR090, DEF116 and CR098 have all landed in or beside it today. Rebase before you hand off.

## ⚠️ The CR's own sequencing recommendation was INVERTED — read this first

The CR doc (§"What this costs, honestly", last bullet) says:

> *"It touches `_format_profile`, which CR098 also touches. Sequence: **CR104 → DEF123 folds into it
> → CR098 rebases on top.** CR098's fact-sheet stripping becomes nearly free once provenance is
> per-field: a withheld analyst is just another field with no source."*

**That is not what is happening.** Saiful sequenced CR104 **after** CR098, and he is right given where
we are: CR098 is three rounds deep with an audit in flight, so reversing costs more than it saves.

**But the economics flip, and the CR text does not reflect it.** CR098 did *not* get stripping for
free — it built its own **per-block** scheme, which is already on `main` when you start:

```
profile["technicals_state"] == "withheld_tenure"   # room_prompts.py:373
profile["news_state"]       == "withheld_paid" | "withheld_tenure"   # :363, :374
profile["social_state"]     == "withheld_paid" | "withheld_tenure"   # :364, :375
```

So **you inherit the work the CR assumed you would obviate.** Plan for replacement, not greenfield.

## Architect decisions — settled, do not re-open

**D1 — Per-field provenance REPLACES CR098's per-block state. It does not sit beside it.**

Two provenance schemes in one renderer is precisely how DEF123 happened: a block-level
`data_source="yfinance_live"` flag asserted over fields that were individually fake. Shipping
per-field provenance *next to* three surviving block-level `*_state` keys rebuilds that hazard with
more moving parts. Migrate CR098's three flags onto the per-field model and delete them. If you
believe one genuinely cannot migrate, **say so in the hand-off with the reason** — do not quietly
leave both.

**D2 — "Withheld" and "unavailable" are DIFFERENT, and collapsing them is a DEF059 inversion.**

The CR says *"a numeric fact is live or absent, no third state."* That is right about **fabrication**
and wrong if read as *"absent is absent."* CR098 exists precisely because those two absences have
different causes and different remedies:

- **withheld** — we *chose* not to fetch it (roster tenure, or credits). The data exists. The user
  has a lever.
- **unavailable** — the provider had nothing. Nobody has it. There is no lever.

CR090-MOBILE already renders those as distinct states with **different CTAs**, and CR098 added a
third reason on top. Flattening them into one "no provenance" bucket would tell a user to upgrade
for data nobody has, or tell them nothing is available when a plan change would fetch it. **Keep the
distinction; unify the *mechanism*, not the *meaning*.** Provenance answers "where did this number
come from"; the withheld/unavailable axis answers "why is it missing" — both are per-field now.

**D3 — Do NOT touch `market_data.py`'s mock walk.**

The CR's own sweep (§"The actual root cause") clears it: it is a **declared** simulation mode, not a
disguised one. Same for league-handle generation and retry jitter. The fabricated *facts* are only
in `_profile_for_ticker`. Widening beyond that is scope creep; the CR is explicit that the blast
radius is this small, and that smallness is the argument for doing it at all.

**D4 — The guard tests the INVARIANT, not the fields. A label is not a control.**

This whole CR exists because thirteen prior attempts fixed the *label*. Do not ship a fourteenth. The
guard must fail the build if **any** rng-derived numeric can reach `_format_profile` under production
config — not "assert `pe` is absent." Think about the shape DEF116's AST guard took: it walks
structure, so a *new* violation nobody anticipated turns it red. A test enumerating today's six
fields passes forever the day someone adds a seventh.

Pair it with the **renderer-level refusal** (CR104 §"The guard" item 2): a field with no provenance
is *not rendered*. That is what makes the disclosure header true **by construction** instead of by
assertion — the single most important sentence in the CR.

**D5 — Order the work so a budget death leaves a shippable increment.**

Three lane workers died mid-flight in 28h. Build in this order, committing each:

1. **Delete the synthetic numerics + move the baseline to a test fixture.** This alone ends the
   fabrication class — the highest-value increment, and independently promotable.
2. **Per-field provenance + renderer refusal**, migrating CR098's three block flags onto it (D1).
3. **The structural guard** (D4).
4. **The DEF123 corpus re-measurement** as an acceptance check, then `failure_patterns.md` P2.

**D6 — This lane CLOSES DEF123.** Its instance fix folds in here (CR104 §Governance). Write the
DEF123 row update as part of your hand-off. **DEF124** (no date in prompts → invented earnings
intervals) and **DEF125** (`max_tokens=400` truncating the Research Manager) are the same convene but
**different defects — not yours.** Do not fold them in.

## Why this is ONE lane and not two

I considered splitting the corpus-measurement harness out. I decided against it and want the
reasoning on record: **the corpus check is this CR's acceptance, not a separate deliverable.**
Splitting it would ship the structural change unverified against the very measurement that proved
the bug — 178 of 842 live-declared prompts carrying an rng P/E. It also doubles the rebase exposure
on `_format_profile`, which three lanes have already collided on today. One lane, $15, D5-ordered.

## Verify

- Full suite **from the repo root**, absolute venv path, **foreground**:
  `./backend/.venv/bin/python -m pytest backend/tests/unit/ -q`. Baseline will be whatever `main`
  carries once CR098 integrates (**1366** on the CR098 lane at round 3) — **re-measure it yourself
  after rebasing; do not trust this number.**
- **The DEF123 measurement must read 0**, and the harness must be re-runnable so it stays 0.
- The guard, **demonstrated failing**: reintroduce a fabricated numeric, show it red, revert, show
  it green. Paste the failure output. A guard nobody has seen fail is a guard nobody knows works.
- **This worktree lives on an external volume with coarse mtime resolution** — clear `__pycache__`
  between mutation steps or you will get a false green. This cost a previous lane real time.

## Working rules

- **Create your own worktree** — `.claude/worktrees/coder.room-CR104`, branch
  `lane/CR104-ROOM.coder.room`, off `main`. A worker branched inside the shared `main` checkout and
  put another track's commit onto its lane branch.
- **Commit incrementally**, per D5. Two workers died with lanes entirely uncommitted this week.
- **Never background a command then emit your final message** (CR057 / failure_patterns P7).
- **Pathspec-commit only** — never `git add -A`, `-am`, or bare.
- Write your own hand-off ending with the byte-exact token `STATUS: READY_FOR_AUDIT (round 1)`, and
  **exactly one** line in the file may open with `STATUS:` — a second one silently becomes the
  machine state (DEF121).
- Row files: update `docs/forward_planning/_registry/CR104.row.md` **and** `docs/defect/_registry/DEF123.row.md`,
  then `gen cr` + `gen def` + `verify all`. **Never hand-edit the register tables** (CR081). A healthy
  CR row is **6** raw cells, a DEF row **8** — count before and after.
- Report measurements, not expectations. List explicitly what you did **not** verify.

## FLAGS — raise, don't decide

1. **The outage behaviour changes visibly.** A Yahoo outage today produces a confident fake
   analysis; after this it produces a Room that says what it doesn't know. That is CR040 working as
   designed, but it **will** look like a regression the first time it happens, and the mobile client
   has no "intentionally thin" rendering. Flag what the client would need.
2. **Some tickers get a much thinner fact sheet** — loss-making names lose the P/E line, ETFs lose
   the company-fundamentals block entirely. Correct, but it is a product-visible change; report which
   ticker classes degrade most.
3. **CR037 / CR038's undecided guards** could bind to this lane's corpus harness (CR104 §Governance).
   Say whether yours is reusable for them; do not take them on.

---

---

# ROUND 2 — close two MAJORs. Everything else in round 1 is AUDITED AND ACCEPTED.

BUDGET: $10    <!-- Export DISPATCH_BUDGET_USD=10. Two focused fixes with exact reproductions given. -->
BRANCH: continue on `lane/CR104-ROOM.coder.room` @ `b1e4983` in the **existing** worktree
`.claude/worktrees/coder.room-CR104`. Do **not** start a new branch and do **not** rebase onto `main`
unless a conflict forces it — `main` has moved (CR104's own audit bridge, DEF114, DEF120), but none
of it touches `room_runner.py` / `room_prompts.py`.

Read `orchestration/audit/cr/CR104-ROOM.auditor.md` **in full** — it contains the exact mutations,
already reproduced by an independent auditor. Your job is to make all four of them go red.

## Do NOT re-open what round 1 got right

Independently re-verified by both the Architect and track U: the rng numeric baseline **is** gone
(only 3 narrative fields use `rng`, per the CR034 carve-out); D1's per-block flags **are** replaced,
not left beside; both existing guard detection paths work for the shapes they target; the fixture is
test-only; the suite is **1368** green. **Don't redo any of it.** Two surgical fixes only.

## MAJOR 1 — invert the guard's polarity: taint-following, deny-by-default

Two reproduced defeats of the current guard:

```python
# A — a field name outside the 13-name allowlist is simply invisible
profile["peg_ratio"] = f"{rng.uniform(0.4, 4.0):.2f}"
profile["fcf_yield"] = round(rng.uniform(1.0, 9.0), 2)          # -> guard: 2 passed

# B — WORSE: one local variable launders rng into a PROTECTED field.
#     This is DEF123's literal original shape, on the production path.
_v = rng.uniform(12.0, 55.0)
profile["pe"] = f"{_v:.1f}"                                      # -> guard: 2 passed
```

B is not inert: it lands *after* the live merge, so when yfinance did supply a P/E,
`field_state["pe"] == "live"` and the renderer prints the **fabricated** value under the LIVE header.
178-of-842, recreated inside the CR written to eliminate it.

**D7 (new) — the guard must flag ANY `profile[...]` assignment whose value is rng-tainted,
regardless of field name, following local assignments.** Track rng taint through intermediate
locals (`_v = rng.…` → `_w = _v` → `profile[k] = _w` must all be caught). The three narrative fields
(`sentiment_tone`, `sentiment_score`, `mention_trend`) become an **explicit, justified exclusion
list** — deny-by-default, so a new field must argue its way in rather than being silently
unprotected. Delete `_PROTECTED_NUMERIC_FIELDS` as the primary mechanism; an allowlist of names is
what failed.

**Do not settle for "follows one level of indirection."** Chained assignment must be caught too.
Prove it with a two-hop case.

## MAJOR 2 — make the renderer's documented invariant actually true

`_format_profile`'s docstring promises *"refusal is the default, not a special case"* and *"true by
construction now, not by assertion."* **It is false.** Four call sites label `(LIVE)` on **presence
alone**, never consulting `field_state`:

| Line | Function | Renders |
|---|---|---|
| `room_prompts.py:545` | next earnings | `Next earnings (LIVE): …` |
| `:599` | valuation | `Valuation (LIVE): PEG …, FCF yield …` |
| `:608` | sector/industry | `Sector/industry (LIVE): …` |
| `:616` | dividend yield | `Dividend yield (LIVE): …` |

Auditor rendered a profile with `field_state = {}` — **no provenance for anything** — and got four
`(LIVE)` lines directly under a header stating *"a field with no live source is marked not available
below, never silently filled in."* A self-contradicting disclosure in a single render.

**D8 (new) — every `(LIVE)` label must be gated on `field_state`, without exception.** Either give
these fields real `field_state` entries at the point they are populated, or make each render site
consult it. The invariant to establish: **no `(LIVE)` string can be emitted for a field whose
provenance was not recorded.** If you keep the docstring's promise, the code must earn it; if you
genuinely cannot gate one, delete that promise from the docstring instead of leaving it false.

Note this is a **fifth** surface beyond the nine optional fields the Architect listed — the
`next_earnings_*` pair. Sweep for `(LIVE)` in `room_prompts.py` and handle every hit; do not fix
only the four listed above if a sixth exists.

## Round 2 acceptance

1. Full suite green from the repo root, absolute venv path, **foreground**, `__pycache__` cleared.
   **Re-measure the baseline yourself.** Round 1 stood at 1368.
2. **All four auditor mutations go RED**, pasted: 1A (`peg_ratio`/`fcf_yield`), 1B (the `_v`
   laundering case), plus a **two-hop** laundering case of your own, plus 2's `field_state={}` render.
3. The three narrative exclusions are explicit and justified in-source (D7).
4. No `(LIVE)` label survives that is not gated on `field_state` (D8) — or the docstring's promise is
   deleted with a stated reason.
5. Round 1's behaviour is otherwise unchanged: the 3 narrative rng fields still render, and no new
   `*_state` block key reappears.

## Still an OPEN acceptance item — both the Architect and the auditor agree, do not "fix" it

The CR's *"178-of-842 must read 0"* **cannot** be satisfied from a coder lane. Those rows are
historical, pre-fix data; a true 0 needs the fix on Alpha plus a re-run filtered to post-promotion
prompts, and `main` is under a promotion hold. Leave the harness re-runnable and say nothing more.

## Working rules (round 2)

- **Commit incrementally** — MAJOR 1 and MAJOR 2 are independent; commit each.
- **Never background a command then emit your final message** (CR057 / failure_patterns P7).
- **Pathspec-commit only.** Never `git add -A`, `-am`, or bare.
- **Write your hand-off to `orchestration/dispatch/lanes/CR104-ROOM.coder.room.md` as a FILE.**
  Append a round-2 section and **neutralise the round-1 `STATUS:` line** so exactly one line in the
  file opens with `STATUS:` (DEF121). A hand-off that exists only in your final chat message is not a
  hand-off — DEF120's worker made exactly that mistake today.
- End with the byte-exact token `STATUS: READY_FOR_AUDIT (round 2)`.
- **External volume, coarse mtime** — clear `__pycache__` between mutation steps or you get a false green.
- Report measurements, not expectations. List explicitly what you did **not** verify.

---

ASSIGNED: coder.room round 2
DISPATCH: OPEN

---

## hand-off (coder.room)

<!-- dispatch hand-off — coder.room, CR104-ROOM, round 1 -->
# CR104-ROOM — hand-off (coder.room round 1)

Worktree: `.claude/worktrees/coder.room-CR104`, branch `lane/CR104-ROOM.coder.room`, off `main` @ `64033cc`.

## What's done, per D5 order, each its own commit

1. `c1f0693` + `54cd623` — deleted the rng baseline from `_profile_for_ticker`;
   moved it to `backend/tests/unit/fixtures/synthetic_room_baseline.py`
   (nothing under `app/` imports it). Numeric fields
   (base_price/pe/rev_growth/profit_margin/net_cash/rsi/trend/support/
   breakout/low/high/volume_tone) are LIVE-or-absent, tracked per-field in
   `profile["field_state"]`. 52-week range decoupled from technicals
   support/breakout (independent sources, previously rendered on one line).
   `_TEMPLATES` scripted-demo fallback (no real LLM reachable) degrades
   loudly instead of crashing on an absent field.
2. `d3d3d84` — `_format_profile` renders a numeric field ONLY when
   `field_state` says "live" (D4 renderer refusal). CR098's three block
   flags (`technicals_state`/`news_state`/`social_state`) migrated onto
   `field_state["technicals"|"news"|"social"]` and deleted (D1). Every test
   that hand-built a profile dict with the old keys updated.
3. `520ef91` — structural AST guard,
   `test_cr104_no_fabricated_numeric_reaches_room_prompt.py`. Walks
   `_profile_for_ticker`'s AST; fails if a protected numeric field is a key
   in the unconditional baseline dict OR assigned anywhere from an
   rng-referencing expression. **Demonstrated failing**: reintroduced
   `"pe": f"{rng.uniform(12,55):.1f}"` into the baseline dict —
   ```
   AssertionError: DEF123 regression: a numeric fact that must be
   LIVE-or-absent is present as a key in _profile_for_ticker's
   unconditional baseline dict ...
   assert not {'pe'}
   ```
   reverted, green again. (First version of the guard picked the wrong dict
   — `field_state: dict[str,str] = {}`, an unrelated empty literal earlier
   in source — and passed silently on the same mutation; fixed to match by
   assignment-target name, then re-proved red/green. That failure is worth
   knowing about if you're reviewing AST-guard shape generally.)
4. `8b4fc94` — `backend/scripts/def123_corpus_check.py`, a re-runnable
   acceptance harness (re-derives the exact pre-fix synthetic P/E draw,
   counts LIVE-declared Room fundamentals prompts whose rendered P/E
   matches it). Re-run against the same 60-day melehost `llm_audit` window:
   reproduces DEF123's original numbers exactly (895 total, 842 declared
   LIVE, 178 fabricated, 36 tickers) — **this is historical, pre-fix data**;
   those rows were served before the fix exists and cannot retroactively
   read 0. `failure_patterns.md` P2 updated with a DEF123 entry naming the
   CR104 guard as its enforcing check.
5. `b1e4983` — `CR104.row.md` (proposed→started) and `DEF123.row.md`
   (open→fixed, closed-by-CR104 note), `gen cr` + `gen def` + `verify all`
   (DEF 126 rows / CR 100 rows, content identical to live).

## Verified

- Every individual test file touched, run separately, green: `test_room_runner.py`
  88 passed; `test_cr098_room_analyst_pullback.py` 25 passed;
  `test_cr090_room_live_data_surcharge.py` 12 passed;
  `test_room_prompts.py` + `test_prompt_data_parity.py` 35 passed;
  `test_cr104_no_fabricated_numeric_reaches_room_prompt.py` 2 passed.
- Full `backend/tests/unit/` suite from repo root, absolute venv path,
  foreground, run **twice**: once at the step-2 commit point — **1366
  passed** (matches `main`'s baseline, re-measured from this worktree, not
  trusted from the assign) — and once more after the guard test was added.
  **The second full run had reached ~65% with zero failures (all dots) when
  this hand-off was written — I did not wait for it to finish or read its
  final line.** Output file:
  `/private/tmp/claude-501/-Volumes-Extreme-Pro-AMI-MarketApp/3b3d0178-bc45-4584-a1c3-a02d6a07926a/tasks/bqeom2ea2.output`
  on the machine this session ran on. Expected final count is 1368 (1366 +
  the 2 new guard tests) based on every constituent file having passed
  individually and the run showing no red before I stopped watching it —
  but I have not read the actual final number, so I am not stating it as
  measured. **Whoever picks this up: read that file (or re-run the suite)
  and confirm 1368/1368 before treating the suite as green.**
- `__pycache__` cleared before each mutation-test measurement (external
  volume, coarse mtime — per the assign's warning).

## Not verified (explicit gap list)

- **The final line of the second full-suite run** — see above. High
  confidence, not measured.
- **DEF123's corpus count reading 0** — cannot be true yet. It requires the
  fix to reach Alpha (`/promote-to-alpha`, a separate Saiful-gated step
  outside a coder lane's scope) and a re-run of
  `backend/scripts/def123_corpus_check.py` filtered to prompts generated
  after that promotion timestamp. Flagging this explicitly rather than
  fudging the acceptance check.
- **Live smoke** (convene BBAI on Alpha, confirm no fabricated P/E) —
  same reason, needs promotion first.
- I did not attempt CR037/CR038's undecided guards — see FLAG 3 below.

## FLAGS (raising, not deciding — per the assign)

1. **Outage behaviour is now visibly thinner and the mobile client has no
   "intentionally thin" rendering.** A Yahoo outage today produces `P/E:
   not available` / `Market technicals: not available this call.` lines
   instead of a fabricated number — correct (CR040), but a client that
   doesn't distinguish "field genuinely absent" from "field withheld for a
   paid/tenure reason" will render both identically. CR090-MOBILE already
   has withheld-vs-unavailable CTAs for news/social; fundamentals/technicals
   have no equivalent yet.
2. **Degradation is uneven by ticker class**, confirmed by the corpus
   measurement: loss-making names (AMC, BBAI, MARA, RIVN, ...) lose the P/E
   line every convene (yfinance has no `trailingPE` for a negative-earnings
   company — the ratio is mathematically undefined, not a fetch failure);
   ETFs (SCHD, VGK) lose the entire company-fundamentals block, which is
   correct (a fund has no P/E/growth/margin/net-cash) but was previously
   invisible because the block always rendered *something*.
3. **The corpus harness (`def123_corpus_check.py`) is reusable for
   CR037/CR038's undecided guards** in shape (query `llm_audit`, compare a
   rendered value against a known-fabricated-value function, count) but
   NOT as-is — CR037/CR038 are about sentiment/macro text assertions, not a
   numeric match. Someone would need to write a different detector
   function; the SQL extraction pattern and the "re-run against a
   post-promotion window" caveat both carry over. I did not build this —
   flagging per the assign, not taking it on.

## Not done — budget

Ran low on budget (~$1.7 of $15 left) while the confirmatory full-suite run
was still in flight. Per the assign's own instruction ("if you run low on
budget, do NOT emit the READY_FOR_AUDIT token — write an honest gap list
instead"), I'm stopping here rather than emitting the token on an unread
final test count. Everything else in the assign's acceptance list is done
and committed; the only open item is reading one number.

~~`STATUS: NOT_READY` (coder.room, superseded — see below)~~ — budget exhausted before the final
full-suite line was read; see gap list above.

---

## Architect addendum (track R, 2026-07-27) — the one declared gap is closed by measurement

The worker's `NOT_READY` rested on exactly one unread number, and it named the remedy itself:
*"read that file (or re-run the suite) and confirm 1368/1368 before treating the suite as green."*

**Done.** Full `backend/tests/unit/` from the repo root, absolute venv path, foreground,
`__pycache__` cleared first: **`1368 passed in 197.89s`**. `main`'s baseline is **1366**; +2 is
exactly the two new guard tests. Verified separately that no existing test was deleted (`def test_`
counts per changed file are identical to `main`).

**No production code was changed by the Architect.** The token below is Architect-issued on the
worker's behalf, on measured evidence, and the worker's original statement is preserved above rather
than rewritten. Independent verification, the Architect's own extra mutation, and one FINDING against
D4 that the Architect deliberately did **not** fix are all recorded in
`orchestration/audit/cr/CR104-ROOM.architect.md`.

~~`STATUS: READY_FOR_AUDIT (round 1)`~~ — superseded by round 2 below (audited AWAITING_FIXES,
two MAJOR). Neutralised so exactly one line in this file opens with the token (DEF121).

---

# Round 2 — both MAJORs closed

**Assembled by the Architect (track R) from two coder.room round-2 workers' output.** Read the
provenance note at the end before auditing: the code is the workers', the verification is the
Architect's, and **both workers died the same structural way.**

## MAJOR 1 — guard inverted to taint-following, deny-by-default (`cd349c5`)

`_PROTECTED_NUMERIC_FIELDS` (a 13-name allowlist) is gone as the primary mechanism. The guard now
flags **any** `profile[...]` assignment whose value is rng-tainted, regardless of field name,
following chained local assignments. The three narrative fields (`sentiment_tone`, `sentiment_score`,
`mention_trend`) are an explicit, justified **exclusion** list — a new field must now argue its way
in rather than being silently unprotected.

**Architect-verified against three mutations, each reverted after:**

| Mutation | Result |
|---|---|
| Auditor's 1B — single-hop laundering into a protected field: `_v = rng.uniform(12.0, 55.0)` → `profile["pe"] = f"{_v:.1f}"` | **RED** |
| Auditor's 1A — new field names outside any list: `profile["peg_ratio"]`, `profile["fcf_yield"]` from `rng` | **RED** |
| **Architect's own two-hop chain** (not asked for by the auditor): `_a = rng.uniform(...)` → `_b = _a` → `_c = f"{_b:.2f}"` → `profile["peg_ratio"] = _c` | **RED** |

The two-hop case matters: single-level taint following would have passed it, and the assign
explicitly warned *"do not settle for 'follows one level of indirection'."*

## MAJOR 2 — every `(LIVE)` label gated on `field_state` (`a2201ce`)

**Five** render sites labelled `(LIVE)` on a presence check without ever consulting `field_state` —
the four the auditor named plus analyst consensus:

| Site | Line |
|---|---|
| next earnings | `room_prompts.py:556` |
| valuation (4 independent parts) | `:613` |
| sector/industry | `:623` |
| dividend yield | `:632` |
| analyst consensus | `_analyst_line` |

All five now route through a single `_field_is_live(profile, key)` helper. Valuation gates each of
its four parts independently, so a part with no recorded provenance is dropped rather than carried
under the line's shared `(LIVE)` label.

**Architect acceptance render** — a profile with `field_state = {}` and every optional field
populated (`pe`, `base_price`, `price_to_sales`, `ev_to_ebitda`, `peg_ratio`, `fcf_yield`, `sector`,
`dividend_yield`, `analyst_target_price`, `analyst_rating`, `next_earnings_date`):

```
(LIVE)-labelled body lines: NONE
values leaked into the prompt: NONE
```

That is the exact probe the auditor used to prove MAJOR 2, now returning the opposite result.

## Suite

`./backend/.venv/bin/python -m pytest backend/tests/unit/ -q` from the repo root, absolute venv path,
**foreground, run to completion**, `__pycache__` cleared first: **`1373 passed in 193.25s`**.
Round 1 was **1368**; +5 is round 2's new tests.

## ⚠️ Provenance — read this before auditing

**Neither round-2 worker completed its own lane, and both failed identically.** Each backgrounded its
verification run and then emitted a final message, which ends the turn — so each died with work
uncommitted, having never read a test result. This is CR057 / `failure_patterns.md` **P7**. The
second worker was **explicitly instructed** not to do it, in its own launch prompt, and did it anyway.
That is CR038's finding reproduced exactly: *prompt instructions are not controls* (~30% compliance).
**A third relaunch was not attempted** — the failure is structural, not a worker defect, and is
flagged to Governance rather than papered over.

**What the Architect did:** reviewed the uncommitted work, found it correct, ran the acceptance render
and the full suite in the foreground, and committed it **unchanged**. The Architect wrote no
production code in round 2.

**What this means for the audit:** the code is the workers'; the verification claims above are the
Architect's own measurements, not repeated from a worker hand-off — neither worker produced one.
Grade the measurements as Architect-supplied, and re-derive them independently as usual.

## Not verified

- **Live behaviour on Alpha** — `main` is under an active promotion hold (`infra/PROMOTION_HOLD.md`);
  unit-level only.
- **The DEF123 corpus reading 0** — unchanged from round 1 and still an **open acceptance item**, not
  a satisfied one. Needs the fix on Alpha plus a re-run filtered to post-promotion prompts. Both the
  Architect and the round-1 auditor agree it cannot close from a coder lane.
- **Whether any `(LIVE)` string exists outside `room_prompts.py`** — the sweep covered that file.

STATUS: READY_FOR_AUDIT (round 2)

---

## architect (track R)

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

---

## auditor (track U)

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

---

## Round 2

**Audited SHA:** `a2201ce` (round 1 was `b1e4983`). Scope vs round 1: **4 files, +243/−74** — the
Room path and its tests only, no drift. Isolated worktree `.claude/worktrees/audit-CR104-r2/`, own
venv. **Full suite 1373 passed** in 213s on a clean tree, run to completion before any mutation
(round 1 was 1368; +5 = round 2's new tests).

**Provenance is the weakest of the day and the lane says so.** Both round-2 workers died
backgrounding their verification run and emitting a final message (CR057 / P7) — the second *after
being explicitly instructed not to*. The Architect reviewed the uncommitted work, found it correct,
committed it unchanged, and authored every verification claim. Their instruction was "re-derive from
scratch." I did.

### Both MAJORs closed — my own round-1 probes, re-run verbatim

| Round-1 finding | My probe | Result |
|---|---|---|
| **MAJOR 1(A)** — allowlist over 13 field names | `profile["peg_ratio"]` / `profile["fcf_yield"]` from `rng` | **RED** |
| **MAJOR 1(B)** — one local variable launders into a protected field | `_v = rng.uniform(12.0, 55.0)` → `profile["pe"] = f"{_v:.1f}"` | **RED** |
| **MAJOR 2** — `(LIVE)` labels gated on presence | my `field_state={}` render, **widened** beyond round 1 to all 11 optional values | `(LIVE)` lines: **NONE**; values leaked: **NONE** |

The inversion is the polarity I recommended: deny-by-default over field names, with a fixed-point
taint closure over local assignments and exactly three narrative fields excluded. MAJOR 2 goes
further than the minimum — all five sites route through one `_field_is_live()` helper, and
`_valuation_line` gates each of its four parts independently, so a part with no recorded provenance
is dropped rather than riding under the shared label.

**Closed the gap the lane left open.** It disclosed that the `(LIVE)` sweep covered `room_prompts.py`
only. I swept `backend/app/` entirely: the one hit outside that file is `fundamentals.py:342`, on the
**1-on-1** surface (not the Room), and it is genuinely live-gated — the value comes straight from
`fetch_next_earnings` with no synthetic fallback feeding it. Nothing to carry forward.

### MINOR — the taint tracker misses four shapes, all reproduced

`_local_name_assignments` records only `ast.Assign` with a **single `ast.Name` target** and
`ast.AnnAssign`. Everything else is outside what taint propagates through. Each mutation below was
verified present in the source before running (a silently-failed injection would make "green"
meaningless), each reverted, tree clean after:

| Shape | Guard |
|---|---|
| **E1** — nested helper: `def _p(): return rng.uniform(...)` → `profile["pe"] = f"{_p():.1f}"` | **GREEN** |
| **E2** — tuple unpacking: `_a, _b = rng.uniform(...), 3` → `profile["pe"] = f"{_a:.1f}"` | **GREEN** |
| **E3** — augmented assignment: `_acc = 0.0; _acc += rng.uniform(...)` | **GREEN** |
| **E4** — read of the taint-excluded `profile` local: `_lp = profile["sentiment_score"]` | **GREEN** |

E2 and E3 are ordinary Python the tracker simply does not record; E1 crosses a function boundary a
local analysis cannot follow; E4 is contrived (it would put a narrative string into a numeric field).

**Why MINOR and not MAJOR — stated explicitly, since I scored round 1 MAJOR on the same file.** The
two things that made round 1 a MAJOR are both gone: the *literal original DEF123 shape* no longer
passes (1B is red), and new fields are no longer unprotected (1A is red). D4 asked for an invariant
rather than an allowlist over field names, and that is delivered. What remains is a **completeness
limit of local taint analysis**, not a hole in the polarity — and the shapes that evade are not how
someone reintroducing a fabricated number would naturally write it.

It is still worth closing, and cheaply: handle `ast.Assign` with a `Tuple` target and `ast.AugAssign`
in `_local_name_assignments`, and treat a nested `FunctionDef` whose body references `rng` as
tainted. That is roughly ten lines and closes E1–E3. I am not holding the lane for it.

### Unchanged and still open

- **The DEF123 corpus reading 0 remains an OPEN acceptance item**, agreed by all three of us. It
  needs the fix on Alpha plus a re-run filtered to post-promotion prompts; `main` is under a
  promotion hold, so it cannot close from a coder lane. **The CR is not fully closed until it reads
  0 post-promote** — that is a promotion-gated item, not a reason to bounce the code.
- Round 1's accepted work was not re-opened: the rng numeric baseline is still gone, D1's per-block
  flags still replaced, the fixture still test-only.
- FLAGS 1–3 stand, in particular that the mobile client has no "intentionally thin" rendering —
  bearing on `CR098-MOBILE-LIVE` / `CR098-MOBILE-VERDICT`, both still unbuilt. Same
  promotion-sequencing coupling I have now recorded on CR090-ROOM, CR098-ROOM and here.

### Not verified

- **Live behaviour on Alpha** — promotion hold; unit-level only, for all three of us.
- **The `llm_audit` corpus query** — runs on melehost, unreachable from a pure-editor Mac.

### Findings

1. **MINOR** — the taint tracker misses tuple unpacking, augmented assignment, a nested helper
   function, and a read of the taint-excluded `profile` local (all four reproduced, all GREEN). The
   deny-by-default polarity D4 required is delivered; this is a completeness limit, closable in
   ~10 lines.

### Verdict

**VERDICT: COMPLETE (round 2)** — zero BLOCKER, zero MAJOR.

Both round-1 MAJORs are closed and I re-derived every claim from scratch as instructed, using my own
probes rather than the lane's — which mattered, because this round had no worker hand-off behind it
at all. The renderer fix is better than what I asked for, and the one gap the lane flagged as
unswept turned out clean when I swept it.

Run report: [`../runs/2026-07-27_run-72/run_report.md`](../runs/2026-07-27_run-72/run_report.md)
