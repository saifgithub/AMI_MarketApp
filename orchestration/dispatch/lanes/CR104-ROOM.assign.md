<!-- dispatch assign lane — Architect-owned. CR052. -->
# CR104-ROOM — assign (delete the synthetic numeric baseline from the production Room path)

KIND: code
INSTANCE: coder.room
GATE: independent    <!-- The CR's own Governance section requires it: this changes what every agent is told is true, upstream of the safety floor's inputs. It also closes DEF123, a live fabrication shipping today. -->
BUDGET: $15    <!-- Export DISPATCH_BUDGET_USD=15 at launch. Do NOT reach for `ultra` for headroom — it switches on fan-out tooling this lane does not need. -->
ACCEPTANCE: docs/forward_planning/CR104_delete_the_synthetic_baseline/CR104_delete_the_synthetic_baseline.md — **140 lines. Read it in full; it is short and every section is load-bearing.** Its §"The change" (4 items) and §"The guard" (4 items) are your acceptance criteria.
DEPENDS-ON: **CR098-ROOM audited COMPLETE and integrated to `main`.** Saiful sequenced this after CR098 (2026-07-27). It is `IN_AUDIT` at round 3 as of this writing. **Do not start before it lands** — you would be rebasing onto a moving `_format_profile`, and that renderer has already been the collision point for three lanes in one day.
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

ASSIGNED: -
DISPATCH: UNASSIGNED
